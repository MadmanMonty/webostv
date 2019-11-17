"""Support for interface with an LG webOS Smart TV."""
import asyncio
from datetime import timedelta
import logging
from urllib.parse import urlparse
from typing import Dict

import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import MediaPlayerDevice, PLATFORM_SCHEMA
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_CHANNEL,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

_CONFIGURING: Dict[str, str] = {}
_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = "sources"
CONF_ON_ACTION = "turn_on_action"

DEFAULT_NAME = "LG webOS Smart TV"
LIVETV_APP_ID = "com.webos.app.livetv"

WEBOSTV_CONFIG_FILE = "webostv.conf"

SUPPORT_WEBOSTV = (
    SUPPORT_TURN_OFF
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
)

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
    if discovery_info is not None:
        host = urlparse(discovery_info[1]).hostname
    else:
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
        [LgWebOSDevice(host, name, customize, config, timeout, hass, turn_on_action)],
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


class LgWebOSDevice(MediaPlayerDevice):
    """Representation of a LG WebOS TV."""

    def __init__(self, host, name, customize, config, timeout, hass, on_action):
        """Initialize the webos device."""
        from pylgtv import WebOsClient

        self._client = WebOsClient(host, config, timeout)
        self._on_script = Script(hass, on_action) if on_action else None
        self._customize = customize

        self._name = name
        # Assume that the TV is not muted
        self._muted = False
        # Assume that the TV is in Play mode
        self._playing = True
        self._volume = 0
        self._current_source = None
        self._current_source_id = None
        self._state = None
        self._source_list = {}
        self._app_list = {}
        self._channel = None
        self._last_icon = None

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data."""
        from websockets.exceptions import ConnectionClosed

        try:
            current_input = self._client.get_input()
            if current_input is not None:
                self._current_source_id = current_input
                if self._state in (None, STATE_OFF):
                    self._state = STATE_PLAYING
            else:
                self._state = STATE_OFF
                self._current_source = None
                self._current_source_id = None
                self._channel = None

            if self._state is not STATE_OFF:
                self._muted = self._client.get_muted()
                self._volume = self._client.get_volume()
                self._channel = self._client.get_current_channel()

                self._source_list = {}
                self._app_list = {}
                conf_sources = self._customize.get(CONF_SOURCES, [])

                for app in self._client.get_apps():
                    self._app_list[app["id"]] = app
                    if app["id"] == self._current_source_id:
                        self._current_source = app["title"]
                        self._source_list[app["title"]] = app
                    elif (
                        not conf_sources
                        or app["id"] in conf_sources
                        or any(word in app["title"] for word in conf_sources)
                        or any(word in app["id"] for word in conf_sources)
                    ):
                        self._source_list[app["title"]] = app

                for source in self._client.get_inputs():
                    if source["id"] == self._current_source_id:
                        self._current_source = source["label"]
                        self._source_list[source["label"]] = source
                    elif (
                        not conf_sources
                        or source["label"] in conf_sources
                        or any(
                            source["label"].find(word) != -1 for word in conf_sources
                        )
                    ):
                        self._source_list[source["label"]] = source
        except (OSError, ConnectionClosed, TypeError, asyncio.TimeoutError):
            self._state = STATE_OFF
            self._current_source = None
            self._current_source_id = None
            self._channel = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return sorted(self._source_list.keys())

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_title(self):
        """Title of current playing media."""
        if (self._channel is not None) and ("channelName" in self._channel):
            return self._channel["channelName"]
        return None

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._current_source_id in self._app_list:
            icon = self._app_list[self._current_source_id]["largeIcon"]
            if not icon.startswith("http"):
                icon = self._app_list[self._current_source_id]["icon"]

            # 'icon' holds a URL with a transient key. Avoid unnecessary
            # updates by returning the same URL until the image changes.
            if self._last_icon and (
                icon.split("/")[-1] == self._last_icon.split("/")[-1]
            ):
                return self._last_icon
            self._last_icon = icon
            return icon
        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._on_script:
            return SUPPORT_WEBOSTV | SUPPORT_TURN_ON
        return SUPPORT_WEBOSTV

    def turn_off(self):
        """Turn off media player."""
        from websockets.exceptions import ConnectionClosed

        self._state = STATE_OFF
        try:
            self._client.power_off()
        except (OSError, ConnectionClosed, TypeError, asyncio.TimeoutError):
            pass

    def turn_on(self):
        """Turn on the media player."""
        if self._on_script:
            self._on_script.run()

    def volume_up(self):
        """Volume up the media player."""
        self._client.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._client.volume_down()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        tv_volume = volume * 100
        self._client.set_volume(tv_volume)

    def mute_volume(self, mute):
        """Send mute command."""
        self._muted = mute
        self._client.set_mute(mute)

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def select_source(self, source):
        """Select input source."""
        source_dict = self._source_list.get(source)
        if source_dict is None:
            _LOGGER.warning("Source %s not found for %s", source, self.name)
            return
        self._current_source_id = source_dict["id"]
        if source_dict.get("title"):
            self._current_source = source_dict["title"]
            self._client.launch_app(source_dict["id"])
        elif source_dict.get("label"):
            self._current_source = source_dict["label"]
            self._client.set_input(source_dict["id"])

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        _LOGGER.debug("Call play media type <%s>, Id <%s>", media_type, media_id)

        if media_type == MEDIA_TYPE_CHANNEL:
            _LOGGER.debug("Searching channel...")
            partial_match_channel_id = None
            perfect_match_channel_id = None

            for channel in self._client.get_channels():
                if media_id == channel["channelNumber"]:
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() == channel["channelName"].lower():
                    perfect_match_channel_id = channel["channelId"]
                    continue

                if media_id.lower() in channel["channelName"].lower():
                    partial_match_channel_id = channel["channelId"]

            if perfect_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with perfect match",
                    perfect_match_channel_id,
                )
                self._client.set_channel(perfect_match_channel_id)
            elif partial_match_channel_id is not None:
                _LOGGER.info(
                    "Switching to channel <%s> with partial match",
                    partial_match_channel_id,
                )
                self._client.set_channel(partial_match_channel_id)

            return

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._state = STATE_PLAYING
        self._client.play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._state = STATE_PAUSED
        self._client.pause()

    def media_next_track(self):
        """Send next track command."""
        current_input = self._client.get_input()
        if current_input == LIVETV_APP_ID:
            self._client.channel_up()
        else:
            self._client.fast_forward()

    def media_previous_track(self):
        """Send the previous track command."""
        current_input = self._client.get_input()
        if current_input == LIVETV_APP_ID:
            self._client.channel_down()
        else:
            self._client.rewind()
