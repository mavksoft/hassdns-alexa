"""Config flow for HassDNS Alexa."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL

from .const import (
    CONF_CLOUD_URL,
    CONF_LINK_TOKEN,
    CONF_LOCALE,
    DEFAULT_CLOUD_URL,
    DEFAULT_LOCALE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

LOCALES = ["en-US", "es-ES", "de-DE", "fr-FR", "it-IT", "pt-BR"]


class HassdnsAlexaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Ask for locale/cloud; generate the link token automatically."""
        self._async_abort_entries_match()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                token_obj = await self.hass.auth.async_create_long_lived_access_token(
                    "HassDNS Alexa", 3600 * 24 * 365 * 10
                )
                link_token = token_obj.access_token
            except Exception as err:  # noqa: BLE001 — surface any auth API failure
                _LOGGER.error("Could not create link token: %s", err)
                errors["base"] = "token_failed"
            else:
                ha_url = user_input.get(CONF_URL) or str(
                    self.hass.config.api.base_url or ""
                )
                return self.async_create_entry(
                    title="HassDNS Alexa",
                    data={
                        CONF_CLOUD_URL: user_input[CONF_CLOUD_URL].rstrip("/"),
                        CONF_LOCALE: user_input.get(CONF_LOCALE, DEFAULT_LOCALE),
                        CONF_LINK_TOKEN: link_token,
                        "ha_url": ha_url.rstrip("/"),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Required(CONF_CLOUD_URL, default=DEFAULT_CLOUD_URL): str,
                    vol.Required(CONF_LOCALE, default=DEFAULT_LOCALE): vol.In(LOCALES),
                }
            ),
            errors=errors,
            description_placeholders={"cloud": DEFAULT_CLOUD_URL},
        )
