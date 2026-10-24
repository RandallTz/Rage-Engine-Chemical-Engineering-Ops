/** Persist choices, not trusted scientific output. Python regenerates the equations. */
import type { HojaMotor } from '../motor/hojasMotor';
import type { ConfigAdimensionalizacion } from '../../motores/modelo/contrato';
import type { Documento } from '../adimensionalizacion/contrato';
import type { FormulacionNucleo, RespuestaNucleo } from '../adimensionalizacion/contratoNucleo';
import { leerHojaMotor } from '../adimensionalizacion/desdeMotor';
import { transformationSourceSignature } from '../motor/modeloHojaMotor';
import { modeloDesdeHojaMotor } from '../../motores/modelo/desdeHojaMotor';
import { leerModeloComun } from '../../motores/modelo/lector';

export type TransformationSelection = {
  version: 1; sourceSignature: string; label: string;
  config: ConfigAdimensionalizacion & { execution: NonNullable<ConfigAdimensionalizacion['execution']> };
};

export function transformationDocument(model: HojaMotor): Documento | null {
  const reading = leerHojaMotor(model);
  if (!reading.importacion) return null;
  const document = reading.importacion.documento;
  return { ...document, id: `model-transform-${model.id}`, nombre: model.nombre,
    modelo: { ...document.modelo, id: `model-equations-${model.id}` } };
}

export function selectFormulation(model: HojaMotor, response: RespuestaNucleo, formulation: FormulacionNucleo,
  label: string, freeScales: NonNullable<ConfigAdimensionalizacion['execution']>['freeScales']): TransformationSelection {
  if (!response.formaBase || !formulation.objetivosAplicados || formulation.equivalencia.estado !== 'demostrada') throw new Error('This formulation has no executable selection record. Calculate it again.');
  return { version: 1, sourceSignature: transformationSourceSignature(model), label,
    config: { version: 2, formas: [structuredClone(response.formaBase)], activaId: response.formaBase.id,
      execution: { version: 1, objectives: [...formulation.objetivosAplicados], freeScales } } };
}

export function selectedTransformedModel(model: HojaMotor) {
  const selection = model.transformation;
  if (!selection || selection.version !== 1 || selection.sourceSignature !== transformationSourceSignature(model)) throw new Error('The selected transformation is outdated. Recalculate it in Transform or explicitly use the physical formulation.');
  if (model.redTermodinamica || model.ensamblaje) throw new Error('Scaling execution for coupled volumes is not connected yet.');
  const common = modeloDesdeHojaMotor(model);
  if (!common.matematico || common.matematico.simbolos.some(symbol => symbol.rol === 'coordenada')) throw new Error('Scaled spatial execution is not connected to the finite-volume solver yet. Use the physical formulation with the mesh in Transform.');
  const mathematical = { ...common.matematico, id: `model-equations-${model.id}` };
  return leerModeloComun({ ...common, matematico: mathematical, motores: { ...common.motores, adimensionalizacion: selection.config } });
}
