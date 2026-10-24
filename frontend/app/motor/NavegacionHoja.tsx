import Link from 'next/link';
import { modelUrl, WORKSPACES } from '../models/workflow';
import styles from './trabajoMotor.module.css';
export default function NavegacionHoja({ id, actual, propietarioId }: { id: string; propietarioId?: string; actual: 'ecuaciones' | 'estado' | 'resolver' | 'resultados' }) {
  const active = actual === 'resolver' ? 'solve' : actual === 'resultados' ? 'results' : 'model';
  return <nav className={styles.workNav} aria-label="Model workflow"><Link href="/models">← Models</Link>{WORKSPACES.map(stage => { const owner = propietarioId && (stage.id === 'model' || stage.id === 'solve' && propietarioId !== 'componentes'); const href = modelUrl(id, stage.id) + (stage.id === 'model' && owner ? '/state' : '') + (owner ? `?${new URLSearchParams({elemento:propietarioId!})}` : ''); return <Link key={stage.id} href={href} aria-current={active === stage.id ? 'page' : undefined}>{stage.name}</Link>; })}</nav>;
}
