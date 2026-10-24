'use client';

import Link from 'next/link';
import { useHojasMotor } from '../motor/useHojasMotor';
import { auditModelDerivation } from './modelDerivationAudit';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';

export default function ModelDerivationStatus({ id }: { id: string }) {
  const model = useHojasMotor().find(item => item.id === id);
  if (!model) return null;
  const audit = auditModelDerivation(model);
  const network = !!model.redTermodinamica;
  return <section className={styles.derivationStandard} aria-label="Assumptions and derivation standard">
    <details open={audit.status==='needs_review'}><summary>{audit.status === 'fundamental' ? 'Fundamental starting point · no assumptions applied' : audit.status === 'recorded' ? `Recorded assumptions · ${audit.recordedSteps} steps` : 'Derivation evidence needs review'}</summary>
    <p>Fundamental laws → recorded assumptions → derived physical model. History records how the model was built; it does not certify physical validity or solver compatibility.</p>
    {audit.findings.length > 0 && <details className={styles.derivationFindings}><summary>Audit details · {audit.findings.length} {audit.findings.length === 1 ? 'finding' : 'findings'}</summary><ul>{audit.findings.map((finding, index) => <li key={`${finding.ownerId}:${finding.family}:${index}`}><strong>{finding.ownerId} · {finding.family} · {finding.severity === 'gap' ? 'Missing evidence' : 'Verification limit'}</strong><p>{finding.message}</p></li>)}</ul><p>{network ? 'Per-volume journals are available in Matter, Energy and Thermodynamics. Rebuild missing histories explicitly; a recorded journal is provenance, not a physical certificate.' : 'Stored evidence is preserved. Missing history is not filled in automatically from the final formulation.'}</p></details>}
    <Link href={`${modelUrl(id)}/state`}>Configure the physical system →</Link>
    </details>
  </section>;
}
