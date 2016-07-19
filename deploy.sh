#!/bin/bash
ssh mhs-deploy '
ssh hermes "
cd /var/www/meerkat_hermes;
sudo git checkout master;
sudo git stash;
sudo git pull;
sudo stop uwsgi-hermes;
sudo start uwsgi-hermes" '
