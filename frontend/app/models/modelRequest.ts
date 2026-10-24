import {commonSource,selectedDerivedModel} from './derivedSelection';
/** Shared transport adapter; it selects a protocol, never derives equations. */
import type { HojaMotor } from '../motor/hojasMotor';
import { cabeEnBalances, modeloBalancesDesdeHoja } from '../../motores/modelo/desdeHojaBalances';
import { modeloDesdeHojaMotor } from '../../motores/modelo/desdeHojaMotor';
import { selectedTransformedModel } from './transformationSelection';
import {journalFromHistory} from '../motor/materialDerivation';
import {energyJournalFromHistory,thermodynamicJournalFromHistory} from '../motor/physicalDerivation';

/** The same authoring source for Model and its read-only workspace handoffs. */
export function equationSource(model:HojaMotor){
  if(model.commonModel)return {modelo:commonSource(model)};
  const unbound=!model.ensamblaje&&!model.redTermodinamica&&!model.historial.pasos[model.historial.activo].formulacion.componentes?.length;
  if(!unbound)return modelRequest(model);
  const formulation=model.historial.pasos[model.historial.activo].formulacion;
  const energy=model.energia?energyJournalFromHistory(model.energia.historial):undefined;
  const thermo=model.recorridoTermodinamico?thermodynamicJournalFromHistory(model.recorridoTermodinamico):undefined;
  return {draft:{format:'rage.fundamental-equations',version:3,modelId:model.id,definition:model.equationWorkbench??{format:'rage.equation-workbench',version:1,operations:[],cursor:0},
    materialJournal:journalFromHistory(model.historial),ports:formulation.fronteras,
    ...(model.momentumDerivation?{momentumJournal:model.momentumDerivation}:{}),
    ...(energy?{energyJournal:{format:'rage.energy-derivation',version:1,volumes:{dominio:energy}}}:{}),
    ...(thermo?{thermodynamicJournal:{format:'rage.thermodynamic-derivation',version:1,volumes:{dominio:thermo}}}:{})}};
}

export function modelRequest(model: HojaMotor, transformed = false) {
  if(model.commonModel)return {modelo:transformed?selectedDerivedModel(model):commonSource(model)};
  if (transformed && model.transformation) return { modelo: selectedTransformedModel(model) };
  if (model.redTermodinamica) return { solicitudV2: model.redTermodinamica.solicitud };
  const common = cabeEnBalances(model) ? modeloBalancesDesdeHoja(model) : modeloDesdeHojaMotor(model);
  if(model.equationWorkbench)common.motores={...common.motores,equationWorkbench:model.equationWorkbench};
  // Older adapters predate momentum execution; never report an active balance as inactive.
  if (model.balances?.momento&&!model.ensamblaje) common.volumenes = common.volumenes.map(volume => ({ ...volume, balances: { ...volume.balances, momento: true } }));
  return { modelo: common };
}
