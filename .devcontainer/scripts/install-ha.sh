#!/usr/bin/env bash

hassver="${1:-}"
if [ "$hassver" = "" ]; then
    hassver="dev"
fi
echo "Fetching Home Assistant branch: $hassver"

# Update Home Assistant to the latest version
sudo python3 -m pip --disable-pip-version-check install --upgrade git+https://github.com/home-assistant/home-assistant.git@$hassver
# Install requirements for default_config and all configured integrations
sudo python3 -c "
import json, os

base = os.path.dirname(__import__('homeassistant').__file__) + '/components'

# Home Assistant always sets up its base entity platforms, whether or not any
# configured integration references them. They are reachable neither from
# default_config nor from the config entries, so without seeding them here
# their requirements are never collected and setup fails with
# 'No module named ...' - e.g. 'radio_frequency' needs rf-protocols and
# 'infrared' needs infrared-protocols. Reading the list from the installed
# Home Assistant keeps it correct as that list changes.
try:
    from homeassistant.const import BASE_PLATFORMS
except ImportError:
    # Renamed or removed upstream: fall back to the old behaviour rather than
    # taking the whole environment setup down with us.
    BASE_PLATFORMS = set()
    print('# warning: homeassistant.const.BASE_PLATFORMS not found')

# Anything still missed. Normally empty.
EXTRA_DOMAINS = []

# Start with default_config and the base platforms, plus any integrations
# from the config entries
seeds = ['default_config'] + sorted(BASE_PLATFORMS) + EXTRA_DOMAINS
config_entries = '/config/.storage/core.config_entries'
if os.path.exists(config_entries):
    data = json.load(open(config_entries))
    seeds.extend(e.get('domain','') for e in data.get('data',{}).get('entries',[]))

to_visit, visited, reqs = list(seeds), set(), set()
while to_visit:
    comp = to_visit.pop(0)
    if comp in visited: continue
    visited.add(comp)
    mf = os.path.join(base, comp, 'manifest.json')
    if not os.path.exists(mf): continue
    m = json.load(open(mf))
    to_visit.extend(m.get('dependencies', []) + m.get('after_dependencies', []))
    reqs.update(m.get('requirements', []))
print('\n'.join(sorted(reqs)))
" | sudo pip install --disable-pip-version-check -r /dev/stdin
sudo hass --script ensure_config -c /config
