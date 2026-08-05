"""Fetch per-program reference consumption from the BSH program-assistant-service.

The public Home Connect API only exposes ``BSH.Common.Option.EnergyForecast`` /
``WaterForecast`` as percentages. The absolute kWh / liter reference values that
the official app shows - and accumulates into its monthly usage statistics - come
from a separate "program-assistant" service that lives on the regional app-backend
host (``eu`` / ``na.services.home-connect.com``) and accepts the same OAuth token
as the public API.

Request:  ``POST /program-assistant-service/api/v1/{applianceType}/{haId}/program-metadata/{programKey}``
          body ``{"parameters": [{"key": <optionKey>, "value": <optionValue>}, ...]}``
Response: ``metadata.data`` with ``Consumption.Energy`` (Wh), ``Consumption.Water`` (mL),
          ``Runtime.Total`` (s), among others.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

SERVICES_HOSTS = {
    "EU": "https://eu.services.home-connect.com",
    "US": "https://na.services.home-connect.com",
}
_PATH = "/program-assistant-service/api/v1/{app_type}/{ha_id}/program-metadata/{program_key}"

# Remember the services host that answered for a given appliance so we don't probe
# both regions on every call.
_host_cache: dict[str, str] = {}


async def async_get_program_reference(
    auth,
    ha_id: str,
    app_type: str,
    program_key: str,
    options=None,
    region: str | None = None,
) -> dict | None:
    """Return ``{'energy_kwh', 'water_liters', 'runtime_seconds'}`` for a program.

    ``auth`` is any object exposing ``websession`` (an aiohttp ClientSession) and an
    awaitable ``async_get_access_token()`` - i.e. the integration's existing auth.
    ``options`` is a list of ``{'key', 'value'}`` for the program settings, which
    influence the result. ``region`` ('EU'/'US') forces a host; otherwise the host
    is auto-detected and cached per appliance. Returns ``None`` on any failure.
    """
    token = await auth.async_get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"parameters": options or []}
    path = _PATH.format(
        app_type=quote(app_type, safe=""),
        ha_id=quote(ha_id, safe=""),
        program_key=quote(program_key, safe=""),
    )

    if region and region.upper() in SERVICES_HOSTS:
        hosts = [SERVICES_HOSTS[region.upper()]]
    elif ha_id in _host_cache:
        hosts = [_host_cache[ha_id]]
    else:
        hosts = list(SERVICES_HOSTS.values())

    for host in hosts:
        try:
            async with auth.websession.post(
                host + path, json=body, headers=headers
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "program-metadata %s%s -> %s", host, path, resp.status
                    )
                    continue
                payload = await resp.json()
        except Exception as ex:  # noqa: BLE001 - network/JSON errors are non-fatal
            _LOGGER.debug("program-metadata request to %s failed: %s", host, ex)
            continue

        _host_cache[ha_id] = host
        data = (payload.get("metadata") or {}).get("data") or {}
        result: dict[str, float] = {}
        if data.get("Consumption.Energy") is not None:
            result["energy_kwh"] = data["Consumption.Energy"] / 1000.0
        if data.get("Consumption.Water") is not None:
            result["water_liters"] = data["Consumption.Water"] / 1000.0
        if data.get("Runtime.Total") is not None:
            result["runtime_seconds"] = data["Runtime.Total"]
        return result

    return None
