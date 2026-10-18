'use client';
import {usePathname} from 'next/navigation';
import type {ReactNode} from 'react';
import {useHojasMotor} from './useHojasMotor';
import styles from './balances.module.css';
export default function TemaMotor({children}:{children:ReactNode}){
  const pathname=usePathname();
  const hojas=useHojasMotor(),id=pathname.match(/^\/motor\/hojas\/([^/]+)/)?.[1];
  const balance=hojas.find(h=>h.id===id)?.vistaBalance??'materia';
  return <div className={styles.espacio} data-balance={balance}>{children}</div>;
}
