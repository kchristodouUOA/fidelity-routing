# Fidelity-Based Quantum Routing Project

## Overview
This project implements and replicates quantum internet routing algorithms from the paper:
> *Fidelity-Guaranteed Entanglement Routing in Quantum Networks* (arXiv:2111.07764v4)

The algorithms optimize path selection based on **entanglement fidelity** and **capacity constraints**,
finding reliable routes between source and destination nodes while maintaining minimum fidelity
thresholds. The reference implementation is in `tmp_repo/src/` (official code).

## Key Concepts

### Quantum Entanglement Fidelity
- Quality of entangled pairs between neighboring nodes; ranges from 0 to 1.
- Degrades over paths via entanglement swapping; improved locally via purification.

### Entanglement Purification (BBPSSW)
- Consumes two imperfect entangled pairs to produce one higher-fidelity pair.
- Formula: `F_new = (F1 × F2) / (F1 × F2 + (1-F1) × (1-F2))`
- Limited by edge capacity (number of available pairs per link).

### End-to-End Fidelity
- Product of per-link fidelities after purification: `F_e2e = ∏ F_i`.
- Must exceed threshold `F_th` for the entanglement to be usable.

---

## Project Structure

### Core Algorithm Modules

#### `q_path.py` — Q-PATH (Algorithm 1)
Priority-queue routing that finds and commits paths in order of minimum purification cost.
- Path enumeration via incremental Yen's k-shortest-paths (adapted from `tmp_repo/src/spfmincost.py`).
- Greedy purification assignment (`_mostup`) per path.
- Resource tracking: capacity consumption, graph update, link pruning.

#### `q_leap.py` — Q-LEAP (Algorithm 2)
Low-complexity routing using multiplicative-metric Dijkstra.
- Finds the best-quality path by maximising the product of `(4F-1)/3` link factors.
- Uniform purification per link to reach the per-hop target `F_avg = F_th^(1/L)`.

#### `throughput_official.py` — Shared Physical Model
Purification formulas, success probability, and throughput helpers used by both algorithms.
Replicates the functions in `tmp_repo/src/throughput.py`.

### Test / Replication Scripts

#### `test_fig6.py`
Replicates Figure 6 of the paper: throughput, fidelity, and network utilization vs. fidelity
threshold on the US Backbone topology. Runs both official (from `tmp_repo/src/`) and our
implementations side-by-side and prints a parity table.
- Parameters: 50 trials, `C=50`, request=200, thresholds [0.6, 0.7, 0.8, 0.9].
- Output: `fig6_replication.png`, `fig6_final_run_50.log`.

#### `test_fig7.py`
Replicates Figure 7 of the paper: throughput, fidelity, and network utilization vs. link capacity.
- Parameters: 50 trials, fixed $F_{th}=0.7$, request=200, capacities [10, 30, 50, 70, 90].
- Output: `fig7_replication.png`, `fig7_final_run_50.log`.

### Reference Implementation
`tmp_repo/src/` — official code from the paper authors:
- `qpath.py`, `qleap.py`: official algorithm implementations.
- `spfmincost.py`: Yen's k-shortest-paths (Spfmc class) used by Q-PATH.
- `pathf.py`: path fidelity and purification helpers.
- `throughput.py`, `pud.py`: physical model utilities.
- `vtopology.py`, `vlink.py`: network graph and link data structures.

---

## Simulation Setup (Figure 6)

**Topology**: US Backbone — 34 nodes, 53 edges (real US city interconnects).
**Link fidelity**: drawn from `N(0.925, 0.05)` clipped to `[0.85, 1.0]` per trial.
**Capacity**: `C = 50` pairs per link.
**Request limit**: 200 entangled pairs delivered.
**Seeds**: 300–349 (50 trials).

---

## Replication Status

| Algorithm | Match quality | Notes |
|---|---|---|
| Q-LEAP | **Exact match** (ΔTput = 0.000 on Fig 7; < 0.02 on Fig 6) | Floating-point rounding only |
| Q-PATH | **< 0.1–2% higher throughput** than official | Yen's tie-breaking; core logic identical |
| Utilization metric | Per-used-edge average — matches paper's `Step5_Capacity_Utilization` | See note below |

**Note on utilization trend**: The paper (Fig 6c) shows utilization *increasing* with fidelity
threshold. Our single-SD-pair simulation shows it *decreasing* for Q-LEAP. This is expected: at
high thresholds, bottleneck links (high $d_i$) cap $n_{\max}$ for the whole path, leaving
non-bottleneck links under-utilized and pulling down the per-edge average. With multiple SD pairs
(the paper's original scenario) different pairs collectively fill each link, reversing the trend.
The metric formula itself is correct. See `algorithms.md` Section 5 for full analysis.

See `algorithms.md` for full results tables (Fig 6 and Fig 7) and explanation of all differences.

---

## Dependencies
- `networkx`: graph algorithms and path finding
- `numpy`: numerical computations
- `matplotlib`: plotting
- Python standard library: `math`, `copy`, `heapq`, `queue`
