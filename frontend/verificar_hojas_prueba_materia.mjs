import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(nombre){if(cache.has(nombre))return cache.get(nombre);const m={exports:{}};new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${nombre}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));cache.set(nombre,m.exports);return m.exports;}
const {crearHojasPruebaMateria}=cargar('hojasPruebaMateria'),{analizarMotor}=cargar('modeloNumerico'),{resolverMotor}=cargar('integracionMotor'),alm=cargar('hojasMotor');
let comprobaciones=0;const comprobar=(v,m)=>{comprobaciones++;assert.ok(v,m);};
const cerca=(x,y,tol,m)=>comprobar(Math.abs(x-y)<=tol,m+`: ${x} frente a ${y}`);
const hojas=crearHojasPruebaMateria(),evidencias=[];
comprobar(hojas.length===8&&new Set(hojas.map(h=>h.id)).size===8,'Ocho documentos distintos');
for(const [i,h] of hojas.entries()){
  const f=h.historial.pasos[h.historial.activo].formulacion,a=analizarMotor(f,h.config);
  comprobar(a.listo&&a.gl===0&&a.inicialesPendientes===0,h.nombre+': completa sin editar');
  comprobar(!h.resultado&&!h.resultadoRef,h.nombre+': no contiene resultado fabricado o preejecutado');
  comprobar(a.campos.length===Object.keys(h.config.datos).length,h.nombre+': cada dato pertenece a la ecuación vigente');
  const r=await resolverMotor(f,h.config);
  comprobar(r.estado===(i===4?'parcial':'resuelto'),h.nombre+': estado correcto '+r.mensaje);
  comprobar(r.valores.every(v=>v.flat().every(z=>Number.isFinite(z)&&z>=0)),h.nombre+': trayectoria física publicada');
  r.conservacion.forEach(v=>cerca(v,0,1e-9,h.nombre+': cierre del presupuesto'));
  let error=0;
  r.tiempos.forEach((t,k)=>{
    const y=r.valores[k];
    if(i<5){const exacto=i===0?100+t:i===1?100-2*t:i===2?.1+.002*t:i===3?100:100-2*t;error=Math.max(error,Math.abs(y[0][0]-exacto));cerca(y[0][0],exacto,1e-8,h.nombre+': analítica temporal');}
    if(i===5){const A=Math.exp(-.2*t);error=Math.max(error,Math.abs(y[0][0]-A),Math.abs(y[1][0]-(1-A)));cerca(y[0][0],A,2e-8,'A contra la exponencial');cerca(y[1][0],1-A,2e-8,'B contra la exponencial');cerca(y[0][0]+y[1][0],1,1e-10,'Conservación de masa entre especies');}
    if(i===6){const l1=r.x.reduce((s,x,j)=>s+Math.abs(y[0][j]-(2+.3*Math.sin(2*Math.PI*(x-t)))),0)/r.x.length;error=Math.max(error,l1);comprobar(l1<.012,'Error espacial de advección a 80 celdas');cerca(y[0].reduce((s,v)=>s+v,0)*r.dx,2,1e-10,'Masa por área conservada en advección');}
    if(i===7){const amplitud=.1*Math.exp(-4*Math.PI**2*.05*t);let e=0;for(const [j,x] of r.x.entries()){e=Math.max(e,Math.abs(y[0][j]-(.5+amplitud*Math.sin(2*Math.PI*x))));cerca(y[0][j]+y[1][j],1,1e-10,'La densidad de mezcla se conserva');}error=Math.max(error,e);comprobar(e<3e-5,'Difusión frente a la solución continua, incluido error espacial');}
  });
  if(i===4)cerca(r.tiempos.at(-1),50,1e-8,'Vaciado exacto a los 50 s');
  evidencias.push({nombre:h.nombre,estado:r.estado,tiempo_final_s:r.tiempos.at(-1),ultimo_estado:r.modo==='temporal'?r.valores.at(-1).map(v=>v[0]):null,error_referencia:error,residuo_presupuesto:r.conservacion});
}
const memoria=new Map();globalThis.window=new EventTarget();globalThis.localStorage={getItem:k=>memoria.get(k)??null,setItem:(k,v)=>memoria.set(k,String(v))};
const propia=alm.nuevaHoja('Hoja del usuario');alm.guardarHoja(propia);
comprobar(alm.guardarHojasNuevas(hojas)===8,'Creación de las ocho hojas en un solo guardado');
comprobar(alm.leerHojas().find(h=>h.id===propia.id).nombre==='Hoja del usuario','Se conserva la hoja del usuario');
const primera=alm.leerHojas().find(h=>h.id===hojas[0].id);alm.guardarHoja({...primera,nombre:'Mi variante',archivada:true});
comprobar(alm.guardarHojasNuevas(crearHojasPruebaMateria())===0,'No se crean duplicados al repetir');
const intacta=alm.leerHojas().find(h=>h.id===primera.id);comprobar(intacta.nombre==='Mi variante'&&intacta.archivada,'No sobrescribir ni desarchivar variantes del usuario');
const otraTanda=crearHojasPruebaMateria();otraTanda[0].config.datos.inicial_1.texto='999';comprobar(hojas[0].config.datos.inicial_1.texto==='100','Las copias son independientes');
delete globalThis.window;delete globalThis.localStorage;
console.log(`Hojas de prueba de materia: ${comprobaciones} comprobaciones. Ocho hojas completas, referencias analíticas, conservación, agotamiento y guardado sin sobrescribir documentos.`);
console.log(JSON.stringify(evidencias,null,2));
