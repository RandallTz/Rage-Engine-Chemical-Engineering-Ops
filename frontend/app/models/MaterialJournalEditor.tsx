'use client';

import { useEffect, useRef, useState } from 'react';
import type { SolicitudEnsamblajeV2, VolumenV2 } from '../motor/contratoEnsamblajeV2';
import { emptyMaterialJournal, journalInRequest, requestMaterialDevelopment } from '../motor/materialDerivation';
import type { MaterialDevelopment, MaterialJournal, MaterialState } from '../motor/materialDerivation';
import Link from 'next/link';
import RecordedDerivation from './RecordedDerivation';
import { MaterialAssumptions } from '../motor/ModelAssumptions';
import VariablesMateria from '../motor/VariablesMateria';
import { materialState } from '../motor/materialDerivation';
import { appendRecordedOperation } from '../motor/physicalDerivation';
import type { FormulacionMateria } from '../motor/recorridoMateria';
import { modelUrl } from './workflow';
import styles from '../motor/motor.module.css';

export default function MaterialJournalEditor({ request, volume, save, restore, canRestore, modelId }: {
  request: SolicitudEnsamblajeV2; volume: VolumenV2; modelId:string;
  save: (journal: MaterialJournal, formulation: MaterialState, starting: boolean, expected: string) => boolean;
  restore: () => void; canRestore: boolean;
}) {
  const signature = JSON.stringify(request), controller = useRef<AbortController | null>(null);
  const [response, setResponse] = useState<{ signature: string; development: MaterialDevelopment } | null>(null);
  const [error, setError] = useState(''), [pending, setPending] = useState<string | null>(null);
  let journal: MaterialJournal | undefined, invalid = '';
  try { journal = journalInRequest(request.derivacion); } catch (failure) { invalid = (failure as Error).message; }
  const entry = journal?.volumes[volume.id];
  const current = response?.signature === signature ? response.development : null;
  useEffect(() => {
    controller.current?.abort();
    if (!entry || invalid) return;
    const abort = new AbortController(); controller.current = abort;
    requestMaterialDevelopment(journal!, volume.id, undefined, abort.signal)
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
      const result = await requestMaterialDevelopment(journal ?? emptyMaterialJournal(), volume.id, { kind }, abort.signal);
      if (abort.signal.aborted) return;
      save(result.journal, result.development.formulation, kind === 'start', signature);
    } catch (failure) { if (!abort.signal.aborted) setError((failure as Error).message); }
    finally { setPending(null); }
  }

  async function change(title:string,changes:Partial<FormulacionMateria>){
    if(!journal||!entry)return;
    const abort=new AbortController();controller.current?.abort();controller.current=abort;
    setPending('edit');setError('');
    try{
      const next=structuredClone(journal);next.volumes[volume.id]=appendRecordedOperation(entry,title,materialState(changes));
      const result=await requestMaterialDevelopment(next,volume.id,undefined,abort.signal);
      if(!abort.signal.aborted&&!save(result.journal,result.development.formulation,false,signature))throw new Error('The deduction could not be saved.');
    }catch(failure){if(!abort.signal.aborted)setError((failure as Error).message);}finally{setPending(null);}
  }
  const formulation:FormulacionMateria={...volume.formulacionMateria,componentes:request.componentes.filter(component=>volume.componenteIds.includes(component.id)),fronteras:[]};
  return <RecordedDerivation family="Material" steps={current?.steps} notes={current?.notes} pending={!!pending} canUndo={!!entry?.operations.length} undo={()=>apply('undo')} start={!entry?()=>apply('start'):undefined} restore={canRestore?restore:undefined} error={error||invalid} rebuilt={entry?.origin==='reviewed_rebuild'}
    sidebar={<MaterialAssumptions formulation={formulation} stepNumber={(entry?.operations.length??0)+1} cambiar={change} enEnsamblaje disabled={!entry||!!pending||!!invalid} components={<fieldset className={styles.operationGroup}><legend>Components</legend>{formulation.componentes?.map(component=><p key={component.id} className={styles.groupHint}>{component.nombre} · {component.simbolo}</p>)}<Link className={styles.textOperation} href={`${modelUrl(modelId)}/state?elemento=componentes`}>Edit components →</Link></fieldset>}/>}
    variables={<VariablesMateria formulacion={formulation}/>}/>;
}
