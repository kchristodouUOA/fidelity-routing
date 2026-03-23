import networkx as nx
import numpy as np
import os, math
import throughput_official as th

def compute_metrics(G, source, target, f_th, capacity, config):
    """Compute Q-LEAP metrics for a single SD pair (Iterative multi-path)."""
    total_throughput = 0.0
    total_consumption = 0.0
    delivered_fidelities = []
    delivered_tputs = []
    debug_list = []
    
    G_work = G.copy()
    request_limit = float(config.get('request', 50))

    while total_throughput < request_limit - 1e-9:
        # 1. Official LEAP uses Max Fidelity Search (topoljbf)
        for u, v, d in G_work.edges(data=True):
            # Q-LEAP uses weights directly proportional to fidelity for max product
            d['fid_weight'] = max(d.get('fidelity', 0.5), 1e-6)
        
        try:
            # Dijkstra for max product of 'fidelity'
            # We use -log(f) for sum minimization
            for u, v, d in G_work.edges(data=True):
                d['neg_log_f'] = -math.log(d['fid_weight'])
                
            path = nx.shortest_path(G_work, source=source, target=target, weight='neg_log_f')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            break
            
        L = len(path) - 1
        link_fids = [G_work[path[i]][path[i+1]]['fidelity'] for i in range(L)]
        
        # 2. Purification decisions (LEAP Algorithm 2)
        # CRITICAL: Official only purifies if path f < fth
        raw_f = math.prod(link_fids)
        if raw_f >= f_th - 1e-9:
            de = [0] * L
        else:
            fave = f_th**(1.0/L) if L > 0 else f_th
            de = th.cal_pud(link_fids, f_th) # Note: th.cal_pud uses f_ave internally
            
        f_path = th.cal_epathf([th.calfgn_n(link_fids[i], de[i]) for i in range(L)])
        
        # 3. Capacity and Throughput (Bottleneck model)
        n_potential = int(min(G_work[path[i]][path[i+1]]['weight'] // (de[i] + 1) for i in range(L)))
        if n_potential <= 0:
            for i in range(L):
                if G_work[path[i]][path[i+1]]['weight'] < (de[i] + 1):
                    G_work.remove_edge(path[i], path[i+1])
            continue
            
        t_per_vlink = th.caletp_path(G_work, path, de)
        if t_per_vlink <= 0:
            G_work.remove_edge(path[0], path[1])
            continue
            
        remaining_demand = request_limit - total_throughput
        n_needed = math.ceil(remaining_demand / t_per_vlink)
        n_actual = min(n_potential, n_needed)
        
        actual_tput = n_actual * t_per_vlink
        
        # Commit
        if f_path >= f_th - 1e-9:
            total_throughput += actual_tput
            delivered_fidelities.append(f_path)
            delivered_tputs.append(actual_tput)
        con = [n_actual * (de[i] + 1) for i in range(L)]
        debug_list.append({
            'path': path,
            'de': de,
            'tput': actual_tput,
            'f_path': f_path,
            'con': con,
        })

        for i in range(L):
            usage = con[i]
            G_work[path[i]][path[i+1]]['weight'] -= usage
            total_consumption += usage
            if G_work[path[i]][path[i+1]]['weight'] < 1.0:
                G_work[path[i]][path[i+1]]['weight'] = 0.0
                G_work.remove_edge(path[i], path[i+1])

    avg_fid = sum(delivered_fidelities[i] * delivered_tputs[i] for i in range(len(delivered_tputs))) / total_throughput if total_throughput > 0 else 0.0
    return float(total_throughput), float(avg_fid), float(total_consumption), debug_list
