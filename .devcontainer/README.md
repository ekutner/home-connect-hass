# Developing with Visual Studio Code + devcontainer

The easiest way to get started with **custom** integration development is to use Visual Studio Code with devcontainers. This approach will create a preconfigured development environment with all the tools you need.

The container will be built with all the pre-requisites required in order to run and debug your integration using a dedicated Home Assistant core instance.
I've created this devcontainer after getting frustrated with the existing ones offered by the communitym which didn't include all the features I expected. In particular, supporting parallel development of the integration itself and an associated API library for abstracting access to the functionality the integration is exposing.

</br>

# Using this devcontainer
Opening multiple projects inside of a devcontainer is a bit cluncky so follow these steps carefullty

1. Create a parent directory that will contain both the integration and the API library.
2. Create a folder for the integration. Make sure it follows the structure required by HACS, in particular it must have "custome_components" subfolder where all the integration code will reside. The .devcontainer folder should also be here.
3. Create a folder for the API library. Since this library has to be pubuilshed to 
   pypi make sure it has a setup.py file at its root.  
   At this point your folder structure should look something like this:  
    ```
    <main_folder>  
    ┣━━━━━━ <integration folder>  
    ┃       ┣━━━ .devcontainer  
    ┃       ┗━━━ custom_components folder  
    ┃            ┗━━━ the integration itself  
    ┣━━━━━━ <library folder>  
    ┃       ┗━━━ setup.py  
    ┣━━━━━━ ... additional libraries ...  
    ```
4. Edit the .devcontainer/devcontainer.json file as follows:
    * Set the "*name*" as appropriate
    * Edit the last row in the "*mounts*" list to point to the name of your library folder.
5. Now open ONLY the **integration** folder in VSCode. You will see a popup,
   suggesting to reopen the folder in a devcontainer. Click on that and let the container build itself. This might take a while.
6. Now select *File -> Add Folder to Workspace* from VSCode menu and select the library folder.
7. You should now have both folders in your workspace. Use *File -> Save Workspace As*  to save the workspace **TO THE INTEGRATION FOLDER**, if you don't save it there it will get lost when the container is rebuilt.

If you ever need to reopen the container from sratch you can just click the workspace file. You will get a warning saying the workspace may not open properly, ignore that warning and continue.


You can configure this instance by updating the `./devcontainer/configuration.yaml` file.

**Prerequisites**

- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- Docker
  -  For Linux, macOS, or Windows 10 Pro/Enterprise/Education use the [current release version of Docker](https://docs.docker.com/install/)
  -   Windows 10 Home requires [WSL 2](https://docs.microsoft.com/windows/wsl/wsl2-install) and the current Edge version of Docker Desktop (see instructions [here](https://docs.docker.com/docker-for-windows/wsl-tech-preview/)). This can also be used for Windows Pro/Enterprise/Education.
- [Visual Studio code](https://code.visualstudio.com/)
- [Remote - Containers (VSC Extension)][extension-link]

[More info about requirements and devcontainer in general](https://code.visualstudio.com/docs/remote/containers#_getting-started)

[extension-link]: https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers

**Getting started:**

1. Fork the repository.
2. Clone the repository to your computer.
3. Open the repository using Visual Studio code.

When you open this repository with Visual Studio code you are asked to "Reopen in Container", this will start the build of the container.

_If you don't see this notification, open the command palette and select `Remote-Containers: Reopen Folder in Container`._

### Tasks

The devcontainer comes with some useful tasks to help you with development, you can start these tasks by opening the command palette and select `Tasks: Run Task` then select the task you want to run.

When a task is currently running (like `Run Home Assistant on port 9123` for the docs), it can be restarted by opening the command palette and selecting `Tasks: Restart Running Task`, then select the task you want to restart.

The available tasks are:

Task | Description
-- | --
Run Home Assistant on port 9123 | Launch Home Assistant with your custom component code and the configuration defined in `.devcontainer/configuration.yaml`.
Run Home Assistant configuration against /config | Check the configuration.
Upgrade Home Assistant to latest dev | Upgrade the Home Assistant core version in the container to the latest version of the `dev` branch.
Install a specific version of Home Assistant | Install a specific version of Home Assistant core in the container.

### Step by Step debugging

With the development container,
you can test your custom component in Home Assistant with step by step debugging.

You need to modify the `configuration.yaml` file in `.devcontainer` folder
by uncommenting the line:

```yaml
# debugpy:
```

Then launch the task `Run Home Assistant on port 9123`, and launch the debugger
with the existing debugging configuration `Python: Attach Local`.

For more information, look at [the Remote Python Debugger integration documentation](https://www.home-assistant.io/integrations/debugpy/).
