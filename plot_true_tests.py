import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# FIGURE 6
df1 = pd.read_csv('tmp_repo/true_t1_fig6.txt', sep=r'\s+')

fig, axs = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle('Raw Original Script (t1.py): Figure 6 (Fidelity Threshold vs Metrics)', fontsize=16)

axs[0].plot(df1['fth'], df1['throughput_alg1'], marker='o', label='Q-PATH (t1)')
axs[0].plot(df1['fth'], df1['throughput_alg2'], marker='x', linestyle='--', label='Q-LEAP (t1)')
axs[0].set_title('(a) Throughput')
axs[0].set_xlabel('Fidelity Threshold')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(df1['fth'], df1['avgFidelity_alg1'], marker='s', label='Q-PATH (t1)')
axs[1].plot(df1['fth'], df1['avgFidelity_alg2'], marker='+', linestyle='--', label='Q-LEAP (t1)')
axs[1].set_title('(b) Average E2E Fidelity')
axs[1].set_xlabel('Fidelity Threshold')
axs[1].legend()
axs[1].grid(True)

# Calculate utilization proxy (just consumption for now scaled down or raw)
# Let's plot raw consumption or a scaled version. Assuming US backbone has ~42 edges, capacity=50. Max space = 42 * 50 = 2100.
util1 = df1['consumption_alg1'] / (50 * 42)
util2 = df1['consumption_alg2'] / (50 * 42)

axs[2].plot(df1['fth'], util1, marker='^', label='Q-PATH (t1)')
axs[2].plot(df1['fth'], util2, marker='v', linestyle='--', label='Q-LEAP (t1)')
axs[2].set_title('(c) Network Resource Utilization (Proxy)')
axs[2].set_xlabel('Fidelity Threshold')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.savefig('true_t1_fig6_plot.png', dpi=300)
plt.close()

# FIGURE 7
df2 = pd.read_csv('tmp_repo/true_t2_fig7.txt', sep=r'\s+')

fig, axs = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle('Raw Original Script (t2.py): Figure 7 (Channel Capacity vs Metrics)', fontsize=16)

axs[0].plot(df2['fth'], df2['throughput_alg1'], marker='o', label='Q-PATH (t2)')
axs[0].plot(df2['fth'], df2['throughput_alg2'], marker='x', linestyle='--', label='Q-LEAP (t2)')
axs[0].set_title('(a) Throughput')
axs[0].set_xlabel('Channel Capacity')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(df2['fth'], df2['avgFidelity_alg1'], marker='s', label='Q-PATH (t2)')
axs[1].plot(df2['fth'], df2['avgFidelity_alg2'], marker='+', linestyle='--', label='Q-LEAP (t2)')
axs[1].set_title('(b) Average E2E Fidelity')
axs[1].set_xlabel('Channel Capacity')
axs[1].legend()
axs[1].grid(True)

util1_c = df2['consumption_alg1'] / (df2['fth'] * 42)
util2_c = df2['consumption_alg2'] / (df2['fth'] * 42)

axs[2].plot(df2['fth'], util1_c, marker='^', label='Q-PATH (t2)')
axs[2].plot(df2['fth'], util2_c, marker='v', linestyle='--', label='Q-LEAP (t2)')
axs[2].set_title('(c) Network Resource Utilization (Proxy)')
axs[2].set_xlabel('Channel Capacity')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.savefig('true_t2_fig7_plot.png', dpi=300)
plt.close()

print("True test script plots generated.")
