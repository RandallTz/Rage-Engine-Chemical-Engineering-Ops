import { analizarExpresion, evaluarExpresion } from './expresionesMotor';
import type { Expresion } from './expresionesMotor';
import { acumulacionTotalNula, campoEfectivo, indiceComponente, terminosTotalesMateria } from './recorridoMateria';
import type { FormulacionMateria } from './recorridoMateria';
import { COORDENADAS, fuentesActivas } from './operadores';
import { factorUnidad } from './unidadesMotor';
import type { MagnitudMotor } from './unidadesMotor';
import type {DatoMateria,EvaluacionRegla,VariableNumerica} from './materiaEstado';
import {analizarReglasEstado,concentracionConstante} from './reglasEstadoMateria';

export type DatoMotor=DatoMateria;
export type ConfiguracionMotor={datos:Record<string,DatoMotor>;tiempo:DatoMotor;metodo:'rk45'|'euler_implicito';muestras:number;celdas:number;rtol:number;atol:number;frontera:'periodica'|'valores'|'sin_flujo'|'';cierre?:'densidad'|'volumen'|''};
export const iniciarConfiguracion=():ConfiguracionMotor=>({datos:{},tiempo:{texto:'',unidad:'s'},metodo:'rk45',muestras:101,celdas:40,rtol:1e-6,atol:1e-9,frontera:''});
export type CampoDato={id:string;nombre:string;simbolo:string;magnitud:MagnitudMotor;funcion:'inicial'|'dato'|'geometria';variables:string[];grupo:string};
export type AnalisisMotor={modo:'temporal'|'1d'|null;campos:CampoDato[];bloqueos:string[];errores:Record<string,string>;pendientes:string[];gl:number;inicialesPendientes:number;definidas:number;totalDatos:number;totalIniciales:number;variables:number;ecuaciones:number;listo:boolean;evaluacionReglas?:EvaluacionRegla[]};
export type EstadoAcoplado={id:string;volumenId:string;volumenNombre:string;componenteId:number;componenteNombre:string;simbolo:string};
export type GrupoGlobal={id:number;nombre:string;indices:number[]};
export type SerieEvaluadaMotor={id:string;nombre:string;unidad:string;grupo:string;valores:number[]};
export type ResultadoMotor={version:1;motor:string;modo:'temporal'|'1d';metodo:string;tiempos:number[];x:number[];dx:number;valores:number[][][];componentes:{id:number;nombre:string;simbolo:string}[];estado:'resuelto'|'parcial';mensaje:string;pasos:number;rechazados:number;conservacion:number[];unidadEstado:'kg'|'kg/m3'|'m3'|'J'|'mixta';firma:string;seriesEvaluadas?:SerieEvaluadaMotor[];balancesEjecutados?:('materia'|'energia')[];trazabilidadEnergia?:{ecuacion:string;relaciones:string[];terminos:{id:string;unidad:string;signo:number}[]};estadosAcoplados?:EstadoAcoplado[];conservacionGlobal?:{id:number;nombre:string;residuo:number}[];variablesNumericas?:VariableNumerica[];evaluacionReglas?:EvaluacionRegla[];ensamblajeV2?:{solicitud:import('./contratoEnsamblajeV2').SolicitudEnsamblajeV2;respuesta:import('./contratoEnsamblajeV2').RespuestaResolucionV2};ensamblajeTermodinamico?:{solicitud:import('./contratoEnsamblajeTermodinamico').SolicitudEnsamblajeDinamico;respuesta:import('./contratoEnsamblajeTermodinamico').RespuestaResolucionDinamica}};
export const VERSION_SOLVER='motor-independiente-materia-1';
export const firmaMotor=(f:FormulacionMateria,c:ConfiguracionMotor)=>JSON.stringify([VERSION_SOLVER,f,c]);
export const esTemporalLocal=(f:FormulacionMateria)=>f.vista==='campo'&&f.coordenadas==='cartesianas'&&f.invariantes.every(Boolean);
export const esVolumetrico=(f:FormulacionMateria)=>f.vista==='cantidad'&&f.cantidadVolumen&&!f.fija&&concentracionConstante(f)&&f.densidadComunPuertos;
export const necesitaCierre=(f:FormulacionMateria)=>f.vista==='cantidad'&&f.cantidadVolumen&&!f.fija&&!concentracionConstante(f);
export function aliasEstados(f:FormulacionMateria,y:number[],modo:'masa'|'densidad'|'volumen',V=NaN,rhoD=NaN):Record<string,number>{
  const env:Record<string,number>={};
  for(const [i,s] of (f.componentes??[]).entries()) {
    const masa=modo==='masa'?y[i]:modo==='volumen'?y[0]*rhoD:NaN;
    const densidad=modo==='densidad'?y[i]:modo==='volumen'?rhoD:V>0?masa/V:NaN;
    env[`m_${s.simbolo}`]=masa;env[`rho_${s.simbolo}`]=densidad;
  }
  env.m_total=(f.componentes??[]).reduce((sum,s)=>sum+env[`m_${s.simbolo}`],0);
  env.rho_total=(f.componentes??[]).reduce((sum,s)=>sum+env[`rho_${s.simbolo}`],0);return env;
}
export function camposMotor(f:FormulacionMateria,c?:ConfiguracionMotor):{modo:AnalisisMotor['modo'];campos:CampoDato[];bloqueos:string[]} {
  const campos:CampoDato[]=[],bloqueos:string[]=[];
  bloqueos.push(...analizarReglasEstado(f).bloqueos);
  const cs=f.componentes??[],o=campoEfectivo(f),fuentes=fuentesActivas(o);
  const eje=COORDENADAS[f.coordenadas].ejes.find((_,i)=>!f.invariantes[i])??'x';
  if(!cs.length)bloqueos.push('Añade al menos un componente a la hoja.');
  if(cs.length>8)bloqueos.push('El solver admite hasta ocho componentes.');
  if(f.vista==='campo'&&f.campo.estacionario||f.vista==='cantidad'&&acumulacionTotalNula(f))bloqueos.push('La ecuación no tiene acumulación temporal. La resolución algebraica queda pendiente.');
  const local=esTemporalLocal(f);
  const modo:AnalisisMotor['modo']=f.vista==='cantidad'||local?'temporal':f.vista==='campo'?'1d':null;
  if(f.vista==='integral')bloqueos.push('La forma integral necesita una reducción total o una discretización espacial declarada.');
  if(modo==='1d') {
    if(f.coordenadas!=='cartesianas')bloqueos.push('La primera discretización 1D admite coordenadas cartesianas.');
    if(f.invariantes.filter(x=>!x).length!==1)bloqueos.push('Deja una dirección espacial activa y declara invariancia en las otras dos.');
    if(!f.fija)bloqueos.push('Declara una frontera fija para esta malla 1D.');
    if(f.fronteras.length)bloqueos.push('En 1D declara las condiciones de los extremos en Resolver. Los puertos macroscópicos necesitan geometría adicional.');
    if(f.restoImpermeable)bloqueos.push('Retira la condición global de frontera sin flujo para declarar cada extremo en Resolver.');
    if(f.cantidadVolumen||f.sinAcumulacion)bloqueos.push('Usa la conservación local sin sustituciones macroscópicas para discretizar el campo.');
  }
  if(modo==='temporal'&&f.cantidadVolumen&&cs.length!==1)bloqueos.push('La reducción a un volumen común de varias especies necesita un cierre adicional. Conserva las masas como estados.');
  if(f.vista==='cantidad'&&(f.invariantes.some(Boolean)||f.campo.estacionario))bloqueos.push('Las restricciones locales del campo necesitan compatibilidad adicional con los flujos totales. Resuelve la forma local o retira esas restricciones para este cálculo macroscópico.');
  if(local&&(f.fronteras.length||f.cantidadVolumen||f.sinAcumulacion))bloqueos.push('Para ejecutar también las relaciones macroscópicas, expresa la ecuación en forma total.');
  const add=(id:string,nombre:string,simbolo:string,magnitud:MagnitudMotor,funcion:CampoDato['funcion'],variables:string[],grupo:string)=>campos.push({id,nombre,simbolo,magnitud,funcion,variables,grupo});
  if(modo==='1d') {
    add('inicio','Inicio del dominio',eje+'_a','longitud','geometria',[],'Dominio');add('fin','Final del dominio',eje+'_b','longitud','geometria',[],'Dominio');
    if(!o.sinConveccion)add('velocidad',`Velocidad en ${eje}`,`v_{${eje}}`,'velocidad','dato',['t',eje],'Dominio');
  }
  if(modo==='temporal'&&!local) {
    const volumenNecesario=f.cantidadVolumen||(fuentes.generacion&&f.generacionUniforme)||(fuentes.consumo&&f.consumoUniforme)||((fuentes.generacion||fuentes.consumo)&&f.invariantes.every(Boolean));
    const densidadNecesaria=!esVolumetrico(f)||terminosTotalesMateria(f).some(t=>!['entrada','salida'].includes(t.rol));
    if(necesitaCierre(f)&&!c?.cierre) { /* The user chooses which function closes rho_bar V. */ }
    else if(f.cantidadVolumen&&!f.fija&&!(necesitaCierre(f)&&c?.cierre==='volumen')&&densidadNecesaria)add('densidad','Concentración media del componente',String.raw`\bar\rho`,'densidad','dato',concentracionConstante(f)?[]:['t'],'Dominio');
    else if(necesitaCierre(f)&&c?.cierre==='volumen')add('volumen','Volumen del dominio','V','volumen','dato',['t'],'Dominio');
    else if(esVolumetrico(f)) { /* Density cancels completely when no source/rest term needs it. */ }
    else if(volumenNecesario)add('volumen','Volumen del dominio','V','volumen','dato',f.fija?[]:['t'],'Dominio');
  }
  for(const comp of cs) {
    const aliasM=cs.map(s=>`m_${s.simbolo}`),aliasR=cs.map(s=>`rho_${s.simbolo}`);
    const volumenConocido=campos.some(c=>['volumen','densidad'].includes(c.id));
    const i=indiceComponente(comp),g=comp.nombre,vs=modo==='1d'?['t',eje,'rho','rho_total',...aliasR]:volumenConocido?['t','m','V','rho','m_total','rho_total',...aliasM,...aliasR]:['t','m','m_total',...aliasM];
    const inicialVolumen=esVolumetrico(f);
    add(`inicial_${comp.id}`,inicialVolumen?'Volumen inicial':modo==='1d'||local?'Densidad inicial':'Masa inicial',inicialVolumen?'V(0)':modo==='1d'?String.raw`\rho_{${i}}(${eje},0)`:local?String.raw`\rho_{${i}}(0)`:String.raw`m_{${i}}(0)`,inicialVolumen?'volumen':modo==='1d'||local?'densidad':'masa','inicial',modo==='1d'?[eje]:[],g);
    if(modo==='temporal'&&!local)for(const term of terminosTotalesMateria(f,i)) {
      const id=`${term.rol}_${comp.id}${term.puertoId===undefined?'':'_'+term.puertoId}`;
      const volumetrico=esVolumetrico(f)&&['entrada','salida'].includes(term.rol);
      const constante=term.puertoId!==undefined&&f.fronteras.find(p=>p.id===term.puertoId)?.constante!==false;
      const variables=constante?[]:esVolumetrico(f)?campos.some(c=>c.id==='densidad')?['t','V','rho','m','m_total','rho_total',...aliasM,...aliasR]:['t','V']:vs;
      const simbolo=volumetrico?constante?String.raw`Q^{\mathrm{cte}}_{${term.puertoId}}`:`Q_{${term.puertoId}}(t)`:term.forma==='tasa_por_volumen'?`${term.rol==='generacion'?String.raw`\gamma`:String.raw`\chi`}_{${i}}(t)`:term.latex;
      add(id,term.rol==='entrada'?`Entrada ${term.puertoId}`:term.rol==='salida'?`Salida ${term.puertoId}`:term.rol==='resto'?'Flujo por la frontera restante':term.rol==='generacion'?'Generación':'Consumo',simbolo,volumetrico?'caudal_volumetrico':term.forma==='tasa_por_volumen'?'tasa':'caudal','dato',variables,g);
    }
    if(local){const variables=['t','rho','rho_total',...aliasR];if(fuentes.generacion)add(`generacion_${comp.id}`,'Generación local',String.raw`\gamma_{${i}}`,'tasa','dato',variables,g);if(fuentes.consumo)add(`consumo_${comp.id}`,'Consumo local',String.raw`\chi_{${i}}`,'tasa','dato',variables,g);}
    if(modo==='1d') {
      if(!o.sinDifusion)add(`difusion_${comp.id}`,o.difusion==='flujo'?'Flujo difusivo':'Difusividad',o.difusion==='flujo'?String.raw`j_{${i},${eje}}`:`D_{${i}}`,o.difusion==='flujo'?'flujo':'difusividad','dato',o.difusion==='laplaciano'?['t']:['t',eje],g);
      if(fuentes.generacion)add(`generacion_${comp.id}`,'Generación local',String.raw`\gamma_{${i}}`,'tasa','dato',f.generacionUniforme?['t']:vs,g);
      if(fuentes.consumo)add(`consumo_${comp.id}`,'Consumo local',String.raw`\chi_{${i}}`,'tasa','dato',f.consumoUniforme?['t']:vs,g);
    }
  }
  if(bloqueos.length)return {modo:null,campos:[],bloqueos};
  return {modo,campos,bloqueos};
}
export function analizarMotor(f:FormulacionMateria,c:ConfiguracionMotor):AnalisisMotor {
  const {modo,campos,bloqueos}=camposMotor(f,c),errores:Record<string,string>={},pendientes:string[]=[];
  const completos=[...campos];
  if(modo==='1d'&&c.frontera==='valores')for(const comp of f.componentes??[])for(const lado of ['izquierda','derecha'])completos.push({id:`${lado}_${comp.id}`,nombre:`${lado==='izquierda'?'Extremo izquierdo':'Extremo derecho'} · ${comp.nombre}`,simbolo:String.raw`\rho_{${indiceComponente(comp)},${lado==='izquierda'?'a':'b'}}`,magnitud:'densidad',funcion:'dato',variables:['t'],grupo:'Fronteras'});
  for(const campo of completos) {
    const dato=c.datos[campo.id];if(!dato?.texto.trim()){pendientes.push(campo.id);continue;}
    try{analizarExpresion(dato.texto,campo.variables);factorUnidad(campo.magnitud,dato.unidad);}catch(e){errores[campo.id]=(e as Error).message;}
  }
  if(!c.tiempo.texto.trim())pendientes.push('tiempo');else try {const t=evaluarExpresion(analizarExpresion(c.tiempo.texto,[]),{})*factorUnidad('tiempo',c.tiempo.unidad);if(!Number.isFinite(t)||t<=0)throw new Error('El tiempo debe ser finito y mayor que cero.');}catch(e){errores.tiempo=(e as Error).message;}
  if(modo==='1d'&&!c.frontera)pendientes.push('frontera');
  if(modo==='1d'&&c.frontera&&!['periodica','valores','sin_flujo'].includes(c.frontera))errores.frontera='Condición de frontera no admitida.';
  if(necesitaCierre(f)&&!c.cierre)pendientes.push('cierre');
  if(necesitaCierre(f)&&c.cierre&&!['densidad','volumen'].includes(c.cierre))errores.cierre='Selecciona densidad o volumen.';
  if(!['rk45','euler_implicito'].includes(c.metodo))errores.metodo='Método no admitido.';
  if(modo==='1d'&&c.metodo!=='rk45')bloqueos.push('El método implícito está disponible solo para la ecuación temporal sin malla.');
  if(!Number.isInteger(c.celdas)||c.celdas<4||c.celdas>160)errores.celdas='Usa de 4 a 160 celdas.';
  if(!Number.isInteger(c.muestras)||c.muestras<2||c.muestras>201)errores.muestras='Usa de 2 a 201 muestras.';
  if(!Number.isFinite(c.rtol)||c.rtol<1e-9||c.rtol>.01||!Number.isFinite(c.atol)||c.atol<1e-30||c.atol>.01)errores.tolerancias='Tolerancias fuera del rango admitido.';
  const datos=completos.filter(d=>d.funcion!=='inicial'),inicialesPendientes=completos.filter(d=>d.funcion==='inicial'&&(pendientes.includes(d.id)||!!errores[d.id])).length;
  const gl=datos.filter(d=>pendientes.includes(d.id)||!!errores[d.id]).length+(pendientes.includes('cierre')?1:0);
  return {modo,campos:completos,bloqueos,errores,pendientes,gl,inicialesPendientes,definidas:datos.filter(d=>!pendientes.includes(d.id)&&!errores[d.id]).length,totalDatos:datos.length+(pendientes.includes('cierre')?1:0),totalIniciales:completos.length-datos.length,variables:(f.componentes?.length??0)+datos.length+(pendientes.includes('cierre')?1:0),ecuaciones:f.componentes?.length??0,listo:!!modo&&!bloqueos.length&&!pendientes.length&&!Object.keys(errores).length,...(f.reglasEstado?{evaluacionReglas:analizarReglasEstado(f).evaluacion}:{})};
}
export type EventoNumerico={id:string;nombre:string;valor:(t:number,y:number[])=>number;derivada?:(t:number,y:number[],dy:number[])=>number};
export type SistemaNumerico={eventos?:EventoNumerico[];modo:'temporal'|'1d';unidadEstado:'kg'|'kg/m3'|'m3'|'J'|'mixta';inicial:number[];x:number[];dx:number;n:number;nc:number;tfinal:number;rhs:(t:number,y:number[])=>number[];limitePaso:(t:number,y:number[])=>number;observacion:(t:number,y:number[])=>number[][];balance:(t:number,y:number[])=>number[];estadosAcoplados?:EstadoAcoplado[];gruposGlobales?:GrupoGlobal[];valoresDatos?:(t:number,y:number[])=>Record<string,number>;variablesNumericas?:VariableNumerica[];evaluacionReglas?:EvaluacionRegla[]};
export function compilarMotor(f:FormulacionMateria,c:ConfiguracionMotor):SistemaNumerico {
  const s=compilarMotorBase(f,c);
  const variablesNumericas:VariableNumerica[]=s.inicial.map((_,i)=>({id:`c${f.componentes![Math.floor(i/s.n)].id}_celda${i%s.n}`,propietarioId:'dominio',componenteId:f.componentes![Math.floor(i/s.n)].id,magnitud:s.unidadEstado==='kg'?'masa':s.unidadEstado==='m3'?'volumen':'concentracion_masica',unidad:s.unidadEstado,rol:'diferencial',restriccion:'no_negativo',toleranciaAbsoluta:c.atol}));
  return {...s,variablesNumericas,...(f.reglasEstado?{evaluacionReglas:analizarReglasEstado(f).evaluacion}:{})};
}
function compilarMotorBase(f:FormulacionMateria,c:ConfiguracionMotor):SistemaNumerico {
  const analisis=analizarMotor(f,c);if(!analisis.listo)throw new Error(analisis.bloqueos[0]??Object.values(analisis.errores)[0]??'Completa los datos pendientes.');
  const ast:Record<string,{e:Expresion;factor:number}>={};
  for(const campo of analisis.campos){const d=c.datos[campo.id];ast[campo.id]={e:analizarExpresion(d.texto,campo.variables),factor:factorUnidad(campo.magnitud,d.unidad)};}
  const valor=(id:string,v:Record<string,number>)=>{try{const z=evaluarExpresion(ast[id].e,v)*ast[id].factor;if(!Number.isFinite(z))throw new Error('El valor normalizado no es finito.');return z;}catch(e){throw new Error(`${analisis.campos.find(x=>x.id===id)?.nombre}: ${(e as Error).message}`);}};
  const cs=f.componentes!,nc=cs.length,tfinal=evaluarExpresion(analizarExpresion(c.tiempo.texto,[]),{})*factorUnidad('tiempo',c.tiempo.unidad),o=campoEfectivo(f);
  if(analisis.modo==='temporal') {
    const inicial=cs.map(s=>valor(`inicial_${s.id}`,{}));if(inicial.some(x=>x<0))throw new Error('La masa inicial no puede ser negativa.');
    if(esVolumetrico(f)) {
      if(inicial[0]===0&&terminosTotalesMateria(f).some(t=>!['entrada','salida'].includes(t.rol)))throw new Error('Para empezar desde volumen cero, retira las fuentes de dominio y declara los flujos de frontera.');
      const rhs=(t:number,y:number[])=>{const rho=ast.densidad?valor('densidad',{}):NaN;if(ast.densidad&&rho<=0)throw new Error('La densidad debe ser positiva.');const env={t,V:y[0],rho,m:rho*y[0],...aliasEstados(f,y,'volumen',y[0],rho)};return [terminosTotalesMateria(f,indiceComponente(cs[0])).reduce((sum,term)=>{const v=valor(`${term.rol}_${cs[0].id}${term.puertoId===undefined?'':'_'+term.puertoId}`,env);if(['generacion','consumo'].includes(term.rol)&&v<0)throw new Error('Las tasas brutas no pueden ser negativas.');return sum+term.signo*(['entrada','salida'].includes(term.rol)?v:v*(term.forma==='tasa_por_volumen'?y[0]:1)/rho);},0)];};rhs(0,inicial);
      return {modo:'temporal',unidadEstado:'m3',inicial,x:[],dx:1,n:1,nc,tfinal,rhs,limitePaso:()=>tfinal/(c.muestras-1),observacion:(_t,y)=>[[y[0]]],balance:rhs};
    }
    if(esTemporalLocal(f)) {
      const fuentes=fuentesActivas(o);
      const rhs=(t:number,y:number[])=>cs.map((s,i)=>{const env={t,rho:y[i],...aliasEstados(f,y,'densidad')},g=fuentes.generacion?valor(`generacion_${s.id}`,env):0,k=fuentes.consumo?valor(`consumo_${s.id}`,env):0;if(g<0||k<0)throw new Error('Las tasas brutas no pueden ser negativas.');return g-k;});rhs(0,inicial);
      return {modo:'temporal',unidadEstado:'kg/m3',inicial,x:[],dx:1,n:1,nc,tfinal,rhs,limitePaso:()=>tfinal/(c.muestras-1),observacion:(_t,y)=>cs.map((_,i)=>[y[i]]),balance:rhs};
    }
    const volumen=(t:number,y:number[])=>ast.densidad?y[0]/valor('densidad',{t}):ast.volumen?valor('volumen',{t}):NaN;
    if(ast.densidad&&inicial[0]===0)throw new Error('La definición de densidad media exige un volumen positivo. Para iniciar vacío, conserva la masa como variable.');
    let ultimoT=NaN,ultimoY:number[]=[],cache:{dy:number[];datos:Record<string,number>}|undefined;
    const evaluar=(t:number,y:number[])=>{
      if(cache&&t===ultimoT&&y.length===ultimoY.length&&y.every((v,i)=>v===ultimoY[i]))return cache;
      const datos:Record<string,number>={};
      const dy=cs.map((s,i)=> {
      const V=volumen(t,y);if(ast.densidad&&valor('densidad',{t})<=0)throw new Error('La densidad debe ser positiva.');if((ast.volumen||ast.densidad)&&V<=0&&!(ast.densidad&&y[0]===0))throw new Error('El volumen debe ser positivo.');
      const env={t,m:y[i],V,rho:V>0?y[i]/V:NaN,...aliasEstados(f,y,'masa',V)};
      return terminosTotalesMateria(f,indiceComponente(s)).reduce((sum,term)=>{
        const id=`${term.rol}_${s.id}${term.puertoId===undefined?'':'_'+term.puertoId}`,v=valor(id,env);datos[id]=v;
        if(['generacion','consumo'].includes(term.rol)&&v<0)throw new Error(`${term.rol}: la tasa bruta declarada no puede ser negativa.`);
        return sum+term.signo*v*(term.forma==='tasa_por_volumen'?V:1);
      },0);
      });ultimoT=t;ultimoY=[...y];cache={dy,datos};return cache;
    };
    const rhs=(t:number,y:number[])=>evaluar(t,y).dy;rhs(0,inicial);
    return {modo:'temporal',unidadEstado:'kg',inicial,x:[],dx:1,n:1,nc,tfinal,rhs,limitePaso:()=>tfinal/(c.muestras-1),observacion:(_t,y)=>cs.map((_,i)=>[y[i]]),balance:rhs,valoresDatos:(t,y)=>evaluar(t,y).datos};
  }
  const a=valor('inicio',{}),b=valor('fin',{}),n=c.celdas,dx=(b-a)/n;if(!(b>a))throw new Error('El final del dominio debe ser mayor que el inicio.');
  const eje=COORDENADAS[f.coordenadas].ejes.find((_,i)=>!f.invariantes[i])??'x';
  const x=Array.from({length:n},(_,i)=>a+(i+.5)*dx),inicial=cs.flatMap(s=>x.map(p=>valor(`inicial_${s.id}`,{[eje]:p})));
  if(inicial.some(v=>v<0))throw new Error('La densidad inicial no puede ser negativa.');
  if(x.some((v,i)=>i>0&&v<=x[i-1]))throw new Error('La malla no puede distinguir sus celdas a esa escala y posición.');
  const fuentes=fuentesActivas(o);
  let evaluaciones=0;
  function calcular(t:number,y:number[]) {
    evaluaciones++;
    const rhoTotal=(j:number)=>cs.reduce((sum,_,i)=>sum+y[i*n+j],0);
    if(!o.sinDifusion&&o.difusion==='laplaciano'){
      const r0=rhoTotal(0);if(Array.from({length:n},(_,j)=>rhoTotal(j)).some(r=>Math.abs(r-r0)>(evaluaciones===1?64*Number.EPSILON:1e-9)*Math.max(Math.abs(r0),Number.MIN_VALUE)))throw new Error('La densidad total no es uniforme en espacio: contradice la relación laplaciana elegida.');
    }
    const extremos=(i:number,lado:'izquierda'|'derecha')=>c.frontera==='valores'?valor(`${lado}_${cs[i].id}`,{t}):y[i*n+(lado==='izquierda'?0:n-1)];
    if(c.frontera==='valores'&&cs.some((_,i)=>extremos(i,'izquierda')<0||extremos(i,'derecha')<0))throw new Error('Una condición de frontera tiene densidad negativa.');
    const velocidades=Array.from({length:n+1},(_,j)=>o.sinConveccion?0:valor('velocidad',{t,[eje]:a+j*dx}));
    const flujos=cs.map(()=>Array(n+1).fill(0)),dy=Array(y.length).fill(0),balances=Array(nc).fill(0);const vmax=Math.max(...velocidades.map(Math.abs));let dmax=0;
    for(let j=0;j<=n;j++) {
      const xf=a+j*dx,env={t,[eje]:xf},v=velocidades[j];
      const izq=cs.map((_,i)=>j?y[i*n+j-1]:c.frontera==='periodica'?y[i*n+n-1]:extremos(i,'izquierda'));
      const der=cs.map((_,i)=>j<n?y[i*n+j]:c.frontera==='periodica'?y[i*n]:extremos(i,'derecha'));
      const rl=izq.reduce((s,v)=>s+v,0),rr=der.reduce((s,v)=>s+v,0),difusivos:number[]=[];
      const distancia=(c.frontera==='valores'&&(j===0||j===n))?dx/2:dx;
      const dependiente=izq.reduce((mejor,_,i)=>Math.abs(izq[i])+Math.abs(der[i])>Math.abs(izq[mejor])+Math.abs(der[mejor])?i:mejor,0);
      const gradientes=Array(nc).fill(0);
      if(!o.sinDifusion&&o.difusion!=='flujo') {
        if(o.difusion==='fick'&&(rl<=0||rr<=0))throw new Error('La relación de Fick necesita densidad total positiva.');
        for(let i=0;i<nc;i++)if(i!==dependiente)gradientes[i]=o.difusion==='fick'?(der[i]/rr-izq[i]/rl)/distancia:(der[i]-izq[i])/distancia;
        // Differentiate the declared identity sum(w)=1 (or uniform total rho).
        // Eliminate the largest fraction so traces retain their own derivatives.
        gradientes[dependiente]=-gradientes.reduce((s,v)=>s+v,0);
      }
      for(let i=0;i<nc;i++) {
        let dif=0;
        if(!o.sinDifusion) {
          const D=valor(`difusion_${cs[i].id}`,env);
          if(o.difusion==='flujo')dif=D;
          else {if(D<0)throw new Error('La difusividad no puede ser negativa.');dmax=Math.max(dmax,D);dif=-(o.difusion==='fick'?(rl+rr)/2:1)*D*gradientes[i];}
        }
        const flujo=v*(v>=0?izq[i]:der[i])+dif;
        if(c.frontera==='sin_flujo'&&(j===0||j===n)&&Math.abs(flujo)>64*Number.EPSILON*Math.max(vmax*Math.max(izq[i],der[i]),Math.abs(dif),Number.MIN_VALUE))throw new Error('La velocidad o el flujo declarado contradice la frontera impermeable.');
        difusivos.push(dif);flujos[i][j]=c.frontera==='sin_flujo'&&(j===0||j===n)?0:flujo;
      }
      if(!o.sinDifusion&&Math.abs(difusivos.reduce((s,v)=>s+v,0))>1e-10*Math.max(...difusivos.map(Math.abs),Number.MIN_VALUE))throw new Error('Los flujos difusivos no suman cero. Declara coeficientes compatibles con la velocidad media en masa.');
    }
    for(let i=0;i<nc;i++) {
      let sumaFuentes=0;
      for(let j=0;j<n;j++) {
        const env={t,[eje]:x[j],rho:y[i*n+j],...aliasEstados(f,cs.map((_,i)=>y[i*n+j]),'densidad')},g=fuentes.generacion?valor(`generacion_${cs[i].id}`,env):0,k=fuentes.consumo?valor(`consumo_${cs[i].id}`,env):0;
        if(g<0||k<0)throw new Error('Generación y consumo son tasas brutas no negativas.');
        dy[i*n+j]=-(flujos[i][j+1]-flujos[i][j])/dx+g-k;sumaFuentes+=(g-k)*dx;
      }
      balances[i]=flujos[i][0]-flujos[i][n]+sumaFuentes;
    }
    if(!o.sinDifusion&&o.difusion==='laplaciano'){const sumas=Array.from({length:n},(_,j)=>cs.reduce((s,_,i)=>s+dy[i*n+j],0));const escala=Math.max(...dy.map(Math.abs),...flujos.flat().map(v=>Math.abs(v)/dx),Number.MIN_VALUE);if(sumas.some(v=>Math.abs(v-sumas[0])>1e-10*escala))throw new Error('Fuentes o velocidad incompatibles con la densidad total uniforme.');}
    if(c.frontera==='periodica')for(let i=0;i<nc;i++)if(Math.abs(flujos[i][0]-flujos[i][n])>1e-10*Math.max(...flujos[i].map(Math.abs),vmax*Math.max(...y.map(Math.abs)),Number.MIN_VALUE))throw new Error('Los datos de ambos extremos no son periódicos.');
    return {dy,balances,paso:Math.min(vmax?0.4*dx/vmax:Infinity,dmax?0.2*dx*dx/dmax:Infinity,tfinal/(c.muestras-1))};
  }
  calcular(0,inicial);
  return {modo:'1d',unidadEstado:'kg/m3',inicial,x,dx,n,nc,tfinal,rhs:(t,y)=>calcular(t,y).dy,limitePaso:(t,y)=>calcular(t,y).paso,observacion:(_t,y)=>cs.map((_,i)=>y.slice(i*n,(i+1)*n)),balance:(t,y)=>calcular(t,y).balances};
}
