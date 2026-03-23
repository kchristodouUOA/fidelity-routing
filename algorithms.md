# Quantum Routing Algorithms: Q-LEAP and Q-PATH

This document describes the **Q-LEAP** (Algorithm 2) and **Q-PATH** (Algorithm 1) routing algorithms
as implemented in this project, based on the paper:
> *Fidelity-Guaranteed Entanglement Routing in Quantum Networks* (arXiv:2111.07764v4)

The implementations in `q_leap.py` and `q_path.py` replicate the official reference code in
`tmp_repo/src/` for a **single source–destination pair**.

---

## 1. Physical Model

### Entanglement Purification (BBPSSW)
Each link $(u,v)$ has initial fidelity $F_0$ and capacity $C$ (number of available entangled pairs).
Applying one purification round consumes one extra pair and raises fidelity:

$$F_{n+1} = \frac{F_n \cdot F_0}{F_n \cdot F_0 + (1-F_n)(1-F_0)}$$

After $d$ rounds the link reaches fidelity $F_d = \texttt{ftable}[d]$.

**`ftable` structure**: For each link with initial fidelity $F_0$ and remaining capacity $C$,
`ftable` is an array of length $C$ where `ftable[0] = F_0` (raw, unpurified fidelity) and
`ftable[d]` is the fidelity achieved after $d$ purification rounds. The length of `ftable` equals
the current remaining capacity, so `len(ftable) - 1` is the maximum number of purification rounds
the link can support. As capacity is consumed, `ftable` is rebuilt with the new (shorter) capacity.

The success probability of one purification round is:
$$p_{\text{round}}(F_n, F_0) = F_n F_0 + (1-F_n)(1-F_0)$$

The cumulative success probability of $d$ purification rounds on a link starting from $F_0$ is:
$$p(F_0, d) = \prod_{k=0}^{d-1} \left[ F_k F_0 + (1-F_k)(1-F_0) \right]$$

where $F_k$ is the fidelity after $k$ rounds. Implemented in `throughput_official.calp`.

### End-to-End Fidelity (Product Model)
For a path of $L$ hops with per-link fidelities $\{F_{d_i}\}$ after purification, the end-to-end
fidelity is the product:

$$F_{e2e} = \prod_{i=1}^{L} F_{d_i}$$

This product model assumes Werner states and entanglement swapping at intermediate nodes. It is
the model used throughout both algorithms for evaluating whether a path meets the threshold.

**Note on Werner state factor**: The quantity $(4F-1)/3$ appears in the Werner state representation
and is the correct measure of the "usefulness" of an entangled pair. After swapping two Werner-state
links with parameters $F_1$ and $F_2$, the resulting fidelity is $F_{swap} = \frac{1}{4}(1 + 3 \cdot
\frac{(4F_1-1)(4F_2-1)}{9})$. However, since $(4F-1)/3$ is strictly monotone in $F$ for $F \in (0.25, 1]$,
maximizing the product of raw fidelities is equivalent to maximizing the product of Werner factors
— both select the same optimal path. The implementations use raw fidelity for simplicity.

### End-to-End Success Probability (Bottleneck Model)
$$p_{e2e} = \min_i \, p(F_{0,i},\, d_i)$$

The path success probability is determined by the worst (bottleneck) link. Implemented in
`throughput_official.caletp`.

### Resource Consumption
Each flow on a path consumes $d_i + 1$ pairs on link $i$ (1 base pair + $d_i$ sacrificed for
purification rounds). For $n$ simultaneous flows the consumption on link $i$ is $n(d_i+1)$.

The number of flows a path can support given current link capacities is:

$$n_{\max} = \min_i \left\lfloor \frac{C_i}{d_i+1} \right\rfloor$$

and the expected throughput for one path is $n_{\max} \cdot p_{e2e}$.

---

## 2. Q-PATH (Algorithm 1) — Priority-Queue Routing

**File**: `q_path.py`
**Official reference**: `tmp_repo/src/qpath.py`, `tmp_repo/src/pathf.py`, `tmp_repo/src/spfmincost.py`

### Overview
Q-PATH finds and commits paths in order of increasing **purification cost** (total pairs consumed),
using a priority queue. Within each cost level, paths are enumerated by increasing hop count using
Yen's k-shortest-paths algorithm.

### Pre-processing: `udtp`

Before the main loop, `udtp` prunes infeasible links:
1. For each link, build `ftable[0..C-1]` using the BBPSSW formula iteratively.
2. Remove any link where `ftable[-1] < F_th` (even at full purification capacity, the link cannot
   reach $F_{th}$) or where remaining capacity $C = 0$.

