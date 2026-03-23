"""
Figure 7 replication: Throughput / Fidelity / Utilization vs Link Capacity.

Setup (matching paper):
  - US Backbone topology (same as Fig 6)
  - Fixed fidelity threshold F_th = 0.7
  - Fixed request limit = 200
  - Capacity sweep: [10, 30, 50, 70, 90]
  - Single SD pair (nodes_names[0] -> nodes_names[-1])
  - Seeds 300..(300+num_trials-1), same as Fig 6
"""
import networkx as nx
import numpy as np
import copy
import random
import matplotlib.pyplot as plt
import q_leap
import q_path
import sys
import os
import argparse

# Official imports
sys.path.append(os.path.join(os.getcwd(), 'tmp_repo', 'src'))
from qleap import Qleap
from qpath import Qpath
from vtopology import *
from vlink import *

# US Backbone topology (identical to test_fig6.py)
EDGES = [
    ('Vancouver', 'Seattle'), ('Seattle', 'Portland'), ('Seattle', 'Salt Lake City'),
    ('Portland', 'San Francisco'), ('Salt Lake City', 'Denver'), ('Salt Lake City', 'Los Angeles'),
    ('San Francisco', 'Los Angeles'), ('San Francisco', 'Denver'), ('Los Angeles', 'San Diego'),
    ('San Diego', 'Phoenix'), ('Phoenix', 'Denver'), ('Phoenix', 'Houston'),
    ('Denver', 'Kansas City'), ('Denver', 'Dallas'), ('Houston', 'Dallas'),
    ('Houston', 'New Orleans'), ('New Orleans', 'Jacksonville'), ('Jacksonville', 'Miami'),
    ('Jacksonville', 'Atlanta'), ('Atlanta', 'Miami'), ('Atlanta', 'Charlotte'),
    ('Atlanta', 'Nashville'), ('Charlotte', 'Washington DC'), ('Washington DC', 'Richmond'),
    ('Washington DC', 'Philadelphia'), ('Richmond', 'Atlanta'), ('Philadelphia', 'New York City'),
    ('New York City', 'Boston'), ('New York City', 'Cleveland'), ('Boston', 'Montreal'),
    ('Montreal', 'Toronto'), ('Toronto', 'Cleveland'), ('Toronto', 'Minneapolis'),
    ('Cleveland', 'Pittsburgh'), ('Pittsburgh', 'Washington DC'), ('Pittsburgh', 'Chicago'),
    ('Chicago', 'Detroit'), ('Chicago', 'Minneapolis'), ('Chicago', 'Indianapolis'),
    ('Detroit', 'Toronto'), ('Indianapolis', 'Louisville'), ('Louisville', 'Nashville'),
    ('Nashville', 'Jackson'), ('Jackson', 'New Orleans'), ('Kansas City', 'Minneapolis'),
    ('Kansas City', 'St Louis'), ('St Louis', 'Chicago'), ('St Louis', 'Indianapolis'),
    ('St Louis', 'Nashville'), ('Dallas', 'Kansas City'), ('Dallas', 'Memphis'),
    ('Memphis', 'Nashville'), ('Memphis', 'Jackson')
]


def _per_edge_util(paths, cons_list, capacity):
    """Average per-used-directed-edge utilization — matches paper's Step5_Capacity_Utilization."""
    edge_cons = {}
    for path, cons in zip(paths, cons_list):
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            edge_cons[key] = edge_cons.get(key, 0) + cons[i]
    if not edge_cons:
        return 0.0
    return sum(c / capacity for c in edge_cons.values()) / len(edge_cons)


