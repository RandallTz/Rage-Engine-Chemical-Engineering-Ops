import type {Metadata} from 'next';
import {capabilityReviewDate,engineCapabilities} from './datos';
import styles from './checklist.module.css';
export const metadata:Metadata={title:'Engine capabilities · Checklist'};
export default function ChecklistPage(){
  return <div className={styles.page}>
    <header className={styles.header}><div><h1>Engine capabilities</h1><p>What you can model, transform, solve and inspect today.</p><p>Reviewed {capabilityReviewDate} · Availability applies to the scope stated below.</p></div><a href="/checklist/documento" download="engine-checklist.md">Download checklist</a></header>
    <nav className={styles.navigation} aria-label="Capability areas">{engineCapabilities.map(area=><a key={area.id} href={`#${area.id}`}>{area.name}</a>)}</nav>
    <div className={styles.grid}>{engineCapabilities.map(area=><section key={area.id} className={styles.section} data-area={area.id} aria-labelledby={area.id}><h2 id={area.id}>{area.name}</h2><p className={styles.workspace}>{area.workspace}</p>
      {(['available','pending','deferred'] as const).filter(status=>area[status].length>0).map(status=><div key={status} className={styles.group}><h3>{status==='available'?'Available':status==='pending'?'Pending':'Deferred'}<span>{area[status].length}</span></h3><ul>{(area[status] as readonly string[]).map(item=><li key={item} data-done={status==='available'}><span className={styles.check} aria-hidden="true"/><span>{item}</span></li>)}</ul></div>)}
    </section>)}</div>
  </div>;
}
