"use client";
import { useState, type ReactNode } from 'react';
import { englishLabel } from '../models/english';
import FormulaLatex from './FormulaMateria';
import DiagramaCoordenadas from './DiagramaCoordenadas';
import { FORMAS_MATERIA, acumulacionTotalNula, fuenteUniforme, campoEfectivo } from './recorridoMateria';
import type { FormaMateria, FormulacionMateria } from './recorridoMateria';
import { COORDENADAS, fuentesActivas } from './operadores';
import type { Coordenadas, LeyDifusion } from './operadores';
import styles from './motor.module.css';
import { OPERACIONES_TERMO, type SupuestosTermo } from './recorridoTermodinamico';
import energyStyles from './balances.module.css';
import type {FormulacionEnergia,FormaEnergia} from './recorridoEnergia';
import type {MomentumDevelopment, MomentumControl} from '../models/momentumDerivation';

/** General physical switches; the Python replay supplies dependencies and effects. */
export function MomentumAssumptions({development,disabled,change,represent}:{development:MomentumDevelopment|undefined;disabled:boolean;change:(key:MomentumControl['key'],value:boolean)=>void;represent:(action:string)=>void}){
  const controls=development?.controls??[],groups=[...new Set(controls.map(control=>control.group))];
  const option=(control:MomentumControl)=><label key={control.key} className={styles.smallOption} title={control.reason||undefined}><input type="checkbox" aria-label={control.label} checked={control.value} disabled={!control.canChange} onChange={event=>change(control.key,event.target.checked)}/><span>{control.label}{!control.canChange&&<small>{control.reason}</small>}</span></label>;
  return <fieldset className={styles.assumptionControls} disabled={disabled||!development}>
    <fieldset className={styles.operationGroup}><legend>Equation form</legend><div className={styles.formChoices}>{development?.forms?.map(form=><button key={form.id} aria-pressed={form.selected} disabled={!form.canSelect} title={form.selected?'Current representation':form.reason||undefined} onClick={()=>represent(form.action)}>{form.label}</button>)}</div><p className={styles.groupHint}>Each change records its own deduction. Undo revisits earlier representations.</p></fieldset>
    {!controls.length&&<p role="status">Physical controls require the updated momentum service.</p>}
    {groups.map(group=>{
      const rows=controls.filter(control=>control.group===group);
      const content=group==='Space and velocity'?<>{rows.filter(c=>c.key==='expandCartesian').map(option)}<span className={styles.groupHint}>No field variation along:</span><div className={styles.axisToggles}>{rows.filter(c=>c.key.startsWith('invariant')).map(c=><label key={c.key} data-active={c.value} title={c.reason||undefined}><input type="checkbox" aria-label={c.label} checked={c.value} disabled={!c.canChange} onChange={e=>change(c.key,e.target.checked)}/>{c.key.slice(-1).toLowerCase()}</label>)}</div><span className={styles.groupHint}>No velocity variation along:</span><div className={styles.axisToggles}>{rows.filter(c=>c.key.startsWith('velocityInvariant')).map(c=><label key={c.key} data-active={c.value} title={c.reason||undefined}><input type="checkbox" aria-label={c.label} checked={c.value} disabled={!c.canChange} onChange={e=>change(c.key,e.target.checked)}/>{c.key.slice(-1).toLowerCase()}</label>)}</div><span className={styles.groupHint}>Zero velocity components:</span><div className={styles.twoOptions}>{rows.filter(c=>c.key.startsWith('zeroVelocity')).map(option)}</div><p className={styles.groupHint}>Cartesian axes. Field invariance affects all fields. Velocity invariance keeps pressure gradients possible. Zero velocity retains its transverse force balance.</p></>:rows.map(option);
      const field=<fieldset className={styles.operationGroup}><legend>{group}</legend>{content}{group==='Accumulation'&&<p className={styles.groupHint}>These are permanent momentum constraints. The dynamic law stays visible; an initially stationary condition belongs in Solve.</p>}</fieldset>;
      return ['Geometry and hydraulic closure','Angular momentum and shaft','Geometry and energy closures'].includes(group)?<details key={group} className={styles.details}><summary>{group}</summary>{field}</details>:<div key={group}>{field}</div>;
    })}
  </fieldset>;
}

