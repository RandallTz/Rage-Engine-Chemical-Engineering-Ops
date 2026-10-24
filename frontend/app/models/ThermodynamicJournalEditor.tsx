'use client';

import { useEffect, useRef, useState } from 'react';
import type { SolicitudEnsamblajeV2, VolumenV2 } from '../motor/contratoEnsamblajeV2';
import { emptyThermodynamicJournal, thermodynamicJournalInRequest, requestThermodynamicDevelopment, configuredClosure } from '../motor/physicalDerivation';
import type { ThermodynamicDevelopment, ThermodynamicJournal, ThermodynamicState } from '../motor/physicalDerivation';
import Link from 'next/link';
import RecordedDerivation from './RecordedDerivation';
import { ThermodynamicAssumptions } from '../motor/ModelAssumptions';
import { appendRecordedOperation } from '../motor/physicalDerivation';
import { OPERACIONES_TERMO, TERMO_FUNDAMENTAL } from '../motor/recorridoTermodinamico';
import { modelUrl } from './workflow';

export default function ThermodynamicJournalEditor({ request, volume, save, restore, canRestore, modelId }: {
  request: SolicitudEnsamblajeV2; volume: VolumenV2;modelId:string;
  save: (journal: ThermodynamicJournal, formulation: ThermodynamicState, starting: boolean, expected: string) => boolean;
  restore: () => void; canRestore: boolean;
}) {
  const signature = JSON.stringify(request), controller = useRef<AbortController | null>(null);
  const [response, setResponse] = useState<{ signature: string; development: ThermodynamicDevelopment } | null>(null);
  const [error, setError] = useState(''), [pending, setPending] = useState<string | null>(null);
  let journal: ThermodynamicJournal | undefined, invalid = '';
  try { journal = thermodynamicJournalInRequest(request.derivacion); } catch (failure) { invalid = (failure as Error).message; }
  const entry = journal?.volumes[volume.id];

  const current = response?.signature === signature ? response.development : null;
  useEffect(() => {
    controller.current?.abort();
    if (!entry || invalid) return;
    const abort = new AbortController(); controller.current = abort;
    requestThermodynamicDevelopment(journal!, volume.id, volume.frontera.tipo==='rigida', undefined, undefined, abort.signal)
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
      const result = await requestThermodynamicDevelopment(journal ?? emptyThermodynamicJournal(), volume.id, volume.frontera.tipo==='rigida', { kind }, kind==='select_closure'?configuredClosure(request,volume):undefined, abort.signal);
      if (abort.signal.aborted) return;
      save(result.journal, result.development.formulation, kind === 'start', signature);
    } catch (failure) { if (!abort.signal.aborted) setError((failure as Error).message); }
    finally { setPending(null); }
  }

  async function change(operation:typeof OPERACIONES_TERMO[number],active:boolean){
    if(!journal||!entry||!current)return;
    const abort=new AbortController();controller.current?.abort();controller.current=abort;
    setPending('edit');setError('');
    try{
      const changes:Partial<ThermodynamicState>={[operation.clave]:active?operation.valor:TERMO_FUNDAMENTAL[operation.clave]};
      if(current.formulation.closure&&(operation.clave==='monofasico'||operation.clave==='sinCambioFase')){
        const closure=structuredClone(current.formulation.closure);
        if(operation.clave==='monofasico')closure.policy.cantidad=active?'monofasico':'sin_restriccion';
        else closure.policy.cambioInterno=active?'prohibido':'permitido';
        changes.closure=closure;
      }
      const next=structuredClone(journal);next.volumes[volume.id]=appendRecordedOperation(entry,`${active?'Apply':'Remove'}: ${operation.nombre}`,changes);
      const result=await requestThermodynamicDevelopment(next,volume.id,volume.frontera.tipo==='rigida',undefined,undefined,abort.signal);
      if(!abort.signal.aborted&&!save(result.journal,result.development.formulation,false,signature))throw new Error('The deduction could not be saved.');
    }catch(failure){if(!abort.signal.aborted)setError((failure as Error).message);}finally{setPending(null);}
  }
  return <RecordedDerivation family="Thermodynamic" steps={current?.steps} notes={current?.notes} pending={!!pending} canUndo={!!entry?.operations.length} undo={()=>apply('undo')} start={!entry?()=>apply('start'):undefined} restore={canRestore?restore:undefined} error={error||invalid} rebuilt={entry?.origin==='reviewed_rebuild'}
    sidebar={<><ThermodynamicAssumptions state={volume.formulacionEnergia} policy={volume.politica} equilibrium change={change} disabled={!entry||!current||!!pending||!!invalid}/><fieldset><legend>Equilibrium package</legend><p>{request.paquetes.find(item=>item.id===volume.paqueteId)?.modelo.id??'Missing package'}</p><button disabled={!entry||!!pending} onClick={()=>apply('select_closure')}>Adopt configured package and policy</button><Link href={`${modelUrl(modelId)}/state?elemento=volumen:${volume.id}`}>Configure package in Model →</Link></fieldset></>}/>;
}
