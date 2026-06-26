from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BATTERY_CAPACITY, CONF_BATTERY_VOLTAGE, CONF_SENSOR_INFIX, DOMAIN
from .coordinator import JunctekBLECoordinator


@dataclass(frozen=True, kw_only=True)
class JunctekSensorDescription(SensorEntityDescription):
    key: str
    use_infix: bool = False  # when True, infix is inserted before sensor name in entity_id


SENSORS: tuple[JunctekSensorDescription, ...] = (
    JunctekSensorDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:flash-triangle",
    ),
    JunctekSensorDescription(
        key="current",
        name="Current",
        use_infix=True,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
    ),
    JunctekSensorDescription(
        key="power",
        name="Power",
        use_infix=True,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:home-lightning-bolt-outline",
    ),
    JunctekSensorDescription(
        key="temp",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermometer",
    ),
    JunctekSensorDescription(
        key="soc",
        name="State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    JunctekSensorDescription(
        key="ah_remaining",
        name="Remaining Capacity",
        use_infix=True,
        # No HA device_class for amp-hours; use a plain measurement.
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Ah",
        icon="mdi:battery-charging",
    ),
    JunctekSensorDescription(
        key="mins_remaining",
        name="Remaining Time",
        use_infix=True,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    JunctekSensorDescription(
        key="accum_charge_cap",
        name="Accumulated Charge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Ah",
        icon="mdi:battery-plus-variant",
    ),
    JunctekSensorDescription(
        key="discharge",
        name="Discharged Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-arrow-down",
    ),
    JunctekSensorDescription(
        key="charge",
        name="Charged Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:battery-arrow-up",
    ),
    JunctekSensorDescription(
        key="int_resistance",
        name="Internal Resistance",
        use_infix=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mΩ",
        icon="mdi:omega",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JunctekSensorDescription(
        key="last_message",
        name="Last Message",
        use_infix=True,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-check",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JunctekSensorDescription(
        key="_raw_hex",
        name="Last Raw Packet",
        use_infix=True,
        icon="mdi:bug",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: JunctekBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        JunctekSensor(coordinator, description, entry) for description in SENSORS
    )


class JunctekSensor(CoordinatorEntity[JunctekBLECoordinator], SensorEntity):
    _attr_has_entity_name = True
    entity_description: JunctekSensorDescription

    def __init__(
        self,
        coordinator: JunctekBLECoordinator,
        description: JunctekSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        address = entry.data[CONF_ADDRESS]

        # options overrides data so the user can change it via the options flow
        if CONF_SENSOR_INFIX in entry.options:
            infix = entry.options[CONF_SENSOR_INFIX]
        else:
            infix = entry.data.get(CONF_SENSOR_INFIX, "")
        infix = infix.strip("_").lower()

        if infix and description.use_infix:
            effective_key = f"{infix}_{description.key}"
            self._attr_name = f"{infix} {description.name}"
        else:
            effective_key = description.key

        self._attr_unique_id = f"{address}_{effective_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=f"Junctek Battery Monitor",
            manufacturer="Juntek",
            model="Junctek BLE Battery Monitor",
            serial_number=address,
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.key == "last_message":
            return datetime.fromisoformat(value)
        return value

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key != "_raw_hex":
            return None
        return {"packet_log": list(self.coordinator._packet_log)}

    @property
    def available(self) -> bool:
        if self.coordinator.data is None or not self.coordinator.last_update_success:
            return False
        return self.entity_description.key in self.coordinator.data
