import type {HojaMotor} from './hojasMotor';
import type {AnalisisMotor,CampoDato,SistemaNumerico,SerieEvaluadaMotor} from './modeloNumerico';
import {analizarMotor,compilarMotor} from './modeloNumerico';
import {planEnsamblaje,compilarEnsamblaje,claveCorriente} from './ensamblajeMateria';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {convertirUnidad} from './unidadesMotor';
import {materiaEnergiaHoja,contextoEnergiaHoja,historialEnergiaHoja,formulacionEnergiaHoja,configuracionConEnergia,donanteCorrienteEnergia} from './estadoEnergiaHoja';
import {actualEnergia,terminosEnergia,ecuacionEnergia,relacionesEnergia,sinFuentesMateriales,tienePresionPrescrita} from './recorridoEnergia';
import {balancesHoja} from './seleccionBalances';
import {bloqueosCierreTermodinamico} from './estadoTermodinamicoHoja';
import {campoGeometria,relacionesGeometria} from './volumenControl';
import {relacionesSistemaEnergia} from './ecuacionesSistemaEnergia';

const analisisMateria=(h:HojaMotor)=>h.ensamblaje?planEnsamblaje(h.ensamblaje,h.config).analisis:analizarMotor(materiaEnergiaHoja(h),h.config);
const claveCaudal=(h:HojaMotor,id:number)=>h.ensamblaje?claveCorriente(id,materiaEnergiaHoja(h).componentes![0].id):`${contextoEnergiaHoja(h).puertos.find(p=>p.id===id)!.sentido}_${materiaEnergiaHoja(h).componentes![0].id}_${id}`;
/** A constant outward flow never needs a fictional external temperature.
 * Variable flows require the external donor state, since their direction may reverse. */
