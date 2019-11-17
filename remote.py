"""Support for interface with an LG webOS Smart TV."""
import asyncio
from datetime import timedelta
import logging
from urllib.parse import urlparse
from typing import Dict

from custom_components.webostv.pylgtv.webos_client import WebOsClient

import voluptuous as vol

from homeassistant.components import remote
from homeassistant import util

from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_FILENAME,
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.helpers.entity import Entity

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DOMAIN,
    PLATFORM_SCHEMA,
    RemoteDevice,
)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

_CONFIGURING: Dict[str, str] = {}
_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = "sources"
CONF_ON_ACTION = "turn_on_action"

DEFAULT_NAME = "LG webOS Smart TV"
LIVETV_APP_ID = "com.webos.app.livetv"

WEBOSTV_CONFIG_FILE = "webostv1.conf"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

CUSTOMIZE_SCHEMA = vol.Schema(
    {vol.Optional(CONF_SOURCES): vol.All(cv.ensure_list, [cv.string])}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA,
        vol.Optional(CONF_FILENAME, default=WEBOSTV_CONFIG_FILE): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_TIMEOUT, default=8): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the LG WebOS TV platform."""
    #if discovery_info is not None:
    #    host = urlparse(discovery_info[1]).hostname
    #else:
    host = config.get(CONF_HOST)

    if host is None:
        _LOGGER.error("No TV found in configuration file or with discovery")
        return False

    # Only act if we are not already configuring this host
    if host in _CONFIGURING:
        return

    name = config.get(CONF_NAME)
    customize = config.get(CONF_CUSTOMIZE)
    timeout = config.get(CONF_TIMEOUT)
    turn_on_action = config.get(CONF_ON_ACTION)

    config = hass.config.path(config.get(CONF_FILENAME))

    setup_tv(host, name, customize, config, timeout, hass, add_entities, turn_on_action)


def setup_tv(
    host, name, customize, config, timeout, hass, add_entities, turn_on_action
):
    """Set up a LG WebOS TV based on host parameter."""
    from pylgtv import WebOsClient
    from pylgtv import PyLGTVPairException
    from websockets.exceptions import ConnectionClosed

    client = WebOsClient(host, config, timeout)

    if not client.is_registered():
        if host in _CONFIGURING:
            # Try to pair.
            try:
                client.register()
            except PyLGTVPairException:
                _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
                return
            except (OSError, ConnectionClosed, asyncio.TimeoutError):
                _LOGGER.error("Unable to connect to host %s", host)
                return
        else:
            # Not registered, request configuration.
            _LOGGER.warning("LG webOS TV %s needs to be paired", host)
            request_configuration(
                host,
                name,
                customize,
                config,
                timeout,
                hass,
                add_entities,
                turn_on_action,
            )
            return

    # If we came here and configuring this host, mark as done.
    if client.is_registered() and host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = hass.components.configurator
        configurator.request_done(request_id)

    add_entities(
        [LgWebOSRemote(host, name, customize, config, timeout, hass, turn_on_action)],
        True,
    )


def request_configuration(
    host, name, customize, config, timeout, hass, add_entities, turn_on_action
):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to pair, please try again."
        )
        return

    def lgtv_configuration_callback(data):
        """Handle actions when configuration callback is called."""
        setup_tv(
            host, name, customize, config, timeout, hass, add_entities, turn_on_action
        )

    _CONFIGURING[host] = configurator.request_config(
        name,
        lgtv_configuration_callback,
        description="Click start and accept the pairing request on your TV.",
        description_image="/static/images/config_webos.png",
        submit_caption="Start pairing request",
    )

class LgWebOSRemote(remote.RemoteDevice):
    """Representation of a LG WebOS TV."""
    from custom_components.webostv.pylgtv.webos_client import WebOsClient
    def __init__(self, host, name, customize, config, timeout, hass, on_action):
        """Initialize the webos device."""

        self.remote = WebOsClient(host, config, timeout)
        # self._on_script = Script(hass, on_action) if on_action else None
        # self._customize = customize

        self._name = name

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        return

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def turn_off(self):
        return

    def turn_on(self):
        return

    @property
    def should_poll(self):
        """No polling needed for Roku."""
        return False

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        _LOGGER.warning("send_command:" + str(command))
        #self.remote.up_button()
        
        for single_command in command:
            #if not hasattr(self.remote, single_command):
            #   continue

            #getattr(self.remote, single_command)()
            _LOGGER.warning("send_command:" + str(single_command))
            self.remote.send_button(single_command)
