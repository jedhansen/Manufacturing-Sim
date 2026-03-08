"""
app.py — Streamlit entry-point for the Manufacturing DES Simulator.

Run with:   streamlit run app.py

Two top-level modes:
  1. **Batch Simulation** — run a full shift, then explore bottlenecks,
     critical path, and Six Sigma analytics.
  2. **Live Stepping** — advance the sim in user-controlled time
     increments, see bottlenecks form in real time, and apply
     corrective actions (repair, add capacity, speed up) to meet demand.
"""

import sys
import os

# Ensure project root is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import numpy as np
import pandas as pd

from config import SimConfig, LineConfig
from sim_engine.environment import ManufacturingSim, SteppableSim
from sim_engine.interventions import (
    add_final_assembly_capacity,
    add_station_capacity,
    expand_buffer,
    force_repair,
    reduce_cycle_time,
)
from analytics.bottleneck import (
    bottleneck_heatmap_data,
    compute_avg_wip,
    compute_utilisation,
)
from analytics.critical_path import find_critical_path
from analytics.six_sigma import cp, cpk, sigma_level, throughput_samples
from viz.plots import (
    critical_path_gantt,
    live_queue_area,
    live_snapshot_bar,
    live_utilisation_gauge,
    throughput_histogram,
    utilisation_bar,
    wip_heatmap,
)


# ════════════════════════════════════════════════════════════════════
#  Page config
# ════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Mfg DES Simulator",
    page_icon="🏭",
    layout="wide",
)
st.title("Discrete-Event Manufacturing Simulator")
st.caption("SimPy 4 · Plotly · Six Sigma DMAIC · Aerospace parts line")


# ════════════════════════════════════════════════════════════════════
#  Sidebar — shared configuration
# ════════════════════════════════════════════════════════════════════
st.sidebar.header("Simulation Parameters")
sim_time = st.sidebar.slider("Shift length (min)", 60, 960, 480, 30)
seed = st.sidebar.number_input("Random seed", value=42, step=1)

st.sidebar.header("Six Sigma Specs")
usl = st.sidebar.slider("USL (min)", 4.0, 15.0, 7.0, 0.5)
lsl = st.sidebar.slider("LSL (min)", 0.5, 6.0, 3.0, 0.5)

st.sidebar.header("Line Configuration")
num_lines = st.sidebar.selectbox("Parallel lines", [2, 3, 4, 5], index=1)

line_cfgs: list[LineConfig] = []
for i in range(num_lines):
    with st.sidebar.expander(f"Line {i + 1}", expanded=(i == 0)):
        name = st.text_input("Name", f"Line_{i + 1}", key=f"ln{i}")
        dist = st.selectbox("Distribution", ["exponential", "triangular"],
                            key=f"d{i}")
        if dist == "exponential":
            mean_ct = st.slider("Mean cycle time (min)", 1.0, 15.0, 5.0,
                                key=f"m{i}")
            params = {"mean": mean_ct}
        else:
            lo = st.slider("Low", 1.0, 10.0, 3.0, key=f"lo{i}")
            md = st.slider("Mode", 1.0, 10.0, 5.0, key=f"md{i}")
            hi = st.slider("High", 1.0, 15.0, 8.0, key=f"hi{i}")
            params = {"low": lo, "mode": md, "high": hi}
        ns = st.slider("Stations", 2, 8, 4, key=f"ns{i}")
        qc = st.slider("Queue capacity", 5, 50, 20, key=f"qc{i}")
        mttf = st.slider("MTTF (min)", 50.0, 1000.0, 300.0, key=f"mttf{i}")
        mttr = st.slider("MTTR (min)", 5.0, 120.0, 30.0, key=f"mttr{i}")
        line_cfgs.append(LineConfig(
            name=name, num_stations=ns,
            cycle_time_dist=dist, cycle_time_params=params,
            queue_capacity=qc, mttf=mttf, mttr=mttr,
        ))

st.sidebar.markdown("---")
st.sidebar.header("Demand Target")
demand_target = st.sidebar.number_input(
    "Target units this shift", value=30, min_value=1, step=1,
    help="Used in Live mode to track whether you're on pace.",
)


def _build_cfg() -> SimConfig:
    return SimConfig(
        random_seed=int(seed), sim_time=float(sim_time),
        num_lines=num_lines, lines=line_cfgs,
        spec_usl=usl, spec_lsl=lsl,
    )


# ════════════════════════════════════════════════════════════════════
#  Mode selector
# ════════════════════════════════════════════════════════════════════
mode = st.radio(
    "Simulation mode",
    ["Batch (run full shift)", "Live Stepping (interactive)"],
    horizontal=True,
)


