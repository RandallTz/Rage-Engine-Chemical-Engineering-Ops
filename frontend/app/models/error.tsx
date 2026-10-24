'use client';
import Link from 'next/link';
import styles from './workspace.module.css';
export default function ModelError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <section className={styles.shell} role="alert"><div className={styles.empty}><span className={styles.kicker}>Model workspace</span><h1>The model could not be opened</h1><p>Try loading the workspace again. Your saved browser data has not been removed.</p><button className={styles.primary} onClick={reset}>Try again</button><p><Link href="/models">Return to models →</Link></p></div></section>;
}
