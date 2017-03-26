#! /usr/bin/env bash
# Requires Ubuntu 16

export DJANGO_SETTINGS_MODULE="autograder.settings.production"

sudo apt update
sudo apt install -y postgresql-9.5 postgresql-server-dev-9.5
sudo apt install -y python3-wheel python3-pip python3-venv
sudo pip3 install --upgrade pip

cd .. && sudo pip3 install -r requirements.txt && cd -

