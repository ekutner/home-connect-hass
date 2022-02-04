#!/usr/bin/env bash

hassver="$1"
if [ "$hassver" = "" ]; then
    hassver="dev"
    echo "Fetching Home Assistant branch: $hassVer"
fi

# Update Home Assistant to the latest version
python3 -m pip --disable-pip-version-check install --upgrade git+https://github.com/home-assistant/home-assistant.git@$hassver
hass --script ensure_config -c /config