/** One assumptions panel for ordinary models and recorded network volumes. */
export function MaterialAssumptions({formulation:f,stepNumber,cambiar,components,enEnsamblaje=false,disabled=false,coordinateReview}:{
  formulation:FormulacionMateria;stepNumber:number;components:ReactNode;enEnsamblaje?:boolean;disabled?:boolean;
  cambiar:(title:string,changes:Partial<FormulacionMateria>)=>void;
  coordinateReview?:{pending:Coordenadas|null;setPending:(value:Coordenadas|null)=>void};
}){
  const {campo,coordenadas,vista,fronteras}=f;
  const [localPending,setLocalPending]=useState<Coordenadas|null>(null);
  const coordenadaPendiente=coordinateReview?coordinateReview.pending:localPending,setCoordenadaPendiente=coordinateReview?.setPending??setLocalPending;
  const activas=fuentesActivas(campo),difusionDeducida=f.componentes?.length===1,difusionActiva=!campoEfectivo(f).sinDifusion;
  const acumulacionDeducida=acumulacionTotalNula({...f,sinAcumulacion:false});
  function cambiarCoordenadas(tipo: Coordenadas) {
    if (tipo === coordenadas) return;
    if (f.invariantes.some(Boolean)) setCoordenadaPendiente(tipo);
    else cambiar(`Coordinates: ${englishLabel(COORDENADAS[tipo].nombre)}`, { coordenadas: tipo });
  }
  function agregar(sentido: 'entrada' | 'salida') {
    cambiar(`Declare ${sentido === 'entrada' ? 'inlet' : 'outlet'}`, { fronteras: [...fronteras, { id: Math.max(0, ...fronteras.map(p => p.id)) + 1, sentido, constante: false }] });
  }
  function fuente(rol: 'generacion' | 'consumo', activa: boolean) {
    cambiar(`${activa ? 'Restore' : 'Remove'} ${rol === 'generacion' ? 'generation' : 'consumption'}`, { campo: { ...campo, sinReaccion: false, sinGeneracion: !activas.generacion, sinConsumo: !activas.consumo, [rol === 'generacion' ? 'sinGeneracion' : 'sinConsumo']: !activa }, ...(!activa ? { [rol === 'generacion' ? 'generacionUniforme' : 'consumoUniforme']: false } : {}) });
  }
  return <>
        <p className={styles.eyebrow}>Next change · step {stepNumber}</p>
        <fieldset className={styles.assumptionControls} disabled={disabled}>
        {components}
        <fieldset className={styles.operationGroup}><legend>Equation form</legend><div className={styles.formChoices}>{(Object.keys(FORMAS_MATERIA) as FormaMateria[]).map(forma => <button aria-pressed={vista === forma} key={forma} onClick={() => cambiar(`Use ${englishLabel(FORMAS_MATERIA[forma]).toLowerCase()} form`, { vista: forma })}>{englishLabel(FORMAS_MATERIA[forma])}</button>)}</div></fieldset>
        <fieldset className={styles.operationGroup}><legend>Transport</legend>{(f.componentes?.length ?? 0) > 1 && <span className={styles.groupHint}>Apply to all components</span>}<div className={styles.twoOptions}>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Convection" checked={!campo.sinConveccion} onChange={e => cambiar(`${e.target.checked ? 'Restore' : 'Remove'} convection`, { campo: { ...campo, sinConveccion: !e.target.checked } })} /><span>Convection</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Diffusion" checked={difusionActiva} disabled={difusionDeducida} title={difusionDeducida ? "One species: its velocity equals the mass-average velocity; j = 0" : undefined} onChange={e => cambiar(`${e.target.checked ? 'Restore' : 'Remove'} diffusion`, { campo: { ...campo, sinDifusion: !e.target.checked } })} /><span>Diffusion{difusionDeducida && <small>Zero · one species</small>}</span></label>
        </div>{difusionActiva && <label className={styles.diffusionChoice}>Diffusion relation<select value={campo.difusion} onChange={e => cambiar(`Apply: ${e.target.selectedOptions[0].text}`, { campo: { ...campo, difusion: e.target.value as LeyDifusion } })}><option value="flujo">General flux · jᵢ</option><option value="fick">Fick · variable ρ and D</option><option value="laplaciano">Fick · spatially uniform ρ and D</option></select></label>}
          <button className={styles.textOperation} disabled={vista !== 'campo'} title={vista !== 'campo' ? "Expansion is available in differential form" : undefined} aria-pressed={f.expandida} onClick={() => cambiar(f.expandida ? "Collapse operators" : "Expand operators", { expandida: !f.expandida })}>{f.expandida ? "Collapse operators" : "Expand operators"}</button>
        </fieldset>
        <fieldset className={styles.operationGroup}><legend>Generation and consumption</legend><div className={styles.sourceOptions}>
          {(['generacion','consumo'] as const).map(rol => <div key={rol}><label className={styles.smallOption}><input type="checkbox" aria-label={rol === 'generacion' ? "Generation" : "Consumption"} checked={activas[rol]} onChange={e => fuente(rol, e.target.checked)} /><span>{rol === 'generacion' ? "Generation" : "Consumption"}</span></label><label className={styles.smallOption}><input type="checkbox" aria-label={`${rol === 'generacion' ? "Generation" : "Consumption"} spatially uniform`} checked={activas[rol] && fuenteUniforme(f, rol)} disabled={!activas[rol] || f.invariantes.every(Boolean)} title={f.invariantes.every(Boolean) ? "Implied by spatial constraints" : undefined} onChange={e => cambiar(`${rol === 'generacion' ? "Generation" : "Consumption"} ${e.target.checked ? 'spatially uniform' : 'spatially varying'}`, { [rol === 'generacion' ? 'generacionUniforme' : 'consumoUniforme']: e.target.checked })} /><span>Spatially uniform</span></label></div>)}
        </div></fieldset>
        <fieldset className={styles.operationGroup}><legend>Space and accumulation</legend>
          {vista!=='campo'&&<p className={styles.groupHint}>Coordinate expansion and directional constraints are shown in Differential form. The integrated conservation law is coordinate-independent.</p>}
          <div className={`${styles.coordinateChoices} ${styles.smallCoordinates}`} role="group" aria-label="Coordinates">{(Object.keys(COORDENADAS) as Coordenadas[]).map(tipo => <button aria-pressed={coordenadas === tipo} aria-label={tipo === 'cartesianas' ? 'Cartesian coordinates' : tipo === 'cilindricas' ? 'Cylindrical coordinates' : 'Spherical coordinates'} key={tipo} onClick={() => cambiarCoordenadas(tipo)}><DiagramaCoordenadas tipo={tipo} /><span>{tipo === 'cartesianas' ? "Cartesian" : tipo === 'cilindricas' ? "Cylindrical" : "Spherical"}</span></button>)}</div>
          {coordenadaPendiente && <section className={styles.coordinateReview} aria-label="Change of coordinates"><span>Directional constraints will be removed.</span><button onClick={() => { cambiar(`Coordinates: ${englishLabel(COORDENADAS[coordenadaPendiente].nombre)} · remove directional constraints`, { coordenadas: coordenadaPendiente, invariantes: [false,false,false] }); setCoordenadaPendiente(null); }}>Change</button><button onClick={() => setCoordenadaPendiente(null)}>Cancel</button></section>}
          <span className={styles.groupHint}>No variation along:</span><div className={styles.axisToggles}>{COORDENADAS[coordenadas].ejes.map((eje, a) => <label key={eje} data-active={f.invariantes[a]}><input type="checkbox" aria-label={`No variation in ${eje.endsWith('theta') ? 'θ' : eje.endsWith('varphi') ? 'φ' : eje}`} checked={f.invariantes[a]} onChange={e => cambiar(`${e.target.checked ? 'No variation' : 'Restore variation'} along ${eje.endsWith('theta') ? 'θ' : eje.endsWith('varphi') ? 'φ' : eje}`, { invariantes: f.invariantes.map((x, i) => a === i ? e.target.checked : x), expandida: true })} /><FormulaLatex latex={eje} lectura={eje} /></label>)}</div>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Fixed boundary" checked={f.fija} onChange={e => cambiar(e.target.checked ? 'Fix the boundary' : 'Allow a moving boundary', { fija: e.target.checked })} /><span>Fixed boundary</span></label>
          {campo.estacionario && <label className={styles.smallOption}><input type="checkbox" aria-label="No local accumulation" checked={campo.estacionario} disabled={!campo.estacionario} onChange={e => cambiar(e.target.checked ? 'Zero local accumulation' : 'Restore local accumulation', { campo: { ...campo, estacionario: e.target.checked } })} /><span>Legacy local stationarity<small>Remove to restore dynamics. New constraints use Dynamic inventories.</small></span></label>}
          {(f.sinAcumulacion || acumulacionDeducida) && <label className={styles.smallOption}><input type="checkbox" aria-label="No total accumulation" checked={acumulacionTotalNula(f)} disabled={acumulacionDeducida || !f.sinAcumulacion} onChange={e => cambiar(e.target.checked ? 'Zero total accumulation' : 'Restore total accumulation', { sinAcumulacion: e.target.checked })} /><span>Legacy total stationarity{acumulacionDeducida && <small>Implied by active relations</small>}</span></label>}
        </fieldset>
        <fieldset className={styles.operationGroup}><legend>Amount and volume</legend>
          {vista==='campo'&&<p className={styles.groupHint}>These inventory relations apply in Integral or Total form; they do not replace a local density field.</p>}
          {!fronteras.length&&<p className={styles.groupHint}>Common port density takes effect after a material inlet or outlet is declared.</p>}
          <label className={styles.smallOption}><input type="checkbox" aria-label="Replace amount with mean density times volume" checked={f.cantidadVolumen} onChange={e => cambiar(e.target.checked ? 'Replace amount with mean density times volume' : 'Restore amount as a variable', { cantidadVolumen: e.target.checked, ...(!e.target.checked ? { densidadMediaConstante: false, densidadComunPuertos: false, expandirProducto: false } : {}) })} /><span><FormulaLatex latex={String.raw`m_i=\bar\rho_i V`} lectura="Component mass equals mean density times volume" /></span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Expand the product derivative" checked={f.expandirProducto} disabled={!f.cantidadVolumen || f.densidadMediaConstante || f.fija} onChange={e => cambiar(e.target.checked ? 'Apply the product rule' : 'Group the product derivative', { expandirProducto: e.target.checked })} /><span>Expand the product derivative</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Mean density constant in time" checked={f.densidadMediaConstante} disabled={!f.cantidadVolumen} onChange={e => cambiar(e.target.checked ? "Mean density constant in time" : 'Mean density varies with time', { densidadMediaConstante: e.target.checked, ...(!e.target.checked ? { densidadComunPuertos: false } : {}) })} /><span>Mean density constant in time</span></label>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Convective ports with a common density" checked={f.densidadComunPuertos} disabled={!f.cantidadVolumen || !f.densidadMediaConstante} onChange={e => cambiar(e.target.checked ? 'Convective ports with a common density' : 'Remove the flow conversion', { densidadComunPuertos: e.target.checked })} /><span>Convective ports, common density</span></label>
        </fieldset>
        {!enEnsamblaje&&<fieldset className={styles.operationGroup}><legend>Boundaries</legend><div className={styles.boundaryActions}><button onClick={() => agregar('entrada')}>+ Inlet</button><button onClick={() => agregar('salida')}>+ Outlet</button></div>
          {fronteras.map(p => <div className={styles.portControl} key={p.id}><header><span>{p.sentido === 'entrada' ? "Inflow" : "Outflow"} {p.id}</span><button aria-label={`Remove boundary ${p.id}`} onClick={() => cambiar(`Remove ${p.sentido === 'entrada' ? 'inlet' : 'outlet'} ${p.id}`, { fronteras: fronteras.filter(x => x.id !== p.id) })}>×</button></header><label className={styles.smallOption}><input type="checkbox" aria-label={`Constant flow at boundary ${p.id}`} checked={p.constante !== false} onChange={e => cambiar(`Flow ${p.id}: ${e.target.checked ? 'constant' : 'time varying'}`, { fronteras: fronteras.map(x => x.id === p.id ? { ...x, constante: e.target.checked } : x) })} /><span>Constant flow</span></label></div>)}
          <label className={styles.smallOption}><input type="checkbox" aria-label="No flow through the remaining boundary" checked={f.restoImpermeable} onChange={e => cambiar(e.target.checked ? 'Close the remaining boundary' : 'Restore flow through the remaining boundary', { restoImpermeable: e.target.checked })} /><span>No flow through the remaining boundary<small>Every surface outside the declared ports.</small></span></label>
          <details className={styles.boundaryHelp}><summary>Meaning of Φᵢ,rest</summary><span>Matter crossing those other surfaces, including undeclared streams. Positive outward; negative inward.</span><span>Without declared ports, this term covers the whole boundary. An impermeable wall contributes zero. It is not generation or consumption.</span></details>
          <label className={styles.smallOption}><input type="checkbox" aria-label="Uniform flow at the ports" checked={f.uniforme} disabled={!fronteras.length} onChange={e => cambiar(e.target.checked ? "Uniform flow per port" : 'Remove uniform port flow', { uniforme: e.target.checked })} /><span>Uniform flow per port</span></label>
        </fieldset>}
        {enEnsamblaje&&<fieldset className={styles.operationGroup}><legend>Remaining boundary</legend><label className={styles.smallOption}><input type="checkbox" aria-label="No flow through the remaining boundary" checked={f.restoImpermeable} onChange={e=>cambiar(e.target.checked?'Close the remaining boundary':'Restore flow through the remaining boundary',{restoImpermeable:e.target.checked})}/><span>No flow elsewhere</span></label><div className={styles.groupHint}>{fronteras.map(p=>`S${p.id}: ${p.sentido==='entrada'?'nominal inflow':'nominal outflow'}`).join(' · ')}</div></fieldset>}
        <details className={styles.details}><summary>Mathematical scope</summary><ul><li>ρᵢ, γᵢ and χᵢ are scalar fields; v and jᵢ are vector fields.</li><li>Integrating a variable rate does not make it uniform. Gᵢ and Cᵢ are aggregate quantities.</li><li>Directional constraints preserve the geometry.</li><li>A constant mean density does not imply a uniform local density.</li><li>V belongs to the whole mixture. Each component has its own mass; additive component volumes are not assigned.</li><li>Velocity is mass-averaged: diffusion fluxes sum to zero in a complete mixture. Scalar Fick laws require a compatible closure; they are not a general multicomponent model.</li><li>The formulation is checked for matter, energy and momentum. Supported numerical capabilities are reported in Solve.</li></ul><a href="https://www.comsol.com/multiphysics/diffusion-equation" target="_blank" rel="noreferrer">Species transport · COMSOL</a></details>
        </fieldset>
      </>;
}

