/** Reversible first-law edits; thermodynamic assumptions are owned separately. */
import type { SolicitudEnsamblajeV2, VolumenV2 } from './contratoEnsamblajeV2';
import { energyJournalInRequest, energyJournalMatches, readEnergyJournal } from './physicalDerivation';
import type { EnergyJournal, EnergyState } from './physicalDerivation';
type Metadata=Record<string,unknown>&{energyDerivation?:EnergyJournal;previousEnergyFormulations?:Record<string,VolumenV2['formulacionEnergia']>};
const metadata=(request:SolicitudEnsamblajeV2):Metadata=>request.derivacion&&typeof request.derivacion==='object'&&!Array.isArray(request.derivacion)?request.derivacion as Metadata:{};
export const hasPreviousEnergyFormulation=(request:SolicitudEnsamblajeV2,id:string)=>!!metadata(request).previousEnergyFormulations?.[id];
export function replaceNetworkEnergyJournal(request:SolicitudEnsamblajeV2,id:string,journal:EnergyJournal,formulation:EnergyState,starting:boolean,expected:string):void {
  if(JSON.stringify(request)!==expected)throw new Error('The model changed while the deduction was being developed. Apply it again.');
  readEnergyJournal(journal);
  const volume=request.volumenes.find(item=>item.id===id),meta=metadata(request);
  if(!volume||!journal.volumes[id]||!energyJournalMatches(journal.volumes[id],formulation))throw new Error('The returned first-law deduction does not match this volume.');
  if(starting){if(energyJournalInRequest(request.derivacion)?.volumes[id])throw new Error('This volume already has an energy journal.');meta.previousEnergyFormulations={...meta.previousEnergyFormulations,[id]:structuredClone(volume.formulacionEnergia)};}
  volume.formulacionEnergia={...volume.formulacionEnergia,...formulation};
  request.derivacion={...meta,energyDerivation:journal};
}
export function restoreNetworkEnergyFormulation(request:SolicitudEnsamblajeV2,id:string):void {
  const meta=metadata(request),volume=request.volumenes.find(item=>item.id===id),previous=meta.previousEnergyFormulations?.[id];
  if(!volume||!previous)throw new Error('No previous first-law formulation is stored.');
  const {monofasico,sinCambioFase,densidadConstante,modelo}=volume.formulacionEnergia;
  volume.formulacionEnergia={...structuredClone(previous),monofasico,sinCambioFase,densidadConstante,modelo};
  delete meta.energyDerivation?.volumes[id];
  if(meta.energyDerivation&&!Object.keys(meta.energyDerivation.volumes).length)delete meta.energyDerivation;
  delete meta.previousEnergyFormulations?.[id];
  if(meta.previousEnergyFormulations&&!Object.keys(meta.previousEnergyFormulations).length)delete meta.previousEnergyFormulations;
  request.derivacion=meta;
}
