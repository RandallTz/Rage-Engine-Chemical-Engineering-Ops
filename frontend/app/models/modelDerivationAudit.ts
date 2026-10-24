import { energyJournalInRequest, energyJournalMatches, energyJournalFromHistory, thermodynamicJournalInRequest, thermodynamicJournalMatches, thermodynamicJournalFromHistory, configuredClosure } from '../motor/physicalDerivation';
/** Read-only provenance audit. This checks stored evidence, never reconstructs a
 * supposed historical deduction from the final flags or certifies its physics. */
import type { HojaMotor } from '../motor/hojasMotor';
import type { RecorridoMateria } from '../motor/recorridoMateria';
import { iniciarRecorrido, recorridoMateria } from '../motor/recorridoMateria';
import { ENERGIA_FUNDAMENTAL } from '../motor/recorridoEnergia';
import { TERMO_FUNDAMENTAL } from '../motor/recorridoTermodinamico';
import { balancesHoja } from '../motor/seleccionBalances';
import { journalInRequest, journalMatches } from '../motor/materialDerivation';
import { momentumJournalOf } from './momentumDerivation';

export type DerivationFinding = { code: string; severity: 'gap' | 'limitation'; ownerId: string; family: 'matter' | 'energy' | 'thermodynamics' | 'momentum'; message: string };
export type ModelDerivationAudit = { status: 'fundamental' | 'recorded' | 'needs_review'; recordedSteps: number; findings: DerivationFinding[] };

function equal(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => equal(value, right[index]));
  const a = left as Record<string, unknown>, b = right as Record<string, unknown>;
  return Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => Object.hasOwn(b, key) && equal(a[key], b[key]));
}

