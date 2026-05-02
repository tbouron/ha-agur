"""Repairs for the Agur integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_STATISTICS_UNIT_L = "statistics_unit_liters"


async def async_check_and_create_repair_issues(hass: HomeAssistant, contract_ids: list[str]) -> None:
    """Check each contract's statistics unit and raise a repair issue if still in L."""
    from .coordinator import AgurDataUpdateCoordinator

    coordinator: AgurDataUpdateCoordinator = next(
        iter(hass.data[DOMAIN].values()), None
    )
    if coordinator is None:
        return

    recorder = get_instance(hass)
    for contract_id in contract_ids:
        statistic_id = coordinator.get_statistic_id(contract_id)
        last_stats = await recorder.async_add_executor_job(
            get_last_statistics, hass, 1, statistic_id, True, set("sum")
        )
        if not last_stats:
            continue
        existing_unit = last_stats[statistic_id][0].get("unit")
        if existing_unit == UnitOfVolume.LITERS:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"{ISSUE_STATISTICS_UNIT_L}_{contract_id}",
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_STATISTICS_UNIT_L,
                translation_placeholders={"contract_id": contract_id},
            )


class StatisticsUnitRepairFlow(ConfirmRepairFlow):
    """Repair flow to convert water statistics from L to m³."""

    def __init__(self, contract_id: str) -> None:
        super().__init__()
        self._contract_id = contract_id

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            await _migrate_statistics(self.hass, self._contract_id)
            return self.async_create_entry(data={})
        return await super().async_step_confirm(user_input)


async def _migrate_statistics(hass: HomeAssistant, contract_id: str) -> None:
    """Read all L statistics for a contract and rewrite them as m³."""
    from .coordinator import AgurDataUpdateCoordinator

    coordinator: AgurDataUpdateCoordinator = next(iter(hass.data[DOMAIN].values()))
    statistic_id = coordinator.get_statistic_id(contract_id)
    recorder = get_instance(hass)

    all_stats = await recorder.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(1970, 1, 1),
        None,
        {statistic_id},
        "hour",
        None,
        {"sum", "state"},
    )

    rows = all_stats.get(statistic_id, [])
    if not rows:
        return

    converted = [
        StatisticData(
            start=row["start"],
            state=row["state"] / 1000 if row.get("state") is not None else None,
            sum=row["sum"] / 1000 if row.get("sum") is not None else None,
        )
        for row in rows
    ]

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name="Water consumption",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement=UnitOfVolume.CUBIC_METERS,
    )
    async_add_external_statistics(hass, metadata, converted)
    _LOGGER.info("Migrated statistics for contract %s from L to m³", contract_id)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict | None) -> RepairsFlow:
    """Create the repair fix flow."""
    # issue_id format: statistics_unit_liters_<contract_id>
    contract_id = issue_id.removeprefix(f"{ISSUE_STATISTICS_UNIT_L}_")
    return StatisticsUnitRepairFlow(contract_id)
