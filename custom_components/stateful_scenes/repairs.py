"""Repair issue detection and fix flows for Stateful Scenes."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from homeassistant.components.repairs import RepairsFlow, async_create_issue
from homeassistant.components.repairs import async_register
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REPAIR_DUPLICATE_SCENE_IDS = "duplicate_scene_ids"
REPAIR_EMPTY_SCENE_ATTRIBUTES = "empty_scene_attributes"


@callback
def async_create_repair_issue_duplicate_ids(
    hass: HomeAssistant, duplicate_scenes: list[dict[str, Any]]
) -> None:
    """Create a repair issue for duplicate scene IDs."""
    scene_details = []
    for info in duplicate_scenes:
        scene_details.append(f"- {info['name']} (ID: {info['id']})")

    scene_list = "\n".join(scene_details)
    hass.async_create_task(
        async_create_issue(
            hass,
            DOMAIN,
            REPAIR_DUPLICATE_SCENE_IDS,
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="duplicate_scene_ids",
            translation_placeholders={
                "scene_count": str(len(duplicate_scenes)),
                "scene_list": scene_list,
            },
        )
    )


@callback
def async_create_repair_issue_empty_attributes(
    hass: HomeAssistant, affected_scenes: list[dict[str, Any]]
) -> None:
    """Create a repair issue for scenes with empty attributes."""
    scene_details = []
    for info in affected_scenes:
        scene_details.append(
            f"- {info['name']} has {info['empty_count']} empty attributes"
        )

    scene_list = "\n".join(scene_details)
    hass.async_create_task(
        async_create_issue(
            hass,
            DOMAIN,
            REPAIR_EMPTY_SCENE_ATTRIBUTES,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="empty_scene_attributes",
            translation_placeholders={
                "scene_count": str(len(affected_scenes)),
                "scene_list": scene_list,
            },
        )
    )


def detect_duplicate_scene_ids(scene_confs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect scenes with duplicate IDs."""
    id_count: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for scene in scene_confs:
        scene_id = scene.get("id", "")
        scene_name = scene.get("name", "Unknown")
        id_count[scene_id].append({"name": scene_name, "id": scene_id})

    duplicates: list[dict[str, Any]] = []
    for scenes in id_count.values():
        if len(scenes) > 1:
            duplicates.extend(scenes)

    return duplicates


def detect_empty_scene_attributes(scene_confs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect scenes with empty or None attributes."""
    affected_scenes: list[dict[str, Any]] = []
    for scene in scene_confs:
        empty_count = 0
        entities: dict[str, dict[str, Any]] = scene.get("entities", {})
        for entity_data in entities.values():
            for value in entity_data.values():
                if value is None or value == "":
                    empty_count += 1
        if empty_count:
            affected_scenes.append(
                {
                    "name": scene.get("name", "Unknown"),
                    "id": scene.get("id", ""),
                    "empty_count": empty_count,
                }
            )
    return affected_scenes


def check_for_repair_issues(hass: HomeAssistant, scene_confs: list[dict[str, Any]]) -> None:
    """Create repair issues based on the scene configuration."""
    duplicate_scenes = detect_duplicate_scene_ids(scene_confs)
    if duplicate_scenes:
        _LOGGER.warning("Found %d scenes with duplicate IDs", len(duplicate_scenes))
        async_create_repair_issue_duplicate_ids(hass, duplicate_scenes)

    empty_attr_scenes = detect_empty_scene_attributes(scene_confs)
    if empty_attr_scenes:
        _LOGGER.warning("Found %d scenes with empty attributes", len(empty_attr_scenes))
        async_create_repair_issue_empty_attributes(hass, empty_attr_scenes)


class StatefulScenesRepairFlow(RepairsFlow):
    """Handler for repairing issues."""

    def __init__(self, scene_path: str, repair_type: str) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self._scene_path = scene_path
        self._repair_type = repair_type

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Confirm repair action."""
        if user_input is not None:
            from .scene_repair_service import (
                async_fix_duplicate_scene_ids,
                async_cleanup_empty_attributes,
            )

            if self._repair_type == REPAIR_DUPLICATE_SCENE_IDS:
                await async_fix_duplicate_scene_ids(self.hass, self._scene_path)
            elif self._repair_type == REPAIR_EMPTY_SCENE_ATTRIBUTES:
                await async_cleanup_empty_attributes(self.hass, self._scene_path)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.handler.translation_placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Return a repair flow for an issue."""
    scene_path = data.get("scene_path") if data else None
    if issue_id == REPAIR_DUPLICATE_SCENE_IDS:
        return StatefulScenesRepairFlow(scene_path, REPAIR_DUPLICATE_SCENE_IDS)
    if issue_id == REPAIR_EMPTY_SCENE_ATTRIBUTES:
        return StatefulScenesRepairFlow(scene_path, REPAIR_EMPTY_SCENE_ATTRIBUTES)
    raise ValueError(f"Unknown repair issue {issue_id}")


def async_register_repairs(hass: HomeAssistant, scene_path: str) -> None:
    """Register fix flow with Home Assistant."""
    async_register(hass, DOMAIN, async_create_fix_flow)

