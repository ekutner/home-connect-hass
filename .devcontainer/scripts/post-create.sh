#!/usr/bin/env bash

sudo apt update -y
sudo apt install -y libffi-dev libssl-dev libjpeg-dev zlib1g-dev autoconf build-essential libopenjp2-7 libturbojpeg0 tzdata libpcap-dev ffmpeg
# libtiff5-dev
pip3 install isort colorlog

SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# This chmod is a safety measure for scripts that are added after the container was first created
sudo chmod +x $SCRIPT_PATH/*
sudo $SCRIPT_PATH/install-ha.sh



# # Install mounted python dependencies
# if [ -d "/config/deps" ]
# then
#     for filepath in /config/deps/*
#     do
#         echo "Installing python dependency: $filepath"
#         pip3 install -e $filepath
#     done
# else
#     mkdir -p /config/deps
# fi

