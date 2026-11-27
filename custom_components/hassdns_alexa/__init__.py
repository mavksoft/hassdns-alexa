"""HassDNS Alexa — exposes Home Assistant entities to Alexa via ha-cloud.es."""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.models import TOKEN_TYPE_SYSTEM
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
    CONF_LINK_RT_ID,
    CONF_LINK_TOKEN,
    CONF_LINK_USER_ID,
    DATA_CONFIG,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STORAGE_KEY,
    STORAGE_VERSION,
    WS_TYPE_ENTITIES,
    WS_TYPE_GENERATE_TOKEN,
    WS_TYPE_LINK,
    WS_TYPE_SET_EXPOSE,
)

_LOGGER = logging.getLogger(__name__)

# The link token belongs to a dedicated non-admin system user, so the
# third-party cloud only ever gets entity-level access.
LINK_USER_NAME = "HassDNS Alexa"
LINK_TOKEN_DAYS = 3650


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration once (view + websocket + statics)."""
    cfg = HassdnsAlexaConfig(hass)
    await cfg.async_initialize()
    hass.data.setdefault(DOMAIN, {})[DATA_CONFIG] = cfg

    # The view is registered once: aiohttp refuses a second POST route for
    # the same path, so it cannot live in async_setup_entry. The config
    # resolves the current entry lazily.
    hass.http.register_view(SmartHomeView(cfg))

    websocket_api.async_register_command(hass, ws_entities)
    websocket_api.async_register_command(hass, ws_set_expose)
    websocket_api.async_register_command(hass, ws_link)
    websocket_api.async_register_command(hass, ws_generate_token)

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/api/{DOMAIN}/static/hassdns-alexa-panel.js",
                hass.config.path(
                    "custom_components", DOMAIN, "frontend/hassdns-alexa-panel.js"
                ),
                cache_headers=False,
            ),
            StaticPathConfig(
                f"/api/{DOMAIN}/static/logo.png",
                hass.config.path("custom_components", DOMAIN, "frontend/logo.png"),
                cache_headers=True,
            ),
        ]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HassDNS Alexa from a config entry."""
    expose_store = storage.Store(
        hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}"
    )
    exposed: dict[str, bool] = (await expose_store.async_load()) or {}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "exposed": exposed,
        "expose_store": expose_store,
    }

    cfg: HassdnsAlexaConfig = hass.data[DOMAIN][DATA_CONFIG]
    if cfg.should_report_state:
        await cfg.async_enable_proactive_mode()

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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload."""
    data = hass.data.get(DOMAIN, {})
    data.pop(entry.entry_id, None)
    if cfg := data.get(DATA_CONFIG):
        await cfg.async_disable_proactive_mode()
        cfg.async_deinitialize()
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Revoke the link token, remove the dedicated user and wipe storage."""
    if rt_id := entry.data.get(CONF_LINK_RT_ID):
        if rt := hass.auth.async_get_refresh_token(rt_id):
            hass.auth.async_remove_refresh_token(rt)
    if user_id := entry.data.get(CONF_LINK_USER_ID):
        if user := await hass.auth.async_get_user(user_id):
            await hass.auth.async_remove_user(user)
    await storage.Store(
        hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}"
    ).async_remove()


def _cfg(hass: HomeAssistant) -> HassdnsAlexaConfig | None:
    return hass.data.get(DOMAIN, {}).get(DATA_CONFIG)


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
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_ENTITIES})
def ws_entities(hass, connection, msg):
    """List entities with expose state, grouped by area."""
    cfg = _cfg(hass)
    if cfg is None or cfg.expose_store is None:
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
            "icon": state.attributes.get("icon", ""),
            "area": areas.get(area_id, ""),
            "exposed": bool(cfg.exposed.get(eid)),
        })
    items.sort(key=lambda i: (i["area"], i["domain"], i["name"]))
    connection.send_result(msg["id"], {"entities": items})


@callback
@websocket_api.require_admin
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
    if cfg is None or cfg.expose_store is None:
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
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_LINK})
def ws_link(hass, connection, msg):
    """Return the info the user needs for the ha-cloud.es linking page."""
    cfg = _cfg(hass)
    if cfg is None or cfg._entry is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    connection.send_result(msg["id"], cfg.link_info())


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): WS_TYPE_GENERATE_TOKEN})
@websocket_api.async_response
async def ws_generate_token(hass, connection, msg):
    """Create the link token on a dedicated non-admin system user.

    Rotates cleanly: the previous refresh token is revoked and the dedicated
    user is reused (or created) so it can be wiped in async_remove_entry.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    entry = entries[0]

    if old_rt_id := entry.data.get(CONF_LINK_RT_ID):
        if old_rt := hass.auth.async_get_refresh_token(old_rt_id):
            hass.auth.async_remove_refresh_token(old_rt)

    user = None
    if user_id := entry.data.get(CONF_LINK_USER_ID):
        user = await hass.auth.async_get_user(user_id)
    if user is None:
        user = await hass.auth.async_create_system_user(
            LINK_USER_NAME, group_ids=[GROUP_ID_USER]
        )

    rt = await hass.auth.async_create_refresh_token(
        user,
        token_type=TOKEN_TYPE_SYSTEM,
        access_token_expiration=timedelta(days=LINK_TOKEN_DAYS),
    )
    token = hass.auth.async_create_access_token(rt)

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_LINK_TOKEN: token,
            CONF_LINK_USER_ID: user.id,
            CONF_LINK_RT_ID: rt.id,
        },
    )
    connection.send_result(msg["id"], {"token": token})
