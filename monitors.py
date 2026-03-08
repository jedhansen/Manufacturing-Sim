"""
monitors.py — Live queue-depth and utilisation recorders.

PartLog   – per-part event trace (station enter/start/end times) used
            downstream for critical-path analysis and throughput stats.

Monitor   – periodic sampler that snapshots every registered station
            and buffer at a configurable interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import simpy


# ── Per-part event log ──────────────────────────────────────────────
@dataclass
class PartLog:
    """Collects timing events for one part as it flows through the system."""

    part_id: int
    line: str
    station_events: List[Dict[str, Any]] = field(default_factory=list)
    final_assembly_start: float = 0.0
    final_assembly_end: float = 0.0


# ── Periodic monitor ───────────────────────────────────────────────
class Monitor:
    """
    A SimPy process that samples registered stations and buffers at
    fixed intervals, building time-series logs for post-sim analysis.
    """

    def __init__(self, env: simpy.Environment, interval: float = 1.0) -> None:
        self.env = env
        self.interval = interval

        # Time-series data
        self.timestamps: List[float] = []
        self.queue_log: Dict[str, List[float]] = {}
        self.util_log: Dict[str, List[float]] = {}

        # Per-part traces
        self.part_logs: List[PartLog] = []

        # Internal registries
        self._stations: Dict[str, Any] = {}
        self._buffers: Dict[str, Any] = {}

    # ── registration ────────────────────────────────────────────────
    def register_station(self, name: str, station_resource) -> None:
        """Register a StationResource (or duck-typed equivalent)."""
        self._stations[name] = station_resource
        self.queue_log[name] = []
        self.util_log[name] = []

    def register_buffer(self, name: str, store) -> None:
        """Register a MonitoredStore buffer."""
        self._buffers[name] = store
        self.queue_log[name] = []

    # ── SimPy process ───────────────────────────────────────────────
    def run(self):
        """Infinite sampling loop — started via env.process(monitor.run())."""
        while True:
            self.timestamps.append(self.env.now)

            for name, st in self._stations.items():
                busy = st.resource.count > 0 and not st.broken
                self.util_log[name].append(1.0 if busy else 0.0)
                self.queue_log[name].append(len(st.resource.queue))

            for name, buf in self._buffers.items():
                self.queue_log[name].append(buf.level)

            yield self.env.timeout(self.interval)