def run_experiment(num_trials=50, request=200):
    capacities = [10, 30, 50, 70, 90]
    f_th = 0.7

    nodes_names = list(set([u for u, v in EDGES] + [v for u, v in EDGES]))
    src_name, tgt_name = nodes_names[0], nodes_names[-1]

    results = {
        'capacity': capacities,
        'off_qpath_tput': [], 'our_qpath_tput': [],
        'off_qpath_fid':  [], 'our_qpath_fid':  [],
        'off_qpath_cons': [], 'our_qpath_cons': [],
        'off_qleap_tput': [], 'our_qleap_tput': [],
        'off_qleap_fid':  [], 'our_qleap_fid':  [],
        'off_qleap_cons': [], 'our_qleap_cons': [],
    }

    for capacity in capacities:
        print(f"--- Testing Capacity: {capacity} ---")
        trial_data = {k: [] for k in results if k != 'capacity'}
        total_net_cap = 2 * len(EDGES) * capacity  # directed count × capacity

        for i in range(num_trials):
            seed = 300 + i
            random.seed(seed)
            np.random.seed(seed)

            # Draw per-link fidelities (same distribution as Fig 6)
            edge_data = {}
            for edge in EDGES:
                f = np.random.normal(0.925, 0.05)
                f = max(0.85, min(1.0, f))
                edge_data[edge] = {'fidelity': f, 'weight': capacity}

            # --- Build official topology ---
            off_nodes = list(range(len(nodes_names)))
            off_edges = []
            for (u, v), d in edge_data.items():
                u_int = nodes_names.index(u)
                v_int = nodes_names.index(v)
                l1 = Link(u_int, v_int, d['weight'], d['fidelity'], 1, True)
                l2 = Link(v_int, u_int, d['weight'], d['fidelity'], 1, True)
                l1.calftable(); l2.calftable()
                off_edges.append(l1); off_edges.append(l2)

            g_off = Vtopo().creatvtopo([off_nodes, off_edges])
            src_idx = nodes_names.index(src_name)
            tgt_idx = nodes_names.index(tgt_name)

            try:
                # Official Q-LEAP
                off_leap_res = Qleap().alg2(
                    copy.deepcopy(g_off), src_idx, tgt_idx, f_th, request)
                off_leap_paths = [[nodes_names[idx] for idx in p] for p in off_leap_res[0]]
                off_leap_de    = off_leap_res[1]
                off_leap_fids  = off_leap_res[2]
                off_leap_cons_list = off_leap_res[3]
                off_leap_tputs = off_leap_res[4]

                valid = [j for j, f in enumerate(off_leap_fids) if f >= f_th - 1e-9]
                tot_th = sum(off_leap_tputs[j] for j in valid)
                avg_f  = (sum(round(float(off_leap_fids[j]), 2) * off_leap_tputs[j]
                              for j in valid) / tot_th) if tot_th > 0 else 0.0
                tot_cons = sum(sum(c) for c in off_leap_cons_list)
                trial_data['off_qleap_tput'].append(float(tot_th))
                trial_data['off_qleap_fid'].append(float(avg_f))
                trial_data['off_qleap_cons'].append(_per_edge_util(off_leap_paths, off_leap_cons_list, capacity))

                # Official Q-PATH
                off_path_res = Qpath().alg1(
                    copy.deepcopy(g_off), src_idx, tgt_idx, f_th, request, 1, 1)
                off_path_paths = [[nodes_names[idx] for idx in p] for p in off_path_res[0]]
                off_path_de    = off_path_res[1]
                off_path_fids  = off_path_res[2]
                off_path_cons_list = off_path_res[3]
                off_path_tputs = off_path_res[4]

                valid = [j for j, f in enumerate(off_path_fids) if f >= f_th - 1e-9]
                tot_th = sum(off_path_tputs[j] for j in valid)
                avg_f  = (sum(round(float(off_path_fids[j]), 2) * off_path_tputs[j]
                              for j in valid) / tot_th) if tot_th > 0 else 0.0
                tot_cons = sum(sum(c) for c in off_path_cons_list)
                trial_data['off_qpath_tput'].append(float(tot_th))
                trial_data['off_qpath_fid'].append(float(avg_f))
                trial_data['off_qpath_cons'].append(_per_edge_util(off_path_paths, off_path_cons_list, capacity))

            except Exception as e:
                print(f"  [Error trial {i}]: {e}")
                continue

            # --- Build our topology ---
            G_our = nx.Graph()
            for (u, v), d in edge_data.items():
                G_our.add_edge(u, v, fidelity=d['fidelity'], weight=d['weight'])

            # Our Q-LEAP
            our_leap_th, our_leap_fid, our_leap_cons, our_leap_dbg = q_leap.compute_metrics(
                copy.deepcopy(G_our), src_name, tgt_name, f_th, capacity, {'request': request})
            our_leap_fid = round(float(our_leap_fid), 2)
            trial_data['our_qleap_tput'].append(float(our_leap_th))
            trial_data['our_qleap_fid'].append(float(our_leap_fid))
            trial_data['our_qleap_cons'].append(_per_edge_util(
                [d['path'] for d in our_leap_dbg],
                [d['con'] for d in our_leap_dbg], capacity))

            # Our Q-PATH
            our_path_th, our_path_fid, our_path_cons, our_path_dbg = q_path.compute_metrics(
                copy.deepcopy(G_our), src_name, tgt_name, f_th, capacity, {'request': request})
            our_path_fid = round(float(our_path_fid), 2)
            trial_data['our_qpath_tput'].append(float(our_path_th))
            trial_data['our_qpath_fid'].append(float(our_path_fid))
            trial_data['our_qpath_cons'].append(_per_edge_util(
                [d['path'] for d in our_path_dbg],
                [d['con'] for d in our_path_dbg], capacity))

            # --- Detailed debug for trial 0 ---
            if i == 0:
                print(f"\n  DETAILED DEBUG Trial 0: cap={capacity}, f_th={f_th}, req={request}")
                print(f"  Src: {src_name}  Tgt: {tgt_name}")
                print(f"  LEAP Off Paths: {off_leap_paths}")
                print(f"  LEAP Our Paths: {[d['path'] for d in our_leap_dbg]}")
                print(f"  LEAP Off de:    {off_leap_de}")
                print(f"  LEAP Our de:    {[d['de'] for d in our_leap_dbg]}")
                print(f"  LEAP Off Tput:  {off_leap_tputs}")
                print(f"  LEAP Our Tput:  {[d['tput'] for d in our_leap_dbg]}")
                print(f"  PATH Off Paths: {off_path_paths}")
                print(f"  PATH Our Paths: {[d['path'] for d in our_path_dbg]}")
                print(f"  PATH Off de:    {off_path_de}")
                print(f"  PATH Our de:    {[d['de'] for d in our_path_dbg]}")
                print(f"  PATH Off Tput:  {off_path_tputs}")
                print(f"  PATH Our Tput:  {[d['tput'] for d in our_path_dbg]}")
                print()

        # Average over trials
        for k in trial_data:
            results[k].append(np.mean(trial_data[k]) if trial_data[k] else 0.0)

    # Parity table
    print("\n" + "=" * 140)
    print(f"{'Cap':<6} | {'Alg':<8} | {'Tput(Off)':<10} | {'Tput(Our)':<10} | "
          f"{'Fid(Off)':<10} | {'Fid(Our)':<10} | {'Util(Off)':<10} | {'Util(Our)':<10} | {'D_Tput':<8}")
    print("-" * 140)
    for i, cap in enumerate(capacities):
        d_leap = results['off_qleap_tput'][i] - results['our_qleap_tput'][i]
        d_path = results['off_qpath_tput'][i] - results['our_qpath_tput'][i]
        print(f"{cap:<6} | {'LEAP':<8} | {results['off_qleap_tput'][i]:<10.4f} | "
              f"{results['our_qleap_tput'][i]:<10.4f} | {results['off_qleap_fid'][i]:<10.4f} | "
              f"{results['our_qleap_fid'][i]:<10.4f} | {results['off_qleap_cons'][i]:<10.4f} | "
              f"{results['our_qleap_cons'][i]:<10.4f} | {d_leap:<8.4f}")
        print(f"{'':<6} | {'PATH':<8} | {results['off_qpath_tput'][i]:<10.4f} | "
              f"{results['our_qpath_tput'][i]:<10.4f} | {results['off_qpath_fid'][i]:<10.4f} | "
              f"{results['our_qpath_fid'][i]:<10.4f} | {results['off_qpath_cons'][i]:<10.4f} | "
              f"{results['our_qpath_cons'][i]:<10.4f} | {d_path:<8.4f}")
    print("=" * 140 + "\n")

    return results


