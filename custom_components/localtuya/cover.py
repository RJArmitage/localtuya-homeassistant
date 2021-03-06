"""Platform to locally control Tuya-based cover devices."""
import logging
from time import sleep

import voluptuous as vol

from homeassistant.components.cover import (
    CoverEntity,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    ATTR_POSITION,
)
from homeassistant.const import CONF_ID

from .const import (
    CONF_OPENCLOSE_CMDS,
    CONF_CURRENT_POSITION_DP,
    CONF_SET_POSITION_DP,
    CONF_POSITIONING_MODE,
    CONF_SPAN_TIME,
)
from .common import LocalTuyaEntity, prepare_setup_entities

_LOGGER = logging.getLogger(__name__)

COVER_ONOFF_CMDS = "on_off"
COVER_OPENCLOSE_CMDS = "open_close"
COVER_STOP_CMD = "stop"
COVER_MODE_NONE = "none"
COVER_MODE_POSITION = "position"
COVER_MODE_FAKE = "fake"

DEFAULT_OPENCLOSE_CMDS = COVER_ONOFF_CMDS
DEFAULT_POSITIONING_MODE = COVER_MODE_NONE
DEFAULT_SPAN_TIME = 25.0


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Optional(CONF_OPENCLOSE_CMDS, default=DEFAULT_OPENCLOSE_CMDS): vol.In(
            [COVER_ONOFF_CMDS, COVER_OPENCLOSE_CMDS]
        ),
        vol.Optional(CONF_POSITIONING_MODE, default=DEFAULT_POSITIONING_MODE): vol.In(
            [COVER_MODE_NONE, COVER_MODE_POSITION, COVER_MODE_FAKE]
        ),
        vol.Optional(CONF_CURRENT_POSITION_DP): vol.In(dps),
        vol.Optional(CONF_SET_POSITION_DP): vol.In(dps),
        vol.Optional(CONF_SPAN_TIME, default=DEFAULT_SPAN_TIME): vol.All(
            vol.Coerce(float), vol.Range(min=1.0, max=300.0)
        ),
    }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Tuya cover based on a config entry."""
    tuyainterface, entities_to_setup = prepare_setup_entities(
        hass, config_entry, DOMAIN
    )
    if not entities_to_setup:
        return

    covers = []
    for device_config in entities_to_setup:
        covers.append(
            LocaltuyaCover(
                tuyainterface,
                config_entry,
                device_config[CONF_ID],
            )
        )

    async_add_entities(covers)


class LocaltuyaCover(LocalTuyaEntity, CoverEntity):
    """Tuya cover device."""

    def __init__(
        self,
        device,
        config_entry,
        switchid,
        **kwargs,
    ):
        """Initialize a new LocaltuyaCover."""
        super().__init__(device, config_entry, switchid, **kwargs)
        self._state = None
        self._current_cover_position = None
        self._open_cmd = self._config[CONF_OPENCLOSE_CMDS].split("_")[0]
        self._close_cmd = self._config[CONF_OPENCLOSE_CMDS].split("_")[1]
        print("Initialized cover [{}]".format(self.name))

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP
        if self._config[CONF_POSITIONING_MODE] != COVER_MODE_NONE:
            supported_features = supported_features | SUPPORT_SET_POSITION
        return supported_features

    @property
    def current_cover_position(self):
        """Return current cover position in percent."""
        return self._current_cover_position

    @property
    def is_opening(self):
        """Return if cover is opening."""
        state = self._state
        return state == self._open_cmd

    @property
    def is_closing(self):
        """Return if cover is closing."""
        state = self._state
        return state == self._close_cmd

    @property
    def is_open(self):
        """Return if the cover is open or not."""
        if self._config[CONF_POSITIONING_MODE] != COVER_MODE_POSITION:
            return None
        return self._current_cover_position == 100

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._config[CONF_POSITIONING_MODE] != COVER_MODE_POSITION:
            return None
        return self._current_cover_position == 0

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        _LOGGER.debug("Setting cover position: %r", kwargs[ATTR_POSITION])
        if self._config[CONF_POSITIONING_MODE] == COVER_MODE_FAKE:
            newpos = float(kwargs[ATTR_POSITION])

            currpos = self.current_cover_position
            posdiff = abs(newpos - currpos)
            mydelay = posdiff / 50.0 * self._config[CONF_SPAN_TIME]
            if newpos > currpos:
                _LOGGER.debug("Opening to %f: delay %f", newpos, mydelay)
                self.open_cover()
            else:
                _LOGGER.debug("Closing to %f: delay %f", newpos, mydelay)
                self.close_cover()
            sleep(mydelay)
            self.stop_cover()
            self._current_cover_position = 50
            _LOGGER.debug("Done")

        elif self._config[CONF_POSITIONING_MODE] == COVER_MODE_POSITION:
            converted_position = int(kwargs[ATTR_POSITION])
            if 0 <= converted_position <= 100 and self.has_config(CONF_SET_POSITION_DP):
                self._device.set_dps(
                    converted_position, self._config[CONF_SET_POSITION_DP]
                )

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.debug("Launching command %s to cover ", self._open_cmd)
        self._device.set_dps(self._open_cmd, self._dps_id)

    def close_cover(self, **kwargs):
        """Close cover."""
        _LOGGER.debug("Launching command %s to cover ", self._close_cmd)
        self._device.set_dps(self._close_cmd, self._dps_id)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        _LOGGER.debug("Launching command %s to cover ", COVER_STOP_CMD)
        self._device.set_dps(COVER_STOP_CMD, self._dps_id)

    def status_updated(self):
        """Device status was updated."""
        self._state = self.dps(self._dps_id)
        if self.has_config(CONF_CURRENT_POSITION_DP):
            self._current_cover_position = self.dps(
                self._config[CONF_CURRENT_POSITION_DP]
            )
        else:
            self._current_cover_position = 50
