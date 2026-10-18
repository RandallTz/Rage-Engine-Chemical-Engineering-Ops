import {iniciarRecorrido,recorridoMateria,terminosTotalesMateria,indiceComponente,acumulacionTotalNula} from './recorridoMateria';
import type {RecorridoMateria,FormulacionMateria} from './recorridoMateria';
import {analizarMotor,camposMotor} from './modeloNumerico';
import type {AnalisisMotor,CampoDato,ConfiguracionMotor,SistemaNumerico,EstadoAcoplado} from './modeloNumerico';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {factorUnidad,UNIDADES_MOTOR} from './unidadesMotor';
import type {Componente,DatosCorriente,ResultadoCorriente} from './materiaEstado';
import {masaMolarKg} from './materiaEstado';
import {analizarReglasEstado} from './reglasEstadoMateria';

export type VolumenMateria={id:string;nombre:string;historial:RecorridoMateria;componentesIds?:number[];volumenDeclarado?:boolean};
export type CorrienteMateria={id:number;nombre:string;desde:string|null;hasta:string|null;constante:boolean;componentesIds?:number[];mecanismo?:'convectivo'|'selectivo'|null;datos?:DatosCorriente;resultado?:ResultadoCorriente};
/** componentes is the authoritative catalog. Absent only in legacy documents. */
export type EnsamblajeMateria={version:1|2;componentes?:Componente[];volumenes:VolumenMateria[];corrientes:CorrienteMateria[];ultimoVolumen:number;ultimaCorriente:number;ordenDatosLegado?:string[]};
export const catalogoComponentes=(e:EnsamblajeMateria)=>e.componentes??e.volumenes[0]?.historial.pasos[e.volumenes[0].historial.activo].formulacion.componentes??[];
export const claveVolumen=(v:string,campo:string)=>`${v}__${campo}`;
export const claveCorriente=(id:number,especie:number)=>`s${id}__c${especie}`;
export const claveTotalCorriente=(id:number)=>`s${id}__total`;
/** Input adapter; evaluated stream results never participate in conservation. */
export function datosEnsamblaje(e:EnsamblajeMateria,c:ConfiguracionMotor):ConfiguracionMotor{
  const datos={...c.datos};
  for(const s of e.corrientes){const m=s.datos?.materia;if(!m)continue;
    if(m.modo==='total_y_composicion')datos[claveTotalCorriente(s.id)]=m.caudalTotal;
    else for(const [id,d] of Object.entries(m.caudales))if(d)datos[claveCorriente(s.id,Number(id))]=d;
  }
  const orden=e.ordenDatosLegado;
  return {...c,datos:orden?Object.fromEntries([...new Set([...orden,...Object.keys(datos)])].filter(id=>id in datos).map(id=>[id,datos[id]])):datos};
}
/** Lazy, lossless migration on save. Journal snapshots are retained for undo;
 * current component identity comes exclusively from the common catalog. */
