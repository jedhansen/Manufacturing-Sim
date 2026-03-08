"""
critical_path.py — Forward / backward pass CPM on per-part event traces.

_build_task_graph() – convert a PartLog's station_events into a DAG of
                      {id, name, duration, predecessors}.
forward_pass()      – earliest-start / earliest-finish for every task.
backward_pass()     – latest-start / latest-finish (from project end).
find_critical_path()– return the list of station names with zero float
                      and the total critical-path duration.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from sim_engine.monitors import PartLog


# ── Task-graph construction ─────────────────────────────────────────
def _build_task_graph(part_log: PartLog) -> List[Dict]:
    """
    Turn the station_events list from a single PartLog into a list of
    task dicts suitable for CPM forward/backward passes.

    Each task covers queue-wait + processing time at one station.
    """
    tasks: List[Dict] = []
    for i, ev in enumerate(part_log.station_events):
        tasks.append({
            "id": i,
            "name": ev["station"],
            "duration": ev["end_proc"] - ev["enter_queue"],
            "pred": [i - 1] if i > 0 else [],
        })

    # Append final assembly as the terminal node
    if part_log.final_assembly_end > 0:
        tasks.append({
            "id": len(tasks),
            "name": "FinalAssembly",
            "duration": (
                part_log.final_assembly_end - part_log.final_assembly_start
            ),
            "pred": [len(tasks) - 1],
        })
    return tasks


# ── Forward pass (ES / EF) ─────────────────────────────────────────
def forward_pass(
    tasks: List[Dict],
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """Return (earliest_start, earliest_finish) dicts keyed by task id."""
    es: Dict[int, float] = {t["id"]: 0.0 for t in tasks}
    ef: Dict[int, float] = {t["id"]: 0.0 for t in tasks}
    for t in tasks:
        if t["pred"]:
            es[t["id"]] = max(ef[p] for p in t["pred"])
        ef[t["id"]] = es[t["id"]] + t["duration"]
    return es, ef


# ── Backward pass (LS / LF) ────────────────────────────────────────
def backward_pass(
    tasks: List[Dict],
    ef: Dict[int, float],
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """Return (latest_start, latest_finish) dicts keyed by task id."""
    project_end = max(ef.values())
    lf: Dict[int, float] = {t["id"]: project_end for t in tasks}
    ls: Dict[int, float] = {t["id"]: project_end for t in tasks}
    for t in reversed(tasks):
        successors = [s for s in tasks if t["id"] in s["pred"]]
        if successors:
            lf[t["id"]] = min(ls[s["id"]] for s in successors)
        ls[t["id"]] = lf[t["id"]] - t["duration"]
    return ls, lf


# ── Public API ──────────────────────────────────────────────────────
def find_critical_path(
    part_log: PartLog,
) -> Tuple[List[str], float]:
    """
    Compute the critical path for a single part's journey.

    Returns
    -------
    critical_stations : list[str]
        Station names on the critical path (zero total float).
    duration : float
        Total critical-path duration in sim minutes.
    """
    tasks = _build_task_graph(part_log)
    if not tasks:
        return [], 0.0

    es, ef = forward_pass(tasks)
    ls, lf = backward_pass(tasks, ef)

    critical = [
        t["name"] for t in tasks
        if abs(es[t["id"]] - ls[t["id"]]) < 1e-9
    ]
    return critical, max(ef.values())
