#!/usr/bin/env bash
#
# Runs on every container start. Re-installs the sibling SDK projects as
# editable so edits to them take effect without a reinstall, and rebuilds the
# links in /config.

set -u

HOST_DATA_PATH="${HOST_DATA_PATH:-/root/.home-connect-dev}"
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
    # /workspaces also holds the .code-workspace file
    [ -d "$folder" ] || continue

    if [ -f "$folder/setup.py" ]
    then
        echo "Installing python dependency: $folder"
        pip3 install -e $folder
    fi
    if [ -d "$folder/.devcontainer/config" ]
    then
        for conf_file in $folder/.devcontainer/config/*
        do
            # Templates are sources for files elsewhere, not config themselves
            case "$conf_file" in *.template) continue ;; esac
            echo "Linking config file $conf_file"
            name="$(basename $conf_file)"
            rm -f "$CONFIG_PATH/$name"
            ln -s $conf_file "$CONFIG_PATH/$name"
        done
    fi
done

# secrets.yaml is deliberately not in the repo, so the loop above can't find
# it. It comes from the host folder bind mounted at $HOST_DATA_PATH.
if [ -f "$HOST_DATA_PATH/secrets.yaml" ]
then
    echo "Linking secrets file $HOST_DATA_PATH/secrets.yaml"
    rm -f "$CONFIG_PATH/secrets.yaml"
    ln -s "$HOST_DATA_PATH/secrets.yaml" "$CONFIG_PATH/secrets.yaml"
fi

# Fail loudly now rather than leaving Home Assistant to die much later on an
# opaque "Secret home_connect_client_id not found".
if [ ! -s "$CONFIG_PATH/secrets.yaml" ] || grep -q "YOUR_CLIENT_ID" "$CONFIG_PATH/secrets.yaml" 2>/dev/null
then
    cat <<'EOF'

!!  Home Connect credentials are missing.
!!
!!  Edit this file on your host machine and restart the container:
!!      ~/.home-connect-dev/secrets.yaml           (macOS / Linux)
!!      %USERPROFILE%\.home-connect-dev\secrets.yaml   (Windows)
!!
!!  Register an application to get the values:
!!      https://developer.home-connect.com/applications

EOF
fi
