import numpy as np

def calpgn(f1, f2):
    """Success probability of one purification round (BBPSSW)."""
    return f1 * f2 + (1 - f1) * (1 - f2)

def calfgn(f1, f2):
    """Fidelity after one purification round (BBPSSW)."""
    # Protect against zero denominator
    denom = f1 * f2 + (1 - f1) * (1 - f2)
    if denom <= 0: return 0.0
    return (f1 * f2) / denom

def calfgn_n(f_init, n):
    """Fidelity after n rounds of purification with identical links."""
    f = f_init
    for _ in range(n):
        f = calfgn(f, f_init)
    return f

def calp(f_init, n_purify):
    """Total success probability for a link with n_purify rounds (Linear).
    Following official calp() recursive logic.
    """
    if n_purify == 0:
        return 1.0
    
    p_acc = 1.0
    f_iter = f_init
    for _ in range(n_purify):
        p_round = calpgn(f_iter, f_init)
        p_acc *= p_round
        f_iter = calfgn(f_iter, f_init)
    
    return p_acc

def caletp(link_probs):
    """Path success probability (bottleneck link success prob).
    Matching official caletp() in throughput.py.
    """
    if not link_probs:
        return 0.0
    return min(link_probs)

def cal_epathf(link_fidelities):
    """Path end-to-end fidelity (product model)."""
    if not link_fidelities:
        return 0.0
    return np.prod(link_fidelities)

# Purification Heuristics
def cal_pud(link_fids, f_th):
    """LEAP-style: Each link targets fave = f_th^(1/L)."""
    L = len(link_fids)
    f_ave = f_th**(1.0/L) if L > 0 else f_th
    de = []
    for f in link_fids:
        p = 0
        f_curr = f
        while f_curr < f_ave and p < 3: # Official max is often 50 but QLEAP uses small p
            p += 1
            f_curr = calfgn(f_curr, f)
        de.append(p)
    return de

def cal_mostup(link_fids, f_th):
    """PATH-style: Greedy link selection to hit f_th."""
    L = len(link_fids)
    de = [0] * L
    cur_fids = list(link_fids)
    
    while cal_epathf(cur_fids) < f_th:
        best_idx = -1
        max_fid = -1
        for i in range(L):
            f_next = calfgn(cur_fids[i], link_fids[i])
            # Tentative end-to-end fidelity
            test_fids = list(cur_fids)
            test_fids[i] = f_next
            test_e2e = cal_epathf(test_fids)
            if test_e2e > max_fid:
                max_fid = test_e2e
                best_idx = i
        
        if best_idx == -1 or de[best_idx] >= 3: # Cap at 3 for parity
            break
        
        de[best_idx] += 1
        cur_fids[best_idx] = calfgn(cur_fids[best_idx], link_fids[best_idx])
        
    return de

def calpathsumth(n_max, p_path):
    """Expected throughput for a path.
    n_max: Number of flows.
    p_path: Path success probability.
    """
    return n_max * p_path

def caletp_path(G, path, de):
    probs = [calp(G[path[i]][path[i+1]]['fidelity'], de[i]) for i in range(len(path)-1)]
    return caletp(probs)
