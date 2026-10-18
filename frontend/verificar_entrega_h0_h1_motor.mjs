// Real endpoint fixtures supplied by Claude. No numerical values are manufactured here.
import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const c=cargar('contratoTermodinamica'),estado=cargar('estadoTermodinamicoHoja'),modelo=cargar('modeloHojaMotor');
const dir='../docs/ejemplos',leer=n=>JSON.parse(fs.readFileSync(`${dir}/${n}`,'utf8'));
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=(fn,m)=>{checks++;assert.throws(fn,undefined,m);};
const capacidades=c.validarCapacidadesEstado(leer('motor-termodinamica-capacidades.json'));
check(capacidades.modelos.some(m=>m.id==='agua-iapws95'&&m.version==='1'&&!m.dinamica),'H1 publica consulta, sin dinámica');
for(const n of fs.readdirSync(dir).filter(n=>/^motor-termodinamica-.*-peticion\.json$/.test(n))){
  const s=leer(n),r=leer(n.replace('-peticion','-respuesta')),cap=capacidades.modelos.find(m=>m.id===s.declaracion.modelo.id&&m.version===s.declaracion.modelo.version&&m.especificaciones.includes(s.declaracion.especificacion.tipo));
  check(c.validarRespuestaEstado(r,s,cap)===r,`${n}: respuesta real compatible`);
  if(r.estado==='evaluado')check(!c.analizarSolicitudEstado(s).length,`${n}: datos completos`);
  else check(r.evaluacion===null&&r.diagnosticos.length>0,`${n}: rechazo sin propiedades antiguas`);
}
const s=leer('motor-termodinamica-liquido-25C-1bar-peticion.json'),r=leer('motor-termodinamica-liquido-25C-1bar-respuesta.json'),cap=capacidades.modelos[0];
check(!s.componentes[0].masaMolar,'La consulta no impone una masa molar redondeada');
for(const M of [.018,.018015,.018015268*2,1]){const falso=structuredClone(r);falso.evaluacion.componentes[0].masaMolarKgMol=M;rechaza(()=>c.validarRespuestaEstado(falso,s,cap),'Masa molar falsa aun sin dato declarado');rechaza(()=>c.validarRespuestaEstado(falso,s),'Misma guarda al leer resultados guardados sin catálogo');}
const redondeado=structuredClone(s);redondeado.componentes[0].masaMolar={cantidad:{valor:18.015,unidad:'g/mol'},fuente:'Dato del usuario'};
rechaza(()=>c.validarRespuestaEstado(r,redondeado,cap),'No borra una masa molar declarada contradictoria para aceptar el estado');
const exacto=structuredClone(s);exacto.componentes[0].masaMolar={cantidad:{valor:18.015268,unidad:'g/mol'},fuente:'IAPWS'};
check(c.validarRespuestaEstado(r,exacto,cap)===r,'Masa molar declarada coherente');
const casFalso=structuredClone(r);casFalso.evaluacion.componentes[0].cas='71-43-2';rechaza(()=>c.validarRespuestaEstado(casFalso,s,cap),'Identidad química distinta');
const base=cargar('hojasPruebaEnergia').crearHojasPruebaEnergia()[0],h=estado.identificarComponenteEstado(base,1,'7732-18-5');
const consulta=estado.guardarDeclaracionEstado(h,'volumen:dominio',s.declaracion),solicitud=estado.solicitudEstadoHoja(consulta,'volumen:dominio','qa-h1');
const respuesta={...r,solicitudId:solicitud.solicitudId},guardada=estado.guardarEvaluacionEstado(consulta,solicitud,respuesta);
check(estado.evaluacionVigente(guardada,'volumen:dominio')?.estado==='evaluado','Estado real guardado por propietario');
check(modelo.firmaHoja(guardada)===modelo.firmaHoja(consulta),'Estado puntual no cambia identidad dinámica');
const antes=await modelo.resolverHoja(consulta),despues=await modelo.resolverHoja(guardada);check(JSON.stringify(antes.valores)===JSON.stringify(despues.valores),'Propiedades reales consultadas no sustituyen u(T) manual');
const alterada=structuredClone(guardada);alterada.termodinamica.estados['volumen:dominio'].resultado.respuesta.evaluacion.componentes[0].masaMolarKgMol=.018;
check(!estado.evaluacionVigente(alterada,'volumen:dominio'),'Una masa molar falsa guardada tampoco se muestra como vigente');
const cambiada=estado.guardarDeclaracionEstado(guardada,'volumen:dominio',{...s.declaracion,especificacion:{...s.declaracion.especificacion,T:{valor:30,unidad:'degC'}}});check(!estado.evaluacionVigente(cambiada,'volumen:dominio'),'Cambio de dato invalida estado anterior');
console.log(`${checks} comprobaciones H0/H1: respuestas reales, masa molar por modelo, persistencia y separación del cierre dinámico.`);
