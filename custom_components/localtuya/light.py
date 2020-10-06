"""Platform to locally control Tuya-based light devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_ID
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    LightEntity,
    DOMAIN,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP)

from .common import LocalTuyaEntity, prepare_setup_entities

_LOGGER = logging.getLogger(__name__)

SET = "set"

CONF_MIN_MIREDS = "min_mireds"
CONF_MAX_MIREDS = "max_mireds"
CONF_ISCOLOR = "is_color"

MIN_BRIGHTNESS = 26
MAX_BRIGHTNESS = 255
MAX_LIGHTNESS = 100

UPDATE_RETRY_LIMIT = 3

MODE_WHITE = 'white'
MODE_COLOR = 'colour'

DPS_INDEX_ON = "1"
DPS_INDEX_MODE = "2"
DPS_INDEX_BRIGHTNESS = "3"
DPS_INDEX_COLOURTEMP = "4"
DPS_INDEX_COLOUR = "5"


def flow_schema(dps):
    """Return schema used in config flow."""
    _LOGGER.debug("Invoked light flow_schema")
    return {
        vol.Optional(CONF_MIN_MIREDS): vol.In(dps),
        vol.Optional(CONF_MAX_MIREDS): vol.In(dps),
        vol.Optional(CONF_ISCOLOR): vol.In(dps),
    }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Tuya light based on a config entry."""
    tuyainterface, entities_to_setup = prepare_setup_entities(
        hass, config_entry, DOMAIN
    )
    if not entities_to_setup:
        return

    lights = []
    for device_config in entities_to_setup:
        lights.append(
            LocaltuyaLight(
                tuyainterface,
                config_entry,
                device_config[CONF_ID],
            )
        )

    async_add_entities(lights)


