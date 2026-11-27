"""AlexaConfig for HassDNS cloud."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.alexa.config import AbstractConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CONF_CLOUD_URL,
    CONF_HA_URL,
    CONF_LINK_TOKEN,
    CONF_LOCALE,
    DEFAULT_CLOUD_URL,
    DEFAULT_LOCALE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Alexa event gateways by region — HA POSTs ChangeReports straight to
# Amazon with the LWA token the cloud hands out via proactive_token.php.
EVENT_GATEWAYS = {
    "en-US": "https://api.amazonalexa.com/v3/events",
    "pt-BR": "https://api.amazonalexa.com/v3/events",
    "es-ES": "https://api.eu.amazonalexa.com/v3/events",
    "de-DE": "https://api.eu.amazonalexa.com/v3/events",
    "fr-FR": "https://api.eu.amazonalexa.com/v3/events",
    "it-IT": "https://api.eu.amazonalexa.com/v3/events",
}
DEFAULT_GATEWAY = "https://api.amazonalexa.com/v3/events"


class HassdnsAlexaConfig(AbstractConfig):
    """Config binding HA to the ha-cloud.es bridge.

    A single instance lives for the whole integration lifetime (created in
    async_setup, shared by SmartHomeView). The config entry and per-entry
    runtime data are resolved lazily so the view survives entry reloads.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Init."""
        super().__init__(hass)

    @property
    def _entry(self) -> ConfigEntry | None:
        """The single config entry, if it exists."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        return entries[0] if entries else None

    @property
    def _runtime(self) -> dict:
        """Per-entry runtime data (exposed map + store), set in async_setup_entry."""
        if (entry := self._entry) is None:
            return {}
        return self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    @property
    def exposed(self) -> dict:
        """Entity exposure map for the current entry (empty when unloaded)."""
        return self._runtime.get("exposed", {})

    @property
    def expose_store(self):
        """Storage for the exposure map (None when the entry is unloaded)."""
        return self._runtime.get("expose_store")

    @property
    def supports_auth(self) -> bool:
        """AcceptGrant is handled by the cloud, not here."""
        return False

    @property
    def should_report_state(self) -> bool:
        """We do proactive reporting through the cloud."""
        return True

    @property
    def endpoint(self) -> str | None:
        """Alexa event gateway for the entry's region.

        The cloud only supplies the LWA bearer; the ChangeReport itself is
        POSTed by HA straight to Amazon's gateway (state_report asserts this
        is never None).
        """
        return EVENT_GATEWAYS.get(self.locale, DEFAULT_GATEWAY)

    @property
    def entity_config(self) -> dict:
        """No per-entity overrides."""
        return {}

    @property
    def locale(self) -> str:
        """Locale from the config entry."""
        if (entry := self._entry) is None:
            return DEFAULT_LOCALE
        return entry.data.get(CONF_LOCALE, DEFAULT_LOCALE)

    @callback
    def user_identifier(self) -> str:
        """Identify this config."""
        entry = self._entry
        return f"hassdns-alexa:{entry.entry_id if entry else 'unloaded'}"

    @callback
    def should_expose(self, entity_id: str) -> bool:
        """Only explicitly exposed entities."""
        return bool(self.exposed.get(entity_id))

    @callback
    def async_invalidate_access_token(self) -> None:
        """No-op: the cloud refreshes LWA tokens on expiry."""

    async def async_get_access_token(self) -> str | None:
        """Fetch a proactive-events token from the cloud."""
        if (entry := self._entry) is None:
            return None
        cloud = entry.data[CONF_CLOUD_URL].rstrip("/")
        token = entry.data.get(CONF_LINK_TOKEN)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{cloud}/api/proactive_token.php",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("proactive_token returned %s", resp.status)
                        return None
                    return (await resp.json()).get("access_token")
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("proactive_token failed: %s", err)
            return None

    async def async_accept_grant(self, code: str):
        """Unused — cloud handles grants."""
        return None

    def link_info(self) -> dict:
        """Data the panel shows the user for linking."""
        if (entry := self._entry) is None:
            return {
                "cloud_url": DEFAULT_CLOUD_URL,
                "link_token": "",
                "ha_url": "",
            }
        ha_url = entry.data.get(CONF_HA_URL) or ""
        if not ha_url:
            try:
                ha_url = get_url(self.hass, prefer_external=True)
            except NoURLAvailableError:
                ha_url = ""
        return {
            "cloud_url": entry.data[CONF_CLOUD_URL],
            "link_token": entry.data.get(CONF_LINK_TOKEN, ""),
            "ha_url": ha_url,
        }
