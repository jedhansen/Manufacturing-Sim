"""
interventions.py — Mid-simulation corrective actions for the live mode.

Each function mutates the running simulation state so that the *next*
step reflects the change.  These are the "levers" a user can pull when
they see a bottleneck forming in the live dashboard.

Supported interventions
-----------------------
force_repair()        – immediately repair a broken station
add_station_capacity() – add a parallel worker to a station
reduce_cycle_time()    – lower the mean cycle time (speed-up)
expand_buffer()        – increase a queue's max capacity
add_final_asm_capacity() – add a parallel worker to final assembly
"""

from __future__ import annotations

import simpy

from sim_engine.monitors import Monitor
from sim_engine.processes import station_process
from sim_engine.resources import MonitoredStore, StationResource


# ── Immediate repair ────────────────────────────────────────────────
def force_repair(station: StationResource) -> str:
    """
    Instantly clear the broken flag and credit downtime.
    Returns a human-readable confirmation string.
    """
    if not station.broken:
        return f"{station.name} is not broken — no action taken."
    station.broken = False
    if station._downtime_start is not None:
        station.total_downtime += station.env.now - station._downtime_start
        station._downtime_start = None
    return f"{station.name} repaired at t={station.env.now:.1f} min."


# ── Add parallel capacity to a station ──────────────────────────────
def add_station_capacity(station: StationResource) -> str:
    """
    Increase the station's resource capacity by 1 (simulates adding
    a parallel worker or machine).
    """
    station.resource._capacity += 1          # SimPy internal
    new_cap = station.resource.capacity
    return f"{station.name} capacity → {new_cap}."


# ── Speed up a station (reduce mean cycle time) ────────────────────
def reduce_cycle_time(
    line_cfg,
    reduction_pct: float = 10.0,
) -> str:
    """
    Lower the cycle-time parameters for a line by *reduction_pct* %.
    Affects all future draws; in-flight parts keep their original time.
    """
    factor = 1.0 - reduction_pct / 100.0
    if line_cfg.cycle_time_dist == "exponential":
        old = line_cfg.cycle_time_params["mean"]
        line_cfg.cycle_time_params["mean"] = round(old * factor, 3)
        return (
            f"{line_cfg.name}: mean cycle time "
            f"{old:.2f} → {line_cfg.cycle_time_params['mean']:.2f} min "
            f"(−{reduction_pct:.0f} %)."
        )
    elif line_cfg.cycle_time_dist == "triangular":
        for key in ("low", "mode", "high"):
            old = line_cfg.cycle_time_params[key]
            line_cfg.cycle_time_params[key] = round(old * factor, 3)
        return (
            f"{line_cfg.name}: triangular params reduced by "
            f"{reduction_pct:.0f} %."
        )
    return f"{line_cfg.name}: unknown dist — no change."


# ── Expand an inter-station buffer ──────────────────────────────────
def expand_buffer(store: MonitoredStore, extra: int = 10) -> str:
    """Increase a MonitoredStore's capacity."""
    old = store.capacity
    store._capacity += extra                  # simpy.Store internal
    return f"Buffer capacity {old} → {store.capacity}."


# ── Add final-assembly capacity ─────────────────────────────────────
def add_final_assembly_capacity(asm_resource: simpy.Resource) -> str:
    """Add one more worker/bay to the final assembly station."""
    asm_resource._capacity += 1
    return f"Final assembly capacity → {asm_resource.capacity}."
