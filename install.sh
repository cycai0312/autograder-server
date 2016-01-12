#! /bin/bash
# Requires Ubuntu 14.04

export DJANGO_SETTINGS_MODULE="autograder.settings.production"

# Add postgres and docker repos
sudo touch /etc/apt/sources.list.d/pgdg.list
echo "deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
  sudo apt-key add -

sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D
echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" | sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y nginx postgresql-9.4 postgresql-contrib-9.4 python3-pip python3.4-venv
# Install uwsgi through pip, NOT apt-get
sudo pip3 install uwsgi

# Docker installation 
# See: https://docs.docker.com/engine/installation/ubuntulinux/
sudo apt-get purge lxc-docker
sudo apt-cache policy docker-engine
sudo apt-get install linux-image-extra-$(uname -r)
sudo apt-get install -y docker-engine
sudo service docker start
sudo usermod -aG docker $(whoami)
docker run hello-world
docker build -t autograder ./docker-image-setup


# Python setup
mkdir -p $HOME/python_venvs
python3 -m venv $HOME/python_venvs/$1
source $HOME/python_venvs/$1/bin/activate

pip install -r requirements.txt
# Force secrets to be generated by loading django settings module.
python3 manage.py --help > /dev/null


# Database setup
echo "Enter the db_password found in autograder/settings/secrets.json"
cat ./autograder/settings/secrets.json
sudo -u postgres createuser -P jameslp  # Replace with username
sudo -u postgres createdb --owner=jameslp autograder_db
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE autograder_db TO jameslp;"
sudo -u postgres psql -c "ALTER USER jameslp CREATEDB;"


# Nginx setup
sudo mkdir -p /etc/nginx/ssl
sudo openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048

python3 manage.py collectstatic

sudo mkdir -p /etc/nginx/sites-enabled
nginx_site_enabled=/etc/nginx/sites-enabled/django_autograder.conf
test -f $nginx_site_enabled && \
	sudo ln -s $PWD/server_config/nginx_autograder.conf $nginx_site_enabled

# uwsgi setup
uwsgi_upstart_conf=/etc/init/uwsgi.conf
test -f $uwsgi_upstart_conf && sudo \
	ln -s $PWD/server_config/uwsgi_upstart.conf $uwsgi_upstart_conf
sudo initctl reload-configuration

# Fix permissions for secrets file
chmod 660 $PWD/autograder/settings/secrets.json

echo "You must now take the following steps to complete installation:\n"
echo "Add the autograder-e16e96fda61b.p12 file for gitkit to the settings dir"
echo "Add and update the paths in gitkit-server-config.json to the settings dir"
echo "Register the server url with gitkit in the dev console"
echo "Run the unit tests"
echo "Run: sudo service nginx restart"
echo "Run: sudo start uwsgi"
echo "Start the submission listener"
