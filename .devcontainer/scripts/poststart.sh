#!/usr/bin/env bash

# Install from workspace folder
if [ -d "/config/custom_components" ]
then
    rm -f /config/custom_components/*
else
    mkdir -p /config/custom_components
fi

for folder in /workspaces/*
do
    if [ -d "$folder/custom_components" ]
    then
        for component in $folder/custom_components/*
        do
            echo "Linking custom component $component"
            name="$(basename $component)"
            ln -s $component /config/custom_components/
        done
    elif [ -f "$folder/setup.py" ]
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
            rm -f /config/$name
            ln -s $conf_file /config/$name
        done
    fi
done
