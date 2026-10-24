'use client';

import { useEffect, useRef, useState } from 'react';
import type { SolicitudEnsamblajeV2, VolumenV2 } from '../motor/contratoEnsamblajeV2';
import { emptyEnergyJournal, energyJournalInRequest, requestEnergyDevelopment } from '../motor/physicalDerivation';
import type { EnergyDevelopment, EnergyJournal, EnergyState } from '../motor/physicalDerivation';
import RecordedDerivation from './RecordedDerivation';
import { EnergyAssumptions } from '../motor/ModelAssumptions';
import { appendRecordedOperation } from '../motor/physicalDerivation';

export default function EnergyJournalEditor({ request, volume, save, restore, canRestore }: {
  request: SolicitudEnsamblajeV2; volume: VolumenV2;
  save: (journal: EnergyJournal, formulation: EnergyState, starting: boolean, expected: string) => boolean;
  restore: () => void; canRestore: boolean;
}) {
  const signature = JSON.stringify(request), controller = useRef<AbortController | null>(null);
  const [response, setResponse] = useState<{ signature: string; development: EnergyDevelopment } | null>(null);
  const [error, setError] = useState(''), [pending, setPending] = useState<string | null>(null);
  let journal: EnergyJournal | undefined, invalid = '';
  try { journal = energyJournalInRequest(request.derivacion); } catch (failure) { invalid = (failure as Error).message; }
  const entry = journal?.volumes[volume.id];
  const context={fixed:volume.frontera.tipo==='rigida',remainderClosed:volume.formulacionMateria.restoImpermeable,streamIds:request.corrientes.filter(stream=>stream.desde===volume.id||stream.hasta===volume.id).map(stream=>stream.id),pressurePrescribed:!!volume.formulacionEnergia.presionPrescrita};
  const current = response?.signature === signature ? response.development : null;
  useEffect(() => {
    controller.current?.abort();
    if (!entry || invalid) return;
    const abort = new AbortController(); controller.current = abort;
    requestEnergyDevelopment(journal!, volume.id, context, undefined, abort.signal)
      .then(result => { if (!abort.signal.aborted) setResponse({ signature, development: result.development }); })
      .catch(failure => { if (!abort.signal.aborted) setError((failure as Error).message); });
    return () => abort.abort();
    // The serialized request includes the journal, volume, assumptions and topology.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, volume.id]);

  async function apply(kind: string) {
    const abort = new AbortController(); controller.current?.abort(); controller.current = abort;
    setPending(kind); setError('');
    try {
      const result = await requestEnergyDevelopment(journal ?? emptyEnergyJournal(), volume.id, context, { kind }, abort.signal);
      if (abort.signal.aborted) return;
      save(result.journal, result.development.formulation, kind === 'start', signature);
    } catch (failure) { if (!abort.signal.aborted) setError((failure as Error).message); }
    finally { setPending(null); }
  }

  async function change(title:string,changes:Partial<EnergyState>){
    if(!journal||!entry)return;
    const abort=new AbortController();controller.current?.abort();controller.current=abort;
    setPending('edit');setError('');
    try{
      const next=structuredClone(journal);
      if(changes.sinTrabajoViscoso&&!volume.formulacionEnergia.separarPresion)next.volumes[volume.id]=appendRecordedOperation(entry,'Separate pressure and viscous stress',{separarPresion:true});
      if(changes.presionPrescrita)changes={...changes,presionUniforme:true};
      next.volumes[volume.id]=appendRecordedOperation(next.volumes[volume.id],title,changes);
      const result=await requestEnergyDevelopment(next,volume.id,context,undefined,abort.signal);
      if(!abort.signal.aborted&&!save(result.journal,result.development.formulation,false,signature))throw new Error('The deduction could not be saved.');
    }catch(failure){if(!abort.signal.aborted)setError((failure as Error).message);}finally{setPending(null);}
  }
  return <RecordedDerivation family="Energy" steps={current?.steps} notes={current?.notes} pending={!!pending} canUndo={!!entry?.operations.length} undo={()=>apply('undo')} start={!entry?()=>apply('start'):undefined} restore={canRestore?restore:undefined} error={error||invalid} rebuilt={entry?.origin==='reviewed_rebuild'}
    sidebar={<EnergyAssumptions formulation={volume.formulacionEnergia} context={{puertos:request.corrientes.filter(stream=>stream.desde===volume.id||stream.hasta===volume.id),componentesIds:volume.componenteIds}} matter={{fija:context.fixed,restoImpermeable:context.remainderClosed}} cambiar={change} onForm={forma=>change('Change first-law representation',{forma})} disabled={!entry||!!pending||!!invalid}/>}/>;
}
