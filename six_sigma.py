"""
six_sigma.py — Process capability indices and DMAIC helpers.

cp()                – process capability (spread vs spec width)
cpk()               – centred process capability
sigma_level()       – approximate sigma level from Cpk
throughput_samples() – extract end-to-end cycle times from part logs
"""

from __future__ import annotations

import numpy as np

from sim_engine.monitors import Monitor


def cp(data: np.ndarray, usl: float, lsl: float) -> float:
    """Process capability Cp = (USL − LSL) / 6σ."""
    sigma = float(np.std(data, ddof=1))
    return (usl - lsl) / (6.0 * sigma) if sigma > 0 else float("inf")


def cpk(data: np.ndarray, usl: float, lsl: float) -> float:
    """Centred process capability Cpk = min(CPU, CPL)."""
    mu = float(np.mean(data))
    sigma = float(np.std(data, ddof=1))
    if sigma == 0:
        return float("inf")
    return min((usl - mu) / (3.0 * sigma), (mu - lsl) / (3.0 * sigma))


def sigma_level(cpk_val: float) -> float:
    """Rough sigma level ≈ 3 × Cpk."""
    return cpk_val * 3.0


def throughput_samples(monitor: Monitor) -> np.ndarray:
    """
    Extract end-to-end cycle times (entry to exit) for every part
    that has at least one station event.
    """
    cts: list[float] = []
    for pl in monitor.part_logs:
        if pl.station_events:
            start = pl.station_events[0]["enter_queue"]
            end = (
                pl.final_assembly_end
                if pl.final_assembly_end > 0
                else pl.station_events[-1]["end_proc"]
            )
            cts.append(end - start)
    return np.array(cts)