export function auditModelDerivation(model: HojaMotor): ModelDerivationAudit {
  if(model.commonModel){const journals=model.commonModel.motores;const counts=[journals.materialDerivation,journals.energyDerivation,journals.thermodynamicDerivation,journals.momentumDerivation].flatMap(journal=>Object.values(journal?.volumes??{})).reduce((sum,entry)=>sum+entry.operations.length,0);return {status:counts?'recorded':'needs_review',recordedSteps:counts,findings:[]};}
  const findings: DerivationFinding[] = [];
  let recordedSteps = 0;
  const add = (ownerId: string, family: DerivationFinding['family'], code: string, message: string) => findings.push({ code, severity: code === 'snapshot_history' ? 'limitation' : 'gap', ownerId, family, message });
  let momentum:ReturnType<typeof momentumJournalOf>;
  try{momentum=momentumJournalOf(model);}catch(error){add('model','momentum','invalid_journal',(error as Error).message);}
  function auditMomentum(owner:string,active:boolean){if(!active)return;const entry=momentum?.volumes[owner];if(entry)recordedSteps+=entry.operations.length;else add(owner,'momentum','missing_history','Start the momentum journal explicitly from the fundamental Cauchy balance.');}
  function matter(history: RecorridoMateria | undefined, owner: string) {
    if (!history?.pasos.length || !Number.isInteger(history.activo) || !history.pasos[history.activo]) {
      add(owner, 'matter', 'missing_history', 'No usable material derivation is stored.'); return;
    }
    const path: number[] = [], seen = new Set<number>();
    let index: number | null = history.activo;
    while (index !== null) {
      if (!Number.isSafeInteger(index) || !history.pasos[index] || seen.has(index)) {
        add(owner, 'matter', 'broken_ancestry', 'The active material derivation has a missing or cyclic predecessor.'); return;
      }
      seen.add(index); path.unshift(index); index = history.pasos[index].origen;
    }
    const root = history.pasos[path[0]];
    if (!equal(root.formulacion, iniciarRecorrido().pasos[0].formulacion) || root.operacion !== null) {
      add(owner, 'matter', 'nonfundamental_root', 'The stored material derivation starts from an already modified formulation.'); return;
    }
    let replay = iniciarRecorrido();
    for (const index of path.slice(1)) {
      const step = history.pasos[index];
      if (!step.operacion) { add(owner, 'matter', 'missing_operation', `The step “${step.titulo}” has no recorded operation.`); return; }
      replay = recorridoMateria(replay, { tipo: 'cambiar', titulo: step.titulo, cambios: step.operacion });
      if (!equal(replay.pasos[replay.activo].formulacion, step.formulacion)) {
        add(owner, 'matter', 'snapshot_mismatch', `The stored result of “${step.titulo}” differs from replaying its operation.`); return;
      }
      recordedSteps++;
    }
  }
  if (model.redTermodinamica) {
    let journal;
    try { journal = journalInRequest(model.redTermodinamica.solicitud.derivacion); }
    catch (error) { add('model', 'matter', 'invalid_journal', (error as Error).message); }
    let energyJournal;
    try{energyJournal=energyJournalInRequest(model.redTermodinamica.solicitud.derivacion);}catch(error){add('model','energy','invalid_journal',(error as Error).message);}
    let thermodynamicJournal;
    try{thermodynamicJournal=thermodynamicJournalInRequest(model.redTermodinamica.solicitud.derivacion);}catch(error){add('model','thermodynamics','invalid_journal',(error as Error).message);}
    for (const volume of model.redTermodinamica.solicitud.volumenes) {
      auditMomentum(volume.id,volume.balances.momento);
      const entry = journal?.volumes[volume.id];
      if (entry && journalMatches(entry, volume.formulacionMateria)) recordedSteps += entry.operations.length;
      else add(`volume:${volume.id}`, 'matter', entry ? 'journal_mismatch' : 'final_request_only', entry
        ? 'The material journal differs from the effective assumptions. Rebuild or restore it before compilation.'
        : 'This volume has no material operation journal. Start an explicit derivation from the fundamental law.');
      const energyEntry=energyJournal?.volumes[volume.id];
      if(energyEntry&&energyJournalMatches(energyEntry,volume.formulacionEnergia))recordedSteps+=energyEntry.operations.length;
      else add(`volume:${volume.id}`,'energy','final_request_only','Start an explicit first-law derivation for this volume.');
      const thermoEntry=thermodynamicJournal?.volumes[volume.id];
      try{
        if(thermoEntry&&thermodynamicJournalMatches(thermoEntry,volume.formulacionEnergia,configuredClosure(model.redTermodinamica.solicitud,volume)))recordedSteps+=thermoEntry.operations.length;
        else add(`volume:${volume.id}`,'thermodynamics','final_request_only','The state closure needs recorded constitutive choices and phase assumptions.');
      }catch(error){add(`volume:${volume.id}`,'thermodynamics','journal_mismatch',(error as Error).message);}
    }
    return { status: findings.some(finding=>finding.severity==='gap')?'needs_review':recordedSteps?'recorded':'fundamental', recordedSteps, findings };
  }
  if (model.ensamblaje) for (const volume of model.ensamblaje.volumenes) matter(volume.historial, `volume:${volume.id}`);
  else matter(model.historial, 'volume:dominio');
  const balances = balancesHoja(model);
  if (balances.energia) {
    const history = model.energia?.historial;
    if (!history?.pasos.length) add('model', 'energy', 'missing_history', 'An active energy balance has no stored derivation.');
    else {
      if (!equal(history.pasos[0].formulacion, ENERGIA_FUNDAMENTAL)) add('model', 'energy', 'nonfundamental_root', 'The energy history does not start from the fundamental local first law.');
      recordedSteps += Math.max(0, history.pasos.length - 1);
      let replayable=false;
      try{replayable=!!energyJournalFromHistory(history);}catch(error){add('model','energy','journal_mismatch',(error as Error).message);}
      if(!replayable)add('model', 'energy', 'snapshot_history', 'Energy stores ordered formulation snapshots and relations, but not replayable operation records. Full replay validation is still missing.');
    }
  }
  const thermo = model.recorridoTermodinamico;
  if (thermo) {
    if (!thermo.pasos.length || !equal(thermo.pasos[0].supuestos, TERMO_FUNDAMENTAL)) add('model', 'thermodynamics', 'nonfundamental_root', 'The thermodynamic history does not start from the unrestricted fundamental relations.');
    recordedSteps += Math.max(0, thermo.pasos.length - 1);
    let replayable=false;
    try{replayable=!!thermodynamicJournalFromHistory(thermo);}catch(error){add('model','thermodynamics','journal_mismatch',(error as Error).message);}
    if (thermo.pasos.length > 1&&!replayable) add('model', 'thermodynamics', 'snapshot_history', 'Thermodynamic assumptions have ordered snapshots, but no independently replayable operation records.');
  } else if (balances.energia || Object.keys(model.cierresDinamicos ?? {}).length) {
    add('model', 'thermodynamics', 'missing_history', 'The active state closure has no stored thermodynamic deduction journal.');
  }
  if(model.ensamblaje)for(const volume of model.ensamblaje.volumenes)auditMomentum(volume.id,volume.balances?.momento??balances.momento);
  else auditMomentum('dominio',balances.momento);
  return { status: findings.some(finding => finding.severity === 'gap') ? 'needs_review' : recordedSteps ? 'recorded' : 'fundamental', recordedSteps, findings };
}
