'use client';
import {useEffect,useState} from 'react';
import type {Componente} from './materiaEstado';
import type {ModeloEstado} from './contratoTermodinamica';
import type {CatalogoMotor,PropiedadPura,SustitucionDatosPuros} from './contratoCatalogo';
import {catalogoMotor} from './servicioCatalogo';
import {mismoModelo} from './modelosTermodinamicos';
import {borradorDatoPuro,descripcionDatoOriginal,nombresDatosPuros,problemaBorradorDatoPuro,sustituirDatoPuro} from './sustitucionesDatosPuros';
import type {PropiedadSustituible} from './sustitucionesDatosPuros';
import styles from './datosPuros.module.css';

export type OriginalesDatosPuros=Record<string,PropiedadPura[]>;
type Props={id?:string;modelo:ModeloEstado;componentes:Componente[];datos?:SustitucionDatosPuros;originales?:OriginalesDatosPuros;alcance?:string;cambiar:(datos:SustitucionDatosPuros|undefined,originales:OriginalesDatosPuros)=>boolean};
type Edicion={cas:string;id:PropiedadSustituible;campos:Record<string,string>};
const numero=(x:string)=>x.trim()?Number(x):NaN;
function datoDeEdicion(e:Edicion){
  const c=e.campos,fuente=c.fuente?.trim()??'';
  if(e.id==='volumen_liquido')return {valor:numero(c.valor??''),unidad:c.unidad,fuente};
  const keys=e.id==='cp_gas_ideal'?['a0','a1','a2','a3','a4']:['A','B','C','D','Tc','Pc'];
  return {coeficientes:Object.fromEntries(keys.map(k=>[k,numero(c[k]??'')])),dominio:{T:[numero(c.Tmin??''),numero(c.Tmax??'')]},fuente,...(e.id==='presion_vapor'?{forma:c.forma}:{})};
}
function Contenido({modelo,componentes,datos,originales,alcance,cambiar}:Props){
  const [catalogo,setCatalogo]=useState<CatalogoMotor|null>(null),[error,setError]=useState(''),[intento,setIntento]=useState(0),[edicion,setEdicion]=useState<Edicion|null>(null);
  useEffect(()=>{const c=new AbortController();catalogoMotor(c.signal).then(x=>{if(!c.signal.aborted)setCatalogo(x);}).catch(e=>{if(!c.signal.aborted)setError((e as Error).message);});return()=>c.abort();},[intento]);
  if(error)return <div role="alert">{error}<button type="button" onClick={()=>{setError('');setIntento(n=>n+1);}}>Reintentar catálogo</button></div>;
  if(!catalogo)return <p role="status">Cargando datos originales…</p>;
  const paquete=catalogo.paquetes.find(p=>mismoModelo(p.modelo,modelo)),admite=!!paquete&&!paquete.requisitos.porEspecie.includes('formulacion_iapws95');
  const identidades=new Set([...(admite?componentes.flatMap(c=>c.identidadQuimica?.cas?[c.identidadQuimica.cas]:[]):[]),...Object.keys(datos??{})]);
  function editar(cas:string,id:PropiedadSustituible){
    const s=catalogo!.sustancias.find(s=>s.cas===cas),base=datos?.[cas]?.[id]??(s?borradorDatoPuro(s,id):undefined);if(!base)return;
    const campos:Record<string,string>={fuente:base.fuente};
    if('valor'in base)Object.assign(campos,{valor:String(base.valor),unidad:base.unidad});
    else {for(const [k,v] of Object.entries(base.coeficientes))campos[k]=String(v);campos.Tmin=String(base.dominio.T[0]);campos.Tmax=String(base.dominio.T[1]);if('forma'in base)campos.forma=base.forma;}
    setEdicion({cas,id,campos});
  }
  const problema=edicion?problemaBorradorDatoPuro(edicion.id,datoDeEdicion(edicion)):null;
  function aplicar(){
    if(!edicion||problema)return;
    const valor=datoDeEdicion(edicion) as NonNullable<SustitucionDatosPuros[string][PropiedadSustituible]>,s=catalogo!.sustancias.find(s=>s.cas===edicion.cas),base=structuredClone(originales??{});
    if(!base[edicion.cas]&&s?.datosPuros.propiedades)base[edicion.cas]=structuredClone(s.datosPuros.propiedades);
    if(cambiar(sustituirDatoPuro(datos,edicion.cas,edicion.id,valor),base))setEdicion(null);
  }
  const entrada=(k:string,nombre:string)=> <label key={k}>{nombre}<input aria-label={nombre} inputMode={k==='fuente'?undefined:'decimal'} value={edicion!.campos[k]??''} onChange={e=>setEdicion({...edicion!,campos:{...edicion!.campos,[k]:e.target.value}})}/></label>;
  return <div className={styles.content}>
    {alcance&&<p>{alcance}</p>}
    {admite&&<small>h, s, Cp del líquido y densidad se derivan de estas entradas del potencial.</small>}
    {!admite&&<p>{paquete?'Este paquete usa una formulación completa; no admite sustituciones de datos puros.':'Paquete sin publicar en el catálogo.'}</p>}
    {[...identidades].map(cas=>{
      const s=catalogo.sustancias.find(s=>s.cas===cas),nombre=componentes.find(c=>c.identidadQuimica?.cas===cas)?.nombre??s?.nombre??cas;
      const dentro=componentes.some(c=>c.identidadQuimica?.cas===cas),base=originales?.[cas]??s?.datosPuros.propiedades;
      return <section key={cas}><h3>{nombre}<small>{cas}{!dentro?' · Fuera de la selección actual':''}</small></h3>
        {(['volumen_liquido','cp_gas_ideal','presion_vapor'] as const).filter(id=>admite||datos?.[cas]?.[id]).map(id=>{
          const original=base?.find(p=>p.id===id),actual=datos?.[cas]?.[id],activa=edicion?.cas===cas&&edicion.id===id;
          return <div className={styles.property} key={id}><header><strong>{nombresDatosPuros[id]}</strong><span>{actual?'Sustitución activa':'Registro'}</span></header>
            {original&&<details><summary>{originales?.[cas]?'Registro al crear las sustituciones':'Registro actual'} · {descripcionDatoOriginal(original)}</summary><p>{original.fuente}</p>{'coeficientes'in original&&<p className={styles.coefficients}>{Object.entries(original.coeficientes).map(([k,v])=>`${k} = ${v}`).join(' · ')}</p>}</details>}
            {actual&&<details><summary>Dato aplicado · {actual.fuente}</summary><pre>{JSON.stringify(actual,null,2)}</pre></details>}
            <div className={styles.actions}><button type="button" aria-label={`${actual?'Editar':'Sustituir'} ${nombresDatosPuros[id]} de ${nombre}`} disabled={!admite||!dentro||!original} onClick={()=>editar(cas,id)}>{actual?'Editar sustitución':'Sustituir'}</button>{actual&&<button type="button" aria-label={`Usar registro para ${nombresDatosPuros[id]} de ${nombre}`} onClick={()=>{if(cambiar(sustituirDatoPuro(datos,cas,id,undefined),originales??{}))setEdicion(null);}}>Usar registro</button>}</div>
            {activa&&<div className={styles.form}>
              {id==='volumen_liquido'?<>{entrada('valor','Volumen molar del líquido')}<label>Unidad<select aria-label="Unidad del volumen molar" value={edicion.campos.unidad} onChange={e=>setEdicion({...edicion,campos:{...edicion.campos,unidad:e.target.value}})}>{['m3/mol','cm3/mol','L/mol'].map(u=><option key={u}>{u}</option>)}</select></label></>:<>
                {id==='presion_vapor'&&<label>Forma<select aria-label="Forma de presión de vapor" value={edicion.campos.forma} onChange={e=>setEdicion({...edicion,campos:{...edicion.campos,forma:e.target.value}})}><option>WagnerPoling</option><option>WagnerMcGarry</option></select></label>}
                <small>{id==='cp_gas_ideal'?'Cp/R = a0 + a1 T + a2 T² + a3 T³ + a4 T⁴ · T en K':'Wagner · T y Tc en K; P y Pc en Pa'}</small>
                {(id==='cp_gas_ideal'?['a0','a1','a2','a3','a4']:['A','B','C','D','Tc','Pc']).map(k=>entrada(k,k==='Tc'?'Tc [K]':k==='Pc'?'Pc [Pa]':k))}
                {entrada('Tmin','Tmin [K]')}{entrada('Tmax','Tmax [K]')}
              </>}
              {entrada('fuente','Fuente de la sustitución')}
              {problema&&<small role="status">{problema}</small>}
              <div className={styles.actions}><button type="button" disabled={!!problema} onClick={aplicar}>Aplicar sustitución</button><button type="button" onClick={()=>setEdicion(null)}>Descartar borrador</button></div>
            </div>}
          </div>;
        })}
      </section>;
    })}
    {admite&&!identidades.size&&<p>Declara la identidad de los componentes para consultar sus datos.</p>}
    <small>El backend valida el potencial y sus derivadas al comprobar o evaluar el modelo.</small>
  </div>;
}
export default function EditorDatosPuros(props:Props){
  const [abierto,setAbierto]=useState(false),n=Object.values(props.datos??{}).reduce((n,x)=>n+Object.keys(x).length,0);
  return <details id={props.id} tabIndex={-1} className={styles.editor} onToggle={e=>setAbierto(e.currentTarget.open)}><summary>Propiedades del paquete{n?` · ${n} ${n===1?'sustitución':'sustituciones'}`:''}</summary>{abierto&&<Contenido key={JSON.stringify(props.modelo)} {...props}/>}</details>;
}
