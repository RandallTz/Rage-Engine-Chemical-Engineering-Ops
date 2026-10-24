import type { ReactNode } from 'react';
import type { Metadata } from 'next';
import styles from './workspace.module.css';
export const metadata: Metadata = { title: 'Models · Rage', description: 'Define, transform, solve and inspect mathematical models in one connected workspace.' };
export default function ModelsLayout({ children }: { children: ReactNode }) { return <div className={styles.theme}>{children}</div>; }