def plot_results(results):
    caps = results['capacity']
    plt.figure(figsize=(18, 5))

    plt.subplot(1, 3, 1)
    plt.plot(caps, results['off_qpath_tput'], 'r-o', label='Off Q-PATH')
    plt.plot(caps, results['our_qpath_tput'], 'r--', marker='x', label='Our Q-PATH')
    plt.plot(caps, results['off_qleap_tput'], 'b-o', label='Off Q-LEAP')
    plt.plot(caps, results['our_qleap_tput'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Link Capacity')
    plt.ylabel('Avg Throughput')
    plt.title('Throughput vs Capacity ($F_{th}=0.7$)')
    plt.legend()

    plt.subplot(1, 3, 2)
    plt.plot(caps, results['off_qpath_fid'], 'r-o', label='Off Q-PATH')
    plt.plot(caps, results['our_qpath_fid'], 'r--', marker='x', label='Our Q-PATH')
    plt.plot(caps, results['off_qleap_fid'], 'b-o', label='Off Q-LEAP')
    plt.plot(caps, results['our_qleap_fid'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Link Capacity')
    plt.ylabel('Avg Delivered Fidelity')
    plt.title('Fidelity vs Capacity ($F_{th}=0.7$)')
    plt.legend()

    plt.subplot(1, 3, 3)
    plt.plot(caps, results['off_qpath_cons'], 'r-o', label='Off Q-PATH')
    plt.plot(caps, results['our_qpath_cons'], 'r--', marker='x', label='Our Q-PATH')
    plt.plot(caps, results['off_qleap_cons'], 'b-o', label='Off Q-LEAP')
    plt.plot(caps, results['our_qleap_cons'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Link Capacity')
    plt.ylabel('Network Resource Utilization')
    plt.title('Utilization vs Capacity ($F_{th}=0.7$)')
    plt.legend()

    plt.tight_layout()
    plt.savefig('fig7_replication.png')
    print("Plot saved as 'fig7_replication.png'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--request", type=int, default=200)
    args = parser.parse_args()

    res = run_experiment(num_trials=args.trials, request=args.request)
    plot_results(res)
