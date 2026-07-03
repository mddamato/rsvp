commands to create a .htpasswd file


python3 -m venv .
source ./bin/activate
python3 -m pip install bcrypt
python3 make_htpasswd.py -u mike -f .htpasswd
deactivate