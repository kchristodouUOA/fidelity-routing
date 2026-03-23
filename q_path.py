"""
Q-PATH: Priority-queue routing with minimum purification cost (Algorithm 1).

Path discovery replicates the official Spfmc.costsearch / skshortpath methods
(tmp_repo/src/spfmincost.py) — Yen's k-th shortest by hop count — so path
ordering closely matches the official implementation.

NOTE on minor differences with the official:
  Dijkstra tie-breaking depends on adjacency-list node ordering.  Here we use
  sorted(G.nodes()); the official uses a set-derived nodes_names ordering.
  When multiple paths share the minimum hop count, each code base may pick a
  different "first" path as the Yen's spur base, discovering different k-th
  paths.  This causes small per-trial throughput differences in some cases; the
  algorithmic logic (priority queue by scost, resource tracking, purification
  decisions) is identical to the official.
"""
import networkx as nx
import math
import copy
import heapq
from queue import PriorityQueue
import throughput_official as th


# ---------------------------------------------------------------------------
# Path enumeration helpers
# Adapted from tmp_repo/src/spfmincost.py (Spfmc class) and
# tmp_repo/src/updatetopo.py (Udtp.topocost / Udtp.topoljb).
# We replicate the official's incremental k-shortest-by-hops discovery so
# path selection order closely mirrors the paper's algorithm.
# ---------------------------------------------------------------------------

def _build_hop_adj(G_work, node_list):
    """
    Build hop adjacency list from the current graph G_work.
    adj[i] = [[j, 1], ...] for each neighbor j of node i.
    node_list is fixed at the start so indices are stable across iterations
    even as edges are removed.
    Equivalent to Udtp().topocost(g) + Udtp().topoljb(hopg) in the official.
    """
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    n = len(node_list)
    adj = [[] for _ in range(n)]
    for u, v in G_work.edges():
        if u in node_to_idx and v in node_to_idx:
            i, j = node_to_idx[u], node_to_idx[v]
            adj[i].append([j, 1])
            adj[j].append([i, 1])
    return adj


def _heapdijkstra(adj, source, des):
    """
    Min-hop Dijkstra on adjacency list.  Returns path as index list, or [].
    Adapted from Spfmc.heapdijkstra in tmp_repo/src/spfmincost.py.
    """
    n = len(adj)
    costs = [float('inf')] * n
    prev = [-1] * n
    visited = [0] * n
    costs[source] = 0

    heap = []
    for nb in adj[source]:
        prev[nb[0]] = source
        costs[nb[0]] = nb[1]
        heapq.heappush(heap, (nb[1], nb[0]))

    while heap:
        cur_cost, cur = heapq.heappop(heap)
        if visited[cur]:
            continue
        visited[cur] = 1
        for nb in adj[cur]:
            new_cost = costs[cur] + nb[1]
            if new_cost < costs[nb[0]]:
                costs[nb[0]] = new_cost
                prev[nb[0]] = cur
                heapq.heappush(heap, (new_cost, nb[0]))

    # Reconstruct path
    path = []
    u = des
    while u != -1:
        path.append(u)
        u = prev[u]
    path.reverse()

    if path and path[0] == source and len(path) >= 2:
        return path
    return []


def _noring(path):
    """True iff all nodes are distinct (no cycle). From Pathf.noring."""
    return len(set(path)) == len(path)


def _find_next_kth(adj, source, des, aset, bset):
    """
    Find the next k-th shortest path by hop count, adding it to aset.
    Returns True if a new path was found.
    Adapted from Spfmc.skshortpath in tmp_repo/src/spfmincost.py:
      - For each edge in aset[-1], remove it, find shortest spur to dest.
      - Collect spur candidates in bset; pick the shortest (fewest hops).
    """
    if not aset:
        p = _heapdijkstra(adj, source, des)
        if p:
            aset.append(p)
            return True
        return False

    last_path = aset[-1]
    for i in range(len(last_path) - 1):
        curnode = last_path[i]
        curroot = last_path[i + 1]
        pathahead = last_path[:i]

        # Remove edge curnode <-> curroot from a fresh copy
        tmpg = copy.deepcopy(adj)
        tmpg[curnode] = [x for x in tmpg[curnode] if x[0] != curroot]
        tmpg[curroot] = [x for x in tmpg[curroot] if x[0] != curnode]

        spur = _heapdijkstra(tmpg, curnode, des)
        if not spur:
            continue

        full_path = pathahead + spur
        if full_path not in bset and full_path not in aset and _noring(full_path):
            bset.append(full_path)

    if bset:
        # Pick shortest by hop count (matches official)
        best_idx = min(range(len(bset)), key=lambda x: len(bset[x]))
        new_path = bset[best_idx]
        if new_path not in aset:
            aset.append(new_path)
        bset.pop(best_idx)
        return True
    return False


