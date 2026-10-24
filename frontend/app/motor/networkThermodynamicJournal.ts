/** Reversible state-closure edits, preserving independent energy/matter operations. */
import type { SolicitudEnsamblajeV2, VolumenV2 } from './contratoEnsamblajeV2';
import { configuredClosure, stateKeys, thermodynamicJournalInRequest, thermodynamicJournalMatches, readThermodynamicJournal } from './physicalDerivation';
import type { ThermodynamicJournal, ThermodynamicState } from './physicalDerivation';
type Previous={package:SolicitudEnsamblajeV2['paquetes'][number];packageId:string;policy:VolumenV2['politica'];assumptions:Pick<VolumenV2['formulacionEnergia'],'monofasico'|'sinCambioFase'|'densidadConstante'|'modelo'>};
type Metadata=Record<string,unknown>&{thermodynamicDerivation?:ThermodynamicJournal;previousThermodynamicFormulations?:Record<string,Previous>};
const metadata=(request:SolicitudEnsamblajeV2):Metadata=>request.derivacion&&typeof request.derivacion==='object'&&!Array.isArray(request.derivacion)?request.derivacion as Metadata:{};
export const hasPreviousThermodynamicFormulation=(request:SolicitudEnsamblajeV2,id:string)=>!!metadata(request).previousThermodynamicFormulations?.[id];
export function replaceNetworkThermodynamicJournal(request:SolicitudEnsamblajeV2,id:string,journal:ThermodynamicJournal,state:ThermodynamicState,starting:boolean,expected:string):void {
  if(JSON.stringify(request)!==expected)throw new Error('The model changed while the deduction was being developed. Apply it again.');
  readThermodynamicJournal(journal);
  const volume=request.volumenes.find(item=>item.id===id),meta=metadata(request);
  if(!volume||!journal.volumes[id]||!thermodynamicJournalMatches(journal.volumes[id],state,state.closure))throw new Error('The returned state deduction does not match this volume.');
  if(starting){if(thermodynamicJournalInRequest(request.derivacion)?.volumes[id])throw new Error('This volume already has a thermodynamic journal.');meta.previousThermodynamicFormulations={...meta.previousThermodynamicFormulations,[id]:{package:structuredClone(request.paquetes.find(p=>p.id===volume.paqueteId)!),packageId:volume.paqueteId,policy:structuredClone(volume.politica),assumptions:structuredClone(Object.fromEntries(Object.entries(volume.formulacionEnergia).filter(([key])=>stateKeys.includes(key as typeof stateKeys[number])))) as Previous['assumptions']}};}
  const {closure,...assumptions}=state;
  if(closure){
    const selected=configuredClosure(request,{...volume,paqueteId:closure.packageId,politica:closure.policy});
    if(JSON.stringify(selected.model)!==JSON.stringify(closure.model))throw new Error('The selected package changed during development.');
    volume.paqueteId=closure.packageId;volume.politica=structuredClone(closure.policy);
  }else volume.politica={cantidad:state.monofasico?'monofasico':'sin_restriccion',cambioInterno:state.sinCambioFase?'prohibido':'permitido',evaluacion:'equilibrio_estable'};
  volume.formulacionEnergia={...volume.formulacionEnergia,...assumptions};
  if(volume.formulacionMateria.reglasEstado?.fases)volume.formulacionMateria.reglasEstado.fases={...volume.formulacionMateria.reglasEstado.fases,cantidad:volume.politica.cantidad,cambioInterno:volume.politica.cambioInterno==='prohibido'?'sin_cambio_de_fase':'sin_restriccion'};
  request.derivacion={...meta,thermodynamicDerivation:journal};
}
export function restoreNetworkThermodynamicFormulation(request:SolicitudEnsamblajeV2,id:string):void {
  const meta=metadata(request),volume=request.volumenes.find(item=>item.id===id),previous=meta.previousThermodynamicFormulations?.[id];
  if(!volume||!previous?.package)throw new Error('No previous thermodynamic formulation is available.');
  const existing=request.paquetes.find(p=>p.id===previous.packageId);
  if(existing&&request.volumenes.some(v=>v.id!==id&&v.paqueteId===existing.id)&&JSON.stringify(existing)!==JSON.stringify(previous.package))throw new Error('The previous package ID is now shared with a changed package. Restore its package configuration explicitly first.');
  if(existing)Object.assign(existing,structuredClone(previous.package));else request.paquetes.push(structuredClone(previous.package));
  volume.formulacionEnergia={...volume.formulacionEnergia,...structuredClone(previous.assumptions)};volume.paqueteId=previous.packageId;volume.politica=structuredClone(previous.policy);
  if(volume.formulacionMateria.reglasEstado?.fases)volume.formulacionMateria.reglasEstado.fases={...volume.formulacionMateria.reglasEstado.fases,cantidad:volume.politica.cantidad,cambioInterno:volume.politica.cambioInterno==='prohibido'?'sin_cambio_de_fase':'sin_restriccion'};
  delete meta.thermodynamicDerivation?.volumes[id];
  if(meta.thermodynamicDerivation&&!Object.keys(meta.thermodynamicDerivation.volumes).length)delete meta.thermodynamicDerivation;
  delete meta.previousThermodynamicFormulations?.[id];
  if(meta.previousThermodynamicFormulations&&!Object.keys(meta.previousThermodynamicFormulations).length)delete meta.previousThermodynamicFormulations;
  request.derivacion=meta;
}
