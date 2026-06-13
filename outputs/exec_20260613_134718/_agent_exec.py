import numpy as np
import matplotlib.pyplot as plt

# Data from compute_aerothermal tool (O-atom recombination)
T = np.array([1500, 2000, 2500, 3000])

# SiO2: gamma increases slowly (Arrhenius, E_a ~ 800 K)
gamma_SiO2 = np.array([6.75e-3, 7.72e-3, 8.36e-3, 8.82e-3])

# SiC: gamma saturates near 1.6e-1 — high catalytic activity
gamma_SiC = np.array([1.60e-1, 1.60e-1, 1.60e-1, 1.60e-1])

# RCG: moderate increase (E_a ~ 750 K)
gamma_RCG = np.array([5.91e-3, 6.70e-3, 7.22e-3, 7.59e-3])

# Compute average and relative change
avg_SiO2 = np.mean(gamma_SiO2)
avg_SiC = np.mean(gamma_SiC)
avg_RCG = np.mean(gamma_RCG)

print('=== Catalytic Recombination Coefficient (γ₀) Summary ===')
print(f'SiO2 avg γ₀ (1500–3000 K): {avg_SiO2:.4f}')
print(f'SiC  avg γ₀ (1500–3000 K): {avg_SiC:.4f}')
print(f'RCG  avg γ₀ (1500–3000 K): {avg_RCG:.4f}')

print('\n=== Relative Increase (γ₃₀₀₀/γ₁₅₀₀) ===')
print(f'SiO2: {gamma_SiO2[-1]/gamma_SiO2[0]:.3f}x')
print(f'SiC:  {gamma_SiC[-1]/gamma_SiC[0]:.3f}x (saturated)')
print(f'RCG:  {gamma_RCG[-1]/gamma_RCG[0]:.3f}x')

# Plot
plt.figure(figsize=(8, 5))
plt.semilogy(T, gamma_SiO2, 'o-', label='SiO₂ (quartz)', color='tab:blue')
plt.semilogy(T, gamma_SiC, 's-', label='SiC', color='tab:red')
plt.semilogy(T, gamma_RCG, '^-', label='RCG (HRSI)', color='tab:green')
plt.xlabel('Temperature (K)')
plt.ylabel('γ₀ (O-atom recombination)')
plt.title('Catalytic Recombination Coefficient vs Temperature')
plt.grid(True, which="both", ls="--")
plt.legend()
plt.tight_layout()
plt.savefig('gamma_vs_T.png')
plt.show()

# Export data for report
{'T': T.tolist(), 'SiO2': gamma_SiO2.tolist(), 'SiC': gamma_SiC.tolist(), 'RCG': gamma_RCG.tolist()}