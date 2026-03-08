"""
plots.py — All Plotly chart builders.

utilisation_bar()       – colour-coded bar chart (red > 85 %, yellow > 70 %)
wip_heatmap()           – time × location queue-depth heatmap
throughput_histogram()   – cycle-time distribution with USL/LSL lines
critical_path_gantt()   – Gantt chart for one part's station events
live_snapshot_bar()     – compact bar chart used in the live-stepping UI
live_queue_area()       – stacked-area of queue depths over stepped time
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from sim_engine.monitors import Monitor, PartLog


# ═══════════════════════  Batch-mode charts  ════════════════════════

def utilisation_bar(util_dict: Dict[str, float]) -> go.Figure:
    """Colour-coded utilisation bar chart (green / yellow / red)."""
    names = list(util_dict.keys())
    vals = [v * 100 for v in util_dict.values()]
    colors = [
        "#ef4444" if v > 85 else "#facc15" if v > 70 else "#22c55e"
        for v in vals
    ]
    fig = go.Figure(go.Bar(x=names, y=vals, marker_color=colors))
    fig.update_layout(
        title="Station Utilisation (%)",
        yaxis_range=[0, 100],
        template="plotly_white",
        height=380,
    )
    return fig


def wip_heatmap(
    names: List[str],
    timestamps: List[float],
    z: List[List[float]],
) -> go.Figure:
    """WIP queue-depth heatmap (Y = location, X = sim time)."""
    fig = go.Figure(go.Heatmap(
        z=z, x=timestamps, y=names,
        colorscale="YlOrRd",
        colorbar_title="Queue depth",
    ))
    fig.update_layout(
        title="WIP Queue Heatmap over Time",
        xaxis_title="Sim Time (min)",
        template="plotly_white",
        height=450,
    )
    return fig


def throughput_histogram(
    data: np.ndarray,
    usl: float,
    lsl: float,
    title: str = "Cycle-Time Distribution",
) -> go.Figure:
    """Cycle-time histogram with specification limit lines."""
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=data, nbinsx=30, name="Cycle Time",
        marker_color="#6366f1",
    ))
    fig.add_vline(x=usl, line_dash="dash", line_color="red",
                  annotation_text="USL")
    fig.add_vline(x=lsl, line_dash="dash", line_color="red",
                  annotation_text="LSL")
    fig.update_layout(
        title=title, xaxis_title="Minutes",
        template="plotly_white", height=380,
    )
    return fig


def critical_path_gantt(part_log: PartLog) -> go.Figure:
    """Gantt chart for one part's journey through the system."""
    rows: List[Dict[str, Any]] = []
    for ev in part_log.station_events:
        rows.append({
            "Task": ev["station"],
            "Start": ev["enter_queue"],
            "Finish": ev["end_proc"],
            "Type": "Processing",
        })
    if part_log.final_assembly_end > 0:
        rows.append({
            "Task": "FinalAssembly",
            "Start": part_log.final_assembly_start,
            "Finish": part_log.final_assembly_end,
            "Type": "Assembly",
        })
    df = pd.DataFrame(rows)
    fig = px.timeline(
        df, x_start="Start", x_end="Finish", y="Task", color="Type",
        title="Critical-Path Gantt (sample part)",
    )
    fig.update_layout(template="plotly_white", height=380)
    return fig


# ═══════════════════════  Live-mode charts  ═════════════════════════

def live_snapshot_bar(
    queue_depths: Dict[str, int],
    capacities: Dict[str, int],
) -> go.Figure:
    """
    Compact bar chart showing current queue fill % at each location.
    Bars turn red when a queue exceeds 80 % capacity.
    """
    names = list(queue_depths.keys())
    pcts = [
        (queue_depths[n] / capacities[n] * 100) if capacities.get(n, 0) > 0 else 0
        for n in names
    ]
    colors = ["#ef4444" if p > 80 else "#facc15" if p > 60 else "#22c55e" for p in pcts]
    fig = go.Figure(go.Bar(x=names, y=pcts, marker_color=colors, text=[f"{p:.0f}%" for p in pcts], textposition="outside"))
    fig.update_layout(
        title="Queue Fill (% of capacity)",
        yaxis_range=[0, 120],
        template="plotly_white",
        height=340,
        xaxis_tickangle=-45,
    )
    return fig


def live_queue_area(
    timestamps: List[float],
    queue_history: Dict[str, List[float]],
    highlight: str | None = None,
) -> go.Figure:
    """Stacked-area chart of queue depths over stepped time."""
    fig = go.Figure()
    for name, vals in queue_history.items():
        display_vals = vals[:len(timestamps)]
        opacity = 1.0 if highlight is None or name == highlight else 0.3
        fig.add_trace(go.Scatter(
            x=timestamps[:len(display_vals)],
            y=display_vals,
            name=name,
            mode="lines",
            stackgroup="one" if highlight is None else None,
            opacity=opacity,
        ))
    fig.update_layout(
        title="Queue Depth Over Time",
        xaxis_title="Sim Time (min)",
        yaxis_title="Items in Queue",
        template="plotly_white",
        height=380,
    )
    return fig


def live_utilisation_gauge(
    station_name: str,
    utilisation: float,
) -> go.Figure:
    """Single-station utilisation gauge for the live dashboard."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=utilisation * 100,
        title={"text": station_name},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#6366f1"},
            "steps": [
                {"range": [0, 70], "color": "#d1fae5"},
                {"range": [70, 85], "color": "#fef3c7"},
                {"range": [85, 100], "color": "#fee2e2"},
            ],
        },
    ))
    fig.update_layout(height=220, margin=dict(t=40, b=10, l=30, r=30))
    return fig
