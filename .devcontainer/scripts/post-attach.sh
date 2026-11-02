#!/usr/bin/env bash
#
# Opens the two-folder (integration + SDK) workspace the first time you attach
# to a new container.
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
# Opening the workspace reloads the window, which runs this script again, so the
# marker stops that from looping. /tmp is not a volume: the marker survives the
# reload and container restarts, and only a rebuild clears it. It must not live
# on a persistent volume, or a failed open could never recover.
MARKER="${WORKSPACE_MARKER:-/tmp/.hc-workspace-opened}"

if [ -f "$MARKER" ] || [ ! -f "$WORKSPACE_FILE" ]; then
    exit 0
fi

# Lifecycle commands don't get the VSCode terminal's environment, so plain "code"
# resolves to the image's /usr/local/bin/code stub, which exits 127 because the
# real CLI isn't on PATH. Call the real CLI directly and point it at the client.
CODE_CLI=$( ls -t "$HOME"/.vscode-server/bin/*/bin/remote-cli/code 2> /dev/null | head -n 1 )
IPC_SOCKET="${VSCODE_IPC_HOOK_CLI:-$( ls -t /tmp/vscode-ipc-*.sock 2> /dev/null | head -n 1 )}"

# The socket has to be checked here: without it the CLI prints an error but
# still exits 0.
if [ -z "$CODE_CLI" ] || [ ! -S "$IPC_SOCKET" ]; then
    echo "Open $WORKSPACE_FILE to get both repos in one window"
    exit 0
fi

# Set before the call, which may reload the window before this script gets
# another chance to run. Cleared on failure so the next attach retries.
touch "$MARKER"
echo "Opening $WORKSPACE_FILE"
if ! VSCODE_IPC_HOOK_CLI="$IPC_SOCKET" "$CODE_CLI" --reuse-window "$WORKSPACE_FILE"; then
    rm -f "$MARKER"
    echo "Open $WORKSPACE_FILE to get both repos in one window"
fi

# Opening the workspace is a convenience; never fail the attach over it.
exit 0
