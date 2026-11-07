"""Independent cascade reference: direct mixture calls, no compiler or bridge."""
import numpy as np
from scipy.integrate import solve_ivp

from core import mezclas
from demo02_drum import DEMO
from derived_closure_inputs import PACKAGE_ID, ETHANOL, WATER
from derived_momentum_inputs import total_loss_coefficient


def reference_network(count, times, data=DEMO):
    packages = [mezclas.Sistema(PACKAGE_ID, [ETHANOL, WATER]) for _ in range(count)]
    masses = np.asarray(packages[0].M)
    feed_composition = np.asarray(data['zF'])
    feed_mass = float(feed_composition @ masses)
    feed_components = data['feed'] * feed_composition * masses / feed_mass
    feed_energy = data['feed'] * packages[0].equilibrio_TP(
        data['TF'], data['PF'], feed_composition).H / feed_mass

    def states(values):
        return [package.equilibrio_PH(data['P'], row[2], row[:2] / masses)
                for package, row in zip(packages, np.asarray(values).reshape(count, 4))]

    def rhs(time, values):
        rows = np.asarray(values).reshape(count, 4)
        incoming_components, incoming_energy = feed_components, feed_energy
        rates = []
        # Every stage is at data['P']; a discharge port is at the receiving stage pressure, the last one at Pout.
        discharge = [data['P']] * (count - 1) + [data['Pout']]
        for row, equilibrium, port in zip(rows, states(values), discharge):
            flow = row[3]
            liquid = next(phase for phase in equilibrium.fases if phase.tipo != 'vapor')
            liquid_components = flow * np.asarray(liquid.x) * masses / liquid.M
            liquid_energy = flow * liquid.h / liquid.M
            outgoing_components = liquid_components.copy()
            outgoing_energy = liquid_energy
            for phase in equilibrium.fases:
                if phase.tipo == 'vapor' and phase.n > mezclas.N_AUSENTE * float(np.sum(row[:2] / masses)):
                    vapour_flow = data['vent'] * phase.n
                    outgoing_components += vapour_flow * np.asarray(phase.x) * masses
                    outgoing_energy += vapour_flow * phase.h
            density = liquid.M / liquid.v
            level = liquid.n * liquid.v / data['area']
            pressure = data['P'] + density * data['g'] * level
            loss = total_loss_coefficient(data) * flow**2 / (2 * density * data['pipeArea']**2)
            rates.extend([*(incoming_components - outgoing_components),
                          incoming_energy - outgoing_energy + data['Q'],
                          data['pipeArea'] / data['length'] * (pressure - port - loss)])
            incoming_components, incoming_energy = liquid_components, liquid_energy
        return rates

    initial = []
    for package in packages:
        enthalpy = package.equilibrio_TP(data['T0'], data['P'], np.asarray(data['m0']) / masses).H
        initial.extend([*data['m0'], enthalpy, data['F0']])
    solution = solve_ivp(rhs, (0., float(times[-1])), initial, method='DOP853',
                         rtol=1e-10, atol=np.tile([1e-10, 1e-10, 1e-4, 1e-10], count), t_eval=times)
    temperatures = np.asarray([[state.T for state in states(row)] for row in solution.y.T])
    return solution, temperatures
