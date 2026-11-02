#!/usr/bin/env bash
#
# Runs once, when the container is created. Prepares the workspace volume
# before the (slow) Home Assistant install, so a failure later still leaves a
# usable checkout behind.

set -u

SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DEVCONTAINER_PATH=$( dirname "$SCRIPT_PATH" )
INTEGRATION_PATH="${INTEGRATION_PATH:-$( dirname "$DEVCONTAINER_PATH" )}"
SDK_REPO_URL="${SDK_REPO_URL:-https://github.com/ekutner/home-connect-async.git}"
SDK_PATH="${SDK_PATH:-/workspaces/home-connect-async}"

# ---------------------------------------------------------------------------
# The SDK is developed in parallel with the integration, so it has to be a
# real repo sitting next to it rather than a pip dependency. /workspaces IS the
# container volume, so this clone persists across rebuilds - hence the guard,
# which also leaves an existing sibling clone alone when the workspace happens
# to be bind mounted from the host instead.
# ---------------------------------------------------------------------------
if [ -d "$SDK_PATH/.git" ]; then
    echo "SDK already present at $SDK_PATH, skipping clone"
else
    echo "Cloning SDK from $SDK_REPO_URL into $SDK_PATH"
    git clone "$SDK_REPO_URL" "$SDK_PATH"
fi

# Both repos are owned by root inside the container; without this git refuses
# to touch them ("dubious ownership") and GitLens / Git Graph come up empty.
# /root is a persistent volume, so a plain --add would pile up duplicate
# entries on every rebuild.
for repo in "$INTEGRATION_PATH" "$SDK_PATH"
do
    if ! git config --global --get-all safe.directory | grep -qxF "$repo"; then
        git config --global --add safe.directory "$repo"
    fi
done

# ---------------------------------------------------------------------------
# Home Assistant and its build dependencies
# ---------------------------------------------------------------------------
sudo apt update -y
sudo apt install -y libffi-dev libssl-dev libjpeg-dev zlib1g-dev autoconf build-essential libopenjp2-7 libturbojpeg0 tzdata libpcap-dev ffmpeg
# libtiff5-dev
pip3 install isort colorlog

# This chmod is a safety measure for scripts that are added after the container was first created
sudo chmod +x $SCRIPT_PATH/*
sudo $SCRIPT_PATH/install-ha.sh
