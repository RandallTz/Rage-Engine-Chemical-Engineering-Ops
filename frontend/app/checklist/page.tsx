import type {Metadata} from 'next';
import {checklistMotor} from './datos';
import styles from './checklist.module.css';

export const metadata: Metadata = {title: 'Checklist · Engine'};

export default function ChecklistPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>Checklist del Engine</h1>
        <a href="/checklist/documento" download="CHECKLIST_MOTOR.md">Descargar checklist</a>
      </header>
      <div className={styles.grid}>
        {checklistMotor.map(grupo => (
          <section key={grupo.id} className={styles.section} data-area={grupo.id} aria-labelledby={grupo.id}>
            <h2 id={grupo.id}>{grupo.nombre}</h2>
            {(['hecho', 'pendiente', 'aplazado'] as const).filter(estado => grupo[estado].length > 0).map(estado => (
              <div key={estado} className={styles.group}>
                <h3>{estado === 'hecho' ? 'Hecho' : estado === 'pendiente' ? 'Pendiente' : 'Aplazado'}<span>{grupo[estado].length}</span></h3>
                <ul>
                  {(grupo[estado] as readonly string[]).map(item => (
                    <li key={item} data-done={estado === 'hecho'}>
                      <span className={styles.check} aria-hidden="true" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