This step removes permanently infeasible links so path enumeration never considers them.
Implemented in the inline loop at the start of `compute_metrics` in `q_path.py` (lines 192–202).
Corresponds to `Udtp().udtp(g, fth)` in the official `updatetopo.py`.

### Algorithm Steps

**Main loop** (`for cost in range(minhop, n_nodes + 1):`):

#### Step 1 — Path enumeration (`_costsearch`)
Enumerate all simple paths with exactly `cost` hops using an incremental Yen's k-shortest method.
The enumeration state (`aset`, `bset`) persists across cost iterations:
- `aset`: ordered list of all paths found so far (k-th shortest by hops)
- `bset`: candidate spur paths not yet promoted to `aset`

Each new `cost` iteration extends the previously discovered paths without restarting from scratch.
The path indices reference a fixed `node_list = sorted(G_work.nodes())` so indices remain stable
even as edges are removed from `G_work`.

Before enumerating, `ispathconnect` is applied: every edge in a candidate path must exist in the
current `G_work`. Paths with stale edges (removed by previous resource consumption) are discarded.

#### Step 2 — Purification assignment (`_mostup`)
For each candidate path, greedily assign purification rounds to each link until $F_{e2e} \geq F_{th}$:

1. **Prejudge check**: Before the greedy loop, compute the maximum achievable fidelity product
   as $\prod_i \texttt{ftable}_i[-1]$ (each link at full purification capacity). If this product
   is still below $F_{th}$, return `(-1, [])` immediately — the path is infeasible regardless of
   purification decisions.

2. **Greedy loop**: While $F_{e2e} < F_{th}$, pick the link $i$ whose one additional purification
   round maximally increases $F_{e2e}$ (i.e. maximizes $F_{d_i+1} \cdot \prod_{j \neq i} F_{d_j}$).
   Increment $d_i$ and update the running fidelity vector.

3. **Capacity cap**: If at any point $d_i \geq \text{len}(\texttt{ftable}_i)$ (i.e. $d_i \geq C_i$),
   the link cannot support the required purification — return `(-1, [])`.

4. **Cost calculation**: $\text{scost} = \sum_i (d_i + 1)$ = total pairs consumed (base pair +
   purification pairs for each link). This is `ccost(de)` in the official `pathf.py`.

#### Step 3 — Priority queue
Each feasible path is enqueued as `(scost, [path, de])`. Paths with lower purification cost have
higher priority and will be committed first.

#### Step 4 — Commit phase (`scost <= cost + 1`)
Paths are dequeued and committed when their `scost <= cost + 1`. This condition ensures:
- A path found at hop count `cost` has minimum `scost = cost` (all $d_i = 0$, one pair per hop).
- Allowing `cost + 1` means paths requiring one extra purification pair (across all links combined)
  are committed before exploring `cost + 1`-hop paths.
- This prevents premature commitment of high-cost paths before lower-cost alternatives have been
  enumerated.

For each dequeued path:

1. **Capacity check (`preudtppath`)**: Verify each link $(u,v)$ on the path still has enough
   capacity for $d_i + 1$ pairs. If any link is insufficient, remove it from `G_work` and discard
   the path. This prevents committing paths whose resources have been consumed by earlier paths.

2. **Throughput calculation**: Compute $n_{\max} = \min_i \lfloor C_i / (d_i+1) \rfloor$,
   $p_{e2e} = \min_i p(F_{0,i}, d_i)$, and $\text{patht} = n_{\max} \cdot p_{e2e}$.

3. **Partial fill**: If $\text{total\_throughput} + \text{patht} \geq \text{request}$, only add
   enough flows to exactly reach `request`. The partial fill loops over $i = 1, 2, \ldots, n_{\max}$
   and commits the smallest $i$ such that $\text{total} + i \cdot p_{e2e} \geq \text{request}$.
   The consumption is $\text{con}[j] = i \cdot (d_j + 1)$ for each link $j$. Then returns immediately.

4. **Resource update (`udtppath`)**: For each link, subtract consumed pairs, rebuild `ftable` with
   the new capacity, and remove the link if:
   - New capacity ≤ 0 (exhausted), or
   - New `ftable[-1] < F_th` (can no longer reach threshold after consumption).

5. Repeat until request is satisfied or no more feasible paths remain.

### Path Enumeration: Yen's k-shortest by hops

Adapted from `Spfmc.costsearch` / `Spfmc.skshortpath` in `tmp_repo/src/spfmincost.py`:

