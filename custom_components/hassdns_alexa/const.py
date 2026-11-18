"""Constants for HassDNS Alexa."""

DOMAIN = "hassdns_alexa"

CONF_CLOUD_URL = "cloud_url"
CONF_TOKEN_ID = "token_id"
CONF_LINK_TOKEN = "link_token"
CONF_HA_URL = "ha_url"
CONF_LOCALE = "locale"

DEFAULT_CLOUD_URL = "https://ha-cloud.es"
DEFAULT_LOCALE = "en-US"

STORAGE_KEY = f"{DOMAIN}.expose"
STORAGE_VERSION = 1

PANEL_URL_PATH = "hassdns-alexa"
PANEL_TITLE = "Alexa"
PANEL_ICON = "mdi:amazon-alexa"

WS_TYPE_ENTITIES = f"{DOMAIN}/entities"
WS_TYPE_SET_EXPOSE = f"{DOMAIN}/set_expose"
WS_TYPE_LINK = f"{DOMAIN}/link"
WS_TYPE_SET_TOKEN = f"{DOMAIN}/set_token"