export function normalizarEnsamblaje(e:EnsamblajeMateria,c:ConfiguracionMotor){
  const componentes=structuredClone(catalogoComponentes(e)),ids=componentes.map(s=>s.id),datos={...c.datos};
  if(!e.componentes&&e.volumenes.some(v=>{const cs=v.historial.pasos[v.historial.activo].formulacion.componentes??[];return cs.length!==componentes.length||cs.some(s=>!componentes.some(k=>k.id===s.id&&k.simbolo===s.simbolo));}))throw new Error('No se puede migrar un ensamblaje con identidades de componentes contradictorias. Los datos originales se conservan.');
  const corrientes=e.corrientes.map(s=>{
    let especificacion=s.datos;
    if(!especificacion){const caudales:NonNullable<CorrienteMateria['datos']>['materia'] & {modo:'por_componente'}={modo:'por_componente',base:'masica',caudales:{}};
      for(const id of ids){const d=datos[claveCorriente(s.id,id)];if(d)caudales.caudales[id]=structuredClone(d);}especificacion={materia:caudales};
    }else if(Object.keys(datos).some(k=>k===claveTotalCorriente(s.id)||k.startsWith(`s${s.id}__c`)))throw new Error(`S${s.id}: la especificación está duplicada en la corriente y en config.datos.`);
    for(const id of ids)delete datos[claveCorriente(s.id,id)];delete datos[claveTotalCorriente(s.id)];
    return {...s,componentesIds:[...(s.componentesIds??ids)],mecanismo:s.mecanismo??null,datos:especificacion};
  });
  const ensamblaje:EnsamblajeMateria={...e,version:2,componentes,corrientes,ordenDatosLegado:e.ordenDatosLegado??Object.keys(c.datos),volumenes:e.volumenes.map(v=>({...v,componentesIds:v.componentesIds??v.historial.pasos[v.historial.activo].formulacion.componentes?.map(s=>s.id)??ids}))};
  return {ensamblaje,config:{...c,datos}};
}
/** UI edits change specifications, not evaluated results, and keep one source. */
export function actualizarDatosEnsamblaje(e:EnsamblajeMateria,c:ConfiguracionMotor){
  const datos={...c.datos};
  const corrientes=e.corrientes.map(s=>{const m=s.datos?.materia;if(!m)return s;
    const materia=m.modo==='total_y_composicion'?{...m,caudalTotal:datos[claveTotalCorriente(s.id)]??m.caudalTotal}:{...m,caudales:Object.fromEntries((s.componentesIds??catalogoComponentes(e).map(z=>z.id)).flatMap(id=>datos[claveCorriente(s.id,id)]?[[id,datos[claveCorriente(s.id,id)]]]:[]))};
    for(const id of s.componentesIds??catalogoComponentes(e).map(z=>z.id))delete datos[claveCorriente(s.id,id)];delete datos[claveTotalCorriente(s.id)];
    return {...s,datos:{...s.datos!,materia},resultado:undefined};
  });
  return {ensamblaje:{...e,corrientes},config:{...c,datos}};
}
export function formulacionVolumen(e:EnsamblajeMateria,v:VolumenMateria):FormulacionMateria{
  const f=v.historial.pasos[v.historial.activo].formulacion;
  const componentes=e.componentes?(v.componentesIds??e.componentes.map(s=>s.id)).map(id=>e.componentes!.find(s=>s.id===id)).filter((s):s is Componente=>!!s):f.componentes;
  return {...f,componentes,fronteras:e.corrientes.flatMap(s=>[...(s.hasta===v.id?[{id:s.id,sentido:'entrada' as const,constante:s.constante}]:[]),...(s.desde===v.id?[{id:s.id,sentido:'salida' as const,constante:s.constante}]:[])])};
}
export function actualizarPuertos(e:EnsamblajeMateria):EnsamblajeMateria{return {...e,volumenes:e.volumenes.map(v=>({...v,historial:recorridoMateria(v.historial,{tipo:'cambiar',titulo:'Actualizar las corrientes compartidas',cambios:{fronteras:formulacionVolumen(e,v).fronteras}})}))};}
export function iniciarEnsamblaje(historial:RecorridoMateria,config:ConfiguracionMotor){
  const f=historial.pasos[historial.activo].formulacion;
  const corrientes=f.fronteras.map(p=>({id:p.id,nombre:`Corriente ${p.id}`,desde:p.sentido==='salida'?'v1':null,hasta:p.sentido==='entrada'?'v1':null,constante:p.constante!==false}));
  const ensamblaje:EnsamblajeMateria={version:1,volumenes:[{id:'v1',nombre:'Volumen 1',historial:structuredClone(historial)}],corrientes,ultimoVolumen:1,ultimaCorriente:Math.max(0,...corrientes.map(s=>s.id))};
  const datos:ConfiguracionMotor['datos']={};
  for(const campo of camposMotor(f,config).campos){const d=config.datos[campo.id];if(!d)continue;const match=/^(entrada|salida)_(\d+)_(\d+)$/.exec(campo.id);const copia=structuredClone(d);
    if(match){const especie=f.componentes?.find(s=>s.id===Number(match[2]));const alias:Record<string,string>={m:`m_${especie?.simbolo}_v1`,rho:`rho_${especie?.simbolo}_v1`,m_total:'m_total_v1',rho_total:'rho_total_v1',V:'V_v1'};for(const s of f.componentes??[]){alias[`m_${s.simbolo}`]=`m_${s.simbolo}_v1`;alias[`rho_${s.simbolo}`]=`rho_${s.simbolo}_v1`;}copia.texto=copia.texto.replace(/\b[A-Za-z][A-Za-z0-9_]*\b/g,token=>alias[token]??token);}
    datos[match?claveCorriente(Number(match[3]),Number(match[2])):claveVolumen('v1',campo.id)]=copia;
  }
  return {ensamblaje,config:{...config,datos}};
}
export function agregarVolumen(e:EnsamblajeMateria):EnsamblajeMateria{
  const id=e.ultimoVolumen+1,componentes=catalogoComponentes(e);
  const historial=recorridoMateria(iniciarRecorrido(),{tipo:'cambiar',titulo:'Declarar los componentes del ensamblaje',cambios:{componentes:structuredClone(componentes)}});
  historial.ultimoComponenteId=Math.max(historial.ultimoComponenteId??0,...e.volumenes.map(v=>v.historial.ultimoComponenteId??0));
  return {...e,ultimoVolumen:id,volumenes:[...e.volumenes,{id:`v${id}`,nombre:`Volumen ${id}`,historial,...(e.componentes?{componentesIds:componentes.map(s=>s.id)}:{})}]};
}
type TerminoEnsamblado={fila:number;clave:string;signo:number;volumen:string;porVolumen:boolean;rol:string;corriente?:number};
export type PlanEnsamblaje={analisis:AnalisisMotor;estados:EstadoAcoplado[];terminos:TerminoEnsamblado[];incidencia:number[][];especies:NonNullable<FormulacionMateria['componentes']>;volumenesConDato:string[]};
export function planEnsamblaje(e:EnsamblajeMateria,c:ConfiguracionMotor):PlanEnsamblaje{
  const entrada=c;c=datosEnsamblaje(e,c);
  const campos:CampoDato[]=[],bloqueos:string[]=[],errores:Record<string,string>={},pendientes:string[]=[],estados:EstadoAcoplado[]=[],terminos:TerminoEnsamblado[]=[];
  const especies=catalogoComponentes(e);
  if(![1,2].includes(e.version)||!e.volumenes.length)bloqueos.push('Añade un volumen al ensamblaje con versión soportada.');
  if(new Set(especies.map(s=>s.id)).size!==especies.length||new Set(especies.map(s=>s.simbolo)).size!==especies.length||especies.some(s=>!Number.isInteger(s.id)||s.id<1||!/^([A-Z]|S\d+)$/.test(s.simbolo)))bloqueos.push('Los componentes deben tener identidades y símbolos únicos.');
  for(const s of especies)if(s.masaMolar)try{masaMolarKg(s);}catch(error){bloqueos.push((error as Error).message);}
  if(e.volumenes.length>32||e.volumenes.length*especies.length>128)bloqueos.push('Límite del cálculo de referencia: 32 volúmenes y 128 estados.');
  if(new Set(e.volumenes.map(v=>v.id)).size!==e.volumenes.length||e.volumenes.some(v=>!/^v[1-9]\d*$/.test(v.id)))bloqueos.push('Los identificadores de volumen deben ser únicos y estables.');
  if(new Set(e.corrientes.map(s=>s.id)).size!==e.corrientes.length||e.corrientes.some(s=>!Number.isInteger(s.id)||s.id<1))bloqueos.push('Las corrientes deben tener identificadores únicos.');
  for(const s of e.corrientes)if((s.desde===null&&s.hasta===null)||[s.desde,s.hasta].some(id=>id!==null&&!e.volumenes.some(v=>v.id===id)))bloqueos.push(`${s.nombre}: falta un volumen del extremo de la corriente.`);
  const volumenesConDato=e.volumenes.filter(v=>v.volumenDeclarado||camposMotor({...formulacionVolumen(e,v),fronteras:[]},c).campos.some(p=>p.id==='volumen')).map(v=>v.id);
  const aliases=e.volumenes.flatMap(v=>[...especies.map(s=>`m_${s.simbolo}_${v.id}`),`m_total_${v.id}`,...(volumenesConDato.includes(v.id)?[`V_${v.id}`,`rho_total_${v.id}`,...especies.map(s=>`rho_${s.simbolo}_${v.id}`)]:[])]);
  for(const v of e.volumenes){
    if(v.componentesIds&&(new Set(v.componentesIds).size!==v.componentesIds.length||v.componentesIds.some(id=>!especies.some(s=>s.id===id))))bloqueos.push(`${v.nombre}: referencias de componentes inválidas.`);
    const f=formulacionVolumen(e,v),cs=f.componentes??[];
    if(f.vista!=='cantidad'||f.cantidadVolumen)bloqueos.push(`${v.nombre}: usa balances temporales de masa total por componente para este acoplamiento. La sustitución por volumen o un campo espacial necesita otro contrato de interfaz.`);
    if(cs.length!==especies.length||cs.some(s=>!especies.some(k=>k.id===s.id&&k.simbolo===s.simbolo)))bloqueos.push(`${v.nombre}: declara las mismas identidades de componentes que los otros volúmenes.`);
    const local=camposMotor(f,c);local.bloqueos.forEach(b=>bloqueos.push(`${v.nombre}: ${b}`));
    for(const s of especies)estados.push({id:`${v.id}_c${s.id}`,volumenId:v.id,volumenNombre:v.nombre,componenteId:s.id,componenteNombre:cs.find(k=>k.id===s.id)?.nombre??s.nombre,simbolo:s.simbolo});
    for(const p of local.campos.filter(p=>!p.id.startsWith('entrada_')&&!p.id.startsWith('salida_'))){
      campos.push({...p,id:claveVolumen(v.id,p.id),grupo:`${v.nombre} · ${p.grupo}`,variables:p.funcion==='inicial'?[]:p.id==='volumen'?p.variables:[...new Set([...p.variables,...aliases,...(volumenesConDato.includes(v.id)?['V','rho','rho_total',...especies.map(s=>`rho_${s.simbolo}`)]:[])])]});
    }
    if(v.volumenDeclarado&&!local.campos.some(p=>p.id==='volumen'))campos.push({id:claveVolumen(v.id,'volumen'),nombre:'Volumen del dominio',simbolo:`V_{${v.id}}${f.fija?'':'(t)'}`,magnitud:'volumen',funcion:'dato',variables:f.fija?[]:['t'],grupo:v.nombre});
    for(const s of especies){const fila=estados.findIndex(x=>x.volumenId===v.id&&x.componenteId===s.id);
      for(const t of terminosTotalesMateria(f,indiceComponente(s)))terminos.push({fila,clave:t.puertoId===undefined?claveVolumen(v.id,`${t.rol}_${s.id}`):claveCorriente(t.puertoId,s.id),signo:t.signo,volumen:v.id,porVolumen:t.forma==='tasa_por_volumen',rol:t.rol,corriente:t.puertoId});
    }
  }
  for(const s of e.corrientes){const m=s.datos?.materia,cs=s.componentesIds??especies.map(z=>z.id),variables=s.constante?[]:['t',...aliases],grupo=`S${s.id} · ${s.nombre}`;
    if(new Set(cs).size!==cs.length||cs.length!==especies.length||cs.some(id=>!especies.some(z=>z.id===id)))bloqueos.push(`${grupo}: referencias de componentes inexistentes o incompletas.`);
    if(s.mecanismo!==undefined&&s.mecanismo!==null&&!['convectivo','selectivo'].includes(s.mecanismo))bloqueos.push(`${grupo}: mecanismo no válido.`);
    if(s.datos?.fasesPermitidas&&(!s.datos.fasesPermitidas.length||new Set(s.datos.fasesPermitidas).size!==s.datos.fasesPermitidas.length||s.datos.fasesPermitidas.some(f=>!['liquido','vapor','solido'].includes(f))))bloqueos.push(`${grupo}: restricción de fases no válida.`);
    if(m&&Object.keys(entrada.datos).some(k=>k===claveTotalCorriente(s.id)||k.startsWith(`s${s.id}__c`)))bloqueos.push(`${grupo}: especificación duplicada en config.datos.`);
    if(m&&(!['masica','molar'].includes(m.base)||!['por_componente','total_y_composicion'].includes(m.modo)))bloqueos.push(`${grupo}: especificación material no válida.`);
    if(m?.base==='molar')for(const comp of especies)try{masaMolarKg(comp);}catch(error){bloqueos.push((error as Error).message);}
    if(m?.modo==='total_y_composicion'){
      if('caudales' in m)bloqueos.push(`${grupo}: no combines caudales por componente con un total.`);
      const fr=m.composicion?.fracciones??{};
      if(s.mecanismo==='selectivo')bloqueos.push(`${grupo}: un intercambio selectivo necesita tasas por componente, no una composición del flujo neto.`);
      if(m.composicion?.base!==m.base||Object.keys(fr).length!==cs.length||cs.some(id=>!Number.isFinite(fr[id])||fr[id]<0)||Object.keys(fr).some(id=>!cs.includes(Number(id)))||Math.abs(Object.values(fr).reduce((a,b)=>a+b,0)-1)>1e-12)bloqueos.push(`${grupo}: composición incompatible; declara cada componente y suma uno en la misma base que el caudal.`);
      campos.push({id:claveTotalCorriente(s.id),nombre:'Caudal total',simbolo:`${m.base==='molar'?'F':String.raw`\dot m`}_{s${s.id}}`,magnitud:m.base==='molar'?'caudal_molar':'caudal',funcion:'dato',variables,grupo});
    }else{
      if(m&&('caudalTotal' in m||'composicion' in m||Object.keys(m.caudales).some(id=>!cs.includes(Number(id)))))bloqueos.push(`${grupo}: datos materiales contradictorios o componentes desconocidos.`);
      for(const comp of especies)campos.push({id:claveCorriente(s.id,comp.id),nombre:comp.nombre,simbolo:String.raw`\dot m_{${indiceComponente(comp)},s${s.id}}${s.constante?'':'(t)'}`,magnitud:m?.base==='molar'?'caudal_molar':'caudal',funcion:'dato',variables,grupo});
    }
  }
  for(const p of campos){const d=c.datos[p.id];if(!d?.texto.trim())pendientes.push(p.id);else try{analizarExpresion(d.texto,p.variables);factorUnidad(p.magnitud,d.unidad);}catch(error){errores[p.id]=(error as Error).message;}}
  // Reuse the existing numerical-option validation without counting a fabricated physical datum.
  const control=iniciarRecorrido().pasos[0].formulacion;
  const opciones=analizarMotor({...control,componentes:[{id:1,nombre:'Control',simbolo:'A'}],vista:'cantidad',restoImpermeable:true,campo:{...control.campo,sinReaccion:true}},{...c,datos:{inicial_1:{texto:'0',unidad:'kg'}}});
  Object.assign(errores,opciones.errores);if(opciones.pendientes.includes('tiempo'))pendientes.push('tiempo');
  if(c.metodo==='euler_implicito'&&estados.length>64)errores.metodo='El método implícito admite hasta 64 estados; usa RK45 para este ensamblaje.';
  const evaluacionReglas=e.volumenes.flatMap(v=>analizarReglasEstado(formulacionVolumen(e,v)).evaluacion.map(r=>({...r,reglaId:`${v.id}__${r.reglaId}`})));
  const datos=campos.filter(p=>p.funcion!=='inicial'),iniciales=campos.filter(p=>p.funcion==='inicial'),falta=(p:CampoDato)=>pendientes.includes(p.id)||!!errores[p.id];
  const analisis:AnalisisMotor={modo:bloqueos.length?null:'temporal',campos,bloqueos,errores,pendientes,gl:datos.filter(falta).length,inicialesPendientes:iniciales.filter(falta).length,definidas:datos.filter(p=>!falta(p)).length,totalDatos:datos.length,totalIniciales:iniciales.length,variables:estados.length+datos.length,ecuaciones:estados.length,listo:!bloqueos.length&&!pendientes.length&&!Object.keys(errores).length,...(evaluacionReglas.length?{evaluacionReglas}:{})};
  const incidencia=e.volumenes.map(v=>e.corrientes.map(s=>Number(s.hasta===v.id)-Number(s.desde===v.id)));
  return {analisis,estados,terminos,incidencia,especies,volumenesConDato};
}
export function compilarEnsamblaje(e:EnsamblajeMateria,c:ConfiguracionMotor):SistemaNumerico{
  const p=planEnsamblaje(e,c),a=p.analisis;if(!a.listo)throw new Error(a.bloqueos[0]??Object.values(a.errores)[0]??'Completa los datos del ensamblaje.');
  c=datosEnsamblaje(e,c);
  const ast=Object.fromEntries(a.campos.map(q=>[q.id,{e:analizarExpresion(c.datos[q.id].texto,q.variables),factor:factorUnidad(q.magnitud,c.datos[q.id].unidad)}]));
  const valor=(id:string,env:Record<string,number>)=>{try{const v=evaluarExpresion(ast[id].e,env)*ast[id].factor;if(!Number.isFinite(v))throw new Error('Valor normalizado no finito.');return v;}catch(error){throw new Error(`${a.campos.find(q=>q.id===id)?.grupo} / ${a.campos.find(q=>q.id===id)?.nombre}: ${(error as Error).message}`);}};
  const inicial=p.estados.map(s=>valor(claveVolumen(s.volumenId,`inicial_${s.componenteId}`),{}));if(inicial.some(v=>v<0))throw new Error('Las cantidades iniciales no pueden ser negativas.');
  const tfinal=evaluarExpresion(analizarExpresion(c.tiempo.texto,[]),{})*factorUnidad('tiempo',c.tiempo.unidad);
  const fuentes=p.terminos.filter(z=>z.corriente===undefined);
  const flujos=e.corrientes.flatMap(s=>p.especies.map((comp,ci)=>{
    const terminos=p.terminos.filter(z=>z.corriente===s.id&&p.estados[z.fila].componenteId===comp.id),signos=new Map<number,number>();
    for(const z of terminos)signos.set(z.fila,(signos.get(z.fila)??0)+z.signo);
    const m=s.datos?.materia,total=m?.modo==='total_y_composicion';
    return {s,ci,id:claveCorriente(s.id,comp.id),entrada:total?claveTotalCorriente(s.id):claveCorriente(s.id,comp.id),factor:(total?m.composicion.fracciones[comp.id]:1)*(m?.base==='molar'?masaMolarKg(comp):1),destinos:[...signos].filter(([,signo])=>signo!==0),sinTransporte:e.volumenes.filter(v=>(s.desde===v.id||s.hasta===v.id)&&!terminos.some(z=>z.volumen===v.id))};
  }));
  function contexto(t:number,y:number[]){const env:Record<string,number>={t};for(const v of e.volumenes){env[`m_total_${v.id}`]=0;for(const [i,s] of p.estados.entries())if(s.volumenId===v.id){env[`m_${s.simbolo}_${v.id}`]=y[i];env[`m_total_${v.id}`]+=y[i];}
      if(p.volumenesConDato.includes(v.id)){const V=valor(claveVolumen(v.id,'volumen'),{t});if(V<=0)throw new Error(`${v.nombre}: el volumen debe ser positivo.`);env[`V_${v.id}`]=V;env[`rho_total_${v.id}`]=env[`m_total_${v.id}`]/V;for(const s of p.especies)env[`rho_${s.simbolo}_${v.id}`]=env[`m_${s.simbolo}_${v.id}`]/V;}}
    return env;
  }
  let ultimoT=NaN,ultimoY:number[]=[],cache:{dy:number[];global:number[];datos:Record<string,number>}|undefined;
  function evaluar(t:number,y:number[]){if(t===ultimoT&&y.length===ultimoY.length&&y.every((v,i)=>v===ultimoY[i])&&cache)return cache;
    const env=contexto(t,y),datos:Record<string,number>={},dy=Array(y.length).fill(0),global=Array(p.especies.length).fill(0);
    // Each shared flow is evaluated once and is used with both incidence signs.
    const evaluados=new Map<string,number>(),signosCorrientes=new Map<number,Set<number>>();
    for(const {s,ci,id,entrada,factor,destinos,sinTransporte} of flujos){
      if(!evaluados.has(entrada))evaluados.set(entrada,valor(entrada,env));
      const original=evaluados.get(entrada)!,q=original*factor;datos[entrada]=original;if(entrada!==id)datos[id]=q;datos[`mdot_s${s.id}_c${p.especies[ci].id}`]=q;
      const signos=signosCorrientes.get(s.id)??new Set<number>();if(q!==0)signos.add(Math.sign(q));signosCorrientes.set(s.id,signos);
      if(q!==0&&sinTransporte.length)throw new Error(`${sinTransporte[0].nombre}: S${s.id} contradice la eliminación del transporte en este volumen.`);
      for(const [fila,signo] of destinos)dy[fila]+=signo*q;
      if(s.desde===null)global[ci]+=q;if(s.hasta===null)global[ci]-=q;
    }
    for(const s of e.corrientes)if(s.mecanismo==='convectivo'&&(signosCorrientes.get(s.id)?.size??0)>1)throw new Error(`S${s.id}: los componentes de una corriente convectiva deben compartir sentido; usa intercambio selectivo para contraflujo.`);
    for(const z of fuentes){
      const estado=p.estados[z.fila],local:Record<string,number>={...env,m:y[z.fila],m_total:env[`m_total_${z.volumen}`],V:env[`V_${z.volumen}`],rho:env[`rho_${estado.simbolo}_${z.volumen}`],rho_total:env[`rho_total_${z.volumen}`]};
      for(const s of p.especies){local[`m_${s.simbolo}`]=env[`m_${s.simbolo}_${z.volumen}`];local[`rho_${s.simbolo}`]=env[`rho_${s.simbolo}_${z.volumen}`];}
      const q=valor(z.clave,local);if(['generacion','consumo'].includes(z.rol)&&q<0)throw new Error(`${estado.volumenNombre}: las tasas brutas deben ser no negativas.`);
      datos[z.clave]=q;const contribucion=z.signo*q*(z.porVolumen?env[`V_${z.volumen}`]:1);dy[z.fila]+=contribucion;global[p.especies.findIndex(s=>s.id===estado.componenteId)]+=contribucion;
    }
    if([...dy,...global].some(v=>!Number.isFinite(v)))throw new Error('El balance ensamblado no es finito.');
    for(const campo of a.campos){if(campo.funcion==='inicial')datos[campo.id]=valor(campo.id,{});else if(campo.id.endsWith('__volumen'))datos[campo.id]=env[`V_${campo.id.split('__')[0]}`];}
    ultimoT=t;ultimoY=[...y];cache={dy,global,datos};return cache;
  }
  evaluar(0,inicial);
  return {variablesNumericas:p.estados.map(z=>({id:z.id,propietarioId:z.volumenId,componenteId:z.componenteId,magnitud:'masa',unidad:'kg',rol:'diferencial',restriccion:'no_negativo',toleranciaAbsoluta:c.atol})),...(a.evaluacionReglas?{evaluacionReglas:a.evaluacionReglas}:{}),modo:'temporal',unidadEstado:'kg',inicial,x:[],dx:1,n:1,nc:inicial.length,tfinal,rhs:(t,y)=>evaluar(t,y).dy,balance:(t,y)=>[...evaluar(t,y).dy,...evaluar(t,y).global],limitePaso:()=>tfinal/(c.muestras-1),observacion:(_t,y)=>y.map(v=>[v]),estadosAcoplados:p.estados,gruposGlobales:p.especies.map(s=>({id:s.id,nombre:s.nombre,indices:p.estados.flatMap((x,i)=>x.componenteId===s.id?[i]:[])})),valoresDatos:(t,y)=>({...contexto(t,y),...evaluar(t,y).datos})};
}
export function ecuacionesEnsamblaje(e:EnsamblajeMateria){return e.volumenes.map(v=>{const f=formulacionVolumen(e,v);return {id:v.id,nombre:v.nombre,ecuaciones:(f.componentes??[]).map(s=>{
  const i=indiceComponente(s),terminos=terminosTotalesMateria(f,i).map(z=>{const simbolo=z.puertoId!==undefined?String.raw`\dot m_{${i},s${z.puertoId}}`:z.rol==='resto'?String.raw`\Phi_{${i},${v.id},\mathrm{resto}}`:z.forma==='tasa_por_volumen'?String.raw`${z.rol==='generacion'?String.raw`\gamma`:String.raw`\chi`}_{${i},${v.id}}(t)V_{${v.id}}${f.fija?'':'(t)'}`:`${z.rol==='generacion'?'G':'C'}_{${i},${v.id}}(t)`;
    const s=z.puertoId===undefined?undefined:e.corrientes.find(s=>s.id===z.puertoId);const latex=s?.desde&&s?.hasta?String.raw`\color{#536844}{${simbolo}}`:simbolo;return {signo:z.signo,latex};});
  const rhs=terminos.map((t,n)=>`${t.signo<0?'-':n?'+':''}${t.latex}`).join('')||'0';const lhs=acumulacionTotalNula(f)?'0':String.raw`\frac{dm_{${i},${v.id}}}{dt}`;return {componente:s,latex:`${lhs}=${rhs}`};})};});}
export function unidadCampo(campo:CampoDato){return Object.keys(UNIDADES_MOTOR[campo.magnitud])[0];}
