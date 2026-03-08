"""
bottleneck.py — WIP and utilisation analytics for bottleneck detection.

compute_utilisation()     – average busy fraction per station
compute_avg_wip()         – average queue depth per buffer / station
bottleneck_heatmap_data() – 2-D matrix (location × time) of queue depths,
                            ready for Plotly Heatmap consumption
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from sim_engine.monitors import Monitor


def compute_utilisation(monitor: Monitor) -> Dict[str, float]:
    """Return {station_name: mean_utilisation} across the simulation."""
    return {
        name: float(np.mean(vals)) if vals else 0.0
        for name, vals in monitor.util_log.items()
    }


def compute_avg_wip(monitor: Monitor) -> Dict[str, float]:
    """Return {location_name: mean_queue_depth} for all monitored points."""
    return {
        name: float(np.mean(vals)) if vals else 0.0
        for name, vals in monitor.queue_log.items()
    }


def bottleneck_heatmap_data(
    monitor: Monitor,
) -> Tuple[List[str], List[float], List[List[float]]]:
    """
    Prepare a 2-D matrix for a WIP heatmap chart.

    Returns
    -------
    names : list[str]
        Y-axis labels (buffer / station names).
    timestamps : list[float]
        X-axis (sim minutes).
    z : list[list[float]]
        Queue depth matrix, rows = locations, cols = time steps.
    """
    names = sorted(monitor.queue_log.keys())
    z: List[List[Any]] = [monitor.queue_log[n] for n in names]

    # Align to the shortest series (Monitor may stop mid-interval)
    min_len = min((len(row) for row in z), default=0)
    z = [row[:min_len] for row in z]

    return names, monitor.timestamps[:min_len], z
