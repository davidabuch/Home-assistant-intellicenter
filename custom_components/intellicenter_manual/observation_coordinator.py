"""Read-only fanout of native observations to manual HA entities.

This module never dispatches equipment commands. Registration/unregistration
are explicit so unloading cannot leave stale callbacks behind.
"""
from __future__ import annotations
from collections.abc import Callable
import asyncio
import threading
import logging

_LOGGER = logging.getLogger(__name__)
from .observation import ReadObservation

class ObservationFanout:
    def __init__(self, transport, loop: asyncio.AbstractEventLoop):
        self.transport = transport
        self._loop = loop
        self._loop_thread = threading.get_ident()
        self._listeners: set[Callable[[ReadObservation], None]] = set()
        self._closed = False

    def subscribe(self, listener: Callable[[ReadObservation], None]) -> Callable[[], None]:
        if self._closed:
            raise RuntimeError("observation fanout closed")
        # A failed initial snapshot must not leave a ghost subscriber behind.
        observation = self.transport.read_observation()
        listener(observation)
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("observation fanout closed")
        self.transport.set_observation_callback(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        # A late transport callback after unload must not schedule work on a
        # stopped HA event loop (or read stale native observations).
        if self._closed:
            return
        if threading.get_ident() != self._loop_thread:
            self._loop.call_soon_threadsafe(self.refresh)
            return
        observation = self.transport.read_observation()
        for listener in tuple(self._listeners):
            try:
                listener(observation)
            except Exception:
                _LOGGER.exception("Native observation listener failed; continuing other entities")

    def close(self) -> None:
        self._closed = True
        self.transport.set_observation_callback(None)
        self._listeners.clear()