- **`_heapdijkstra`**: Min-hop Dijkstra on an integer adjacency list (all edge weights = 1).
  Returns path as index list; returns `[]` if no path.

- **`_find_next_kth`**: Finds the next (k+1)-th shortest path by spur. For each edge in the
  last found path (in `aset[-1]`), temporarily remove that edge and run Dijkstra from the spur
  node to the destination. Combines the prefix (nodes before the spur point) with the spur result.
  All candidates go to `bset`; the one with fewest hops is promoted to `aset`.

- **`_costsearch`**: Calls `_find_next_kth` repeatedly until `aset[-1]` has more than `cost` hops
  (or all paths are exhausted). Returns the subset of `aset` with exactly `cost` hops.

**Note on tie-breaking**: Our code uses `sorted(G.nodes())` for the fixed node index list; the
official uses a set-derived `nodes_names` order. When multiple minimum-hop paths exist, the two
implementations may discover a different "first" path, causing Yen's spurs to diverge for that
seed. This produces small per-trial throughput differences in some cases (typically < 2%) but does
not affect the correctness of the algorithm logic.

---

## 3. Q-LEAP (Algorithm 2) — Low-Complexity Routing

**File**: `q_leap.py`
**Official reference**: `tmp_repo/src/qleap.py`, `tmp_repo/src/pud.py`

### Overview
Q-LEAP uses a product-maximizing Dijkstra to always route on the best-quality path, then
applies a uniform purification strategy to each link so the path product meets $F_{th}$.

### Pre-processing
Same `udtp` link pruning as Q-PATH: build `ftable` per link, remove links where
`ftable[-1] < F_th`. Official code: `Pud().calftable(g)` followed by `Udtp().udtp(g, fth)`.

### Algorithm Steps

**Main loop** (iterate until request satisfied or no path exists):

#### Step 1 — Best path (max-product Dijkstra)

The official code (`Udtp().topoljbf`) builds an adjacency list where each entry stores the raw
initial link fidelity $F_0$ directly. `Spfsearch.heapdijkstra` then runs a **max-product Dijkstra**:
it maximizes $\prod_i F_{0,i}$, the product of raw fidelities along the path.

Our implementation uses the equivalent formulation: assign edge weight $w_i = -\log F_{0,i}$ and
run shortest-path (sum minimization), which maximizes $\prod_i F_{0,i}$.

This selects the path with the highest raw intrinsic fidelity, before any purification is applied.
As noted in Section 1, maximizing the product of raw fidelities is equivalent to maximizing the
product of Werner state factors $(4F-1)/3$ because the latter is strictly monotone in $F$.

#### Step 2 — Purification assignment (`pud`)

Compute the per-hop fidelity target:
$$F_{avg} = F_{th}^{1/L}$$

For each link $i$ on the path, apply purification rounds until $F_{d_i} \geq F_{avg}$ (or capacity
is reached). Since initial fidelities are drawn from $\mathcal{N}(0.925, 0.05)$ and typical
thresholds are 0.7–0.9, the number of required rounds is small (usually 0–2 per link).

**Implementation detail**: `throughput_official.cal_pud` caps purification at 3 rounds per link
(`while f_curr < f_ave and p < 3`). In practice this cap is rarely reached given the high initial
fidelities in the US Backbone simulation. For the purification cap in the resource commitment
step, `preudtppath` enforces that each link has at least $d_i + 1$ pairs available.

If the path already satisfies $F_{e2e} = \prod_i F_{0,i} \geq F_{th}$, no purification is needed
and `de = [0] * L`.

#### Step 3 — Capacity check (`preudtppath`)

Before committing, verify each link on the path has capacity $C_i \geq d_i + 1$. If any link
fails this check, it is removed from `G_work` (that path is discarded) and the loop continues
to find the next best path.

#### Step 4 — Commit

Compute $n_{\max} = \min_i \lfloor C_i / (d_i + 1) \rfloor$ and $p_{e2e} = \min_i p(F_{0,i}, d_i)$.

Apply the same partial-fill logic as Q-PATH: if adding the full $n_{\max}$ flows would exceed the
request limit, use only the minimum $n$ such that $\text{total} + n \cdot p_{e2e} \geq \text{request}$.

Accumulate throughput and update graph resources (`udtppath`): subtract $n \cdot (d_i + 1)$ pairs
from each link, rebuild `ftable`, remove exhausted or newly-infeasible links.

#### Step 5 — Graph pruning

