"""Platform to locally control Tuya-based fan devices."""
import logging

from homeassistant.components.fan import (
    FanEntity,
    DOMAIN,
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SUPPORT_SET_SPEED,
    SUPPORT_OSCILLATE,
)
from homeassistant.const import CONF_ID

from .common import LocalTuyaEntity, prepare_setup_entities

_LOGGER = logging.getLogger(__name__)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Tuya fan based on a config entry."""
    tuyainterface, entities_to_setup = prepare_setup_entities(
        hass, config_entry, DOMAIN
    )
    if not entities_to_setup:
        return

    fans = []

    for device_config in entities_to_setup:
        fans.append(
            LocaltuyaFan(
                tuyainterface,
                config_entry,
                device_config[CONF_ID],
            )
        )

    async_add_entities(fans)


class LocaltuyaFan(LocalTuyaEntity, FanEntity):
    """Representation of a Tuya fan."""

    def __init__(
        self,
        device,
        config_entry,
        fanid,
        **kwargs,
    ):
        """Initialize the entity."""
        super().__init__(device, config_entry, fanid, **kwargs)
        self._is_on = False
        self._speed = SPEED_OFF
        self._oscillating = False

    @property
    def oscillating(self):
        """Return current oscillating status."""
        return self._oscillating

    @property
    def is_on(self):
        """Check if Tuya fan is on."""
        return self._is_on

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        await self._device.set_dps(True, "1")
        if speed is not None:
            await self.async_set_speed(speed)
        else:
            self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        await self._device.set_dps(False, "1")
        self.schedule_update_ha_state()

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self._speed = speed
        if speed == SPEED_OFF:
            await self._device.set_dps(False, "1")
        elif speed == SPEED_LOW:
            await self._device.set_dps("1", "2")
        elif speed == SPEED_MEDIUM:
            await self._device.set_dps("2", "2")
        elif speed == SPEED_HIGH:
            await self._device.set_dps("3", "2")
        self.schedule_update_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self._oscillating = oscillating
        await self._device.set_value("8", oscillating)
        self.schedule_update_ha_state()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED | SUPPORT_OSCILLATE

    def status_updated(self):
        """Get state of Tuya fan."""
        self._is_on = self.dps(self._dps_id)
        if not self._is_on:
            self._speed = SPEED_OFF
        elif self.dps(2) == "1":
            self._speed = SPEED_LOW
        elif self.dps(2) == "2":
            self._speed = SPEED_MEDIUM
        elif self.dps(2) == "3":
            self._speed = SPEED_HIGH
        self._oscillating = self.dps(8)
