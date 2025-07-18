"""Repair services for Stateful Scenes."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import aiofiles
import aiofiles.os as aioos
import yaml
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .repairs import detect_duplicate_scene_ids, detect_empty_scene_attributes


_LOGGER = logging.getLogger(__name__)


async def _backup_file(path: str) -> str:
    """Create a timestamped backup of a file and return backup path."""
    directory = os.path.dirname(path)
    base = os.path.basename(path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(directory, f"{base}.backup_{timestamp}")
    try:
        async with aiofiles.open(path, encoding="utf-8") as src, aiofiles.open(
            backup_path, "w", encoding="utf-8"
        ) as dst:
            await dst.write(await src.read())
    except OSError as err:
        _LOGGER.error("Failed to create backup for %s: %s", path, err)
        raise
    return backup_path


async def async_fix_duplicate_scene_ids(hass: HomeAssistant, scene_path: str) -> None:
    """Fix duplicate scene IDs by generating unique ones."""
    async with aiofiles.open(scene_path, encoding="utf-8") as f:
        scenes = yaml.load(await f.read(), Loader=yaml.FullLoader)

    duplicates = detect_duplicate_scene_ids(scenes)
    if not duplicates:
        return

    backup = await _backup_file(scene_path)

    used_ids = set()
    for scene in scenes:
        scene_id = scene.get("id", "")
        if scene_id in used_ids:
            new_id = f"{scene_id}_{datetime.now().timestamp():.0f}"
            scene["id"] = new_id
        used_ids.add(scene["id"])

    async with aiofiles.open(scene_path, "w", encoding="utf-8") as f:
        await f.write(yaml.dump(scenes))

    try:
        async with aiofiles.open(scene_path, encoding="utf-8") as f_verify:
            yaml.load(await f_verify.read(), Loader=yaml.FullLoader)
    except yaml.YAMLError as err:
        _LOGGER.error("Repair produced invalid YAML: %s", err)
        await aioos.replace(backup, scene_path)
        raise

    hass.async_create_task(hass.config_entries.async_reload(DOMAIN))


async def async_cleanup_empty_attributes(hass: HomeAssistant, scene_path: str) -> None:
    """Remove empty attributes from scenes."""
    async with aiofiles.open(scene_path, encoding="utf-8") as f:
        scenes = yaml.load(await f.read(), Loader=yaml.FullLoader)

    affected = detect_empty_scene_attributes(scenes)
    if not affected:
        return

    backup = await _backup_file(scene_path)

    for scene in scenes:
        for _entity, attrs in list(scene.get("entities", {}).items()):
            for attr, value in list(attrs.items()):
                if value is None or value == "":
                    del attrs[attr]

    async with aiofiles.open(scene_path, "w", encoding="utf-8") as f:
        await f.write(yaml.dump(scenes))

    try:
        async with aiofiles.open(scene_path, encoding="utf-8") as f_verify:
            yaml.load(await f_verify.read(), Loader=yaml.FullLoader)
    except yaml.YAMLError as err:
        _LOGGER.error("Cleanup produced invalid YAML: %s", err)
        await aioos.replace(backup, scene_path)
        raise

    hass.async_create_task(hass.config_entries.async_reload(DOMAIN))


