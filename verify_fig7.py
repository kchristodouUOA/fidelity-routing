import networkx as nx
import numpy as np
import quantum
import json
import math

def get_q_path_cost(G, path, f_th, capacity, config):
    l = len(path) - 1
    f_inits = [G[path[i]][path[i+1]]['fidelity'] for i in range(l)]
    dp = [{} for _ in range(l + 1)]
    p_model = config['purification']
    f_model = config['fidelity_e2e']
    
    for p in range(1, capacity + 1):
        f_pure = quantum.get_purified_fidelity_for_budget(f_inits[0], p, model=p_model)
        prob = quantum.get_purification_success_prob(f_pure, model=p_model)**(p-1)
        dp[1][p] = (f_pure, prob, p)
        
    for i in range(2, l + 1):
        for p_total in range(i, capacity + 1):
            max_f = -1.0
            best_prob = 0.0
            best_max_p = float('inf')
            
            for j in range(1, p_total - (i - 1) + 1):
                if p_total - j not in dp[i-1]:
                    continue
                f_prev, prob_prev, prev_max_p = dp[i-1][p_total - j]
                f_curr_hop = quantum.get_purified_fidelity_for_budget(f_inits[i-1], j, model=p_model)
                prob_curr = quantum.get_purification_success_prob(f_curr_hop, model=p_model)**(j-1)
                f_comb = quantum.get_end_to_end_fidelity([f_prev, f_curr_hop], model=f_model)
                
                if f_comb > max_f:
                    max_f = f_comb
                    best_prob = prob_prev * prob_curr
                    best_max_p = max(prev_max_p, j)
            
            if max_f >= 0:
                dp[i][p_total] = (max_f, best_prob, best_max_p)
            
    for p in range(l, capacity + 1):
        if p in dp[l]:
            f_achieved, prob_achieved, max_p = dp[l][p]
            if f_achieved >= f_th: 
                return p, max_p, f_achieved, prob_achieved
    return float('inf'), float('inf'), 0.0, 0.0

def get_q_leap_cost(G, path, f_th, capacity, config):
    l = len(path) - 1
    f_inits = [G[path[i]][path[i+1]]['fidelity'] for i in range(l)]
    p_model = config['purification']
    f_model = config['fidelity_e2e']
    
    if f_model == 'swapping':
        if f_th <= 0.25:
            F_avg = 0.5
        else:
            req_W = math.pow((f_th - 0.25) / 0.75, 1.0 / l)
            F_avg = (3.0 * req_W + 1.0) / 4.0
    else:
        F_avg = math.pow(f_th, 1.0 / l)
        
    total_cost = 0
    max_p = 0
    total_prob = 1.0
    f_achieved_list = []
    
    for f_init in f_inits:
        req = quantum.get_required_purification(f_init, F_avg, model=p_model)
        if req > capacity or req == float('inf'):
            return float('inf'), float('inf'), 0.0, 0.0
            
        total_cost += req
        max_p = max(max_p, req)
        
        f_pure = quantum.get_purified_fidelity_for_budget(f_init, req, model=p_model)
        f_achieved_list.append(f_pure)
        
        if req > 1:
            prob_hop = quantum.get_purification_success_prob(f_pure, model=p_model)**(req - 1)
        else:
            prob_hop = 1.0
            
        total_prob *= prob_hop
        
    f_e2e = quantum.get_end_to_end_fidelity(f_achieved_list, model=f_model)
    if f_e2e < f_th - 1e-5: 
        return float('inf'), float('inf'), 0.0, 0.0
        
    return total_cost, max_p, f_e2e, total_prob

def simulate(mu, sigma, trials, capacities, f_th, config, algo='qpath'):
    print(f"\n--- Simulation Fig7: {algo.upper()} | {config['purification'].upper()} | f_th={f_th} | Trials={trials} ---")
    print(f"{'Cap':<6} | {'Tput':<8} | {'Fid':<8} | {'Util':<8}")
    print("-" * 40)
    
    results = {
        'capacity': capacities,
        'throughput': [],
        'fidelity': [],
        'utilization': []
    }

    np.random.seed(42)
    f1_vals = np.clip(np.random.normal(mu, sigma, trials), 0.5, 0.999)
    f2_vals = np.clip(np.random.normal(mu, sigma, trials), 0.5, 0.999)

    for cap in capacities:
        t_list, f_list, u_list = [], [], []
        
        for idx in range(trials):
            G = nx.Graph()
            G.add_edge('S', 'R', fidelity=f1_vals[idx])
            G.add_edge('R', 'D', fidelity=f2_vals[idx])
            
            num_edges = 2
            
            if algo == 'qpath':
                p_total, max_p, fid, prob = get_q_path_cost(G, ['S', 'R', 'D'], f_th, cap, config)
            else:
                p_total, max_p, fid, prob = get_q_leap_cost(G, ['S', 'R', 'D'], f_th, cap, config)
                
            if p_total != float('inf') and max_p > 0:
                flows = math.floor(cap / max_p)
                tput = flows * prob if config['use_probs'] else flows
                
                # Pure local algorithmic utilization computation: used / available
                used_pairs = flows * p_total
                utilization = used_pairs / (cap * num_edges)
                
                t_list.append(tput)
                f_list.append(fid)
                u_list.append(utilization)
            else:
                t_list.append(0)
                f_list.append(0)
                u_list.append(0)
                
        mean_t = np.mean(t_list)
        mean_f = np.mean(f_list)
        mean_u = np.mean(u_list)
        
        results['throughput'].append(mean_t)
        results['fidelity'].append(mean_f)
        results['utilization'].append(mean_u)
        
        print(f"{cap:<6} | {mean_t:<8.3f} | {mean_f:<8.3f} | {mean_u:<8.3f}")
        
    return results

if __name__ == "__main__":
    capacities = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    f_th_fixed = 0.7
    
    cfg_paper = {'purification': 'bbpssw', 'fidelity_e2e': 'swapping', 'use_probs': True}
    res_paper_qpath = simulate(0.8, 0.1, 200, capacities, f_th_fixed, cfg_paper, algo='qpath')
    res_paper_qleap = simulate(0.8, 0.1, 200, capacities, f_th_fixed, cfg_paper, algo='qleap')
    
    cfg_repo = {'purification': 'isotropic', 'fidelity_e2e': 'product', 'use_probs': True}
    res_repo_qpath = simulate(0.9, 0.1, 200, capacities, f_th_fixed, cfg_repo, algo='qpath')
    res_repo_qleap = simulate(0.9, 0.1, 200, capacities, f_th_fixed, cfg_repo, algo='qleap')
    
    with open("fig7_data.json", "w") as f:
        json.dump({
            'paper_qpath': res_paper_qpath, 'paper_qleap': res_paper_qleap, 
            'repo_qpath': res_repo_qpath, 'repo_qleap': res_repo_qleap
        }, f, indent=4)
    print("\nResults saved to fig7_data.json")
