"""
resources.py — SimPy Resource and Store wrappers.

MonitoredStore  – a simpy.Store with a convenience `.level` property so
                  the monitor can sample queue depth without reaching
                  into internals.

StationResource – wraps a PreemptiveResource with autonomous
                  failure / repair behaviour (exponential MTTF & MTTR).
"""

from __future__ import annotations

import random

import simpy


# ── Queue with observable depth ─────────────────────────────────────
class MonitoredStore(simpy.Store):
    """simpy.Store subclass that exposes current queue depth."""

    @property
    def level(self) -> int:
        return len(self.items)


# ── Station with stochastic breakdowns ─────────────────────────────
class StationResource:
    """
    A single workstation backed by a PreemptiveResource (capacity 1).

    If *mttf* > 0 the station will randomly break; the active job is
    interrupted and resumes after a repair whose duration is drawn from
    Exp(1/mttr).
    """

    def __init__(
        self,
        env: simpy.Environment,
        name: str,
        mttf: float,
        mttr: float,
    ) -> None:
        self.env = env
        self.name = name
        self.resource = simpy.PreemptiveResource(env, capacity=1)
        self.mttf = mttf
        self.mttr = mttr
        self.broken: bool = False
        self.total_downtime: float = 0.0
        self._downtime_start: float | None = None

        # Kick off the autonomous failure loop
        if mttf and mttf > 0:
            env.process(self._fail_loop())

    # ── internal ────────────────────────────────────────────────────
    def _fail_loop(self):
        """Randomly trigger failures at Exp(1/mttf) intervals."""
        while True:
            yield self.env.timeout(random.expovariate(1.0 / self.mttf))
            if not self.broken:
                self.broken = True
                self._downtime_start = self.env.now
                # Interrupt whoever is currently using the resource
                if self.resource.users:
                    # SimPy 4: users list contains PriorityRequest objects;
                    # the owning process is on .proc
                    self.resource.users[0].proc.interrupt(cause="failure")

    def repair(self):
        """Generator: repair takes Exp(1/mttr) minutes."""
        yield self.env.timeout(random.expovariate(1.0 / self.mttr))
        self.broken = False
        if self._downtime_start is not None:
            self.total_downtime += self.env.now - self._downtime_start
            self._downtime_start = None
