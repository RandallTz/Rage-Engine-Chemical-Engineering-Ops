'use client';
import ModelWorksheet from '../models/ModelWorksheet';
import worksheetStyles from './motor.module.css';
import { englishLabel } from '../models/english';
import FormulaMateria from './FormulaMateria';
import type {HojaMotor} from './hojasMotor';
import type {FormulacionEnergia} from './recorridoEnergia';
import {actualEnergia,ecuacionEnergia,relacionesEnergia,operarEnergia,transformarEnergia,volverEnergia,rehacerEnergia,iniciarEnergia} from './recorridoEnergia';
import {historialEnergiaHoja,contextoEnergiaHoja,materiaEnergiaHoja} from './estadoEnergiaHoja';
import {recorridoMateria} from './recorridoMateria';
import {aplicarPoliticaDinamica} from './datosEnsamblajeTermodinamico';
import styles from './balances.module.css';
import { EnergyAssumptions } from './ModelAssumptions';
const simbolos=[['e',"Specific internal + kinetic energy",'J/kg'],['u',"Specific internal energy",'J/kg'],[String.raw`\bar u`,"Mean specific internal energy",'J/kg'],['e_c',"Specific kinetic energy",'J/kg'],['E',"Stored internal + kinetic energy",'J'],['U',"Stored internal energy",'J'],['m','Contained mass','kg'],['\\rho','Mixture density','kg/m³'],['\\rho_*','Declared constant mixture density','kg/m³'],['\\mathbf v','Fluid velocity','m/s'],['\\mathbf v_b','Boundary velocity','m/s'],['\\mathbf n','Outward unit normal','1'],['\\mathbf q',"Non-convective energy flux",'W/m²'],['\\boldsymbol\\sigma','Total stress','Pa'],['p',"Absolute pressure",'Pa'],['\\boldsymbol\\tau','Viscous stress','Pa'],['\\mathbf I','Identity tensor','1'],['\\mathbf b','Force per unit mass','m/s²'],['r_v',"Energy source per volume",'W/m³'],['R',"Integrated volumetric source",'W'],['h',"Specific enthalpy",'J/kg'],['\\dot m_p','Oriented flow at port p','kg/s'],['\\bar h_p',"Mean enthalpy transported through the port",'J/kg'],['\\varepsilon_p','−1 inlet; +1 outlet','1'],['\\dot Q','Heat into the volume','W'],['\\dot W_b',"Outward pressure work",'W'],['\\dot W_\\tau','Viscous work into the volume','W'],['\\dot W_\\sigma','Stress work into the volume','W'],['\\dot W_{\\mathbf b}','Body-force work','W'],['\\Phi_{p,\\mathrm{resto}}','Flow work through the remaining boundary','W'],['\\Phi_{E,\\mathrm{resto}}',"Energy transported outward through the remaining boundary",'W'],['V,\\ dV','Domain volume; volume element','m³'],['A_p,\\ dA','Port area; surface element','m²'],['S_{\\mathrm{resto}}','Surface outside the ports','m²'],['T,\\ T_{\\mathrm{ref}}','Absolute temperature; reference','K'],['c_u','Declared derivative du/dT','J/(kg·K)'],['u_{\\mathrm{ref}}',"Reference specific internal energy",'J/kg'],['N_{\\mathrm{fases}}',"Assumed phase count",'1'],['\\nabla','Spatial operator','1/m'],['t','Time','s']];
export default function EnergiaFundamental({h,onGuardar,onTermodinamica}:{h:HojaMotor;onGuardar:(cambio:(h:HojaMotor)=>HojaMotor)=>void;
  /** Abre el panel Termodinámica, donde se declaran los supuestos de estado (fases, u(T), densidad). */
  onTermodinamica?:()=>void}){
  const historial=historialEnergiaHoja(h),paso=actualEnergia(historial),f=paso.formulacion,ctx=contextoEnergiaHoja(h),m=materiaEnergiaHoja(h),desactualizado=JSON.stringify(ctx)!==JSON.stringify(paso.contexto);
  const matematicas=historial.pasos.flatMap(p=>[ecuacionEnergia(p.formulacion,p.contexto),...p.relaciones]).concat(relacionesEnergia(f,paso.contexto)).join(' ');
  const usados=simbolos.filter(([s])=>s.split(',').some(v=>{v=v.trim();if(v.length===1)return new RegExp(`(^|[^a-zA-Z])${v}([^a-zA-Z]|$)`).test(matematicas);return matematicas.includes(v.replace('_p','_'))||matematicas.includes(v);}));
  const guardarHistorial=(r:typeof historial)=>onGuardar(q=>({...q,energia:{...q.energia,historial:r,datos:q.energia?.datos??{}},resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false}));
  function cambiar(titulo:string,cambios:Partial<FormulacionEnergia>,relaciones:string[]=[]){
    const cierre=h.cierresDinamicos?.[ctx.volumenId];
    if(cierre&&(cambios.monofasico!==undefined||cambios.sinCambioFase!==undefined)){
      onGuardar(q=>aplicarPoliticaDinamica(q,{...cierre.politica,...(cambios.monofasico!==undefined?{cantidad:cambios.monofasico?'monofasico':'sin_restriccion'}:{}),...(cambios.sinCambioFase!==undefined?{cambioInterno:cambios.sinCambioFase?'prohibido':'permitido'}:{})}));return;
    }
    if(cambios.presionPrescrita)cambios={...cambios,presionUniforme:true};
    let r=historial;
    if(cambios.sinTrabajoViscoso&&!f.separarPresion)r=operarEnergia(r,"Split stress into pressure and viscosity",{separarPresion:true},[String.raw`\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau`]);
    guardarHistorial(operarEnergia(r,titulo,cambios,relaciones));
  }
  function geometria(clave:'fija'|'restoImpermeable',valor:boolean){
    onGuardar(q=>{
      const titulo=clave==='fija'?(valor?'Declarar frontera fija compartida':"Allow a shared moving boundary"):(valor?'Cerrar transporte material por la superficie restante':'Restaurar transporte material por el resto');
      const historialMateria=recorridoMateria(q.ensamblaje?q.ensamblaje.volumenes[0].historial:q.historial,{tipo:'cambiar',titulo,cambios:{[clave]:valor}});
      const nuevo=q.ensamblaje?{...q,ensamblaje:{...q.ensamblaje,volumenes:q.ensamblaje.volumenes.map((v,i)=>i===0?{...v,historial:historialMateria}:v)}}:{...q,historial:historialMateria};
      const contexto=contextoEnergiaHoja(nuevo),r=operarEnergia(historialEnergiaHoja(q),titulo,{},[clave==='fija'?valor?String.raw`\mathbf v_b=\mathbf0`:String.raw`\mathbf v_b\ \text{sin restricción}`:valor?String.raw`\rho(\mathbf v-\mathbf v_b)\cdot\mathbf n=0\ \text{en }S_{\mathrm{resto}}`:String.raw`\Phi_{E,\mathrm{resto}}\ \text{pendiente}`],contexto);
      return {...nuevo,revisionMateriaExterna:(q.revisionMateriaExterna??0)+1,energia:{...q.energia,historial:r,datos:q.energia?.datos??{}},resultado:undefined,resultadoRef:undefined,graficas:[],tableroIniciado:false};
    });
  }
  return <div className={styles.pagina}>
    <header className={styles.cabecera}><small>First law · {ctx.volumenId}</small><h2>Energy balance</h2><p>Local conservation → control volume → total equation</p></header>
    <ModelWorksheet family="energia" label="Energy derivation" assumptions={<EnergyAssumptions formulation={f} context={ctx} matter={m} cambiar={cambiar} onForm={form=>guardarHistorial(transformarEnergia(historial,form))} geometria={geometria} onTermodinamica={onTermodinamica}/>}>
      <div className={worksheetStyles.sheetToolbar}><h3>Mathematical development</h3><button disabled={historial.pasos.length===1} onClick={()=>guardarHistorial(volverEnergia(historial,historial.pasos.length-2))}>Undo</button><button disabled={!historial.rehacer.length} onClick={()=>guardarHistorial(rehacerEnergia(historial))}>Redo</button><button onClick={()=>guardarHistorial(iniciarEnergia(ctx))}>Reset derivation</button></div>
      {desactualizado&&<div className={styles.contextoPendiente}>The volume or its streams changed.<button onClick={()=>guardarHistorial(operarEnergia(historial,'Actualizar volumen y corrientes compartidos',{},[],ctx))}>Update derivation</button></div>}
      <article className={worksheetStyles.equation}><header><span>First law</span></header><div className={styles.balancePalabras}>Accumulation = Inflow − Outflow + Heat + Work + Sources</div></article>
      {historial.pasos.map((p,i)=><article className={worksheetStyles.derivationRow} key={i} aria-label={`Energy step ${i+1}: ${p.titulo}`}><div className={worksheetStyles.rowNumber}>{String(i+1).padStart(2,'0')}</div><div className={worksheetStyles.rowBody}><header><h3>{englishLabel(p.titulo)}</h3><small>{p.formulacion.forma} · {p.formulacion.forma==='local'?'W/m³':'W'}</small>{i<historial.pasos.length-1&&<button onClick={()=>guardarHistorial(volverEnergia(historial,i))}>Continue here</button>}{i>0&&<button aria-label={`Remove energy step ${i+1}`} onClick={()=>guardarHistorial(volverEnergia(historial,i-1))}>×</button>}</header><div className={worksheetStyles.math}><FormulaMateria latex={ecuacionEnergia(p.formulacion,p.contexto)} lectura={p.titulo} bloque/></div>{p.relaciones.map((r,j)=><div className={styles.identidadEnergia} key={j}><FormulaMateria latex={p.formulacion.uniforme&&p.formulacion.modelo==='sin_declarar'&&r.replaceAll(' ','').startsWith('U=m')?String.raw`T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u`:r} lectura="Applied identity or assumption" bloque/></div>)}</div></article>)}
      <div className={styles.relacionesEnergia}><h3>Active relations</h3>{relacionesEnergia(f,paso.contexto).map(r=><div key={r}><FormulaMateria latex={r} lectura="Energy relation" bloque/></div>)}</div>
      <section className={styles.simbolos} aria-label="Energy symbols and units"><h2>Symbols and units</h2><dl>{usados.map(([s,n,u])=><div key={s}><dt><FormulaMateria latex={s} lectura={n}/></dt><dd>{n}</dd><small>{u}</small></div>)}</dl></section>
    </ModelWorksheet>
    <footer className={styles.nota}><a href="https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node19.html" target="_blank" rel="noreferrer">Conservation and flow work · MIT ↗</a></footer>
  </div>;
}
