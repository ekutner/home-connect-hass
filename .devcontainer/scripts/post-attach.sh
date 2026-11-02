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
WORKSPACE_FILE="${WORKSPACE_FILE:-$INTEGRATION_PATH/home-connect-dev.code-workspace}"
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
# Where VSCode creates its sockets. Overridable only for testing.
IPC_SOCKET_DIR="${IPC_SOCKET_DIR:-/tmp}"
# Seconds to wait for a socket. It can appear well after the attach starts.
IPC_WAIT="${IPC_WAIT:-120}"

# Not every socket can be used. The extension host and each terminal have one
# that serves the CLI, but the agent host listens on one that never replies, so
# probe them with a request that returns quickly and has no side effects. The
# socket is required, as without one the CLI prints an error but still exits 0.
find_ipc_socket() {
    local socket
    for socket in ${VSCODE_IPC_HOOK_CLI:-} $( ls -t "$IPC_SOCKET_DIR"/vscode-ipc-*.sock 2> /dev/null )
    do
        if VSCODE_IPC_HOOK_CLI="$socket" timeout 2 "$CODE_CLI" --list-extensions > /dev/null 2>&1; then
            echo "$socket"
            return 0
        fi
    done
    return 1
}

IPC_SOCKET=""
if [ -n "$CODE_CLI" ]; then
    until IPC_SOCKET=$( find_ipc_socket ) || [ "$SECONDS" -ge "$IPC_WAIT" ]
    do
        sleep 2
    done
fi

if [ -z "$IPC_SOCKET" ]; then
    echo "Open $WORKSPACE_FILE to get both repos in one window"
    exit 0
fi

# Set before the call, which may reload the window before this script gets
# another chance to run. Cleared on failure so the next attach retries, unless
# the call timed out: the request may still have been delivered, and retrying
# could then reload the window in a loop.
touch "$MARKER"
echo "Opening $WORKSPACE_FILE"
VSCODE_IPC_HOOK_CLI="$IPC_SOCKET" timeout 10 "$CODE_CLI" --reuse-window "$WORKSPACE_FILE"
OPEN_RESULT=$?
if [ "$OPEN_RESULT" -ne 0 ]; then
    [ "$OPEN_RESULT" -eq 124 ] || rm -f "$MARKER"
    echo "Open $WORKSPACE_FILE to get both repos in one window"
fi

# Opening the workspace is a convenience; never fail the attach over it.
exit 0
