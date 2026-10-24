'use client';
import Link from 'next/link';
import {useHojasMotor} from '../motor/useHojasMotor';
import CommonModelContent from './CommonModelContent';
import HojaGuardada from '../motor/HojaGuardada';
import EstadoSistema from '../motor/EstadoSistema';
import type { EnfoqueRed } from '../motor/destinoDiagnosticoRed';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';
import ModelDerivationStatus from './ModelDerivationStatus';
import { ModelConfigurationProvider } from './ModelWorksheet';
import { DynamicModelProvider } from './DynamicModelDefinition';

export default function ModelDefinition({ id, state = false, focus }: { id: string; state?: boolean; focus?: EnfoqueRed }) {
  const model=useHojasMotor().find(item=>item.id===id);
  if(model?.commonModel)return <DynamicModelProvider id={id}><CommonModelContent model={model}/></DynamicModelProvider>;
  return <><nav className={styles.subnav} aria-label="Model definition"><Link href={modelUrl(id)} aria-current={!state ? 'page' : undefined}>Equations & assumptions</Link><Link href={`${modelUrl(id)}/state`} aria-current={state ? 'page' : undefined}>Physical system</Link></nav><ModelDerivationStatus id={id}/><DynamicModelProvider id={id}><ModelConfigurationProvider open={state} content={<EstadoSistema id={id} enfoque={focus}/>}><HojaGuardada id={id}/></ModelConfigurationProvider></DynamicModelProvider></>;
}
