import os, math
import networkx as nx

# Initialise terminal size for printing
try:
    Tlen = os.get_terminal_size().columns
except OSError:
    Tlen = 80

def get_purification_fidelity(x1, x2, model='bbpssw'):
    """Return the fidelity of the final pair.
    
    Models:
    - 'bbpssw': Standard BBPSSW formula used in paper Eq. 1
    - 'isotropic': DEJMPS / Isotropic state formula used in GitHub repo (throughput.py)
    """    
    if model == 'bbpssw':
        return x1 * x2 / (x1 * x2 + (1 - x1) * (1 - x2))
    elif model == 'isotropic':
        # Formula from official code (isotropic state, DEJMPS protocol):
        # F' = (F^2 + 1/9 * (1-F)^2) / (F^2 + 2/3 * F * (1-F) + 5/9 * (1-F)^2)
        # Note: Official code implementation assuming x1 = x2 = F
        f = x1
        num = f**2 + (1.0 / 9.0) * (1 - f)**2
        den = f**2 + (2.0 / 3.0) * f * (1 - f) + (5.0 / 9.0) * (1 - f)**2
        return num / den
    return x1 * x2 / (x1 * x2 + (1 - x1) * (1 - x2))

def get_purification_success_prob(f1, f2=None, model='isotropic'):
    """Returns the success probability of a single purification round.
    
    Args:
        f1: Fidelity of the first (purified) pair.
        f2: Fidelity of the second (auxiliary) pair. If None, uses f1 (symmetric).
        model: 'isotropic' for DEJMPS symmetric, 'bbpssw' for BBPSSW asymmetric.
    """
    if model == 'bbpssw':
        # Asymmetric BBPSSW: p = f1*f2 + (1-f1)*(1-f2)
        # Matches official code: calpgn(t1, t2)
        if f2 is None:
            f2 = f1
        return f1 * f2 + (1 - f1) * (1 - f2)
    # Isotropic/DEJMPS symmetric: F^2 + 2/3 * F * (1-F) + 5/9 * (1-F)^2
    return f1**2 + (2.0 / 3.0) * f1 * (1 - f1) + (5.0 / 9.0) * (1 - f1)**2

def get_edge_purification_prob(f_initial, pairs_consumed, model='bbpssw'):
    """Compute exact product of per-round success probabilities for an edge.
    
    Mirrors the official code's recursive calp() in throughput.py.
    Each round purifies the current pair with a raw pair, and the success
    probability for that round depends on both fidelities.
    
    Args:
        f_initial: Raw link fidelity.
        pairs_consumed: Total pairs consumed (1 = no purification).
        model: Purification model ('bbpssw' or 'isotropic').
        
    Returns:
        Product of per-round success probabilities.
    """
    if pairs_consumed <= 1:
        return 1.0
    
    # Build fidelity table (like official ftable)
    f_curr = f_initial
    fidelities = [f_initial]  # fidelities[k] = fidelity after k rounds of purification
    for _ in range(pairs_consumed - 1):
        f_curr = get_purification_fidelity(f_curr, f_initial, model=model)
        fidelities.append(f_curr)
    
    # Compute product of per-round success probabilities
    # Round k purifies fidelities[k-1] with f_initial
    prob = 1.0
    for k in range(1, pairs_consumed):
        prob *= get_purification_success_prob(fidelities[k-1], f_initial, model=model)
    
    return prob

def get_purification_cost(f1, f2, c, debug=False, model='bbpssw'):
    """Calculate the maximum fidelity of the current edge after C-1 iterations.
    
    Args:
        f1: Initial fidelity.
        f2: Auxiliary pair fidelity.
        c: Edge capacity (total pairs available).
    """    
    F_total = []
    F_improve = []
    fnew = f1

    while c > 1:
        c -= 1
        fnew = get_purification_fidelity(f1, f2, model=model)
        F_total.append(fnew)
        F_improve.append(fnew - f1)
        f1 = fnew

        if debug:
            print(f' New purification fidelity: {f1}')
            print(f' Fidelity improvement: {F_improve[-1]}')
            print(f' Capacity after purification: {c}')
            print("-" * Tlen)

    return F_total, F_improve

def delete_edges(G: nx.Graph, F_min, debug=False, model='bbpssw'):
    """Removes edges from G that cannot reach F_min even with full purification."""
    edges_to_remove = []
    for edge in G.edges(data=True):
        c = edge[2]['weight']
        f1 = edge[2]['fidelity']
        f2 = f1

        if debug:
            text = f' Edge: {edge[:2]} Capacity: {c} Initial fidelity: {f1} '
            decor = "=" * (math.floor((Tlen - len(text)) / 2))
            print(decor + text + decor)

        # Max possible purification for this edge
        F_total, _ = get_purification_cost(f1, f2, c, debug=False, model=model)
        
        max_f = F_total[-1] if F_total else f1
        if max_f < F_min:
            if debug:
                print(f' *** Removing edge {edge[:2]} with max fidelity: {max_f}')
            edges_to_remove.append(edge)

    G.remove_edges_from(edges_to_remove)

def get_required_purification(f_initial, f_target, model='bbpssw'):
    """Returns minimum pairs needed to reach f_target on a single link."""
    if f_initial >= f_target:
        return 1
    c = 1
    f_current = f_initial
    while f_current < f_target:
        f_next = get_purification_fidelity(f_current, f_initial, model=model)
        # Check for plateau or diminishing returns
        if f_next <= f_current + 1e-9:
            return float('inf')
        f_current = f_next
        c += 1
    return c

def get_end_to_end_fidelity(path_fidelities, model='product'):
    """Calculates end-to-end fidelity for a path.
    
    Models:
    - 'swapping': Equation 3 from paper (0.25 + 0.75 * prod((4Fi-1)/3))
    - 'product': Simple product model used in GitHub repo (prod(Fi))
    """
    if not path_fidelities:
        return 0.0
    n = len(path_fidelities)
    if n == 1:
        return path_fidelities[0]
        
    if model == 'product':
        return math.prod(path_fidelities)
        
    # 'swapping' (Paper Equation 3)
    prod = 1.0
    for F_i in path_fidelities:
        prod *= (4.0 * F_i - 1.0) / 3.0
    return 0.25 + 0.75 * prod

def get_purified_fidelity_for_budget(f_initial, pairs_consumed, model='bbpssw'):
    """Computes final fidelity after consuming X pairs on a single edge."""
    if pairs_consumed <= 1:
        return f_initial
    f_current = f_initial
    for _ in range(pairs_consumed - 1):
        f_current = get_purification_fidelity(f_current, f_initial, model=model)
    return f_current
