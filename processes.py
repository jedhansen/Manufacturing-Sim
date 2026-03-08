"""
processes.py — SimPy process generators for production lines.

cycle_time()      – draw a random cycle time from the configured
                    distribution (exponential or triangular).
part_source()     – infinite generator that creates new parts and
                    feeds them into the first buffer of a line.
station_process() – pulls parts from an input buffer, processes them
                    (with interruption/repair handling), and pushes
                    to the output buffer.
final_assembly()  – waits for one part from *every* line's output
                    buffer, then assembles.
"""

from __future__ import annotations

import random

import simpy

from sim_engine.monitors import Monitor, PartLog


# ── Random cycle-time draw ─────────────────────────────────────────
def cycle_time(dist: str, params: dict) -> float:
    """Return a random cycle time from the named distribution."""
    if dist == "exponential":
        return random.expovariate(1.0 / params["mean"])
    if dist == "triangular":
        return random.triangular(params["low"], params["high"], params["mode"])
    raise ValueError(f"Unknown distribution: {dist}")


# ── Part source (arrival generator) ────────────────────────────────
def part_source(
    env: simpy.Environment,
    line_cfg,
    buffer_in,
    monitor: Monitor,
    part_counter: list[int],
) -> None:
    """Generate parts at random inter-arrival times and enqueue them."""
    while True:
        ct = cycle_time(line_cfg.cycle_time_dist, line_cfg.cycle_time_params)
        yield env.timeout(ct)
        part_counter[0] += 1
        part_id = part_counter[0]
        log = PartLog(part_id=part_id, line=line_cfg.name)
        monitor.part_logs.append(log)
        yield buffer_in.put((part_id, log))


# ── Station processing (with breakdown handling) ───────────────────
def station_process(
    env: simpy.Environment,
    station,
    dist: str,
    params: dict,
    buffer_in,
    buffer_out,
    monitor: Monitor,
) -> None:
    """
    Pull a part from *buffer_in*, process it at *station*, then push
    to *buffer_out*.  If the station breaks mid-process the remaining
    work is resumed after repair.
    """
    while True:
        item = yield buffer_in.get()
        part_id, log = item
        enter_q = env.now

        done_in = cycle_time(dist, params)
        start = env.now                         # default if no preemption

        while done_in > 0:
            with station.resource.request(priority=0) as req:
                yield req
                start = env.now
                try:
                    yield env.timeout(done_in)
                    done_in = 0.0               # finished normally
                except simpy.Interrupt:
                    done_in -= env.now - start   # remaining work
                    # Wait for repair — may itself be interrupted by
                    # another failure event, so loop until not broken
                    while station.broken:
                        try:
                            yield env.process(station.repair())
                        except simpy.Interrupt:
                            pass  # re-check .broken flag

        log.station_events.append({
            "station": station.name,
            "enter_queue": enter_q,
            "start_proc": start,
            "end_proc": env.now,
        })
        yield buffer_out.put((part_id, log))


# ── Final assembly (merge from all lines) ──────────────────────────
def final_assembly(
    env: simpy.Environment,
    stores_from_lines: list,
    assembly_res: simpy.Resource,
    assembly_time_mean: float,
    monitor: Monitor,
) -> None:
    """
    Wait for exactly one part from each feeder line, then perform
    final assembly (exponential service time).
    """
    while True:
        # Collect one part per line (blocking)
        items = []
        for store in stores_from_lines:
            item = yield store.get()
            items.append(item)

        with assembly_res.request() as req:
            yield req
            start = env.now
            yield env.timeout(random.expovariate(1.0 / assembly_time_mean))

        for _, log in items:
            log.final_assembly_start = start
            log.final_assembly_end = env.now
