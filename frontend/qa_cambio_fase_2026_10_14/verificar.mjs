// Replay audit of requests and responses exported from the visible UI.
// No flash, property correlation, integration or scenario-specific runtime code.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import ts from 'typescript';
const base=path.dirname(fileURLToPath(import.meta.url)),cache=new Map();
function cargar(nombre){
  if(cache.has(nombre))return cache.get(nombre);
  const m={exports:{}};cache.set(nombre,m.exports);
  const codigo=ts.transpileModule(fs.readFileSync(path.join(base,'../app/motor',nombre+'.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('exports','module','require',codigo)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;
}
const lector=cargar('lectorEnsamblajeTermodinamico'),unidades=cargar('unidadesMotor');
let comprobaciones=0;const comprobar=(v,msg)=>{comprobaciones++;assert.ok(v,msg);};
const max=valores=>Math.max(...valores.map(Math.abs));
function leer(nombre){const e=JSON.parse(fs.readFileSync(path.join(base,nombre),'utf8'));lector.validarResolucionEnsamblaje(e.respuesta,e.solicitud);comprobaciones++;return e;}
function auditar(e){
  const s=e.solicitud,r=e.respuesta,a=r.resultados,root=`volumen.${s.volumen.id}.`,series=Object.fromEntries(a.series.map(v=>[v.variableId,v.valores]));
  const dato=id=>{const d=s.datos[id];return unidades.convertirUnidad(d.magnitud,Number(d.declaracion.texto),d.declaracion.unidad);};
  const m0=Object.values(s.volumen.inicial.masaIds).reduce((n,id)=>n+dato(id),0),Q=dato(s.transferencias.calor),P=dato(s.volumen.frontera.presionId),tf=dato(s.estudio.tiempoId);
  comprobar(s.corrientes.length===0,'El caso conserva materia sin caudales artificiales');
  comprobar(s.volumen.frontera.tipo==='presion_prescrita','Frontera a presión prescrita');
  comprobar(!s.volumen.formulacionEnergia.densidadConstante&&!s.volumen.formulacionMateria.densidadMediaConstante,'Sin densidad constante encubierta');
  comprobar(s.volumen.cierre.modelo.id==='agua-iapws95'&&s.componentes[0].identidadQuimica.cas==='7732-18-5','Identidad y cierre explícitos');
  const S=k=>series[root+k],H0=S('H')[0],U0=S('U')[0],W0=S('W')[0];
  const errorH=max(a.tiempos.map((t,i)=>S('H')[i]-H0-Q*t));
  const errorUW=max(a.tiempos.map((t,i)=>S('U')[i]-U0+S('W')[i]-W0-Q*t));
  const escala=Math.max(1,...S('H').map(Math.abs));
  comprobar(errorH<1e-6,'Primera ley independiente: H(t)=H0+Qt');
  comprobar(errorUW<Math.max(100*s.estudio.atol.energia,100*s.estudio.rtol*escala),'Forma en U y trabajo integrado independiente: ΔU+W=Qt');
  comprobar(a.residuos.every(v=>v.maximoEscalado<=v.tolerancia),'Todos los residuos dentro de su tolerancia publicada');
  a.tiempos.forEach((t,i)=>{
    const estado=a.estadosTermodinamicos[i];
    comprobar(Math.abs(S('m.1')[i]-m0)<1e-12,'Masa conservada en cada muestra');
    comprobar(Math.abs(S('P')[i]-P)<1e-6,'Presión prescrita respetada');
    comprobar(Math.abs(S('H')[i]-S('U')[i]-P*S('V')[i])<1e-6,'H=U+PV');
    comprobar(estado.estabilidad.estado==='estable'&&estado.verificaciones.every(v=>['cumple','no_evaluable'].includes(v.estado)),'Sin certificado fallido');
    if(estado.fases.length===2){
      comprobar(estado.mezcla.cp==null&&estado.mezcla.cv==null,'Sin Cp/Cv monofásicos inventados para la mezcla bifásica');
      const liquido=estado.fases.find(f=>f.tipo==='liquido'),vapor=estado.fases.find(f=>f.tipo==='vapor'),q=vapor.fraccionMasica;
      comprobar(Math.abs(S('q')[i]-q)<1e-10,'La serie q es fracción másica de vapor');
      comprobar(Math.abs(estado.mezcla.h-((1-q)*liquido.propiedades.h+q*vapor.propiedades.h))<1e-6,'Regla de la palanca en entalpía');
      comprobar(Math.abs(vapor.fraccionVolumen-q*vapor.propiedades.v/estado.mezcla.v)<1e-10,'Fracción de volumen diferenciada de la másica');
    }
  });
  return {estado:r.estado,muestras:a.tiempos.length,tiempoFinal:a.tiempos.at(-1),horizonteSolicitado:tf,errorH_J:errorH,errorUW_J:errorUW,masaFinal_kg:S('m.1').at(-1),temperaturaFinal_K:S('T').at(-1),qFinal:S('q').at(-1),eventos:a.eventos.map(v=>({codigo:v.codigo,tiempo_s:v.tiempo}))};
}
const principal=leer('ebullicion-ui.json'),control=leer('cambio-prohibido-ui.json'),rapida=leer('potencia-doble-ui.json');
// Negative controls demonstrate that the independent balance audit catches
// inconsistent energy data/work even when point-state identities still hold.
const calorErroneo=structuredClone(principal);calorErroneo.solicitud.datos[calorErroneo.solicitud.transferencias.calor].declaracion.texto='20';
comprobaciones++;assert.throws(()=>auditar(calorErroneo),/Primera ley independiente/);
const trabajoErroneo=structuredClone(principal),serieTrabajo=trabajoErroneo.respuesta.resultados.series.find(v=>v.variableId.endsWith('.W'));
serieTrabajo.valores[serieTrabajo.valores.length-1]+=1000;
comprobaciones++;assert.throws(()=>auditar(trabajoErroneo),/Forma en U y trabajo/);
const mensaje=cargar('resultadoEnsamblaje').mensajeResultadoDinamico(control.respuesta);
comprobar(!mensaje.includes('cambioInterno')&&!mensaje.includes('33.'),'Aviso compacto sin nomenclatura interna ni tiempo duplicado');
comprobar(control.respuesta.validacion.diagnosticos[0].mensaje.includes('cambioInterno'),'Diagnóstico original conservado para inspección');
const resultado={principal:auditar(principal),cambioProhibido:auditar(control),potenciaDoble:auditar(rapida)};
const a=principal.respuesta.resultados,root=`volumen.${principal.solicitud.volumen.id}.`,S=id=>a.series.find(v=>v.variableId===root+id).valores;
const dos=a.estadosTermodinamicos.filter(e=>e.fases.length===2),sat=dos.find(e=>e.fases.every(f=>f.fraccionMasica>1e-5));
comprobar(!!sat&&dos.length>2,'Hay un tramo bifásico verificable');
const hl=sat.fases.find(f=>f.tipo==='liquido').propiedades.h,hv=sat.fases.find(f=>f.tipo==='vapor').propiedades.h;
// Event references use point-state saturation properties and the first law,
// independent of event localization and ODE stepping, not independent of the EOS.
const m=S('m.1')[0],Q=S('Q')[0],H0=S('H')[0],referencias=[m*hl-H0,m*hv-H0].map(H=>H/Q);
for(const [i,codigo]of ['aparicion_fase','desaparicion_fase'].entries()){
  const evento=a.eventos.find(e=>e.codigo===codigo);comprobar(!!evento&&Math.abs(evento.tiempo-referencias[i])<1e-5,'Tiempo de transición obtenido del balance, no del integrador');
  const rapido=rapida.respuesta.resultados.eventos.find(e=>e.codigo===codigo);comprobar(Math.abs(2*rapido.tiempo-evento.tiempo)<1e-5,'Duplicar Q divide por dos el tiempo de cada transición');
}
comprobar(max(dos.map(e=>e.T-sat.T))<1e-8,'Temperatura constante durante coexistencia');
comprobar(S('q')[0]===0&&S('q').at(-1)===1,'Desde líquido hasta vapor puro, sin q=0 para vapor sobrecalentado');
comprobar(principal.respuesta.estado==='resuelto'&&rapida.respuesta.estado==='resuelto','Las dos trayectorias permitidas llegan a tf');
comprobar(control.respuesta.estado==='parcial','Prohibir la transición detiene la trayectoria');
comprobar(Math.abs(control.respuesta.resultados.tiempos.at(-1)-referencias[0])<1e-5,'Detención en la primera transición');
comprobar(control.respuesta.validacion.diagnosticos.some(d=>d.codigo.startsWith('MOTOR_ENS_DETENIDO_')),'Detención diagnosticada');
const pc=structuredClone(principal.solicitud),cc=structuredClone(control.solicitud);
// Policy and derivation may differ; all numerical declarations must be identical.
comprobar(JSON.stringify(pc.datos)===JSON.stringify(cc.datos),'El control negativo conserva exactamente todos los datos');
comprobar(principal.solicitud.volumen.cierre.politica.cambioInterno==='permitido'&&control.solicitud.volumen.cierre.politica.cambioInterno==='prohibido','La restricción es explícita');
const b=rapida.respuesta.resultados;
for(const k of ['T','P','V','q','U','H']){
  const x=S(k).at(-1),y=b.series.find(v=>v.variableId===root+k).valores.at(-1);
  comprobar(Math.abs(x-y)<1e-7*Math.max(1,Math.abs(x)),`Misma energía aportada: mismo estado final ${k}`);
}
resultado.referenciaPrimeraLey={aparicion_s:referencias[0],desaparicion_s:referencias[1],Tsat_K:sat.T};
const rigida=leer('condensacion-rigida-ui.json'),ar=rigida.respuesta.resultados,rr=`volumen.${rigida.solicitud.volumen.id}.`,sr=Object.fromEntries(ar.series.map(v=>[v.variableId.slice(rr.length),v.valores]));
const qr=rigida.solicitud.datos[rigida.solicitud.transferencias.calor],Qrigida=unidades.convertirUnidad(qr.magnitud,Number(qr.declaracion.texto),qr.declaracion.unidad);
comprobar(rigida.respuesta.estado==='resuelto'&&rigida.solicitud.volumen.frontera.tipo==='rigida','La condensación rígida alcanza su horizonte');
comprobar(ar.estadosTermodinamicos[0].fases.length===1&&ar.estadosTermodinamicos[0].fases[0].tipo==='vapor','La fase inicial es un resultado: vapor');
comprobar(ar.estadosTermodinamicos.at(-1).fases.some(f=>f.tipo==='liquido'),'Aparece líquido al enfriar');
const errorUr=max(ar.tiempos.map((t,i)=>sr.U[i]-sr.U[0]-Qrigida*t));
comprobar(errorUr<1e-6,'Primera ley en recipiente rígido: ΔU=Qt');
comprobar(max(sr.V.map(v=>v-sr.V[0]))<1e-12&&max(sr['m.1'].map(m=>m-sr['m.1'][0]))<1e-12,'V y masa constantes');
comprobar(Math.abs(sr.P.at(-1)-sr.P[0])>1000,'La presión se calcula y cambia, no se impone');
comprobar(!sr.W,'Sin una serie ficticia de trabajo en volumen fijo');
comprobar(ar.residuos.every(v=>v.maximoEscalado<=v.tolerancia),'Residuos rígidos dentro de tolerancia');
resultado.condensacionRigida={estado:rigida.respuesta.estado,muestras:ar.tiempos.length,errorU_J:errorUr,T_inicial_K:sr.T[0],T_final_K:sr.T.at(-1),P_inicial_Pa:sr.P[0],P_final_Pa:sr.P.at(-1),q_final:sr.q.at(-1),eventos:ar.eventos};

const abierta=leer('salida-liquido-ui.json'),as=abierta.respuesta.resultados,ro=`volumen.${abierta.solicitud.volumen.id}.`,so=Object.fromEntries(as.series.map(v=>[v.variableId.startsWith(ro)?v.variableId.slice(ro.length):v.variableId,v.valores]));
const corriente=abierta.solicitud.corrientes[0],F=so[`corriente.${corriente.id}.F`][0],qDato=abierta.solicitud.datos[abierta.solicitud.transferencias.calor],Qo=unidades.convertirUnidad(qDato.magnitud,Number(qDato.declaracion.texto),qDato.declaracion.unidad),mo=so['m.1'][0],ho=so.H[0]/mo;
comprobar(abierta.respuesta.estado==='resuelto'&&abierta.solicitud.corrientes.length===1&&F>0,'Sistema abierto con salida positiva');
comprobar(corriente.extraccion.tipo==='fase'&&corriente.extraccion.fase==='liquido','La extracción de líquido está declarada');
const punto=as.estadosTermodinamicos.find(e=>e.fases.length===2),hl_o=punto.fases.find(f=>f.tipo==='liquido').propiedades.h,hv_o=punto.fases.find(f=>f.tipo==='vapor').propiedades.h;
// m dh/dt=Q before boiling; after boiling H=m h_l+Q(t-t_b).
// This uses no heat capacity approximation and no numerical integration.
const tb=mo/F*(1-Math.exp(-F*(hl_o-ho)/Qo));
const Href=t=>{const m=mo-F*t;return t<tb?m*(ho+Qo/F*Math.log(mo/m)):m*hl_o+Qo*(t-tb);};
const errorHo=max(as.tiempos.map((t,i)=>so.H[i]-Href(t))),errorMo=max(as.tiempos.map((t,i)=>so['m.1'][i]-(mo-F*t)));
comprobar(errorMo<1e-10,'Masa abierta: m=m0-Ft');
comprobar(errorHo<20*abierta.solicitud.estudio.rtol*Math.max(...so.H.map(Math.abs)),'Referencia analítica independiente para H con cantidad variable');
as.tiempos.forEach((t,i)=>{if(t>tb+1e-5){
  comprobar(Math.abs(so.q[i]-Qo*(t-tb)/((hv_o-hl_o)*(mo-F*t)))<1e-7,'Calor latente y extracción con masa variable');
  comprobar(Math.abs(so[`corriente.${corriente.id}.h`][i]-hl_o)<1e-5,'Sale h del líquido, no h de la mezcla');
}});
comprobar(Math.abs(as.eventos.find(e=>e.codigo==='aparicion_fase').tiempo-tb)<1e-5,'Evento abierto frente al balance analítico');
comprobar(as.residuos.every(v=>v.maximoEscalado<=v.tolerancia),'Residuos abiertos dentro de tolerancia');
resultado.salidaLiquido={estado:abierta.respuesta.estado,muestras:as.tiempos.length,errorM_kg:errorMo,errorH_J:errorHo,masaFinal_kg:so['m.1'].at(-1),qFinal:so.q.at(-1),aparicionReferencia_s:tb,eventos:as.eventos};
resultado.comprobaciones=comprobaciones;
fs.writeFileSync(path.join(base,'evidencias.json'),JSON.stringify(resultado,null,2)+'\n');
console.log(JSON.stringify(resultado,null,2));
