# Phase 1 infrastructure. Run with OpenTofu (tofu init / plan / apply)
# or Terraform. Region, bucket, and domain come from variables so this
# stays consistent with config/.env.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "backup_bucket_name" {
  type        = string
  description = "S3 bucket for nightly pg_dump backups. Must match BACKUP_S3_BUCKET in config/.env."
}

variable "instance_type" {
  type    = string
  default = "t4g.nano"
}

variable "vpc_id" {
  type        = string
  description = "VPC to deploy into. Leave null to use the account's default VPC."
  default     = null
}

variable "subnet_id" {
  type        = string
  description = "Subnet for the EC2 instance. Leave null to use the default VPC's default subnet."
  default     = null
}

provider "aws" {
  region = var.aws_region
}

# Latest Amazon Linux 2023 arm64 AMI via SSM public parameter
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# ---------- Backup bucket ----------
resource "aws_s3_bucket" "backups" {
  bucket = var.backup_bucket_name
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

# ---------- Networking ----------
resource "aws_security_group" "rsvp" {
  name        = "rsvp-app"
  description = "RSVP app: HTTP/HTTPS only, no SSH"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------- Secrets ----------
# Containers only — values are pushed out of band with
# `aws secretsmanager put-secret-value`, never through Terraform state
# or git. recovery_window_in_days = 0 so a destroy/recreate during
# iteration doesn't get stuck behind the default 30-day deletion hold.
resource "aws_secretsmanager_secret" "env" {
  name                    = "rsvp-app/env"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret" "htpasswd" {
  name                    = "rsvp-app/htpasswd"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret" "cf_cert" {
  name                    = "rsvp-app/cf-cert"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret" "cf_key" {
  name                    = "rsvp-app/cf-key"
  recovery_window_in_days = 0
}

# ---------- IAM ----------
resource "aws_iam_role" "rsvp" {
  name = "rsvp-app-instance"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.rsvp.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "ses_and_backup" {
  name = "rsvp-ses-and-backup"
  role = aws_iam_role.rsvp.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendRecoveryEmail"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      },
      {
        Sid      = "WriteBackupsOnly"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.backups.arn}/*"
      },
      {
        Sid    = "ReadAppSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.env.arn,
          aws_secretsmanager_secret.htpasswd.arn,
          aws_secretsmanager_secret.cf_cert.arn,
          aws_secretsmanager_secret.cf_key.arn,
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "rsvp" {
  name = "rsvp-app-instance"
  role = aws_iam_role.rsvp.name
}

# ---------- EC2 ----------
resource "aws_instance" "rsvp" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.rsvp.id]
  iam_instance_profile   = aws_iam_instance_profile.rsvp.name

  # hop limit 2 is required so Docker containers (one extra network hop
  # through the bridge) can reach IMDSv2 for IAM role credentials.
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    dnf install -y docker git
    systemctl enable --now docker
    mkdir -p /usr/local/lib/docker/cli-plugins
    ARCH=$(uname -m)
    curl -sL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$${ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    case "$${ARCH}" in
      aarch64) BUILDX_ARCH=arm64 ;;
      x86_64) BUILDX_ARCH=amd64 ;;
      *) echo "unsupported arch $${ARCH}" >&2; exit 1 ;;
    esac
    # Pinned instead of resolved via the GitHub releases/latest API,
    # which is prone to silent failures under the API's unauthenticated
    # rate limit and previously left an ancient buildx in place with no
    # error (compose build requires buildx >= 0.17.0).
    BUILDX_VERSION=v0.36.1
    curl -sL "https://github.com/docker/buildx/releases/download/$${BUILDX_VERSION}/buildx-$${BUILDX_VERSION}.linux-$${BUILDX_ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-buildx
    chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
    usermod -aG docker ec2-user

    cat > /etc/systemd/system/rsvp-secrets.service <<'UNIT'
    [Unit]
    Description=Fetch RSVP app secrets from Secrets Manager

    [Service]
    Type=oneshot
    Environment=AWS_DEFAULT_REGION=${var.aws_region}
    WorkingDirectory=/opt/rsvp-app
    ExecStart=/opt/rsvp-app/scripts/fetch-secrets.sh
    UNIT

    cat > /etc/systemd/system/rsvp-app.service <<'UNIT'
    [Unit]
    Description=RSVP app (docker compose)
    After=docker.service rsvp-secrets.service network-online.target
    Requires=docker.service rsvp-secrets.service
    Wants=network-online.target

    [Service]
    Type=oneshot
    RemainAfterExit=yes
    WorkingDirectory=/opt/rsvp-app
    ExecStart=/opt/rsvp-app/scripts/rsvp-up.sh
    ExecStop=/usr/bin/docker compose -f /opt/rsvp-app/docker-compose.yml down

    [Install]
    WantedBy=multi-user.target
    UNIT

    systemctl daemon-reload
    systemctl enable rsvp-secrets.service rsvp-app.service
  EOT

  tags = { Name = "rsvp-app" }
}

resource "aws_eip" "rsvp" {
  instance = aws_instance.rsvp.id
  domain   = "vpc"
  tags     = { Name = "rsvp-app" }
}

output "public_ip" {
  value = aws_eip.rsvp.public_ip
}
