#!/usr/bin/env bash

# Create proxy python files under custom_components so debugging works as expected in vscode
for folder in /workspaces/*
do
    if [ -d "$folder/custom_components" ]
    then
        for component in $folder/custom_components/*
        do
            component_name="$(basename $component)"
            dest_folder="/config/custom_components/$component_name"
            rm -rf $dest_folder
            mkdir -p $dest_folder
            for filepath in $component/*.py
            do
                filename="$(basename $filepath)"
                echo "import sys" > $dest_folder/$filename
                echo "sys.path.insert(0, '$folder/custom_components/')" >> $dest_folder/$filename
                echo "from home_connect_alt.${filename%.*} import *" >> $dest_folder/$filename
            done
            for filepath in $(find $component -mindepth 1 -maxdepth 1 -not -name '*.py' -a -not -name '__pycache__')
            do
                filename="$(basename $filepath)"
                ln -s $filepath $dest_folder/$filename
            done
        done
    fi
done
