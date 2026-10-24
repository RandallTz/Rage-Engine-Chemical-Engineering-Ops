import { createPhaseDiscoveryExamples } from '../app/motor/phaseDiscoveryExample';
/** Internal numerical regression inputs. Never import into the product library.
 * New user examples are created only on request through the shared Model tools. */
import { crearHojasPruebaMateria } from '../app/motor/hojasPruebaMateria';
import { crearHojasPruebaEnergia } from '../app/motor/hojasPruebaEnergia';
import { crearHojasPruebaAcoplamiento, crearHojasPruebaMulticomponente } from '../app/motor/hojasPruebaAcoplamiento';
import { crearHojasDemostracion } from '../app/motor/hojasDemostracion';
import { crearHojasPruebaUNIFAC } from '../app/motor/hojasPruebaUNIFAC';
import { crearHojasPruebaNComponentes } from '../app/motor/hojasPruebaNComponentes';
import { crearHojasPruebaMultifasico } from '../app/motor/hojasPruebaMultifasico';

export const REGRESSION_MODELS = [
  { name: 'Matter transport', create: crearHojasPruebaMateria },
  { name: 'Matter & energy', create: crearHojasPruebaEnergia },
  { name: 'Coupled volumes', create: crearHojasPruebaAcoplamiento },
  { name: 'Multicomponent', create: crearHojasPruebaMulticomponente },
  { name: 'Multiphase & UNIFAC', create: () => [...crearHojasPruebaMultifasico(), ...crearHojasPruebaNComponentes(), ...crearHojasPruebaUNIFAC()] },
  { name: 'Phase discovery · rigid vessel', create: createPhaseDiscoveryExamples },
  { name: 'Process demonstrations', create: crearHojasDemostracion },
];
