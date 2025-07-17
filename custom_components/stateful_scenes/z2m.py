"""Zigbee2MQTT scene learning helpers."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from collections.abc import Callable

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class Z2MSceneLearner:
    """Minimal Zigbee2MQTT scene learner."""

    def __init__(self, hass: HomeAssistant, hub: Any) -> None:
        """Initialize helper with hass instance and hub."""
        self.hass = hass
        self.hub = hub
        self._unsubs: list[Callable[[], None]] = []

    async def start_learning(self) -> None:
        """Start listening to Zigbee2MQTT MQTT topics."""
        mqtt = self.hass.components.mqtt
        try:
            self._unsubs.append(
                await mqtt.async_subscribe(
                    "zigbee2mqtt/bridge/request/group/members/scene/+",
                    self._handle_scene_command,
                )
            )
            self._unsubs.append(
                await mqtt.async_subscribe(
                    "zigbee2mqtt/+", self._handle_device_state
                )
            )
            _LOGGER.debug("Started Zigbee2MQTT scene learning")
        except Exception as err:  # pragma: no cover - best effort
            _LOGGER.error("Failed to start Z2M learning: %s", err)

    async def stop_learning(self) -> None:
        """Cancel subscriptions."""
        while self._unsubs:
            unsub = self._unsubs.pop()
            try:
                unsub()
            except Exception as err:  # pragma: no cover - best effort
                _LOGGER.debug("Failed to unsubscribe: %s", err)
        _LOGGER.debug("Stopped Zigbee2MQTT scene learning")

    async def manual_learn_scene(self, group: str, scene: int) -> None:
        """Manually trigger a learning session."""
        await self._process_scene(group, scene)

    async def _handle_scene_command(self, msg) -> None:
        try:
            payload = json.loads(msg.payload)
        except Exception as err:  # pragma: no cover - best effort
            _LOGGER.error("Failed to parse Z2M message: %s", err)
            return
        group = payload.get("group")
        scene = payload.get("scene")
        await self._process_scene(group, scene)

    async def _handle_device_state(self, _msg) -> None:
        """Stub handler for device updates."""
        return

    async def _process_scene(self, group: str | None, scene: int | None) -> None:
        if not group or scene is None:
            return
        _LOGGER.info("Learning Z2M scene %s in group %s", scene, group)
        # Wait for devices to report new states
        await asyncio.sleep(self.hub.z2m_transition_time)
        # Placeholder for analysing changes
        # In a real implementation we would correlate device states here
        _LOGGER.debug("Finished learning Z2M scene %s:%s", group, scene)
