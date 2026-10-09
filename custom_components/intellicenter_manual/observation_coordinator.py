"""Read-only fanout of native observations to manual HA entities.

This module never dispatches equipment commands. Registration/unregistration
are explicit so unloading cannot leave stale callbacks behind.
"""
from __future__ import annotations
from collections.abc import Callable
import asyncio
import threading
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
        self._listeners.add(listener)
        listener(self.transport.read_observation())
        return lambda: self._listeners.discard(listener)

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("observation fanout closed")
        self.transport.set_observation_callback(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        if threading.get_ident() != self._loop_thread:
            self._loop.call_soon_threadsafe(self.refresh)
            return
        if self._closed:
            return
        observation = self.transport.read_observation()
        for listener in tuple(self._listeners):
            listener(observation)

    def close(self) -> None:
        self._closed = True
        self.transport.set_observation_callback(None)
        self._listeners.clear()