class LocaltuyaLight(LocalTuyaEntity, LightEntity):
    """Representation of a Tuya light."""

    def __init__(
        self,
        device,
        config_entry,
        lightid,
        **kwargs,
    ):
        """Initialize the Tuya light."""
        super().__init__(device, config_entry, lightid, **kwargs)

        self._state = True
        self._brightness = MAX_BRIGHTNESS
        self._mode = MODE_WHITE
        self._min_mireds = None
        self._max_mireds = None
        self._hs_color = None

        min_mireds = self._config.get(CONF_MIN_MIREDS)
        max_mireds = self._config.get(CONF_MAX_MIREDS)

        max_mireds = 370
        if config_entry.data["local_key"] == "38715fc5c39ab587":
            min_mireds = 154
        else:
            min_mireds = 167

        if min_mireds is not None and max_mireds is not None:
            self._min_mireds = min_mireds
            self._max_mireds = max_mireds
        self._color_temp = self._min_mireds

        is_color = self._config.get(CONF_ISCOLOR)
        is_color = True
        if is_color is not None:
            if is_color:
                self._hs_color = [0, 0]

    @property
    def is_on(self):
        """Check if Tuya light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return color temperature min mireds."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return color temperature max mireds."""
        return self._max_mireds

    @property
    def hs_color(self):
        """Return color."""
        if self._mode == MODE_COLOR:
            return self._hs_color
        else:
            return [0, 0]

    @property
    def should_poll(self):
        """Return if platform should poll for updates."""
        return True

    @property
    def available(self):
        """Return if device is available or not."""
        # Update if necessary
        status = self._device.status()
        return bool(self._status)

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_BRIGHTNESS
        if self._min_mireds is not None and self._max_mireds is not None:
            supports = supports | SUPPORT_COLOR_TEMP
        if self._hs_color is not None:
            supports = supports | SUPPORT_COLOR
        return supports

    def turn_on(self, **kwargs):
        """Turn on or control the light."""
        dps = {}

        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            brightness = max(MIN_BRIGHTNESS, brightness)
            brightness = min(MAX_BRIGHTNESS, brightness)
            self._brightness = brightness

        if ATTR_COLOR_TEMP in kwargs and self._min_mireds is not None and self._max_mireds is not None:
            self._mode = MODE_WHITE
            self._color_temp = int(kwargs[ATTR_COLOR_TEMP])
            self._hs_color = [0, 0]

        if ATTR_HS_COLOR in kwargs:
            self._mode = MODE_COLOR
            self._hs_color = kwargs.get(ATTR_HS_COLOR)

            if self._hs_color[1] < 5:
                self._mode = MODE_WHITE

        if self._mode == MODE_WHITE:
            mireds_range = self._max_mireds - self._min_mireds
            normalised_mireds = self._color_temp - self._min_mireds
            color_temp = int(
                round(255 - normalised_mireds / mireds_range * 255))
            dps[DPS_INDEX_COLOURTEMP] = color_temp
            dps[DPS_INDEX_BRIGHTNESS] = self._brightness

            _LOGGER.debug("Setting white mode"
                          + ", brightness = " + str(self._brightness)
                          + ", color_temp = " + str(color_temp))
        else:
            lightness = int(
                round(self._brightness / MAX_BRIGHTNESS * MAX_LIGHTNESS))
            lightness = min(MAX_LIGHTNESS, lightness)
            rgb = color_util.color_hsv_to_RGB(
                self._hs_color[0], self._hs_color[1], lightness)

            red = format(int(rgb[0]), "02x")
            green = format(int(rgb[1]), "02x")
            blue = format(int(rgb[2]), "02x")

            h = format(int(self._hs_color[0]), "04x")
            s = format(int(self._hs_color[1]), "02x")
            v = format(lightness, "02x")

            hexvalue = red + green + blue + h + s + v
            dps[DPS_INDEX_COLOUR] = hexvalue

            _LOGGER.debug("Setting color mode"
                          + ", hs_colour = " + str(self._hs_color)
                          + ", brightness = " + str(self._brightness)
                          + ", hexvalue = " + hexvalue
                          + ", lightness = " + str(lightness))

        dps[DPS_INDEX_MODE] = self._mode
        dps[self._dps_id] = True
        self._device.set_dps_set(dps)

    def turn_off(self, **kwargs):
        """Turn Tuya light off."""
        self._device.set_dps(False, self._dps_id)

    def status_updated(self):
        """Device status was updated."""
        state = self.dps(self._dps_id)
        if state is not None:
            self._state = state
        else:
            self._state = False

        mode = self.dps(DPS_INDEX_MODE)
        if mode is not None:
            self._mode = mode

        if mode == MODE_WHITE:
            color_temp = self.dps(DPS_INDEX_COLOURTEMP)
            if color_temp is not None and self._min_mireds is not None and self._max_mireds is not None:
                color_temp = 255 - color_temp
                mireds_range = self._max_mireds - self._min_mireds
                self._color_temp = int(
                    round(color_temp / 255 * mireds_range + self._min_mireds))

            brightness = self.dps(DPS_INDEX_BRIGHTNESS)
            if brightness is not None:
                brightness = int(brightness)
                brightness = min(MAX_BRIGHTNESS, brightness)
                brightness = max(MIN_BRIGHTNESS, brightness)
                self._brightness = brightness

            _LOGGER.debug("Refreshed white mode"
                          + ", color_temp = " + str(self._color_temp)
                          + ", brightness = " + str(self._brightness))

        elif mode == MODE_COLOR:
            color_str = self.dps(DPS_INDEX_COLOUR)

            red = int(color_str[0: 2], 16)
            green = int(color_str[2: 4], 16)
            blue = int(color_str[4: 6], 16)

            brightness = int(color_str[12: 14], 16)
            brightness = int(brightness * MAX_BRIGHTNESS / MAX_LIGHTNESS)
            brightness = min(brightness, MAX_BRIGHTNESS)
            brightness = max(brightness, MIN_BRIGHTNESS)

            self._brightness = brightness
            self._hs_color = color_util.color_RGB_to_hs(red, green, blue)

            _LOGGER.debug("Refreshed color mode"
                          + ", hs_color = " + str(self._hs_color)
                          + ", brightness = " + str(self._brightness))
