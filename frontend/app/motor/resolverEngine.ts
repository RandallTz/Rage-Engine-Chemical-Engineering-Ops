import {selectedDerivedModel} from '../models/derivedSelection';
/** Resolver del Engine: el cálculo lo hace el Engine común del servidor (motor de balances +
 * compilador + solvers, POST /modelo/resolver) para toda hoja que llega a él; el solver del
 * navegador queda solo para lo que todavía no llega (campos 1D y sustitución por volumen).
 *
 * El resultado común se traduce al ResultadoMotor que ya leen las vistas (tablero, CSV,
 * detalles), sin recalcular física: estados, observables y cierres de presupuesto son series
 * publicadas por el servidor. De la compilación local solo se toma la identidad de cada estado
 * (nombres, unidades, catálogo de series) para que las vistas no cambien. */
import type { HojaMotor } from './hojasMotor';
import type { ResultadoMotor, SerieEvaluadaMotor } from './modeloNumerico';
import { compilarHoja, firmaHoja, formulacionHoja, resolverHoja } from './modeloHojaMotor';
import { balancesHoja, bloqueosBalances } from './seleccionBalances';
import { bloqueosCierreTermodinamico } from './estadoTermodinamicoHoja';
import type { SistemaEnergia } from './modeloEnergia';
import { cabeEnBalances, modeloBalancesDesdeHoja } from '../../motores/modelo/desdeHojaBalances';
import { resolverModelo, type TransporteModelo } from '../../motores/modelo/servicioModelo';
import type { ConjuntoResultados } from '../../motores/resultados/contrato';
import { selectedTransformedModel } from '../models/transformationSelection';
import { importarHojaMotor } from '../adimensionalizacion/desdeMotor';
import { igualdadProfunda } from '../adimensionalizacion/lecturaNucleo';

export const MOTOR_ENGINE_COMUN = 'rage.compilador.explicito';
export type OpcionesResolver = { signal?: AbortSignal; progreso?: (v: number) => void; transporte?: TransporteModelo };

/** ¿Resuelve esta hoja el Engine común? */
export const resuelveEngineComun = (h: HojaMotor) => !!h.transformation || cabeEnBalances(h);

export async function resolverHojaEngine(h: HojaMotor, opciones: OpcionesResolver = {}): Promise<ResultadoMotor> {
  if(h.commonModel){const result=await resolverModelo(selectedDerivedModel(h),opciones.signal,opciones.transporte);return derivedResult(h,result);}
  const { ensureInventoryExecution } = await import('../models/dynamicDefinition');
  ensureInventoryExecution(h);
  if (h.transformation) {
    const common = selectedTransformedModel(h);
    const result = await resolverModelo(common, opciones.signal, opciones.transporte);
    opciones.progreso?.(1);
    return transformedResult(h, result);
  }
  if (!resuelveEngineComun(h)) return resolverHoja(h, opciones);
  const bloqueos = [...bloqueosBalances(h), ...bloqueosCierreTermodinamico(h)];
  if (bloqueos.length) throw new Error(bloqueos[0]);
  // Local compilation supplies display identities only. Workbench operations
  // are always replayed and admitted by Python, including new constraints.
  const s = compilarHoja({...h,equationWorkbench:undefined});
  const common=modeloBalancesDesdeHoja(h);
  if(h.equationWorkbench)common.motores={...common.motores,equationWorkbench:h.equationWorkbench};
  const c = await resolverModelo(common, opciones.signal, opciones.transporte);
  opciones.progreso?.(1);
  return resultadoDesdeComun(h, s, c);
}

