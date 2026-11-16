/** Dónde se muestra cada ecuación del Engine (regla de ARCHITECTURE.md §8: cada ecuación va en su lugar).
 *
 * Un panel de la hoja muestra solo las ecuaciones de su familia física:
 *   materia        conservación por componente, transporte material de cada corriente (caudal y composición
 *                  del donante) y su comprobación global;
 *   energía        primera ley, entalpía transportada por las corrientes, calor entre volúmenes, trabajo de
 *                  frontera y su comprobación global;
 *   momento        balance de cantidad de movimiento;
 *   termodinámica  cierre de estado (energía y volumen de todas las fases, U = H − PV) y equilibrio entre las
 *                  fases candidatas con su prueba de estabilidad;
 *   signal         sensor, controller and actuator relations (Demo 0.3 C3, dec-control-surface). A signal
 *                  conserves nothing; the physical actuator join stays in the family it acts on.
 * Una ecuación sin lugar es un error del motor, no algo que se muestre «en todas partes». */
import type { VistaHoja } from './familiasBalance';

export type EcuacionUbicable = { id: string; familia: string };

/** A worksheet panel: one physical view of the sheet, or the Signal family. */
export type PanelEcuacion = VistaHoja | 'senal';

export function panelDeEcuacion(e: EcuacionUbicable): PanelEcuacion | null {
  switch (e.familia) {
    case 'matter': return 'materia';
    case 'energy': return 'energia';
    case 'momentum': return 'momento';
    case 'thermodynamics': return 'termodinamica';
    case 'signal': return 'senal';
    case 'materia': return 'materia';
    case 'energia': return 'energia';
    case 'momento': return 'momento';
    case 'estado': case 'equilibrio': return 'termodinamica';
    case 'mecanica': return e.id.endsWith('.trabajo') ? 'energia' : 'momento';
    case 'transferencia':
      if (e.id.startsWith('transferencia.calor.') || e.id.endsWith('.entalpia')) return 'energia';
      if (e.id.endsWith('.caudal') || e.id.endsWith('.composicion')) return 'materia';
      return null;
    case 'verificacion':
      if (e.id.startsWith('global.materia.')) return 'materia';
      if (e.id === 'global.energia' || e.id.startsWith('global.energia.')) return 'energia';
      return null;
    default: return null;
  }
}

export const TITULO_PANEL: Record<PanelEcuacion, string> = { materia: 'Matter equations', energia: 'Energy equations', momento: 'Momentum equations', termodinamica: 'Thermodynamic equations', senal: 'Signal equations' };