# ════════════════════════════════════════════════════════════════════
#  MODE 1 — Batch simulation
# ════════════════════════════════════════════════════════════════════
if mode == "Batch (run full shift)":
    if st.button("Run Simulation", type="primary"):
        cfg = _build_cfg()
        with st.spinner("Simulating…"):
            sim = ManufacturingSim(cfg)
            mon = sim.run()

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Bottlenecks", "Critical Path", "Six Sigma / DMAIC",
             "Raw Metrics"])

        # ── Bottlenecks ─────────────────────────────────────────────
        with tab1:
            util = compute_utilisation(mon)
            st.plotly_chart(utilisation_bar(util), use_container_width=True)

            names, ts, z = bottleneck_heatmap_data(mon)
            st.plotly_chart(wip_heatmap(names, ts, z),
                            use_container_width=True)

            wip = compute_avg_wip(mon)
            st.dataframe(pd.DataFrame({
                "Location": list(wip.keys()),
                "Avg Queue Depth": [round(v, 2) for v in wip.values()],
            }))

        # ── Critical path ───────────────────────────────────────────
        with tab2:
            completed = [
                p for p in mon.part_logs if p.final_assembly_end > 0
            ]
            if completed:
                sample = completed[-1]
                cp_nodes, cp_dur = find_critical_path(sample)
                st.metric("Critical-Path Duration", f"{cp_dur:.1f} min")
                st.write("Stations on critical path:", cp_nodes)
                st.plotly_chart(
                    critical_path_gantt(sample), use_container_width=True,
                )
            else:
                st.info("No parts completed final assembly yet.")

        # ── Six Sigma / DMAIC ───────────────────────────────────────
        with tab3:
            cts = throughput_samples(mon)
            if len(cts) > 1:
                c1, c2, c3 = st.columns(3)
                cp_val = cp(cts, cfg.spec_usl, cfg.spec_lsl)
                cpk_val = cpk(cts, cfg.spec_usl, cfg.spec_lsl)
                c1.metric("Cp", f"{cp_val:.3f}")
                c2.metric("Cpk", f"{cpk_val:.3f}")
                c3.metric("Sigma Level", f"{sigma_level(cpk_val):.1f}")
                st.plotly_chart(
                    throughput_histogram(cts, cfg.spec_usl, cfg.spec_lsl,
                                        "Before"),
                    use_container_width=True,
                )
                st.markdown("---")
                st.subheader("What-If: Reduce Variation")
                reduce = st.slider("Reduce σ by (%)", 0, 60, 0, 5)
                shift = st.slider("Shift mean (min)", -3.0, 3.0, 0.0, 0.25)
                improved = cts * (1 - reduce / 100) + shift
                cp2 = cp(improved, cfg.spec_usl, cfg.spec_lsl)
                cpk2 = cpk(improved, cfg.spec_usl, cfg.spec_lsl)
                a1, a2, a3 = st.columns(3)
                a1.metric("Cp (after)", f"{cp2:.3f}",
                          delta=f"{cp2 - cp_val:+.3f}")
                a2.metric("Cpk (after)", f"{cpk2:.3f}",
                          delta=f"{cpk2 - cpk_val:+.3f}")
                a3.metric("Sigma", f"{sigma_level(cpk2):.1f}",
                          delta=f"{sigma_level(cpk2) - sigma_level(cpk_val):+.1f}")
                st.plotly_chart(
                    throughput_histogram(improved, cfg.spec_usl,
                                        cfg.spec_lsl, "After"),
                    use_container_width=True,
                )
            else:
                st.info("Not enough data to compute capability indices.")

        # ── Raw metrics ─────────────────────────────────────────────
        with tab4:
            rows = []
            for pl in mon.part_logs:
                for ev in pl.station_events:
                    rows.append({"part": pl.part_id, "line": pl.line, **ev})
            if rows:
                st.dataframe(pd.DataFrame(rows))
            else:
                st.info("No part events recorded.")


