# Alternative Home Connect Integration for Home Assistant
This project is an alternative integration for Home Connect enabled home appliances manufactured by BSH under the Bosch, Siemens, Constructa and Neff brands.  

</br>

# Main features
Home Assistant already has a built-in integration for Home Connect, however it is quite basic, generates entities that are not always supported by the connected appliances and tends to stop getting status updates after a while.
This integration attempts to address those issues and has the following features:
* All the entities are dynamically read from the API and reflect true capabilities of the appliance.
* The integration exposes entities that provide complete control over programs, program options, and global settings. These entities are dynamically read from API and therefor are specifically applicable to the connected appliances.
* Configurable options and settings are exposed for easy selection using "Select", "Switch" or "Number" entities, as appropriate.
* Read only status values, as well as some selectable options are also made available either using "Sensor" or "Binary Sensor" entities for easier use when only wanting to display them.
* Status events that are published by the Home Connect service are exposed as Home Assistant events.
* "Program Started" and "Program Finished" events are exposed as triggers for easier building of automation scripts.
* A "Start Program" Button entity is provided to start operation of the selected program.
* Program and option selections are also available as a service for easier integration in scripts.
* The state of all entities is updated at real time with a cloud push type integration.
* Clean handling of appliances disconnecting and reconnecting from the cloud.
* Clean handling of new appliances being added or removed from the service.
* All the names support translation but currently only English translation is provided.
* Using pure async implementation for reduced load on the platform.
  
</br>  

# Installing this integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Configuration
Follow the instructions for the default Home Connect integration at https://www.home-assistant.io/integrations/home_connect/  
This integration requires the same configuration process and similar settings in configuration.yaml:
```
home_connect_alt:
  client_id: < Your Client ID >
  client_secret: < You Client Secret >
```

After the integration is configured READ THE DAQ then add it from the Home-Assistant UI.  

</br>

# FAQ
* **Some of my appliances are not showing up after I added the integration**  
  Due to unreasonable rate limits set by BSH there is a limit of about 3 
  appliances loaded per minute. If you have more expect the initial load to take longer. The integration will wait for the service to become available and continue loading the rest of the appliances. You may have to refresh your screen to see them in Home Assistant after they were added.

* **I've restarted Home Assistant a few times and now all my appliances are unavilable**  
  This is, again, related to the Home Connect rate limits. Every time you restart Home Assistant the integration makes a few API calls to the service and if that happens too often it may block for up to 24 hours. The best way to fix this is to wait a day and restart Home Assistant again.

* **I select a program or option but nothing happens on the appliance**  
  Make sure the appliance is turned on. Typically the integration will automatically detect appliances that are turned off or disconnected from the network and disable them in Home Assistant but it may happen that it fails to detect that and then attempting make any changes to setting will fail.

* **I try to start the selected program by pressing the button but nothing happens**  
  Make sure Remote Start is enabled on the appliance

* **Sensor related to program progress are showing up as unavailable**  
  These sensors only become available when the appliance is running a program.

* **All the program, option and settings selection boxes, switches and numbers are disabled**  
  Make sure that *Remote Control* is allowed on the appliance. It is typically enabled by default but gets temporarily disabled when changing setting on the appliance itself.

* **The *Start* button is disabled**  
  Make sure that *Remote Control Start* is allowed on the appliance, it's disabled by default. 



</br>

# Automation Notes
* There is a special sensor called **Home Connect Status** which shows the status of the integration. It has the following values:
  * INIT - The integration is initializing
  * LOADING - The integration is loading data from the cloud service
  * LOADED - The integration finished loading data
  * READY - The integration has successfully subscribed to real time updates from the cloud service and is now fully functional. 
  *It may take up to one minute to go from LOADED to READY*

* The integration exposes the events fired by the service as Home Assistant events under the name: **"home_connect_alt_event"**
* The integration exposes two triggers for easy automation:
  * select_program
  * start_program 

# Legal Notice
This integration is not built, maintained, provided or associated with BSH in any way.