"""AlexaConfig for HassDNS cloud."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.alexa.config import AbstractConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_CLOUD_URL, CONF_HA_URL, CONF_LINK_TOKEN, CONF_LOCALE, DEFAULT_LOCALE

_LOGGER = logging.getLogger(__name__)


class HassdnsAlexaConfig(AbstractConfig):
    """Config binding HA to the ha-cloud.es bridge."""

    def __init__(self, hass: HomeAssistant, entry, exposed: dict, expose_store) -> None:
        """Init."""
        super().__init__(hass)
        self._entry = entry
        self.exposed = exposed
        self.expose_store = expose_store
        self._unsub = None

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
        """Events go through the cloud, not directly to Amazon."""
        return None

    @property
    def entity_config(self) -> dict:
        """No per-entity overrides."""
        return {}

    @property
    def locale(self) -> str:
        """Locale from the config entry."""
        return self._entry.data.get(CONF_LOCALE, DEFAULT_LOCALE)

    @callback
    def user_identifier(self) -> str:
        """Identify this config."""
        return f"hassdns-alexa:{self._entry.entry_id}"

    @callback
    def should_expose(self, entity_id: str) -> bool:
        """Only explicitly exposed entities."""
        return bool(self.exposed.get(entity_id))

    @callback
    def async_invalidate_access_token(self) -> None:
        """No-op: the cloud refreshes LWA tokens on expiry."""

    async def async_get_access_token(self) -> str | None:
        """Fetch a proactive-events token from the cloud."""
        cloud = self._entry.data[CONF_CLOUD_URL].rstrip("/")
        token = self._entry.data.get(CONF_LINK_TOKEN)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
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
        ha_url = self._entry.data.get(CONF_HA_URL) or ""
        if not ha_url:
            try:
                ha_url = get_url(self.hass, prefer_external=True)
            except NoURLAvailableError:
                ha_url = ""
        return {
            "cloud_url": self._entry.data[CONF_CLOUD_URL],
            "link_token": self._entry.data.get(CONF_LINK_TOKEN, ""),
            "ha_url": ha_url,
        }