function transformedResult(model: HojaMotor, result: ConjuntoResultados): ResultadoMotor {
  const imported = importarHojaMotor(model);
  const report = result.procedencia.compilation;
  if (result.procedencia.motor !== 'rage.compilador.transformed' || !report || report.formulation !== 'scaled') throw new Error('The server did not execute the selected transformation.');
  if (result.modeloId !== model.id || report.sourceModelId !== `model-equations-${model.id}`
    || !igualdadProfunda(report.selection, { formId: model.transformation!.config.activaId, execution: model.transformation!.config.execution })) throw new Error('The returned execution does not match the selected formulation.');
  const physicalSeries = new Map(result.series.map(item => [item.id, item.valores]));
  const values = (id: string) => {
    const data = physicalSeries.get(id);
    if (!Array.isArray(data) || data.some(value => typeof value !== 'number' || !Number.isFinite(value))) throw new Error(`Missing reconstructed physical series: ${id}.`);
    return data as number[];
  };
  const fields = imported.origen.componentes.map(item => item.campoId);
  const states = fields.map(field => values('campo.' + field));
  const end = result.ejes[0].valores.length - 1;
  return { version: 1, motor: result.procedencia.motor, modo: 'temporal', metodo: `Scaled formulation · ${result.procedencia.metodo}`,
    tiempos: result.ejes[0].valores, x: [], dx: 1, valores: result.ejes[0].valores.map((_, index) => states.map(state => [state[index]])),
    componentes: formulacionHoja(model).componentes!, estado: result.estado === 'resuelto' ? 'resuelto' : 'parcial', mensaje: result.procedencia.mensaje ?? '',
    pasos: result.procedencia.pasos ?? 0, rechazados: result.procedencia.rechazos ?? 0,
    conservacion: fields.map((field, index) => states[index][end] - states[index][0] - values('budget.' + field)[end]),
    unidadEstado: imported.origen.estado === 'masa' ? 'kg' : imported.origen.estado === 'volumen' ? 'm3' : 'kg/m3',
    firma: firmaHoja(model), compilation: report };
}

function idsEstados(h: HojaMotor, s: ReturnType<typeof compilarHoja>): string[] {
  if (s.estadosAcoplados) return s.estadosAcoplados.map(e => `campo.m_${e.simbolo}_${e.volumenId}`);
  const cs = formulacionHoja(h).componentes ?? [];
  if (balancesHoja(h).energia) return [...(balancesHoja(h).materia ? [`campo.m_${cs[0].simbolo}_dominio`] : []), 'campo.U_dominio'];
  return cs.map(k => `campo.m_${k.simbolo}_dominio`);
}