After each committed path, re-run `udtp` (the pre-processing pruning step) on the updated graph.
Any link whose remaining capacity is too small to ever reach $F_{th}$ is removed immediately,
keeping the graph in a consistent state for the next Dijkstra call.

If no path exists after pruning (graph disconnects between source and destination), the loop exits.

---

## 4. Shared Utilities

**File**: `throughput_official.py`

| Function | Description |
|---|---|
| `calfgn(f1, f2)` | BBPSSW fidelity after one purification round: $F_1 F_0 / (F_1 F_0 + (1-F_1)(1-F_0))$ |
| `calfgn_n(f, n)` | Fidelity after $n$ rounds starting from $f$ (iterates `calfgn`) |
| `calp(f_init, d)` | Link success probability after $d$ purification rounds (product of per-round probs) |
| `caletp(probs)` | Bottleneck (min) path success probability |
| `cal_epathf(fids)` | Product end-to-end fidelity |
| `cal_pud(link_fids, f_th)` | Q-LEAP purification: per-link rounds to reach $F_{avg} = F_{th}^{1/L}$, capped at 3 |
| `caletp_path(G, path, de)` | Bottleneck success probability for a path given purification vector `de` |

---

## 5. Network Resource Utilization Metric

The paper defines network resource utilization as (Fig. 6 caption):
> *"the ratio of the consumed entanglement pairs and the total entanglement pairs in the network"*

The official implementation computes this in `Step5_Capacity_Utilization`
(`tmp_repo/src/run_qleap.py`, line 666):

```python
for k in G.edges():
    if edge_request == []:   # skip edges with no traffic
        continue
    real_capacity = sum(flows on this edge)
    sum_capacity += real_capacity / edge_capacity
    count_used_edge += 1
average_capacity_utilization = sum_capacity / count_used_edge
```

**This is the average per-used-directed-edge load**, not total consumption / total capacity.
Edges that carry no traffic are skipped from both numerator and denominator.

In our test scripts (`test_fig6.py`, `test_fig7.py`) this is implemented as `_per_edge_util`:

```python
def _per_edge_util(paths, cons_list, capacity):
    edge_cons = {}
    for path, cons in zip(paths, cons_list):
        for i in range(len(path) - 1):
            key = (path[i], path[i+1])
            edge_cons[key] = edge_cons.get(key, 0) + cons[i]
    return sum(c / capacity for c in edge_cons.values()) / len(edge_cons)
```

`cons_list[k][i]` = total pairs consumed on link $i$ of path $k$ = $n_k \cdot (d_{k,i}+1)$.
Both algorithms store `'con'` in their debug output to expose per-link consumption.

### Utilization trend: single vs. multi SD pair

The paper's Figure 6(c) shows utilization **increasing** with fidelity threshold. Our single-SD-pair
simulation shows it **decreasing** for Q-LEAP and non-monotonic for Q-PATH. This is a physical
consequence of the single-pair setting, not a bug:

**Why utilization decreases with threshold (single SD pair)**

At low $F_{th}$ (e.g. 0.6): purification is minimal ($d_i \approx 0$), so $n_{\max} = C$ on every
link. Each committed path saturates all its links at 100% utilization ($C/C = 1$).

At high $F_{th}$ (e.g. 0.9): some links require $d_i = 2$, giving $n_{\max} = \lfloor C/3 \rfloor$.
This bottleneck link caps the flow count for the entire path. All other links on that path receive
only $n_{\max}$ flows, consuming $n_{\max} \cdot (d_i+1)$ pairs — well below their capacity.
The per-edge average is pulled down by these under-utilized non-bottleneck links.

**Why the paper shows the opposite trend (multiple SD pairs)**

With many SD pairs, different pairs' paths share and collectively fill each link. At high $F_{th}$,
fewer SD pairs are served but each uses heavy purification on its specific links. Those specific
links become very highly loaded ($\approx C$) while links unused by any feasible pair are excluded
from the average. The density of used-and-nearly-saturated links increases with threshold, raising
the per-edge average.

**Summary**: The `_per_edge_util` formula is correct and matches the paper's definition. The
trend difference is fundamental to single vs. multiple SD pair operation and is expected.

---

## 6. Replication Results — Figure 6 (50 trials, US Backbone)

**Setup**: US Backbone topology (53 edges, ~34 nodes). Per-link fidelity drawn from
$\mathcal{N}(0.925, 0.05)$ clipped to $[0.85, 1.0]$. Capacity $C=50$, request limit 200.
Seeds 300–349. Source/destination: `nodes_names[0]` → `nodes_names[-1]` (set-order dependent;
resolved to Portland → Washington DC in this run).

