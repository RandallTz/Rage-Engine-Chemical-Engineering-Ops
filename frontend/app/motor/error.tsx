'use client';
import Link from 'next/link';
import styles from './trabajoMotor.module.css';
export default function ErrorMotor({reset}:{error:Error;reset:()=>void}){return <div className={styles.page}><h1>The model could not be opened</h1><p>Saved data has not been overwritten.</p><button className={styles.primary} onClick={reset}>Try again</button><Link href="/motor"> Open an unsaved model</Link></div>;}