def _costsearch(adj, source, des, cost, aset, bset):
    """
    Return all paths with exactly `cost` hops. Mutates aset / bset.
    Adapted from Spfmc.costsearch in tmp_repo/src/spfmincost.py:
      - Keeps calling _find_next_kth until aset[-1] exceeds cost hops.
      - aset/bset persist across cost iterations (incremental discovery).
    """
    if not aset:
        p = _heapdijkstra(adj, source, des)
        if not p:
            return [], aset, bset
        aset.append(p)

    # Extend aset until last path exceeds `cost` hops (or no more paths)
    while len(aset[-1]) - 1 <= cost:
        prev_len = len(aset)
        _find_next_kth(adj, source, des, aset, bset)
        if len(aset) == prev_len:
            break  # exhausted all paths

    return [p for p in aset if len(p) - 1 == cost], aset, bset


# ---------------------------------------------------------------------------
# Main algorithm
# ---------------------------------------------------------------------------

def compute_metrics(G, source, target, f_th, capacity, config):
    """Q-PATH metrics using priority-queue sorted by purification cost."""
    request_limit = float(config.get('request', 50))
    total_throughput = 0.0
    total_consumption = 0.0
    delivered_fidelities = []
    delivered_tputs = []
    debug_list = []

    G_work = G.copy()

    # --- ftable: ftable[n] = fidelity after n purification rounds ---
    def build_ftable(f_init, c):
        table = []
        f = f_init
        for _ in range(int(c)):
            table.append(f)
            f = th.calfgn(f, f_init)
        return table

    # --- Step 1: udtp — remove edges that can never reach f_th ---
    for u, v in list(G_work.edges()):
        c = int(G_work[u][v]['weight'])
        f_init = G_work[u][v]['fidelity']
        if c == 0:
            G_work.remove_edge(u, v)
            continue
        ftable = build_ftable(f_init, c)
        if ftable[-1] < f_th:
            G_work.remove_edge(u, v)
        else:
            G_work[u][v]['ftable'] = ftable

    try:
        minhop = len(nx.shortest_path(G_work, source=source, target=target, weight=None)) - 1
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return 0.0, 0.0, 0.0, debug_list

    # Fixed node list (stable indices across iterations)
    node_list = sorted(G_work.nodes())
    node_to_idx = {n: i for i, n in enumerate(node_list)}
    src_i = node_to_idx[source]
    dst_i = node_to_idx[target]
    n_nodes = len(node_list)

    # --- _mostup: greedy purification to reach f_th ---
    def mostup(G_w, path):
        L = len(path) - 1
        de = [0] * L
        pathf = [G_w[path[i]][path[i+1]]['fidelity'] for i in range(L)]
        ftables = [G_w[path[i]][path[i+1]]['ftable'] for i in range(L)]

        # prejudge: max achievable fidelity product must reach f_th
        if math.prod(ftables[i][-1] for i in range(L)) < f_th:
            return -1, []

        while math.prod(pathf) < f_th:
            best_f = -1
            best_idx = 0
            best_pathf = None
            for i in range(L):
                test = list(pathf)
                test[i] = th.calfgn(test[i], G_w[path[i]][path[i+1]]['fidelity'])
                val = math.prod(test)
                if val > best_f:
                    best_f = val
                    best_idx = i
                    best_pathf = test

            de[best_idx] += 1
            if de[best_idx] >= len(ftables[best_idx]):  # cap at capacity
                return -1, []
            pathf = best_pathf

        return sum(d + 1 for d in de), de

    # --- preudtppath: check capacity, remove edge if insufficient ---
    def preudtppath(G_w, path, de):
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not G_w.has_edge(u, v) or int(G_w[u][v]['weight']) < de[i] + 1:
                if G_w.has_edge(u, v):
                    G_w.remove_edge(u, v)
                return False
        return True

    # --- udtppath: consume resources, update ftable, remove if can't reach f_th ---
    def udtppath(G_w, path, con):
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            if not G_w.has_edge(u, v):
                continue
            G_w[u][v]['weight'] -= con[i]
            new_c = int(G_w[u][v]['weight'])
            if new_c <= 0:
                G_w.remove_edge(u, v)
                continue
            f_init = G_w[u][v]['fidelity']
            new_ftable = build_ftable(f_init, new_c)
            G_w[u][v]['ftable'] = new_ftable
            if new_ftable[-1] < f_th:
                G_w.remove_edge(u, v)

    def epathf(G_w, path, de):
        f = 1.0
        for i in range(len(path) - 1):
            f *= G_w[path[i]][path[i+1]]['ftable'][de[i]]
        return f

    def caletp(G_w, path, de):
        probs = [th.calp(G_w[path[i]][path[i+1]]['fidelity'], de[i])
                 for i in range(len(path) - 1)]
        return min(probs)

    def calpathsumth(G_w, path, de):
        return int(min(int(G_w[path[i]][path[i+1]]['weight']) // (de[i] + 1)
                       for i in range(len(path) - 1)))

    # --- Main loop ---
    pq = PriorityQueue()
    aset, bset = [], []

    for cost in range(minhop, n_nodes + 1):
        # Rebuild hop graph from current G_work
        if not nx.has_path(G_work, source, target):
            break

        adj = _build_hop_adj(G_work, node_list)

        # Check if destination still reachable on hop graph
        if not _heapdijkstra(adj, src_i, dst_i):
            break

        # Enumerate paths with exactly `cost` hops (Yen's incremental)
        if cost <= n_nodes - 1:
            pathset_idx, aset, bset = _costsearch(adj, src_i, dst_i, cost, aset, bset)

            for path_idx in pathset_idx:
                path = [node_list[i] for i in path_idx]
                # ispathconnect: all edges must exist in G_work
                if not all(G_work.has_edge(path[j], path[j+1]) for j in range(len(path)-1)):
                    continue
                scost, tmpde = mostup(G_work, path)
                if tmpde:
                    pq.put((scost, [path, tmpde]))

        if cost > n_nodes and pq.empty():
            break

        # Process queue: commit paths with scost <= cost + 1
        if not pq.empty():
            while not pq.empty():
                cur = pq.get()
                if cur[0] <= cost + 1:
                    path_cur, de_cur = cur[1][0], cur[1][1]
                    if preudtppath(G_work, path_cur, de_cur):
                        t_li = caletp(G_work, path_cur, de_cur)
                        fi = epathf(G_work, path_cur, de_cur)
                        n = calpathsumth(G_work, path_cur, de_cur)
                        patht_li = n * t_li

                        if total_throughput + patht_li >= request_limit:
                            for i in range(1, n + 1):
                                if total_throughput + i * t_li >= request_limit:
                                    actual_tput = i * t_li
                                    con = [i * (de_cur[j] + 1) for j in range(len(de_cur))]
                                    total_throughput += actual_tput
                                    total_consumption += sum(con)
                                    delivered_fidelities.append(fi)
                                    delivered_tputs.append(actual_tput)
                                    debug_list.append({
                                        'path': path_cur, 'de': de_cur,
                                        'tput': actual_tput, 'f_path': fi,
                                        'con': con,
                                    })
                                    avg_fid = _wavg(delivered_fidelities, delivered_tputs)
                                    return (float(total_throughput), float(avg_fid),
                                            float(total_consumption), debug_list)
                        else:
                            actual_tput = patht_li
                            con = [n * (de_cur[j] + 1) for j in range(len(de_cur))]
                            total_throughput += actual_tput
                            total_consumption += sum(con)
                            delivered_fidelities.append(fi)
                            delivered_tputs.append(actual_tput)
                            debug_list.append({
                                'path': path_cur, 'de': de_cur,
                                'tput': actual_tput, 'f_path': fi,
                                'con': con,
                            })
                            udtppath(G_work, path_cur, con)
                else:
                    pq.put(cur)
                    break

    avg_fid = _wavg(delivered_fidelities, delivered_tputs)
    return float(total_throughput), float(avg_fid), float(total_consumption), debug_list


def _wavg(fids, tputs):
    total = sum(tputs)
    if total <= 0:
        return 0.0
    return sum(fids[i] * tputs[i] for i in range(len(fids))) / total
