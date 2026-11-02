#!/usr/bin/env bash
#
# Opens the two-folder (integration + SDK) workspace the first time you attach
# to a new volume.
#
# There is no devcontainer.json property that can do this: workspaceFolder
# cannot name a .code-workspace file, and it is ignored outright when cloning
# into a container volume. So this nudges the VSCode client instead. It is the
# only undocumented trick in this setup - delete this script and the
# postAttachCommand line in devcontainer.json and you simply open the
# workspace by hand via File -> Open Workspace...

set -u

SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
INTEGRATION_PATH="${INTEGRATION_PATH:-$( dirname "$( dirname "$SCRIPT_PATH" )" )}"
WORKSPACE_FILE="${WORKSPACE_FILE:-$( dirname "$INTEGRATION_PATH" )/home-connect-dev.code-workspace}"
# /root is a persistent volume, so this fires at most once per volume and
# cannot bounce the window repeatedly.
MARKER="${WORKSPACE_MARKER:-/root/.hc-workspace-opened}"

if [ -f "$MARKER" ] || [ ! -f "$WORKSPACE_FILE" ]; then
    exit 0
fi

if ! command -v code > /dev/null 2>&1; then
    echo "Open $WORKSPACE_FILE to get both repos in one window"
    exit 0
fi

touch "$MARKER"
echo "Opening $WORKSPACE_FILE"
code --reuse-window "$WORKSPACE_FILE"
