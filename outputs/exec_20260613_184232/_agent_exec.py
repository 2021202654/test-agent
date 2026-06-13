import numpy as np
import matplotlib.pyplot as plt
import os

# Ensure outputs directory exists
os.makedirs('outputs', exist_ok=True)

# Temperature range
T = np.array([1500, 2000, 2500, 3000])

# Catalytic recombination coefficients from compute_aerothermal tool
# SiO2 (O-atom recombination)
gamma_SiO2 = np.array([6.75e-3, 7.72e-3, 8.36e-3, 8.82e-3])

# SiC (O-atom recombination) - note: tool shows saturation at 0.16
gamma_SiC = np.array([0.16, 0.16, 0.16, 0.16])

# RCG (O-atom recombination)
gamma_RCG = np.array([5.91e-3, 6.70e-3, 7.22e-3, 7.59e-3])

# Create plot
fig, ax = plt.subplots(figsize=(10, 6))

ax.semilogy(T, gamma_SiO2, 'bo-', linewidth=2, markersize=8, label='SiO₂ (quartz)')
ax.semilogy(T, gamma_SiC, 'rs-', linewidth=2, markersize=8, label='SiC (silicon carbide)')
ax.semilogy(T, gamma_RCG, 'g^-', linewidth=2, markersize=8, label='RCG (Reaction Cured Glass)')

ax.set_xlabel('Temperature (K)', fontsize=12)
ax.set_ylabel('Catalytic Recombination Coefficient γ (O-atoms)', fontsize=12)
ax.set_title('Catalytic Recombination Coefficient vs Temperature\n(1500K - 3000K, O-atom recombination)', fontsize=14)
ax.legend(loc='upper left', fontsize=11)
ax.grid(True, alpha=0.3)
ax.set_xlim(1400, 3100)
ax.set_ylim(1e-3, 1)

# Add annotations
ax.annotate('SiC: γ ≈ 0.16\n(highly catalytic)', xy=(2000, 0.16), xytext=(2100, 0.25),
            fontsize=10, ha='left',
            arrowprops=dict(arrowstyle='->', color='red'))
ax.annotate('SiO₂: γ ≈ 0.007-0.009\n(low catalytic)', xy=(2000, 7.72e-3), xytext=(2100, 0.015),
            fontsize=10, ha='left',
            arrowprops=dict(arrowstyle='->', color='blue'))
ax.annotate('RCG: γ ≈ 0.006-0.008\n(low catalytic)', xy=(2000, 6.70e-3), xytext=(2100, 0.01),
            fontsize=10, ha='left',
            arrowprops=dict(arrowstyle='->', color='green'))

plt.tight_layout()
plt.savefig('outputs/catalytic_coefficient_comparison.png', dpi=150)
print("Plot saved to outputs/catalytic_coefficient_comparison.png")

# Print summary table
print("\n=== Catalytic Recombination Coefficient Summary (O-atoms) ===")
print(f"{'Temperature (K)':<15} {'SiO₂':<12} {'SiC':<12} {'RCG':<12}")
print("-" * 51)
for i, temp in enumerate(T):
    print(f"{temp:<15} {gamma_SiO2[i]:<12.4e} {gamma_SiC[i]:<12.2e} {gamma_RCG[i]:<12.4e}")

print("\n=== Key Observations ===")
print(f"SiC/SiO₂ ratio at 1500K: {gamma_SiC[0]/gamma_SiO2[0]:.1f}x")
print(f"SiC/SiO₂ ratio at 3000K: {gamma_SiC[3]/gamma_SiO2[3]:.1f}x")
print(f"SiO₂ increase 1500→3000K: {(gamma_SiO2[3]-gamma_SiO2[0])/gamma_SiO2[0]*100:.1f}%")
print(f"RCG increase 1500→3000K: {(gamma_RCG[3]-gamma_RCG[0])/gamma_RCG[0]*100:.1f}%")
