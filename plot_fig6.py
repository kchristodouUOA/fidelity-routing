import json
import matplotlib.pyplot as plt
import os

# Ensure we're reading the generated data
data_file = 'fig6_data.json'
if not os.path.exists(data_file):
    print(f"Error: {data_file} not found. Please run verify_fig6.py first.")
    exit(1)

with open(data_file, 'r') as f:
    data = json.load(f)

res_pq = data['paper_qpath']
res_pl = data['paper_qleap']
res_rq = data['repo_qpath']
res_rl = data['repo_qleap']

f_ths = res_pq['f_th']

fig, axs = plt.subplots(1, 3, figsize=(15, 5))

def plot_metric(ax, metric, title, ylabel):
    ax.plot(f_ths, res_pq[metric], marker='o', linestyle='-', color='blue', label='Q-PATH (Paper)')
    ax.plot(f_ths, res_pl[metric], marker='s', linestyle='--', color='blue', label='Q-LEAP (Paper)')
    ax.plot(f_ths, res_rq[metric], marker='^', linestyle='-', color='red', label='Q-PATH (Repo)')
    ax.plot(f_ths, res_rl[metric], marker='d', linestyle='--', color='red', label='Q-LEAP (Repo)')
    
    ax.set_xlabel('Fidelity Threshold')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True)
    ax.legend()

# (a) Throughput
plot_metric(axs[0], 'throughput', '(a) Throughput', 'Throughput (qbits/slot)')

# (b) Average E2E Fidelity
plot_metric(axs[1], 'fidelity', '(b) Average E2E Fidelity', 'Average E2E Fidelity')

# (c) Network Resource Utilization
plot_metric(axs[2], 'utilization', '(c) Network Resource Utilization', 'Network Resource Utilization')

plt.tight_layout()
plt.savefig('fig6_plot.png', dpi=300)
print("Plot successfully saved to fig6_plot.png")
