"""
environment.py — High-level SimPy Environment wrappers.

ManufacturingSim  – build-and-run-to-completion (batch mode).
SteppableSim      – build once, then advance in user-controlled time
                    steps so the Streamlit live dashboard can snapshot
                    state between steps and the user can intervene.

Both classes share the same _build() wiring logic via a common base.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

import simpy

from config import SimConfig
from sim_engine.monitors import Monitor
from sim_engine.processes import (
    final_assembly,
    part_source,
    station_process,
)
from sim_engine.resources import MonitoredStore, StationResource


# ════════════════════════════════════════════════════════════════════
#  Shared wiring logic
# ════════════════════════════════════════════════════════════════════

class _SimBase:
    """Common factory that wires lines → buffers → stations → assembly."""

    cfg: SimConfig
    env: simpy.Environment
    monitor: Monitor

    # Exposed for the live dashboard / interventions
    stations: Dict[str, StationResource]
    buffers: Dict[str, MonitoredStore]
    line_cfgs_by_name: Dict[str, Any]
    asm_resource: simpy.Resource | None

    def _build(self) -> None:
        self.stations = {}
        self.buffers = {}
        self.line_cfgs_by_name = {}
        line_out_stores: List[MonitoredStore] = []
        part_counter = [0]

        for lc in self.cfg.lines:
            self.line_cfgs_by_name[lc.name] = lc

            # Inter-station buffers (num_stations + 1)
            buf_list: List[MonitoredStore] = []
            for s in range(lc.num_stations + 1):
                buf = MonitoredStore(self.env, capacity=lc.queue_capacity)
                buf_name = f"{lc.name}_buf{s}"
                self.monitor.register_buffer(buf_name, buf)
                self.buffers[buf_name] = buf
                buf_list.append(buf)

            # Stations wired between consecutive buffers
            for s in range(lc.num_stations):
                st = StationResource(
                    self.env, f"{lc.name}_S{s}", lc.mttf, lc.mttr,
                )
                self.monitor.register_station(st.name, st)
                self.stations[st.name] = st
                self.env.process(station_process(
                    self.env, st,
                    lc.cycle_time_dist, lc.cycle_time_params,
                    buf_list[s], buf_list[s + 1], self.monitor,
                ))

            # Part source feeds the first buffer
            self.env.process(part_source(
                self.env, lc, buf_list[0], self.monitor, part_counter,
            ))
            line_out_stores.append(buf_list[-1])

        # Final assembly merge station
        self.asm_resource = simpy.Resource(
            self.env, capacity=self.cfg.final_assembly_capacity,
        )
        self.monitor.register_station(
            "FinalAssembly",
            type("_FA", (), {
                "resource": self.asm_resource, "broken": False,
            })(),
        )
        self.env.process(final_assembly(
            self.env, line_out_stores, self.asm_resource,
            self.cfg.final_assembly_time_mean, self.monitor,
        ))

        # Periodic monitor
        self.env.process(self.monitor.run())


# ════════════════════════════════════════════════════════════════════
#  Batch mode (run to completion)
# ════════════════════════════════════════════════════════════════════

class ManufacturingSim(_SimBase):
    """Build and run a full simulation in one shot."""

    def __init__(self, cfg: SimConfig) -> None:
        self.cfg = cfg
        random.seed(cfg.random_seed)
        self.env = simpy.Environment()
        self.monitor = Monitor(self.env, cfg.monitor_interval)
        self._build()

    def run(self) -> Monitor:
        self.env.run(until=self.cfg.sim_time)
        return self.monitor


# ════════════════════════════════════════════════════════════════════
#  Live-steppable mode (advance in user-controlled increments)
# ════════════════════════════════════════════════════════════════════

class SteppableSim(_SimBase):
    """
    Interactive simulation that advances in discrete time-steps.

    Usage
    -----
        sim = SteppableSim(cfg)
        while sim.current_time < cfg.sim_time:
            snapshot = sim.step(dt=15)   # advance 15 minutes
            # render snapshot in the dashboard
            # user applies interventions via sim.stations / sim.buffers
    """

    def __init__(self, cfg: SimConfig) -> None:
        self.cfg = cfg
        random.seed(cfg.random_seed)
        self.env = simpy.Environment()
        self.monitor = Monitor(self.env, cfg.monitor_interval)
        self._build()
        self._step_snapshots: List[Dict[str, Any]] = []

    # ── advance by dt minutes ───────────────────────────────────────
    def step(self, dt: float = 15.0) -> Dict[str, Any]:
        """
        Advance the simulation by *dt* minutes and return a snapshot
        dict with current queue depths, utilisation, broken stations,
        and throughput count.
        """
        target = min(self.env.now + dt, self.cfg.sim_time)
        self.env.run(until=target)
        snap = self._snapshot()
        self._step_snapshots.append(snap)
        return snap

    # ── current sim clock ───────────────────────────────────────────
    @property
    def current_time(self) -> float:
        return self.env.now

    @property
    def finished(self) -> bool:
        return self.env.now >= self.cfg.sim_time

    # ── internal snapshot builder ───────────────────────────────────
    def _snapshot(self) -> Dict[str, Any]:
        queue_depths: Dict[str, int] = {}
        capacities: Dict[str, int] = {}
        for name, buf in self.buffers.items():
            queue_depths[name] = buf.level
            capacities[name] = buf.capacity

        station_util: Dict[str, float] = {}
        broken_stations: List[str] = []
        for name, st in self.stations.items():
            vals = self.monitor.util_log.get(name, [])
            station_util[name] = float(sum(vals[-10:])) / max(len(vals[-10:]), 1)
            if st.broken:
                broken_stations.append(name)

        completed = sum(
            1 for p in self.monitor.part_logs if p.final_assembly_end > 0
        )

        return {
            "time": self.env.now,
            "queue_depths": queue_depths,
            "capacities": capacities,
            "station_util": station_util,
            "broken_stations": broken_stations,
            "completed_units": completed,
            "total_parts_started": len(self.monitor.part_logs),
        }

    # ── convenience: all snapshots so far ───────────────────────────
    @property
    def snapshots(self) -> List[Dict[str, Any]]:
        return list(self._step_snapshots)
