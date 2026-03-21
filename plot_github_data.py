import matplotlib.pyplot as plt

def parse_line(line):
    line = line.strip().replace('np.float64(', '').replace('np.int64(', '').replace(')', '')
    return eval(line)

def read_data(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    x = parse_line(lines[1])
    tput = parse_line(lines[3])
    fid = parse_line(lines[5])
    util = parse_line(lines[7])
    return x, tput, fid, util

# --- FIGURE 6 (Fidelity Threshold) ---
x_qp6, tput_qp6, fid_qp6, util_qp6 = read_data('tmp_repo/src/qpath_fig6.txt')
x_ql6, tput_ql6, fid_ql6, util_ql6 = read_data('tmp_repo/src/qleap_fig6.txt')

fig, axs = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle('Official GitHub Output: Figure 6 (Fidelity Threshold vs Metrics)', fontsize=16)

axs[0].plot(x_qp6, tput_qp6, marker='o', label='Q-PATH (Official)')
axs[0].plot(x_ql6, tput_ql6, marker='x', linestyle='--', label='Q-LEAP (Official)')
axs[0].set_title('(a) Throughput')
axs[0].set_xlabel('Fidelity Threshold')
axs[0].set_ylabel('Throughput (pairs)')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(x_qp6, fid_qp6, marker='s', label='Q-PATH (Official)')
axs[1].plot(x_ql6, fid_ql6, marker='+', linestyle='--', label='Q-LEAP (Official)')
axs[1].set_title('(b) Average E2E Fidelity')
axs[1].set_xlabel('Fidelity Threshold')
axs[1].set_ylabel('Fidelity')
axs[1].legend()
axs[1].grid(True)

axs[2].plot(x_qp6, util_qp6, marker='^', label='Q-PATH (Official)')
axs[2].plot(x_ql6, util_ql6, marker='v', linestyle='--', label='Q-LEAP (Official)')
axs[2].set_title('(c) Network Resource Utilization')
axs[2].set_xlabel('Fidelity Threshold')
axs[2].set_ylabel('Utilization Ratio')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.savefig('official_fig6_plot.png', dpi=300)
plt.close()

# --- FIGURE 7 (Channel Capacity) ---
x_qp7, tput_qp7, fid_qp7, util_qp7 = read_data('tmp_repo/src/qpath_fig7.txt')
x_ql7, tput_ql7, fid_ql7, util_ql7 = read_data('tmp_repo/src/qleap_fig7.txt')

fig, axs = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle('Official GitHub Output: Figure 7 (Channel Capacity vs Metrics)', fontsize=16)

axs[0].plot(x_qp7, tput_qp7, marker='o', label='Q-PATH (Official)')
axs[0].plot(x_ql7, tput_ql7, marker='x', linestyle='--', label='Q-LEAP (Official)')
axs[0].set_title('(a) Throughput')
axs[0].set_xlabel('Channel Capacity')
axs[0].set_ylabel('Throughput (pairs)')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(x_qp7, fid_qp7, marker='s', label='Q-PATH (Official)')
axs[1].plot(x_ql7, fid_ql7, marker='+', linestyle='--', label='Q-LEAP (Official)')
axs[1].set_title('(b) Average E2E Fidelity')
axs[1].set_xlabel('Channel Capacity')
axs[1].set_ylabel('Fidelity')
axs[1].legend()
axs[1].grid(True)

axs[2].plot(x_qp7, util_qp7, marker='^', label='Q-PATH (Official)')
axs[2].plot(x_ql7, util_ql7, marker='v', linestyle='--', label='Q-LEAP (Official)')
axs[2].set_title('(c) Network Resource Utilization')
axs[2].set_xlabel('Channel Capacity')
axs[2].set_ylabel('Utilization Ratio')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.savefig('official_fig7_plot.png', dpi=300)
plt.close()

print("Official multi-algorithm plots generated: official_fig6_plot.png and official_fig7_plot.png")
