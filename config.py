"""
config.py — All tuneable simulation parameters as frozen dataclasses.

Each LineConfig describes one parallel assembly line (stations, cycle-time
distribution, queue limits, failure/repair behaviour).  SimConfig bundles
them together with global settings (shift length, Six Sigma specs, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# ── Per-line configuration ──────────────────────────────────────────
@dataclass
class LineConfig:
    """Parameters for a single parallel assembly line."""

    name: str
    num_stations: int = 4

    # Cycle-time distribution: "exponential" | "triangular"
    cycle_time_dist: str = "exponential"
    cycle_time_params: Dict = field(
        default_factory=lambda: {"mean": 5.0}
    )

    queue_capacity: int = 20          # max WIP between adjacent stations
    mttf: float = 300.0               # mean-time-to-failure  (minutes)
    mttr: float = 30.0                # mean-time-to-repair   (minutes)


# ── Global simulation configuration ────────────────────────────────
@dataclass
class SimConfig:
    """Top-level simulation parameters."""

    random_seed: int = 42
    sim_time: float = 480.0           # minutes — one 8-hour shift

    num_lines: int = 3
    lines: List[LineConfig] = field(default_factory=lambda: [
        LineConfig(
            name="Fuselage",
            num_stations=4,
            cycle_time_params={"mean": 6.0},
            queue_capacity=15,
        ),
        LineConfig(
            name="Wing",
            num_stations=3,
            cycle_time_params={"mean": 5.0},
            queue_capacity=20,
        ),
        LineConfig(
            name="Tail",
            num_stations=3,
            cycle_time_dist="triangular",
            cycle_time_params={"low": 3.0, "mode": 4.5, "high": 7.0},
            queue_capacity=10,
        ),
    ])

    # Final assembly station
    final_assembly_time_mean: float = 10.0
    final_assembly_capacity: int = 1
    final_queue_capacity: int = 30

    # Six Sigma specification limits
    spec_target: float = 5.0
    spec_usl: float = 7.0            # upper spec limit
    spec_lsl: float = 3.0            # lower spec limit

    # Monitoring sample interval (minutes)
    monitor_interval: float = 1.0
