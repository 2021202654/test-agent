
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

temperatures = np.array([1500, 1800, 2100, 2400, 2700, 3000])
sio2_gamma = np.array([6.75e-03, 7.38e-03, 7.87e-03, 8.25e-03, 8.56e-03, 8.82e-03])
sic_gamma = np.array([1.60e-01, 1.60e-01, 1.60e-01, 1.60e-01, 1.60e-01, 1.60e-01])
rcg_gamma = np.array([5.91e-03, 6.42e-03, 6.82e-03, 7.13e-03, 7.38e-03, 7.59e-03])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

ax1.plot(temperatures, sio2_gamma, 'o-', label='SiO2 (quartz)', linewidth=2, markersize=8, color='blue')
ax1.plot(temperatures, sic_gamma, 's-', label='SiC', linewidth=2, markersize=8, color='red')
ax1.plot(temperatures, rcg_gamma, '^-', label='RCG (Reaction Cured Glass)', linewidth=2, markersize=8, color='green')
ax1.set_xlabel('Temperature (K)', fontsize=12)
ax1.set_ylabel('Catalytic Recombination Coefficient gamma (O-atom)', fontsize=12)
ax1.set_title('Catalytic Recombination Coefficient vs Temperature (Linear Scale)', fontsize=14)
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3)
ax1.set_xlim(1400, 3100)

ax2.semilogy(temperatures, sio2_gamma, 'o-', label='SiO2 (quartz)', linewidth=2, markersize=8, color='blue')
ax2.semilogy(temperatures, sic_gamma, 's-', label='SiC', linewidth=2, markersize=8, color='red')
ax2.semilogy(temperatures, rcg_gamma, '^-', label='RCG (Reaction Cured Glass)', linewidth=2, markersize=8, color='green')
ax2.set_xlabel('Temperature (K)', fontsize=12)
ax2.set_ylabel('Catalytic Recombination Coefficient gamma (O-atom) [Log Scale]', fontsize=12)
ax2.set_title('Catalytic Recombination Coefficient vs Temperature (Log Scale)', fontsize=14)
ax2.legend(fontsize=11)
ax2.grid(True, alpha=0.3, which='both')
ax2.set_xlim(1400, 3100)

plt.tight_layout()
plt.savefig('catalytic_coefficient_comparison.png', dpi=150, bbox_inches='tight')
print("Figure saved successfully")