export function resultadoDesdeComun(h: HojaMotor, s: ReturnType<typeof compilarHoja>, c: ConjuntoResultados): ResultadoMotor {
  const serie = new Map(c.series.map(x => [x.id, x.valores as (number | null)[]]));
  const valor = (id: string) => { const v = serie.get(id); if (!v) throw new Error(`El Engine no publicó la serie ${id}.`); return v.map(x => x ?? NaN); };
  const ids = idsEstados(h, s), t = c.ejes[0].valores, fin = t.length - 1;
  const estados = ids.map(valor);
  // Cierre del presupuesto integrado (como el solver local): cambio del estado menos la integral de su balance, al final.
  const conservacion = ids.map((id, i) => { const aux = valor(id.replace('campo.', 'campo.aux_')); return estados[i][fin] - estados[i][0] - aux[fin]; });
  const mensaje = typeof c.procedencia.mensaje === 'string' ? c.procedencia.mensaje : '';
  const r: ResultadoMotor = {
    version: 1, motor: MOTOR_ENGINE_COMUN, modo: 'temporal', metodo: `Engine común · ${String(c.procedencia.metodo ?? '')}`,
    tiempos: t, x: [], dx: 1, valores: t.map((_, k) => estados.map(v => [v[k]])),
    componentes: s.estadosAcoplados ? s.estadosAcoplados.map((v, i) => ({ id: i + 1, nombre: `${v.volumenNombre} · ${v.componenteNombre}`, simbolo: v.simbolo })) : formulacionHoja(h).componentes!,
    estado: c.estado === 'parcial' ? 'parcial' : 'resuelto', mensaje,
    pasos: Number(c.procedencia.pasos ?? 0), rechazados: Number(c.procedencia.rechazos ?? 0),
    conservacion, unidadEstado: s.unidadEstado, firma: firmaHoja(h),
    ...(c.procedencia.compilation ? { compilation: c.procedencia.compilation } : {}),
    ...(s.variablesNumericas ? { variablesNumericas: s.variablesNumericas } : {}),
    ...(s.evaluacionReglas ? { evaluacionReglas: s.evaluacionReglas } : {}),
  };
  if (s.estadosAcoplados && s.gruposGlobales) {
    r.estadosAcoplados = s.estadosAcoplados;
    r.conservacionGlobal = s.gruposGlobales.map(g => {
      const simbolo = s.estadosAcoplados![g.indices[0]].simbolo, aux = valor(`campo.aux_global_${simbolo}`);
      return { id: g.id, nombre: g.nombre, residuo: g.indices.reduce((sum, j) => sum + estados[j][fin] - estados[j][0], 0) - aux[fin] };
    });
  }
  if (balancesHoja(h).energia) {
    const e = s as SistemaEnergia;
    const cero = t.map(() => 0);
    const opc = (id: string) => serie.get(id)?.map(x => x ?? NaN) ?? cero;     // término que los supuestos eliminan: cero
    const de = (id: string): number[] => {
      if (id.startsWith('m_')) return valor(ids[0]);
      const p = /^(mdot|h|E)_(\d+)$/.exec(id);
      if (p) return valor(`observable.corriente.puerto.${p[2]}.${p[1]}`);
      const mapa: Record<string, string> = { U: 'campo.U_dominio', T: 'observable.volumen.dominio.T', Q: 'observable.volumen.dominio.calor', Wb: 'observable.volumen.dominio.trabajo_frontera',
        dU: 'observable.volumen.dominio.dUdt', V: 'observable.volumen.dominio.V', Wtau: 'observable.volumen.dominio.trabajo_viscoso', Wf: 'observable.volumen.dominio.fuerzas', R: 'observable.volumen.dominio.fuente' };
      return ['T', 'U', 'dU', 'V'].includes(id) ? valor(mapa[id]) : opc(mapa[id]);
    };
    r.balancesEjecutados = balancesHoja(h).materia ? ['materia', 'energia'] : ['energia'];
    r.trazabilidadEnergia = e.trazabilidad;
    r.seriesEvaluadas = e.catalogoSeries.map((q): SerieEvaluadaMotor => ({ ...q, valores: de(q.id) }));
  }
  return r;
}

/** Preserve the common result's series, units and exact compiler provenance. */
export function derivedResult(model:HojaMotor,result:ConjuntoResultados):ResultadoMotor {
  const report=result.procedencia.compilation;
  if(result.modeloId!==model.id||result.procedencia.motor!=='rage.compilador.derived'||!report?.derivedExecution||!igualdadProfunda(report.derivedExecution.selection,model.derivedSelection?.selection))throw new Error('The result does not match the selected derived formulation.');
  const times=result.ejes[0].valores;
  const series=result.series.map(row=>{if(!Array.isArray(row.valores)||row.valores.length!==times.length||row.valores.some(value=>typeof value!=='number'||!Number.isFinite(value)))throw new Error('Invalid published derived trajectory.');return {id:row.id,nombre:row.nombre,unidad:row.unidadSI,grupo:row.id.startsWith('budget.')?'Conservation budgets':row.id.startsWith('transformed.')?'Scaled quantities':'Physical quantities',valores:row.valores as number[]};});
  const states=report.variables.map(variable=>{const row=series.find(item=>item.id==='campo.'+variable.sourceId);if(!row)throw new Error('Missing retained physical state.');return row;});
  return {version:1,motor:result.procedencia.motor,modo:'temporal',metodo:String(result.procedencia.metodo),tiempos:times,x:[],dx:1,valores:times.map((_,i)=>states.map(state=>[state.valores[i]])),componentes:states.map((state,i)=>({id:i+1,nombre:state.nombre,simbolo:report.variables[i].sourceId})),estado:result.estado==='resuelto'?'resuelto':'parcial',mensaje:String(result.procedencia.mensaje??''),pasos:Number(result.procedencia.pasos??0),rechazados:Number(result.procedencia.rechazos??0),conservacion:[],verificationChecks:result.verificaciones,unidadEstado:'mixta',firma:firmaHoja(model),seriesEvaluadas:series,compilation:report};
}
