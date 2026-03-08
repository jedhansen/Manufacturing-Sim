# Discrete-Event Manufacturing Simulator

A modular SimPy-based discrete-event simulator for multi-line production facilities, with interactive Streamlit dashboards for bottleneck analysis, critical-path tracking, Six Sigma DMAIC scenarios, and live stepping with real-time interventions.

## Project Structure

```
mfg-simulator/
  app.py                  # Streamlit entry-point
  config.py               # All tuneable parameters (dataclasses)
  requirements.txt
  README.md
  sim_engine/
    __init__.py
    environment.py         # ManufacturingSim (batch) & SteppableSim (live)
    processes.py           # Process generators: lines, stations, assembly
    resources.py           # Resource / Store models & failure/repair
    monitors.py            # Live queue & utilisation recorders
    interventions.py       # Mid-sim corrective actions
  analytics/
    __init__.py
    bottleneck.py          # WIP & utilisation heatmaps
    critical_path.py       # Forward/backward pass CPM
    six_sigma.py           # Cp, Cpk, histograms, DMAIC helpers
  viz/
    __init__.py
    plots.py               # All Plotly chart builders
  tests/
    __init__.py
    test_sim.py            # Smoke tests
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Run tests
python -m pytest tests -v
```

## Two Simulation Modes

### 1. Batch Mode

Run a full 8-hour (480 min) shift, then explore:
- **Bottlenecks** — utilisation bar chart & WIP queue heatmap
- **Critical Path** — forward/backward pass CPM with Gantt chart
- **Six Sigma / DMAIC** — Cp, Cpk, sigma level with what-if sliders
- **Raw Metrics** — per-part event table

### 2. Live Stepping Mode

Advance the simulation in user-controlled time increments (e.g. 15 min). At each step you see:
- Queue fill gauges — colour-coded bars showing which buffers are close to overflow (bottleneck forming)
- Utilisation gauges — per-station busy fraction
- Trend charts — queue depths over stepped time
- Alerts — broken stations, queues > 80% capacity, pace below demand

| Action              | Effect                                       |
|---------------------|----------------------------------------------|
| Force Repair        | Instantly fix a broken station               |
| Add 1 Worker        | Add parallel capacity to a station           |
| Add Assembly Bay    | Add capacity to final assembly               |
| Speed Up Line       | Reduce mean cycle time by N%                 |
| Expand Buffer       | Increase a queue's max capacity              |

This lets you practice identifying and resolving bottlenecks interactively — a hands-on companion to Six Sigma / Lean training.

## Configuration

All parameters are adjustable via the Streamlit sidebar:
- Number of parallel lines (2–5)
- Per-line: stations, cycle-time distribution (exponential / triangular), queue capacity, MTTF/MTTR
- Shift length, random seed
- Six Sigma spec limits (USL / LSL)
- Demand target (Live mode)

## Tech Stack

- **Python 3.12+**
- **SimPy 4.x** — discrete-event simulation engine
- **Streamlit** — interactive web UI
- **Plotly** — charts & visualisations
- **NumPy / Pandas** — analytics