const formas:{id:FormaEnergia;nombre:string}[]=[{id:'local',nombre:'Local'},{id:'integrada',nombre:"Integrate · Gauss"},{id:'integral',nombre:'Reynolds'},{id:'total',nombre:"Total · ports"}];

export function EnergyAssumptions({formulation:f,context:ctx,matter:m,cambiar,onForm,geometria,onTermodinamica,disabled=false}:{
  formulation:FormulacionEnergia;context:{puertos:readonly unknown[];componentesIds:readonly number[]};matter:{fija:boolean;restoImpermeable:boolean};disabled?:boolean;
  cambiar:(title:string,changes:Partial<FormulacionEnergia>,relations?:string[])=>void;
  onForm:(form:FormaEnergia)=>void;geometria?:(key:'fija'|'restoImpermeable',value:boolean)=>void;onTermodinamica?:()=>void;
}){
  const check=(id:keyof FormulacionEnergia,nombre:string,relacion:string)=>((id==='estacionario'||id==='sinAcumulacionTotal')&&!f[id])?null:<label key={id}><input type="checkbox" aria-label={nombre} checked={!!f[id]} disabled={(id==='estacionario'||id==='sinAcumulacionTotal')&&!f[id]} onChange={e=>cambiar(`${e.target.checked?'Apply':'Remove'}: ${nombre}`,{[id]:e.target.checked},e.target.checked?[relacion]:[])}/><span>{nombre}{f[id]&&<small><FormulaLatex latex={relacion} lectura={relacion}/></small>}</span></label>;
  return <>
      <fieldset disabled={disabled} className={styles.assumptionControls}>
      <fieldset><legend>Equation representation</legend><div className={energyStyles.formasEnergia}>{formas.map(o=><button key={o.id} aria-pressed={f.forma===o.id} onClick={()=>onForm(o.id)}>{o.nombre}</button>)}</div></fieldset>
      {f.trabajoTotalHeredado&&<fieldset><legend>Legacy assumption</legend>{check('trabajoTotalHeredado',"Legacy stress constraint (review)",String.raw`\nabla\cdot(\boldsymbol\sigma\cdot\mathbf v)=0`)}</fieldset>}<fieldset><legend>Flow work</legend><label><input type="checkbox" aria-label="Separate pressure and viscous stress" checked={f.separarPresion} onChange={e=>cambiar("Separate pressure and viscous stress",{separarPresion:e.target.checked,...(!e.target.checked?{entalpia:false}: {})},[String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`])}/><span>Separate pressure and viscosity</span></label><label><input type="checkbox" aria-label="Group flow work as enthalpy" disabled={!f.separarPresion} checked={f.entalpia} onChange={e=>cambiar("Group internal energy and flow work as enthalpy",{entalpia:e.target.checked},[String.raw`h=u+p/\rho`,String.raw`\mathbf v=(\mathbf v-\mathbf v_b)+\mathbf v_b`])}/><span>Group as enthalpy</span></label></fieldset>
      <fieldset><legend>Volume shared with matter</legend><label><input type="checkbox" aria-label="Shared fixed boundary" checked={m.fija} disabled={!geometria} onChange={e=>geometria?.('fija',e.target.checked)}/><span>Fixed boundary</span></label><label><input type="checkbox" aria-label="No material transport through the remaining boundary" checked={m.restoImpermeable} disabled={!geometria} onChange={e=>geometria?.('restoImpermeable',e.target.checked)}/><span>No material transport through the remaining boundary</span></label><small>{ctx.puertos.length} streams · {ctx.componentesIds.length} components</small></fieldset>
      <fieldset><legend>Transfer and accumulation</legend>{check('sinCinetica',"Negligible kinetic energy",String.raw`e_c\simeq0`)}{check('sinTrabajoViscoso','Negligible viscous work',String.raw`\nabla\cdot(\boldsymbol\tau\cdot\mathbf v)\simeq0`)}{check('sinFuerzasVolumen','No body-force work',String.raw`\rho\mathbf b\cdot\mathbf v=0`)}{check('sinFuenteVolumetrica',"No volumetric source",String.raw`r_v=0`)}{check('adiabatico',"Adiabatic boundary",String.raw`\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA=0`)}{check('sinConduccionLocal','Zero local nonconvective heat flux',String.raw`\mathbf q=\mathbf0`)}{check('estacionario',"No local accumulation",String.raw`\partial(\rho e)/\partial t=0`)}{check('sinAcumulacionTotal',"No total accumulation",String.raw`dE/dt=0`)}</fieldset>
      <fieldset><legend>State and energy relation</legend>{check('uniforme',"Uniform temperature and specific energy",String.raw`T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u`)}{check('presionUniforme',"Spatially uniform pressure",String.raw`p(\mathbf x,t)=P(t)`)}{check('presionPrescrita',"Prescribed uniform pressure",String.raw`P(t)=P_{\mathrm{ext}}(t)`)}<small>The volume state—phase count, phase change, u(T) and density—is defined in Thermodynamics and used by this balance.</small>{onTermodinamica&&<button onClick={onTermodinamica}>Define the state in Thermodynamics →</button>}</fieldset>
    </fieldset></>;
}

/** Shared state-assumption controls; package closures retain their own authority. */
export function ThermodynamicAssumptions({state,policy,equilibrium,disabled=false,change}:{
  state:SupuestosTermo;policy?:{cantidad:string;cambioInterno:string};equilibrium:boolean;disabled?:boolean;
  change:(operation:typeof OPERACIONES_TERMO[number],active:boolean)=>void;
}){
  return <><fieldset className={styles.assumptionControls} disabled={disabled}>
    {OPERACIONES_TERMO.map(operation=>{
      const blocked=equilibrium&&(operation.clave==='modelo'||operation.clave==='densidadConstante');
      const active=policy&&operation.clave==='monofasico'?policy.cantidad==='monofasico':policy&&operation.clave==='sinCambioFase'?policy.cambioInterno==='prohibido':operation.clave==='modelo'?state.modelo==='u_lineal':!!state[operation.clave];
      return <label key={operation.clave}><input type="checkbox" aria-label={operation.nombre} checked={active} disabled={blocked} onChange={event=>change(operation,event.target.checked)}/><span>{operation.nombre}<small>{blocked?'The equilibrium package calculates this relation.':operation.efecto}</small>{active&&<small><FormulaLatex latex={operation.relacion} lectura={operation.nombre}/></small>}</span></label>;
    })}
  </fieldset></>;
}
