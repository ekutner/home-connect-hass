#!/usr/bin/env bash
#
# Runs on every container start. Re-installs the sibling SDK projects as
# editable so edits to them take effect without a reinstall, and rebuilds the
# links in /config.

set -u

# Where Home Assistant keeps its configuration. Overridable only for testing.
CONFIG_PATH="${CONFIG_PATH:-/config}"

# Install from workspace folder
if [ -d "$CONFIG_PATH/custom_components" ]
then
    rm -rf "$CONFIG_PATH"/custom_components/*
else
    mkdir -p "$CONFIG_PATH/custom_components"
fi

for folder in /workspaces/*
do
    if [ -f "$folder/setup.py" ]
    then
        echo "Installing python dependency: $folder"
        pip3 install -e $folder
    fi
    if [ -d "$folder/.devcontainer/config" ]
    then
        for conf_file in $folder/.devcontainer/config/*
        do
            echo "Linking config file $conf_file"
            name="$(basename $conf_file)"
            rm -f "$CONFIG_PATH/$name"
            ln -s $conf_file "$CONFIG_PATH/$name"
        done
    fi
done
