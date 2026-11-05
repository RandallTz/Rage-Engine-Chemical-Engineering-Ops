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
import { nuevaHoja, type HojaMotor } from '../app/motor/hojasMotor';
import { leerModeloComun } from '../motores/modelo/lector';
import { DEMO01_BATCH_REACTOR } from './demo01/batchReactor';
import { DEMO01_FLASH_DRUM } from './demo01/flashDrum';
import { DEMO02_FLASH_DRUM } from './demo02/flashDrum';
import { DEMO02_CSTR } from './demo02/continuousReactor';

/** Demo 0.1 models: Python-authored with the shared fundamental-law tools (tests/demo01_*.py), frozen here. */
function createDemo01Models(): HojaMotor[] {
  return [DEMO01_BATCH_REACTOR, DEMO01_FLASH_DRUM].map(source => {
    const model = leerModeloComun(structuredClone(source));
    return { ...nuevaHoja(model.nombre), id: model.id, commonModel: model };
  });
}

/** Demo 0.2 equipment templates: deduced dynamic with matter, energy and momentum (tests/demo02_*.py), frozen here. */
function createDemo02Models(): HojaMotor[] {
  return [DEMO02_FLASH_DRUM, DEMO02_CSTR].map(source => {
    const model = leerModeloComun(structuredClone(source));
    return { ...nuevaHoja(model.nombre), id: model.id, commonModel: model };
  });
}

export const REGRESSION_MODELS = [
  { name: 'Matter transport', create: crearHojasPruebaMateria },
  { name: 'Matter & energy', create: crearHojasPruebaEnergia },
  { name: 'Coupled volumes', create: crearHojasPruebaAcoplamiento },
  { name: 'Multicomponent', create: crearHojasPruebaMulticomponente },
  { name: 'Multiphase & UNIFAC', create: () => [...crearHojasPruebaMultifasico(), ...crearHojasPruebaNComponentes(), ...crearHojasPruebaUNIFAC()] },
  { name: 'Phase discovery · rigid vessel', create: createPhaseDiscoveryExamples },
  { name: 'Process demonstrations', create: crearHojasDemostracion },
  { name: 'Demo 0.1', create: createDemo01Models },
  { name: 'Demo 0.2', create: createDemo02Models },
];
