#!/usr/bin/env python3
"""
Generate or update an htpasswd file using bcrypt.

bcrypt is the strongest algo htpasswd supports (stronger than MD5/SHA/crypt).
Apache httpd 2.4.8+ and nginx (with ngx_http_auth_basic_module + bcrypt
support) can read bcrypt hashes in htpasswd files.

Usage:
    python3 make_htpasswd.py -u alice -f .htpasswd
    python3 make_htpasswd.py -u alice -p 'mypassword' -f .htpasswd
"""

import argparse
import getpass
import os
import bcrypt


def hash_password(password: str, cost: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=cost)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def upsert_entry(filepath: str, username: str, hashed: str) -> None:
    lines = []
    replaced = False

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith(f"{username}:"):
                    lines.append(f"{username}:{hashed}")
                    replaced = True
                elif line:
                    lines.append(line)

    if not replaced:
        lines.append(f"{username}:{hashed}")

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Create or update an htpasswd entry with bcrypt")
    parser.add_argument("-u", "--username", required=True, help="Username")
    parser.add_argument("-p", "--password", help="Password (omit to be prompted securely)")
    parser.add_argument("-f", "--file", default=".htpasswd", help="Path to htpasswd file")
    parser.add_argument("-c", "--cost", type=int, default=12, help="bcrypt cost factor (default 12)")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password cannot be empty")

    hashed = hash_password(password, args.cost)
    upsert_entry(args.file, args.username, hashed)

    print(f"Wrote entry for '{args.username}' to {args.file}")


if __name__ == "__main__":
    main()