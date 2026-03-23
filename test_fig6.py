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
from pud import Pud

def _per_edge_util(paths, cons_list, capacity):
    """Average per-used-directed-edge utilization — matches paper's Step5_Capacity_Utilization.
    Iterates only over edges that appear in at least one committed path (same as the
    official Step5 which skips edges with empty request_ID_on_edge).
    paths: list of paths (each path is a list of node names or indices).
    cons_list: parallel list; cons_list[k][i] = pairs consumed on link i of path k.
    """
    edge_cons = {}
    for path, cons in zip(paths, cons_list):
        for i in range(len(path) - 1):
            key = (path[i], path[i + 1])
            edge_cons[key] = edge_cons.get(key, 0) + cons[i]
    if not edge_cons:
        return 0.0
    return sum(c / capacity for c in edge_cons.values()) / len(edge_cons)


def run_experiment(num_trials=20, capacity=50, request=200):
    # US Backbone Topology
    edges = [
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
    nodes_names = list(set([u for u, v in edges] + [v for u, v in edges]))
    
    f_thresholds = [0.6, 0.7, 0.8, 0.9]
    results = {
        'fth': f_thresholds,
        'off_qpath_tput': [], 'our_qpath_tput': [],
        'off_qpath_fid': [], 'our_qpath_fid': [],
        'off_qpath_cons': [], 'our_qpath_cons': [],
        'off_qleap_tput': [], 'our_qleap_tput': [],
        'off_qleap_fid': [], 'our_qleap_fid': [],
        'off_qleap_cons': [], 'our_qleap_cons': []
    }

    src_name, tgt_name = nodes_names[0], nodes_names[-1]

    for f_th in f_thresholds:
        print(f"--- Testing Fidelity Threshold: {f_th} ---")
        trial_data = {k: [] for k in results.keys() if k != 'fth'}
        
        for i in range(num_trials):
            seed = 300 + i
            random.seed(seed)
            np.random.seed(seed)
            
            # Generate Link Fidelities
            edge_data = {}
            for edge in edges:
                # Based on npj_comparison_scheme_main.py: init()
                f = np.random.normal(0.925, 0.05)
                f = max(0.85, min(1.0, f))
                edge_data[edge] = {'fidelity': f, 'weight': capacity}
            
            total_net_cap = 2 * len(edges) * capacity 
            
            # --- OFFICIAL RUNS ---
            off_nodes = list(range(len(nodes_names)))
            off_edges = []
            for (u, v), d in edge_data.items():
                u_int, v_int = nodes_names.index(u), nodes_names.index(v)
                l1 = Link(u_int, v_int, d['weight'], d['fidelity'], 1, True)
                l2 = Link(v_int, u_int, d['weight'], d['fidelity'], 1, True)
                l1.calftable(); l2.calftable()
                off_edges.append(l1); off_edges.append(l2)
            
            v_topo = Vtopo()
            g_off = v_topo.creatvtopo([off_nodes, off_edges])
            
            try:
                # Official Q-LEAP
                off_leap = Qleap()
                off_leap_res = off_leap.alg2(copy.deepcopy(g_off), nodes_names.index(src_name), nodes_names.index(tgt_name), f_th, request)
                # Extract results with official logic
                off_leap_paths = [[nodes_names[idx] for idx in p] for p in off_leap_res[0]]
                off_leap_de = off_leap_res[1]
                fids, cons_vals, thputs = off_leap_res[2], off_leap_res[3], off_leap_res[4]
                off_leap_th = thputs
                
                # Filtering and Throughput (run_qleap.py Step4)
                valid_indices = [j for j in range(len(thputs)) if fids[j] >= f_th]
                tot_th = sum(thputs[j] for j in valid_indices)
                trial_data['off_qleap_tput'].append(float(tot_th))
                
                # Fidelity (run_qleap.py Step4 rounding)
                if tot_th > 0:
                    avg_f = sum(fids[j] * thputs[j] for j in valid_indices) / tot_th
                    trial_data['off_qleap_fid'].append(round(float(avg_f), 2))
                else:
                    trial_data['off_qleap_fid'].append(0.0)
                
                # Utilization: per-used-edge average (matches paper's Step5_Capacity_Utilization)
                utilization = _per_edge_util(off_leap_paths, cons_vals, capacity)
                trial_data['off_qleap_cons'].append(float(utilization))

                # Official Q-PATH
                off_path = Qpath()
                off_path_res = off_path.alg1(copy.deepcopy(g_off), nodes_names.index(src_name), nodes_names.index(tgt_name), f_th, request, 1, 1)
                # Extract results with official logic
                off_path_paths = [[nodes_names[idx] for idx in p] for p in off_path_res[0]]
                off_path_de = off_path_res[1]
                fids, cons_vals, thputs = off_path_res[2], off_path_res[3], off_path_res[4]
                off_path_th = thputs
                
                valid_indices = [j for j in range(len(thputs)) if fids[j] >= f_th]
                tot_th = sum(thputs[j] for j in valid_indices)
                trial_data['off_qpath_tput'].append(float(tot_th))
                
                if tot_th > 0:
                    avg_f = sum(fids[j] * thputs[j] for j in valid_indices) / tot_th
                    trial_data['off_qpath_fid'].append(round(float(avg_f), 2))
                else:
                    trial_data['off_qpath_fid'].append(0.0)
                
                utilization = _per_edge_util(off_path_paths, cons_vals, capacity)
                trial_data['off_qpath_cons'].append(float(utilization))

            except Exception as e:
                print(f"Error in official run: {e}")
                continue

            # --- OUR RUNS ---
            G_our = nx.Graph()
            for (u, v), d in edge_data.items():
                G_our.add_edge(u, v, fidelity=d['fidelity'], weight=d['weight'])
                
            # Our Q-LEAP
            our_leap_th, our_leap_fid, our_leap_cons, our_leap_debug = q_leap.compute_metrics(copy.deepcopy(G_our), src_name, tgt_name, f_th, capacity, {'request': request})
            
            # Fidelity Rounding (to match official)
            our_leap_fid = round(float(our_leap_fid), 2)
            our_leap_util = _per_edge_util(
                [d['path'] for d in our_leap_debug],
                [d['con'] for d in our_leap_debug], capacity)
            
            trial_data['our_qleap_tput'].append(float(our_leap_th))
            trial_data['our_qleap_fid'].append(float(our_leap_fid))
            trial_data['our_qleap_cons'].append(float(our_leap_util)) 

            # Our Q-PATH
            our_path_th, our_path_fid, our_path_cons, our_path_debug = q_path.compute_metrics(copy.deepcopy(G_our), src_name, tgt_name, f_th, capacity, {'request': request})
            
            our_path_fid = round(float(our_path_fid), 2)
            our_path_util = _per_edge_util(
                [d['path'] for d in our_path_debug],
                [d['con'] for d in our_path_debug], capacity)
            
            trial_data['our_qpath_tput'].append(float(our_path_th))
            trial_data['our_qpath_fid'].append(float(our_path_fid))
            trial_data['our_qpath_cons'].append(float(our_path_util))

            if i == 0:
                print(f"\nDETAILED DEBUG Trial 0: f_th={f_th}")
                print(f"  Path Link Fidelities: {[G_our[best_path[j]][best_path[j+1]]['fidelity'] for j in range(len(best_path)-1)] if 'best_path' in locals() else 'N/A'}")
                # For more robustness:
                p0 = off_leap_paths[0] if off_leap_paths else None
                if p0:
                    pfids = [edge_data.get((p0[j], p0[j+1]), edge_data.get((p0[j+1], p0[j])))['fidelity'] for j in range(len(p0)-1)]
                    print(f"  First Path Link Fids: {pfids}")
                    print(f"  Prod: {np.prod(pfids)}")
                
                print(f"  LEAP Off Paths: {off_leap_paths}")
                print(f"  LEAP Our Paths: {[d['path'] for d in our_leap_debug]}")
                print(f"  LEAP Off de:      {off_leap_de}")
                print(f"  LEAP Our de:      {[d['de'] for d in our_leap_debug]}")
                print(f"  LEAP Off Tput: {off_leap_th}")
                print(f"  LEAP Our Tput: {[d['tput'] for d in our_leap_debug]}")
                
                print(f"  PATH Off Paths: {off_path_paths}")
                print(f"  PATH Our Paths: {[d['path'] for d in our_path_debug]}")
                print(f"  PATH Off de:      {off_path_de}")
                print(f"  PATH Our de:      {[d['de'] for d in our_path_debug]}")
                print(f"  PATH Off Tput: {off_path_th}")
                print(f"  PATH Our Tput: {[d['tput'] for d in our_path_debug]}")
            
        # Average results for this f_th
        for k in trial_data.keys():
            results[k].append(np.mean(trial_data[k]) if trial_data[k] else 0.0)

    # Final Parity Table
    print("\n" + "="*140)
    print(f"{'F_th':<6} | {'Alg':<8} | {'Tput(Off)':<10} | {'Tput(Our)':<10} | {'Fid(Off)':<10} | {'Fid(Our)':<10} | {'Util(Off)':<10} | {'Util(Our)':<10} | {'D_Tput':<8}")
    print("-"*140)
    for i, f_th in enumerate(f_thresholds):
        dtp_leap = results['off_qleap_tput'][i] - results['our_qleap_tput'][i]
        dtp_path = results['off_qpath_tput'][i] - results['our_qpath_tput'][i]
        print(f"{f_thresholds[i]:<6} | {'LEAP':<8} | {results['off_qleap_tput'][i]:<10.4f} | {results['our_qleap_tput'][i]:<10.4f} | {results['off_qleap_fid'][i]:<10.4f} | {results['our_qleap_fid'][i]:<10.4f} | {results['off_qleap_cons'][i]:<10.4f} | {results['our_qleap_cons'][i]:<10.4f} | {dtp_leap:<8.4f}")
        print(f"{'':<6} | {'PATH':<8} | {results['off_qpath_tput'][i]:<10.4f} | {results['our_qpath_tput'][i]:<10.4f} | {results['off_qpath_fid'][i]:<10.4f} | {results['our_qpath_fid'][i]:<10.4f} | {results['off_qpath_cons'][i]:<10.4f} | {results['our_qpath_cons'][i]:<10.4f} | {dtp_path:<8.4f}")
    print("="*140 + "\n")

    return results

def plot_results(results):
    fth = results['fth']
    plt.figure(figsize=(18, 5))
    
    # 1. Throughput
    plt.subplot(1, 3, 1)
    plt.plot(fth, results['off_qpath_tput'], 'r-o', label='Off Q-PATH')
    plt.plot(fth, results['our_qpath_tput'], 'r--', marker='x', label='Our Q-PATH')
    plt.plot(fth, results['off_qleap_tput'], 'b-o', label='Off Q-LEAP')
    plt.plot(fth, results['our_qleap_tput'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Fidelity Threshold ($F_{th}$)')
    plt.ylabel('Avg Throughput')
    plt.title('Throughput vs Threshold')
    plt.legend()

    # 2. Fidelity
    plt.subplot(1, 3, 2)
    plt.plot(fth, results['off_qpath_fid'], 'r-o', label='Off Q-PATH')
    plt.plot(fth, results['our_qpath_fid'], 'r--', marker='x', label='Our Q-PATH')
    plt.plot(fth, results['off_qleap_fid'], 'b-o', label='Off Q-LEAP')
    plt.plot(fth, results['our_qleap_fid'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Fidelity Threshold ($F_{th}$)')
    plt.ylabel('Avg Delivered Fidelity')
    plt.title('Fidelity vs Threshold')
    plt.legend()

    # 3. Network Resource Utilization
    plt.subplot(1, 3, 3)
    plt.plot(fth, results['off_qpath_cons'], 'r-o', label='Off Q-PATH')
    plt.plot(fth, results['our_qpath_tput'] if False else results['our_qpath_cons'], 'r--', marker='x', label='Our Q-PATH') # Fix logic
    plt.plot(fth, results['off_qleap_cons'], 'b-o', label='Off Q-LEAP')
    plt.plot(fth, results['our_qleap_cons'], 'b--', marker='x', label='Our Q-LEAP')
    plt.xlabel('Fidelity Threshold ($F_{th}$)')
    plt.ylabel('Network Resource Utilization')
    plt.title('Utilization vs Threshold')
    plt.legend()

    plt.tight_layout()
    plt.savefig('fig6_replication.png')
    print("Plot saved as 'fig6_replication.png'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()
    
    res = run_experiment(num_trials=args.trials)
    plot_results(res)