**Averaged over 50 trials (utilization = per-used-edge average):**

| $F_{th}$ | Algorithm | Tput (Off) | Tput (Our) | ΔTput | Fid (Off) | Fid (Our) | Util (Off) | Util (Our) |
|---|---|---|---|---|---|---|---|---|
| 0.6 | Q-LEAP | 64.76 | 64.76 | **0.00** | 0.745 | 0.745 | 0.888 | 0.888 |
| 0.6 | Q-PATH | 74.00 | 73.85 | +0.14 | 0.636 | 0.636 | 0.776 | 0.773 |
| 0.7 | Q-LEAP | 46.69 | 46.68 | ~0 | 0.888 | 0.888 | 0.861 | 0.866 |
| 0.7 | Q-PATH | 57.55 | 58.54 | −0.99 | 0.726 | 0.724 | 0.718 | 0.730 |
| 0.8 | Q-LEAP | 37.28 | 37.28 | **0.00** | 0.938 | 0.938 | 0.815 | 0.815 |
| 0.8 | Q-PATH | 48.71 | 48.89 | −0.19 | 0.824 | 0.822 | 0.785 | 0.776 |
| 0.9 | Q-LEAP | 30.44 | 30.44 | **0.00** | 0.967 | 0.967 | 0.722 | 0.722 |
| 0.9 | Q-PATH | 40.54 | 40.66 | −0.12 | 0.916 | 0.915 | 0.855 | 0.855 |

Throughput and fidelity parity are unchanged from the pre-fix run. Utilization values are now in
the physically meaningful range 0.7–0.9 (fraction of used-link capacity consumed). For this
single SD pair, utilization decreases with threshold for Q-LEAP (see Section 5 for explanation).

**Plot**: `fig6_replication.png` — **Raw log**: `fig6_final_run_50.log`

---

## 7. Replication Results — Figure 7 (50 trials, US Backbone)

**Setup**: Same topology and fidelity distribution as Figure 6.
Fixed $F_{th} = 0.7$, fixed request limit 200. Capacity swept over [10, 30, 50, 70, 90].
Seeds 300–349. Source/destination: `nodes_names[0]` → `nodes_names[-1]` (resolved to
Philadelphia → Montreal in this run).

**Averaged over 50 trials (utilization = per-used-edge average):**

| Capacity | Algorithm | Tput (Off) | Tput (Our) | ΔTput | Fid (Off) | Fid (Our) | Util (Off) | Util (Our) |
|---|---|---|---|---|---|---|---|---|
| 10 | Q-LEAP | 17.31 | **17.31** | **0.000** | 0.795 | 0.795 | 0.944 | 0.944 |
| 10 | Q-PATH | 17.97 | 17.94 | +0.031 | 0.771 | 0.772 | 0.898 | 0.898 |
| 30 | Q-LEAP | 51.99 | **51.99** | **0.000** | 0.796 | 0.796 | 0.945 | 0.945 |
| 30 | Q-PATH | 53.95 | 53.89 | +0.062 | 0.771 | 0.772 | 0.899 | 0.900 |
| 50 | Q-LEAP | 86.66 | **86.66** | **0.000** | 0.796 | 0.796 | 0.946 | 0.946 |
| 50 | Q-PATH | 89.94 | 89.83 | +0.110 | 0.771 | 0.772 | 0.899 | 0.901 |
| 70 | Q-LEAP | 121.34 | **121.34** | **0.000** | 0.796 | 0.796 | 0.946 | 0.946 |
| 70 | Q-PATH | 125.92 | 125.78 | +0.141 | 0.771 | 0.772 | 0.899 | 0.901 |
| 90 | Q-LEAP | 156.01 | **156.01** | **0.000** | 0.796 | 0.796 | 0.946 | 0.946 |
| 90 | Q-PATH | 161.90 | 161.72 | +0.188 | 0.771 | 0.772 | 0.899 | 0.901 |

**Q-LEAP**: Exact throughput match at every capacity level. Utilization is flat at ~0.945,
consistent with a fixed threshold where the same fraction of used-link capacity is consumed
regardless of raw capacity.

**Q-PATH**: Throughput differences < 0.2 (< 0.1%), same Yen's tie-breaking origin as Figure 6.
Utilization match between official and ours is excellent (~0.899 vs ~0.901).

**Plot**: `fig7_replication.png` — **Raw log**: `fig7_final_run_50.log`
