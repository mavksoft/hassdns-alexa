"""HassDNS Alexa — exposes Home Assistant entities to Alexa via ha-cloud.es."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.alexa.smart_home import SmartHomeView
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    storage,
)

from .alexa_config import HassdnsAlexaConfig
from .const import (
    CONF_CLOUD_URL,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STORAGE_KEY,
    STORAGE_VERSION,
    WS_TYPE_ENTITIES,
    WS_TYPE_LINK,
    WS_TYPE_SET_EXPOSE,
    WS_TYPE_SET_TOKEN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration (websocket commands registered once)."""
    websocket_api.async_register_command(hass, ws_entities)
    websocket_api.async_register_command(hass, ws_set_expose)
    websocket_api.async_register_command(hass, ws_link)
    websocket_api.async_register_command(hass, ws_set_token)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HassDNS Alexa from a config entry."""
    expose_store = storage.Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")
    exposed: dict[str, bool] = (await expose_store.async_load()) or {}

    cfg = HassdnsAlexaConfig(hass, entry, exposed, expose_store)
    await cfg.async_initialize()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = cfg

    # Expose the same endpoint HA core uses: /api/alexa/smart_home
    hass.http.register_view(SmartHomeView(cfg))

    if cfg.should_report_state:
        await cfg.async_enable_proactive_mode()

    # Panel
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "hassdns-alexa-panel",
                "module_url": f"/api/{DOMAIN}/static/hassdns-alexa-panel.js",
            }
        },
        require_admin=True,
    )
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/api/{DOMAIN}/static/hassdns-alexa-panel.js",
                hass.config.path(
                    "custom_components", DOMAIN, "frontend/hassdns-alexa-panel.js"
                ),
                cache_headers=False,
            )
        ]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    if cfg := hass.data.get(DOMAIN, {}).pop(entry.entry_id, None):
        await cfg.async_disable_proactive_mode()
        cfg.async_deinitialize()
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True


def _cfg(hass: HomeAssistant) -> HassdnsAlexaConfig | None:
    entries = hass.data.get(DOMAIN, {})
    return next(iter(entries.values()), None)


def _is_supported(entity_id: str) -> bool:
    domain = entity_id.split(".", 1)[0]
    # Domains the Alexa Smart Home API understands
    return domain in {
        "alert", "automation", "binary_sensor", "button", "camera", "climate",
        "cover", "fan", "group", "humidifier", "input_boolean", "input_button",
        "light", "lock", "media_player", "scene", "script", "sensor",
        "switch", "vacuum", "water_heater",
    }


@callback
@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_ENTITIES})
def ws_entities(hass, connection, msg):
    """List entities with expose state, grouped by area."""
    cfg = _cfg(hass)
    if cfg is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    areas = {a.id: a.name for a in area_reg.async_list_areas()}
    items = []
    for state in hass.states.async_all():
        eid = state.entity_id
        if not _is_supported(eid):
            continue
        entry = ent_reg.async_get(eid)
        area_id = entry.area_id if entry else None
        if not area_id and entry and entry.device_id:
            dev = dev_reg.async_get(entry.device_id)
            area_id = dev.area_id if dev else None
        items.append({
            "entity_id": eid,
            "name": state.name,
            "domain": eid.split(".", 1)[0],
            "area": areas.get(area_id, ""),
            "exposed": bool(cfg.exposed.get(eid)),
        })
    items.sort(key=lambda i: (i["area"], i["domain"], i["name"]))
    connection.send_result(msg["id"], {"entities": items})


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SET_EXPOSE,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("expose"): bool,
    }
)
def ws_set_expose(hass, connection, msg):
    """Toggle exposure of one entity."""
    cfg = _cfg(hass)
    if cfg is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    eid = msg["entity_id"]
    if msg["expose"]:
        cfg.exposed[eid] = True
    else:
        cfg.exposed.pop(eid, None)
    hass.async_create_task(cfg.expose_store.async_save(cfg.exposed))
    connection.send_result(msg["id"], {"entity_id": eid, "exposed": bool(cfg.exposed.get(eid))})


@callback
@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_LINK})
def ws_link(hass, connection, msg):
    """Return the info the user needs for the ha-cloud.es linking page."""
    cfg = _cfg(hass)
    if cfg is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    connection.send_result(msg["id"], cfg.link_info())


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SET_TOKEN,
        vol.Required("token"): str,
    }
)
def ws_set_token(hass, connection, msg):
    """Store the link token created via auth/long_lived_access_token."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    entry = entries[0]
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "link_token": msg["token"]}
    )
    connection.send_result(msg["id"], {"ok": True})
