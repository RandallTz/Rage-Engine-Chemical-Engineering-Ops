'use client';
import Link from 'next/link';
import styles from './trabajoMotor.module.css';
export default function ErrorMotor({reset}:{error:Error;reset:()=>void}){return <div className={styles.page}><h1>No se pudo abrir la hoja</h1><p>Los datos guardados no se han sobrescrito.</p><button className={styles.primary} onClick={reset}>Volver a intentar</button><Link href="/motor"> Abrir una hoja sin guardar</Link></div>;}
