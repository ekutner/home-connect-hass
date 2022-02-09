# Developing with Visual Studio Code + devcontainer

This devcontainer sets up the environment to make it extremly easy to test this integration and with minor changes can be used for any integration.
I've created this devcontainer after getting frustrated with the existing ones, offered by the community, which didn't include all the features I expected. In particular, supporting parallel development of the integration itself and an associated API library / SDK is very often developed in parallel.

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

# How it works
When the devcontainer is launched the assosicated scipts will automatically:
1. Install Home Assistant 
2. Load the main integration project + any number of library porojects into the */workspaces* folder
3. pip install the API libraries
4. Create a /config folder and copy the files from the .devcontainer/config folder to there
5. Set-up a set of proxy folder with references to the integration files under */config/custom_components*. This allows Home Assistant to load the integration from its usual location which allowing vscode to debug it from the standard code location under */workspaces*

# How to debug
Just launch the "Home Assistant" launch configuration from vscode. Setup breakpoints normally.
The Home Assistant portal can be access on http://localhost:9123 of the host machine.

