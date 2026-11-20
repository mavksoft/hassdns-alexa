"""Config flow for HassDNS Alexa."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL

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

LOCALES = ["en-US", "es-ES", "de-DE", "fr-FR", "it-IT", "pt-BR"]


class HassdnsAlexaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Ask for the public URL, cloud and locale."""
        self._async_abort_entries_match()
        errors: dict[str, str] = {}

        if user_input is not None:
            # The link token is created later from the panel via the stable
            # `auth/long_lived_access_token` websocket command — the auth
            # manager API signature varies across HA versions.
            return self.async_create_entry(
                title="HassDNS Alexa",
                data={
                    CONF_CLOUD_URL: user_input[CONF_CLOUD_URL].rstrip("/"),
                    CONF_LOCALE: user_input.get(CONF_LOCALE, DEFAULT_LOCALE),
                    CONF_LINK_TOKEN: "",
                    CONF_HA_URL: user_input[CONF_URL].rstrip("/"),
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
            description_placeholders={
                "cloud": DEFAULT_CLOUD_URL,
                "example_url": "https://casa.example.com",
            },
        )