# ════════════════════════════════════════════════════════════════════
#  MODE 2 — Live stepping with interventions
# ════════════════════════════════════════════════════════════════════
else:
    # ── Session-state initialisation ────────────────────────────────
    if "live_sim" not in st.session_state:
        st.session_state.live_sim = None
        st.session_state.live_log = []  # action log

    col_start, col_step = st.columns([1, 1])

    with col_start:
        if st.button("Initialise New Simulation", type="primary"):
            cfg = _build_cfg()
            st.session_state.live_sim = SteppableSim(cfg)
            st.session_state.live_log = []
            st.success("Simulation initialised. Use the step button to advance time.")

    sim: SteppableSim | None = st.session_state.live_sim

    if sim is None:
        st.info("Click **Initialise New Simulation** to begin.")
        st.stop()

    # ── Step controls ───────────────────────────────────────────────
    with col_step:
        dt = st.number_input("Step size (min)", 5.0, 120.0, 15.0, 5.0)
        step_clicked = st.button(
            "⏩ Step Forward",
            disabled=sim.finished,
            type="secondary",
        )

    if step_clicked and not sim.finished:
        snap = sim.step(dt)
        st.session_state.live_log.append(
            f"t={snap['time']:.0f}: stepped +{dt:.0f} min "
            f"| {snap['completed_units']} units done "
            f"| {len(snap['broken_stations'])} broken"
        )

    # ── Dashboard header ────────────────────────────────────────────
    snaps = sim.snapshots
    if not snaps:
        st.info("Press **Step Forward** to advance the simulation clock.")
        st.stop()

    latest = snaps[-1]

    st.markdown("---")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Sim Time", f"{latest['time']:.0f} / {sim.cfg.sim_time:.0f} min")
    h2.metric("Units Completed", latest["completed_units"])
    pace = (latest["completed_units"] / latest["time"] * sim.cfg.sim_time
            if latest["time"] > 0 else 0)
    h3.metric("Projected Output", f"{pace:.0f}",
              delta=f"{pace - demand_target:+.0f} vs target")
    h4.metric("Broken Stations", len(latest["broken_stations"]))

    # ── Progress bar ────────────────────────────────────────────────
    st.progress(min(latest["time"] / sim.cfg.sim_time, 1.0))

    # ── Bottleneck visualisation ────────────────────────────────────
    st.subheader("Current Queue Fill")
    st.plotly_chart(
        live_snapshot_bar(latest["queue_depths"], latest["capacities"]),
        use_container_width=True,
    )

    # Queue trend over steps
    if len(snaps) > 1:
        ts = [s["time"] for s in snaps]
        q_hist = {}
        for name in latest["queue_depths"]:
            q_hist[name] = [s["queue_depths"].get(name, 0) for s in snaps]
        st.plotly_chart(
            live_queue_area(ts, q_hist),
            use_container_width=True,
        )

    # Station utilisation gauges
    st.subheader("Station Utilisation (recent window)")
    gauge_cols = st.columns(min(len(latest["station_util"]), 6))
    for idx, (sname, sutil) in enumerate(latest["station_util"].items()):
        with gauge_cols[idx % len(gauge_cols)]:
            st.plotly_chart(
                live_utilisation_gauge(sname, sutil),
                use_container_width=True,
            )

    # ── Alerts ──────────────────────────────────────────────────────
    st.subheader("Alerts")
    alerts = []
    for bname, depth in latest["queue_depths"].items():
        cap = latest["capacities"].get(bname, 1)
        if cap > 0 and depth / cap > 0.80:
            alerts.append(f"⚠️  **{bname}** is at {depth}/{cap} "
                          f"({depth/cap*100:.0f} % full)")
    for broken in latest["broken_stations"]:
        alerts.append(f"🔴  **{broken}** is BROKEN — needs repair")

    if pace < demand_target and latest["time"] > 0:
        alerts.append(
            f"📉  Projected output ({pace:.0f}) is below target "
            f"({demand_target}). Take action to increase throughput."
        )

    if alerts:
        for a in alerts:
            st.markdown(a)
    else:
        st.success("All systems nominal — on pace to meet demand.")

    # ════════════════════════════════════════════════════════════════
    #  INTERVENTION PANEL
    # ════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("🔧 Take Action")
    st.caption(
        "Apply corrective actions below. Changes take effect on the next step."
    )

    act_col1, act_col2 = st.columns(2)

    # ── Column 1: station-level actions ─────────────────────────────
    with act_col1:
        station_names = list(sim.stations.keys())

        st.markdown("**Repair a broken station**")
        repair_target = st.selectbox("Station to repair", station_names,
                                     key="repair_sel")
        if st.button("Force Repair", key="btn_repair"):
            msg = force_repair(sim.stations[repair_target])
            st.session_state.live_log.append(msg)
            st.success(msg)

        st.markdown("**Add parallel capacity**")
        cap_target = st.selectbox("Station", station_names, key="cap_sel")
        if st.button("Add +1 Worker", key="btn_cap"):
            msg = add_station_capacity(sim.stations[cap_target])
            st.session_state.live_log.append(msg)
            st.success(msg)

        st.markdown("**Add final-assembly capacity**")
        if st.button("Add +1 Assembly Bay", key="btn_asm"):
            msg = add_final_assembly_capacity(sim.asm_resource)
            st.session_state.live_log.append(msg)
            st.success(msg)

    # ── Column 2: line / buffer actions ─────────────────────────────
    with act_col2:
        line_names = list(sim.line_cfgs_by_name.keys())

        st.markdown("**Speed up a line (reduce cycle time)**")
        speed_line = st.selectbox("Line", line_names, key="speed_sel")
        speed_pct = st.slider("Reduction %", 5, 30, 10, 5, key="speed_pct")
        if st.button("Apply Speed-Up", key="btn_speed"):
            lc = sim.line_cfgs_by_name[speed_line]
            msg = reduce_cycle_time(lc, speed_pct)
            st.session_state.live_log.append(msg)
            st.success(msg)

        st.markdown("**Expand a buffer**")
        buf_names = list(sim.buffers.keys())
        buf_target = st.selectbox("Buffer", buf_names, key="buf_sel")
        buf_extra = st.slider("Extra capacity", 5, 50, 10, 5, key="buf_extra")
        if st.button("Expand Buffer", key="btn_buf"):
            msg = expand_buffer(sim.buffers[buf_target], buf_extra)
            st.session_state.live_log.append(msg)
            st.success(msg)

    # ── Action log ──────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("Action Log", expanded=False):
        for entry in reversed(st.session_state.live_log):
            st.text(entry)
