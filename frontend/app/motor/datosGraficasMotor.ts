import {analizarMotor,aliasEstados} from './modeloNumerico';
import type {ResultadoMotor} from './modeloNumerico';
import type {HojaMotor} from './hojasMotor';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {factorUnidad,UNIDADES_MOTOR} from './unidadesMotor';
import {COORDENADAS} from './operadores';
import {datosGraficasEnsamblaje} from './datosGraficasEnsamblaje';
import {fraccionesFaseGraficas} from './fraccionesFaseGraficas';
import {seriesFasesV2} from './resultadoEnsamblajeV2';
export type VariableGraficaMotor={id:string;nombre:string;unidad:string;grupo:string};
export type DatosGraficaMotor={variables:VariableGraficaMotor[];filas:Record<string,number>[]};
/** Keep floating-point noise in constant signals from filling the entire plot.
 * This adjusts axes only; stored values are never rounded or corrected. */
export function limitesGraficaMotor(filas:Record<string,number>[],ids:string[],defecto:[string,string]=['auto','auto']):[number,number]|[string,string]{
  if(ids.length&&ids.every(id=>/^fase\..*\.(fraccionMasica|fraccionMolar|fraccionVolumen|(x|reparto)\.\d+)$/.test(id)))return [0,1];
  let min=Infinity,max=-Infinity;
  for(const fila of filas)for(const id of ids){const v=fila[id];if(Number.isFinite(v)){min=Math.min(min,v);max=Math.max(max,v);}}
  const escala=Math.max(Math.abs(min),Math.abs(max))||1;
  return Number.isFinite(min)&&max-min<1e-6*escala?[(min+max)/2-.01*escala,(min+max)/2+.01*escala]:defecto;
}
export function datosGraficasMotor(h:HojaMotor,r:ResultadoMotor,tipo:'tiempo'|'perfil',instante=0):DatosGraficaMotor {
  if(r.seriesEvaluadas){const series=[...r.seriesEvaluadas,...fraccionesFaseGraficas(r),...seriesFasesV2(r)];return {variables:[{id:'t',nombre:'Tiempo',unidad:'s',grupo:'Dominio'},...series.map(({id,nombre,unidad,grupo})=>({id,nombre,unidad,grupo}))],filas:r.tiempos.map((t,k)=>Object.fromEntries([['t',t],...series.map(q=>[q.id,q.valores[k]])]))};}
  if(h.ensamblaje&&r.estadosAcoplados)return datosGraficasEnsamblaje(h,r);
  const f=h.historial.pasos[h.historial.activo].formulacion,c=h.config,campos=analizarMotor(f,c).campos;
  const eje=COORDENADAS[f.coordenadas].ejes.find((_,i)=>!f.invariantes[i])??'x';
  const compiled=campos.map(campo=>{const d=c.datos[campo.id];return {campo,e:analizarExpresion(d.texto,campo.variables),factor:factorUnidad(campo.magnitud,d.unidad)};});
  const dato=(id:string,env:Record<string,number>)=>{const q=compiled.find(q=>q.campo.id===id);return q?evaluarExpresion(q.e,env)*q.factor:undefined;};
  const variables:VariableGraficaMotor[]=[],filas:Record<string,number>[]=[];
  const add=(id:string,nombre:string,unidad:string,grupo:string)=>variables.push({id,nombre,unidad,grupo});
  if(tipo==='perfil'&&r.modo==='1d') {
    add('x',`Coordenada ${eje}`,'m','Dominio');
    r.componentes.forEach(s=>add(`rho_${s.id}`,`Densidad · ${s.nombre}`,'kg/m3',s.nombre));
    compiled.forEach(q=>add(`dato_${q.campo.id}`,q.campo.nombre,Object.keys(UNIDADES_MOTOR[q.campo.magnitud])[0],q.campo.grupo));
    const k=Math.min(Math.max(0,instante),r.tiempos.length-1),t=r.tiempos[k];
    r.x.forEach((x,j)=>{const fila:Record<string,number>={x};const alias=aliasEstados(f,r.componentes.map((_,i)=>r.valores[k][i][j]),'densidad');r.componentes.forEach((s,i)=>fila[`rho_${s.id}`]=r.valores[k][i][j]);compiled.forEach(q=>{const i=r.componentes.findIndex(s=>q.campo.id.endsWith(`_${s.id}`));fila[`dato_${q.campo.id}`]=evaluarExpresion(q.e,{t,[eje]:x,rho:i<0?0:r.valores[k][i][j],...alias})*q.factor;});filas.push(fila);});
    return {variables,filas};
  }
  add('t','Tiempo','s','Dominio');
  if(r.modo==='temporal') {
    const volumenEstado=r.unidadEstado==='m3';
    const densidadDada=compiled.some(q=>q.campo.id==='densidad');
    const volumenDado=compiled.some(q=>q.campo.id==='volumen');
    const tieneVolumen=volumenEstado||densidadDada||volumenDado;
    if(volumenEstado)add('V','Volumen','m3','Dominio');
    else r.componentes.forEach(s=>add(r.unidadEstado==='kg'?`m_${s.id}`:`rho_${s.id}`,`${r.unidadEstado==='kg'?'Masa':'Densidad'} · ${s.nombre}`,r.unidadEstado,s.nombre));
    if(tieneVolumen&&!volumenEstado)add('V','Volumen','m3','Dominio');
    if(tieneVolumen&&(!volumenEstado||densidadDada))r.componentes.forEach(s=>{add(`rho_${s.id}`,`Densidad media · ${s.nombre}`,'kg/m3',s.nombre);if(volumenEstado)add(`m_${s.id}`,`Masa · ${s.nombre}`,'kg',s.nombre);});
    compiled.forEach(q=>add(`dato_${q.campo.id}`,q.campo.nombre,Object.keys(UNIDADES_MOTOR[q.campo.magnitud])[0],q.campo.grupo));
    r.tiempos.forEach((t,k)=>{
      const fila:Record<string,number>={t};
      const rhoD= densidadDada?dato('densidad',{t}):undefined;
      const V=volumenEstado?r.valores[k][0][0]:densidadDada?r.valores[k][0][0]/rhoD!:dato('volumen',{t});
      if(V!==undefined)fila.V=V;
      r.componentes.forEach((s,i)=>{const estado=r.valores[k][i][0];if(!volumenEstado)fila[r.unidadEstado==='kg'?`m_${s.id}`:`rho_${s.id}`]=estado;if(volumenEstado&&rhoD!==undefined){fila[`m_${s.id}`]=rhoD*V!;fila[`rho_${s.id}`]=rhoD;}else if(V!==undefined&&V>0)fila[`rho_${s.id}`]=estado/V;});
      const alias=aliasEstados(f,r.componentes.map((_,i)=>r.valores[k][i][0]),volumenEstado?'volumen':r.unidadEstado==='kg'?'masa':'densidad',V,rhoD);
      compiled.forEach(q=>{const i=r.componentes.findIndex(s=>q.campo.id==='inicial_'+s.id||q.campo.id.split('_')[1]===String(s.id));const estado=i<0?0:r.valores[k][i][0];const masa=volumenEstado?rhoD!==undefined?rhoD*estado:NaN:estado;fila[`dato_${q.campo.id}`]=evaluarExpresion(q.e,{t,m:masa,V:V??NaN,rho:volumenEstado?rhoD??NaN:r.unidadEstado==='kg/m3'?estado:V?masa/V:NaN,...alias})*q.factor;});
      filas.push(fila);
    });
  } else {
    const dx=r.dx;
    r.componentes.forEach(s=>{add(`prom_${s.id}`,`Densidad media · ${s.nombre}`,'kg/m3',s.nombre);add(`carga_${s.id}`,`Cantidad por área · ${s.nombre}`,'kg/m2',s.nombre);add(`min_${s.id}`,`Mínimo · ${s.nombre}`,'kg/m3',s.nombre);add(`max_${s.id}`,`Máximo · ${s.nombre}`,'kg/m3',s.nombre);r.x.forEach((x,j)=>add(`celda_${s.id}_${j}`,`${s.nombre} · ${eje}=${Number(x.toPrecision(4))} m`,'kg/m3',s.nombre));});
    r.tiempos.forEach((t,k)=>{const fila:Record<string,number>={t};r.componentes.forEach((s,i)=>{const v=r.valores[k][i],sum=v.reduce((a,b)=>a+b,0);fila[`prom_${s.id}`]=sum/v.length;fila[`carga_${s.id}`]=sum*dx;fila[`min_${s.id}`]=Math.min(...v);fila[`max_${s.id}`]=Math.max(...v);v.forEach((a,j)=>fila[`celda_${s.id}_${j}`]=a);});filas.push(fila);});
  }
  return {variables,filas};
}
