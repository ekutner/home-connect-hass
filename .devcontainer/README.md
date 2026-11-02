# Developing with Visual Studio Code + devcontainer

This devcontainer sets up the environment to make it extremely easy to test this integration and with minor changes can be used for any integration.
I've created this devcontainer after getting frustrated with the existing ones, offered by the community, which didn't include all the features I expected. In particular, supporting parallel development of the integration itself and an associated API library / SDK is very often developed in parallel.

The repository is cloned **into a Docker volume** rather than mounted from the host. On Windows in particular this is dramatically faster for the many-small-files work that git, pip and Home Assistant do constantly.

</br>

# Using this devcontainer

1. In VSCode press `F1` and select **Dev Containers: Clone Repository in Container Volume...**, then give it this repository. Let the container build — this takes a while the first time.

2. The container clones the SDK (`home-connect-async`) in beside the integration and opens a two-folder workspace automatically. If it doesn't, use *File -> Open Workspace...* and pick `/workspaces/home-connect-dev.code-workspace`, a link the container creates to the file in `.devcontainer`. The window reloads once while this happens, after the extensions have finished installing.

That's it. There is no host folder structure to set up and no workspace file to save by hand.

> **Your code lives in a Docker volume.** Commit and push regularly — `docker volume rm` will take the working tree with it. To get files out without VSCode, use `docker cp <container>:/workspaces/. ./backup/`.

## Working on a different library

To develop against your own fork of the SDK, or a different library altogether, change `SDK_REPO_URL` (and `SDK_PATH`) in `devcontainer.json` and rebuild. If the folder name changes, update it in `.devcontainer/home-connect-dev.code-workspace` too. Any folder in `/workspaces` that has a `setup.py` is pip installed as editable on every container start, so additional libraries can simply be cloned in alongside.

# How it works

When the devcontainer is launched the associated scripts will automatically:
1. Clone the SDK next to the integration, into the same volume, so it persists across rebuilds
2. Install Home Assistant
3. pip install every library in */workspaces* as editable, so edits to the SDK take effect immediately
4. Create a /config folder and link the files from the .devcontainer/config folder into it
5. Set up a set of proxy folders with references to the integration files under */config/custom_components*. This allows Home Assistant to load the integration from its usual location while letting vscode debug it from the standard code location under */workspaces*

The *Home Assistant* launch configuration passes `--skip-pip-packages home-connect-async`. Without it Home Assistant would check the version pinned in `manifest.json` and quietly install the published wheel from PyPI over your editable SDK, so you would be running the released library instead of the one you are editing.

`/config` is a persistent Docker volume, so your Home Assistant state — logins, config entries, OAuth tokens, entity registry — survives container rebuilds. It does not survive deleting that volume, which costs you a re-authentication rather than any real data.

# How to debug

Just launch the "Home Assistant" launch configuration from vscode. Setup breakpoints normally — in the integration and in the SDK alike.
The Home Assistant portal can be accessed on http://localhost:8123 of the host machine.