const requiereExterior=(h:HojaMotor,id:number)=>donanteCorrienteEnergia(h,id)!=='volumen';
export function camposEnergia(h:HojaMotor):CampoDato[]{
  const e=formulacionEnergiaHoja(h),ctx=contextoEnergiaHoja(h),campos:CampoDato[]=[],vs=['t','m','T','U',...(e.densidadConstante?['V','rho']:campoGeometria(h)?['V']:[])];
  const add=(id:string,nombre:string,simbolo:string,magnitud:CampoDato['magnitud'],funcion:CampoDato['funcion']='dato',variables:string[]=[],grupo='Energía · relación de estado')=>campos.push({id:`energia_${id}`,nombre,simbolo,magnitud,funcion,variables,grupo});
  if(e.modelo==='u_lineal'){
  add('c','Derivada du/dT declarada','c_u','capacidad_especifica');add('u_ref','Energía interna específica de referencia',String.raw`u_{\mathrm{ref}}`,'energia_especifica');add('T_ref','Temperatura de referencia',String.raw`T_{\mathrm{ref}}`,'temperatura');
  if(h.energia?.inicial==='U')add('U0','Energía inicial','U(0)','energia','inicial');else add('T0','Temperatura inicial','T(0)','temperatura','inicial');
  add('T_min','Límite térmico inferior',String.raw`T_{\min}`,'temperatura');add('T_max','Límite térmico superior',String.raw`T_{\max}`,'temperatura');
  }
  if(e.densidadConstante||ctx.puertos.length)add('rho','Densidad de mezcla constante',String.raw`\rho_*`,'densidad');
  if(tienePresionPrescrita(e,ctx))add('p','Presión impuesta','P_ext','presion','dato',['t']);
  for(const t of terminosEnergia(e,ctx)){
    if(t.rol==='calor')add('Q','Calor hacia el volumen (+ entra, − sale)',String.raw`\dot Q`,'potencia','dato',vs,'Energía · transferencias');
    if(t.id==='trabajo_viscoso')add('Wtau','Trabajo de esfuerzos viscosos hacia el volumen',String.raw`\dot W_\tau`,'potencia','dato',vs,'Energía · transferencias');
    if(t.rol==='fuerzas')add('Wb','Trabajo de fuerzas de volumen',String.raw`\dot W_{\mathbf b}`,'potencia','dato',vs,'Energía · transferencias');
    if(t.rol==='fuente')add('R','Aporte volumétrico integrado','R','potencia','dato',vs,'Energía · transferencias');
  }
  for(const p of ctx.puertos)if(e.modelo==='u_lineal'&&ctx.componentesIds.length===1&&requiereExterior(h,p.id))add(`T_${p.id}`,`Temperatura exterior · corriente ${p.id}${p.sentido==='salida'?' (si invierte su sentido)':''}`,String.raw`T_{\mathrm{ext},${p.id}}`,'temperatura','dato',['t'],`Corriente ${p.id} · energía`);
  return campos;
}
export function analizarEnergia(h:HojaMotor):AnalisisMotor{
  const m=materiaEnergiaHoja(h),e=formulacionEnergiaHoja(h),ctx=contextoEnergiaHoja(h),a=analisisMateria(h),bloqueos=[...a.bloqueos,...bloqueosCierreTermodinamico(h)];
  if(h.ensamblaje&&h.ensamblaje.volumenes.length!==1)bloqueos.unshift('El primer ensamblaje de energía admite un volumen. La energía de varios volúmenes queda pendiente.');
  if(m.componentes?.length!==1)bloqueos.push('La relación energética ejecutable requiere un componente; la energía de mezclas queda pendiente.');
  if(m.vista!=='cantidad'||m.cantidadVolumen)bloqueos.push('Conserva la masa como estado y expresa materia en forma total para acoplar U.');
  if(!sinFuentesMateriales(m))bloqueos.push('Las fuentes materiales requieren declarar la energía asociada; quedan fuera de este primer hito.');
  if(e.forma!=='total')bloqueos.push('Completa la transformación de energía a forma total (Gauss, Reynolds y puertos).');
  if(JSON.stringify(actualEnergia(historialEnergiaHoja(h)).contexto)!==JSON.stringify(ctx))bloqueos.push('Actualiza el volumen y las corrientes en el desglose de energía.');
  if(e.estacionario||e.sinAcumulacionTotal)bloqueos.push('El primer solver energético es temporal; no ejecuta la reducción estacionaria.');
  if(!e.sinCinetica)bloqueos.push('Declara la energía cinética despreciable o aporta su modelo; este primer solver conserva U.');
  if(!e.separarPresion)bloqueos.push('Descompón los esfuerzos en presión y esfuerzo viscoso antes de ensamblar energía.');
  if(!e.uniforme)bloqueos.push('Declara estado térmico uniforme para reducir U a m u(T).');
  if(!e.monofasico||!e.sinCambioFase)bloqueos.push('Declara en Termodinámica el régimen monofásico sin cambio de fase para esta relación u(T).');
  if(e.modelo!=='u_lineal')bloqueos.push('Declara en Termodinámica una relación u(T); no se puede obtener T únicamente con el balance.');
  if(!ctx.restoCerrado)bloqueos.push('El intercambio material por la superficie restante sigue pendiente.');
  if(ctx.puertos.length&&(!e.densidadConstante||!e.presionUniforme))bloqueos.push('Para corrientes abiertas, declara densidad constante (Termodinámica) y presión uniforme.');
  if(!ctx.fija&&!e.presionUniforme)bloqueos.push('La frontera móvil necesita una relación de trabajo de presión; declara presión uniforme.');
  if((ctx.puertos.length||!ctx.fija)&&!tienePresionPrescrita(e,ctx))bloqueos.push('Declara la presión impuesta o un cierre que permita calcularla; la uniformidad espacial no determina P(t).');
  if(tienePresionPrescrita(e,ctx)&&!e.presionUniforme)bloqueos.push('La reducción de presión impuesta requiere equilibrio mecánico con presión espacialmente uniforme.');
  if(!ctx.fija&&!e.densidadConstante)bloqueos.push('Declara densidad constante en Termodinámica para obtener dV/dt de dm/dt en esta primera relación.');
  if(!balancesHoja(h).materia&&ctx.puertos.length)bloqueos.push('Activa materia para resolver cantidades variables con corrientes. Energía sola admite masa constante en un volumen cerrado.');
  if(h.ensamblaje?.corrientes.some(s=>s.mecanismo==='selectivo'))bloqueos.push('La transferencia energética selectiva requiere otra relación y no se ejecuta como convección.');
  if(e.trabajoTotalHeredado)bloqueos.push('La antigua exclusión de todos los esfuerzos necesita reformularse explícitamente en el nuevo desglose.');
  const geo=campoGeometria(h),materia=balancesHoja(h).materia,campos=[...a.campos.filter(p=>p.id!==geo?.id).map(p=>!materia&&p.funcion==='inicial'?{...p,funcion:'dato' as const,nombre:'Masa constante declarada',simbolo:'m'}:p),...(geo?[geo]:[]),...camposEnergia(h)];
  const errores={...a.errores},pendientes=a.pendientes.filter(id=>!a.campos.some(p=>p.id===id));
  const c=configuracionConEnergia(h);
  for(const s of h.ensamblaje?.corrientes??[])if(s.datos?.T&&h.energia?.datos[`energia_T_${s.id}`])bloqueos.push(`S${s.id}: temperatura duplicada en corriente y datos de energía.`);
  for(const p of campos){const d=c.datos[p.id];if(!d?.texto.trim()){pendientes.push(p.id);continue;}try{const ast=analizarExpresion(d.texto,p.variables);if(p.id.startsWith('energia_')||p.id===geo?.id){convertirUnidad(p.magnitud,0,d.unidad);if(!p.variables.length){const v=convertirUnidad(p.magnitud,evaluarExpresion(ast,{}),d.unidad);if(!Number.isFinite(v))throw new Error('Dato no finito.');if((['energia_c','energia_rho'].includes(p.id)||p.id===geo?.id)&&v<=0)throw new Error('Debe ser positivo.');if(p.magnitud==='temperatura'&&(p.id==='energia_T_ref'?v<0:v<=0))throw new Error('Temperatura absoluta no positiva.');}}}catch(error){errores[p.id]=(error as Error).message;}}
  const atol=h.energia?.atol??1e-6;if(!Number.isFinite(atol)||atol<=0||atol>.1)errores.tolerancias='Tolerancia energética fuera de rango (J).';
  const dato=(id:string)=>{const d=c.datos[id];return d?.texto.trim()?convertirUnidad('temperatura',evaluarExpresion(analizarExpresion(d.texto,[]),{}),d.unidad):undefined;};
  if(e.modelo==='u_lineal')try{const min=dato('energia_T_min'),max=dato('energia_T_max'),T0=h.energia?.inicial==='U'?undefined:dato('energia_T0');if(min!==undefined&&max!==undefined&&max<=min)errores.energia_T_max='Debe superar el límite inferior.';if(min!==undefined&&max!==undefined&&T0!==undefined&&(T0<min||T0>max))errores.energia_T0='Estado inicial fuera del dominio térmico.';}catch{}
  // Check the algebraic initial state without integrating or introducing a new unknown.
  const inicialM=a.campos.find(p=>p.funcion==='inicial'&&p.magnitud==='masa');
  if(inicialM&&!pendientes.includes(inicialM.id)&&!errores[inicialM.id])try{
    const d=c.datos[inicialM.id],m0=convertirUnidad('masa',evaluarExpresion(analizarExpresion(d.texto,[]),{}),d.unidad);
    if(m0<=0)errores[inicialM.id]='Debe ser positiva para definir T desde U/m.';
    if(m0>0&&e.modelo==='u_lineal'&&h.energia?.inicial==='U'){
      const ids=['energia_U0','energia_c','energia_u_ref','energia_T_ref','energia_T_min','energia_T_max'];
      if(ids.every(id=>!pendientes.includes(id)&&!errores[id])){
        const val=(id:string)=>{const p=campos.find(p=>p.id===id)!,d=c.datos[id];return convertirUnidad(p.magnitud,evaluarExpresion(analizarExpresion(d.texto,[]),{}),d.unidad);};
        const T0=val('energia_T_ref')+(val('energia_U0')/m0-val('energia_u_ref'))/val('energia_c');
        if(!Number.isFinite(T0)||T0<val('energia_T_min')||T0>val('energia_T_max'))errores.energia_U0='La temperatura derivada de U(0) está fuera del dominio térmico.';
      }
    }
  }catch{}
  const requeridos=campos.filter(p=>p.funcion!=='inicial'),iniciales=campos.filter(p=>p.funcion==='inicial'),falta=(p:CampoDato)=>pendientes.includes(p.id)||!!errores[p.id],n=materia?2:1;
  return {modo:'temporal',campos,bloqueos:bloqueos.map(b=>`El balance de energía: ${b}`),errores,pendientes:[...new Set(pendientes)],gl:requeridos.filter(falta).length,inicialesPendientes:iniciales.filter(falta).length,definidas:requeridos.filter(p=>!falta(p)).length,totalDatos:requeridos.length,totalIniciales:iniciales.length,variables:n+requeridos.length+(e.modelo==='u_lineal'?1+(e.densidadConstante?1:0)+ctx.puertos.length:0),ecuaciones:n+(e.modelo==='u_lineal'?1+(e.densidadConstante?1:0)+ctx.puertos.length:0),listo:!bloqueos.length&&!pendientes.length&&!Object.keys(errores).length};
}
export type SistemaEnergia=SistemaNumerico & {evaluarEnergia:(t:number,y:number[])=>Record<string,number>;catalogoSeries:Omit<SerieEvaluadaMotor,'valores'>[];trazabilidad:{ecuacion:string;relaciones:string[];terminos:{id:string;unidad:string;signo:number}[];datosUsados:string[];datosInactivos:string[];estadoDeFase:'asumido_sin_verificar'}};
export function compilarEnergia(h:HojaMotor):SistemaEnergia{
  const a=analizarEnergia(h);if(!a.listo)throw new Error(a.bloqueos[0]??Object.values(a.errores)[0]??'Completa los datos de materia y energía.');
  const f=materiaEnergiaHoja(h),e=formulacionEnergiaHoja(h),ctx=contextoEnergiaHoja(h),c=configuracionConEnergia(h),materia=balancesHoja(h).materia;
  const base=h.ensamblaje?compilarEnsamblaje(h.ensamblaje,h.config):compilarMotor(f,h.config);
  if(base.unidadEstado!=='kg'||base.inicial.length!==1)throw new Error('Este ensamblaje energético requiere una sola masa, en kg.');
  const ast=Object.fromEntries(a.campos.map(p=>[p.id,{p,e:analizarExpresion(c.datos[p.id].texto,p.variables),unidad:c.datos[p.id].unidad}]));
  const valor=(id:string,env:Record<string,number>={})=>{const x=ast[id];if(!x)throw new Error(`Dato pendiente: ${id}.`);const v=convertirUnidad(x.p.magnitud,evaluarExpresion(x.e,env),x.unidad);if(!Number.isFinite(v))throw new Error(`${x.p.nombre}: dato no finito.`);return v;};
  const cu=valor('energia_c'),uref=valor('energia_u_ref'),Tref=valor('energia_T_ref'),Tmin=valor('energia_T_min'),Tmax=valor('energia_T_max'),rho=ast.energia_rho?valor('energia_rho'):undefined;
  const geo=campoGeometria(h),Vgeom=geo?valor(geo.id):undefined;
  const m0=base.inicial[0];if(m0<=0)throw new Error('Una masa inicial positiva es necesaria para definir T desde U/m.');
  const u=(T:number)=>uref+cu*(T-Tref);
  const U0=h.energia?.inicial==='U'?valor('energia_U0'):m0*u(valor('energia_T0'));
  const inicial=materia?[m0,U0]:[U0],indices={m:materia?0:-1,U:materia?1:0};
  const terminos=terminosEnergia(e,ctx);
  function evaluarEnergia(t:number,y:number[]):Record<string,number>{
    const m=materia?y[indices.m]:m0,U=y[indices.U];if(m===0)throw new Error('Masa agotada: U/m no define temperatura.');
    const T=Tref+(U/m-uref)/cu,V=rho?m/rho:Vgeom,env={t,m,U,T,...(rho?{rho}:{}),...(V!==undefined?{V}:{})};
    const dm=materia?base.rhs(t,[m])[0]:0,p=ast.energia_p?valor('energia_p',{t}):0;
    if(Vgeom!==undefined&&V!==undefined&&Math.abs(V-Vgeom)>1e-10*Math.max(Math.abs(V),Math.abs(Vgeom),Number.MIN_VALUE))throw new Error('La masa y densidad declaradas contradicen el volumen geométrico fijo.');
    if(p<0)throw new Error('Presión absoluta negativa.');
    const volumenDeclarado=h.ensamblaje?.volumenes[0].volumenDeclarado;
      if(volumenDeclarado&&rho&&V!==undefined){const real=base.valoresDatos!(t,[m])[`V_${ctx.volumenId}`];if(Math.abs(real-V)>1e-10*Math.max(Math.abs(real),Math.abs(V),Number.MIN_VALUE))throw new Error('El volumen declarado contradice V=m/rho de la relación de estado.');}
    const datosBase=base.valoresDatos?.(t,[m]);
    const contribuciones:Record<string,number>={},flujos:Record<string,number>={};let escalaFlujos=0;
    for(const pto of ctx.puertos){
      const mdot=h.ensamblaje?datosBase![`mdot_s${pto.id}_c${f.componentes![0].id}`]:datosBase![claveCaudal(h,pto.id)];
      const neto=(pto.sentido==='entrada'?1:-1)*mdot;escalaFlujos=Math.max(escalaFlujos,Math.abs(mdot));
      const Tin=neto>0?valor(`energia_T_${pto.id}`,{t}):T;
      if(neto>0&&(Tin<Tmin||Tin>Tmax))throw new Error(`Corriente ${pto.id}: temperatura exterior fuera del dominio térmico.`);
      const Pext=h.ensamblaje?.corrientes.find(s=>s.id===pto.id)?.datos?.P;
      if(Pext){const declarado=convertirUnidad('presion',evaluarExpresion(analizarExpresion(Pext.texto,['t']),{t}),Pext.unidad);if(Math.abs(declarado-p)>1e-10*Math.max(Math.abs(p),Math.abs(declarado),1))throw new Error(`Corriente ${pto.id}: presión incompatible con la hipótesis de presión uniforme.`);}
      const entalpia=u(Tin)+p/rho!;
      // A term's sign is applied below exactly once, matching the rendered equation.
      contribuciones[`puerto_${pto.id}`]=mdot*(e.entalpia?entalpia:u(Tin));
      contribuciones[`presion_flujo_${pto.id}`]=mdot*p/rho!;
      flujos[`mdot_${pto.id}`]=mdot;flujos[`h_${pto.id}`]=entalpia;flujos[`E_${pto.id}`]=neto*entalpia;
    }
    if(ctx.fija&&ctx.puertos.length&&Math.abs(dm)>1e-10*Math.max(escalaFlujos,Number.MIN_VALUE))throw new Error('Frontera fija y densidad constante exigen dm/dt=0 cuando el fluido ocupa el dominio completo; los caudales declarados se contradicen.');
    contribuciones.calor=ast.energia_Q?valor('energia_Q',env):0;
    contribuciones.trabajo_viscoso=ast.energia_Wtau?valor('energia_Wtau',env):0;
    contribuciones.fuerzas=ast.energia_Wb?valor('energia_Wb',env):0;
    contribuciones.fuente=ast.energia_R?valor('energia_R',env):0;
    contribuciones.trabajo_frontera=ctx.fija?0:p*dm/rho!;
    const dU=terminos.reduce((sum,t)=>{const v=contribuciones[t.id];if(v===undefined)throw new Error(`Término energético no implementado: ${t.id}.`);return sum+t.signo*v;},0);
    const estado={m,U,T,...(V!==undefined?{V}:{}),...(rho?{rho}:{}),...(ast.energia_p?{p}:{}),dm,dU,Q:contribuciones.calor,Wb:contribuciones.trabajo_frontera,Wtau:contribuciones.trabajo_viscoso,Wf:contribuciones.fuerzas,R:contribuciones.fuente,...flujos};
    if(Object.values(estado).some(v=>!Number.isFinite(v)))throw new Error('Evaluación energética no finita.');
    return estado;
  }
  const estado0=evaluarEnergia(0,inicial);if(estado0.T<Tmin||estado0.T>Tmax)throw new Error('Estado inicial fuera del dominio térmico.');
  const derivadaT=(t:number,y:number[],dy:number[])=>{const x=evaluarEnergia(t,y);return (dy[indices.U]-u(x.T)*(materia?dy[indices.m]:0))/(x.m*cu);};
  const rhs=(t:number,y:number[])=>{const v=evaluarEnergia(t,y);return materia?[v.dm,v.dU]:[v.dU];};
  const catalogoSeries:Omit<SerieEvaluadaMotor,'valores'>[]=[{id:`m_${f.componentes![0].id}`,nombre:`Masa · ${f.componentes![0].nombre}`,unidad:'kg',grupo:'Materia'},{id:'U',nombre:'Energía interna almacenada',unidad:'J',grupo:'Energía'},{id:'T',nombre:'Temperatura',unidad:'K',grupo:'Estado'},{id:'Q',nombre:'Calor hacia el volumen',unidad:'W',grupo:'Energía'},{id:'Wb',nombre:'Trabajo de presión de la frontera',unidad:'W',grupo:'Energía'},{id:'dU',nombre:'Acumulación energética',unidad:'W',grupo:'Energía'},...(rho||geo?[{id:'V',nombre:geo?'Volumen geométrico fijo':'Volumen ocupado',unidad:'m3',grupo:'Estado'}]:[]),...ctx.puertos.flatMap(p=>[{id:`mdot_${p.id}`,nombre:`Caudal · corriente ${p.id}`,unidad:'kg/s',grupo:`Corriente ${p.id}`},{id:`h_${p.id}`,nombre:`Entalpía del donante · corriente ${p.id}`,unidad:'J/kg',grupo:`Corriente ${p.id}`},{id:`E_${p.id}`,nombre:`Energía hacia el volumen · corriente ${p.id}`,unidad:'W',grupo:`Corriente ${p.id}`}])];
  for(const [dato,id,nombre] of [['energia_Wtau','Wtau','Trabajo viscoso hacia el volumen'],['energia_Wb','Wf','Trabajo de fuerzas de volumen'],['energia_R','R','Aporte volumétrico integrado']])if(ast[dato])catalogoSeries.push({id,nombre,unidad:'W',grupo:'Energía'});
  return {modo:'temporal',unidadEstado:materia?'mixta':'J',inicial,x:[],dx:1,n:1,nc:inicial.length,tfinal:base.tfinal,rhs,balance:rhs,observacion:(_t,y)=>y.map(v=>[v]),limitePaso:base.limitePaso,variablesNumericas:[...(materia?[{id:`m_${f.componentes![0].id}`,propietarioId:ctx.volumenId,componenteId:f.componentes![0].id,magnitud:'masa',unidad:'kg',rol:'diferencial' as const,restriccion:'no_negativo' as const,toleranciaAbsoluta:h.config.atol}]:[]),{id:'U',propietarioId:ctx.volumenId,magnitud:'energia',unidad:'J',rol:'diferencial',restriccion:'libre',toleranciaAbsoluta:h.energia?.atol??1e-6}],eventos:[{id:'Tmin',nombre:'Límite térmico inferior',valor:(t,y)=>evaluarEnergia(t,y).T-Tmin,derivada:derivadaT},{id:'Tmax',nombre:'Límite térmico superior',valor:(t,y)=>Tmax-evaluarEnergia(t,y).T,derivada:(t,y,dy)=>-derivadaT(t,y,dy)}],evaluarEnergia,catalogoSeries,trazabilidad:{ecuacion:ecuacionEnergia(e,ctx),relaciones:[...new Set([...relacionesEnergia(e,ctx),...relacionesGeometria(h),...relacionesSistemaEnergia(h).map(r=>r.latex)])],terminos:terminos.map(t=>({id:t.id,unidad:t.unidad,signo:t.signo})),datosUsados:a.campos.map(p=>p.id),datosInactivos:Object.keys(c.datos).filter(id=>id.startsWith('energia_')&&!a.campos.some(p=>p.id===id)),estadoDeFase:'asumido_sin_verificar'}};
}
