import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';import katex from 'katex';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));cache.set(n,m.exports);return m.exports;}
const red=cargar('ensamblajeMateria'),hoja=cargar('modeloHojaMotor'),ejemplos=cargar('hojasPruebaAcoplamiento');let checks=0;
const check=(v,m)=>{checks++;assert.ok(v,m);};const cerca=(x,y,tol,m)=>check(Math.abs(x-y)<tol,`${m}: ${x} / ${y}`);
const casos=ejemplos.crearHojasPruebaAcoplamiento();
for(const [i,h] of casos.entries()){
  const p=red.planEnsamblaje(h.ensamblaje,h.config);check(p.analisis.listo,h.nombre+': '+JSON.stringify(p.analisis));check(p.analisis.gl===0,h.nombre+' GL');check(p.estados.length===p.especies.length*h.ensamblaje.volumenes.length,'N balances por cada volumen');
  h.ensamblaje.corrientes.forEach((s,j)=>{if(s.desde&&s.hasta)cerca(p.incidencia.reduce((a,r)=>a+r[j],0),0,1e-30,'Cancelación estructural interna');});
  const r=await hoja.resolverHoja(h);check(r.estado==='resuelto',h.nombre+': '+r.mensaje);r.conservacionGlobal.forEach(q=>cerca(q.residuo,0,1e-9,'Conservación global con presupuesto externo'));
  for(const [k,t] of r.tiempos.entries()){
    const y=r.valores[k].map(v=>v[0]);let exacto;
    if(i===0)exacto=[100+t,200+t];
    if(i===1){const z=.1*t;exacto=[Math.exp(-z),z*Math.exp(-z),z*z/2*Math.exp(-z)];}
    if(i===2)exacto=[100,20+.5*t,30+.5*t,40];
    if(i===3){const z=Math.sqrt(3)*.2*t/2,at=2*Math.exp(-3*.2*t/2);exacto=[1+at*Math.cos(z),1+at*Math.cos(z-2*Math.PI/3),1+at*Math.cos(z+2*Math.PI/3)];}
    if(i===4){const z=Math.exp(-.4*t);exacto=[(1+z)/2,2,(1-z)/2,3];}
    if(i===5){const a=Math.exp(-.3*t),b=Math.exp(-.2*t)*(1-Math.exp(-.1*t)),a2=2/3*(1-a);exacto=[a,b,a2,1-a-b-a2];}
    exacto.forEach((v,j)=>cerca(y[j],v,2e-8,h.nombre+' analítica'));check(y.every(v=>v>=0),'No publicar masa negativa');
  }
  console.log(`${h.nombre}: ${r.valores.at(-1).map(v=>v[0].toPrecision(9)).join(' / ')} kg; ${r.pasos} pasos.`);
}
// Signed exchange, nonlinear laws, expression dependencies and implicit cross-volume Jacobian.
const selectivo=structuredClone(casos[4]);selectivo.ensamblaje.corrientes[0].desde='v2';selectivo.ensamblaje.corrientes[0].hasta='v1';selectivo.config.datos.s1__c1.texto='0.2*(m_A_v2-m_A_v1)';
const r1=await hoja.resolverHoja(casos[4]),r2=await hoja.resolverHoja(selectivo);r1.valores.forEach((v,k)=>v.forEach((a,j)=>cerca(a[0],r2.valores[k][j][0],1e-12,'Invertir orientación y ley conserva la física')));
const implicito=structuredClone(casos[3]);implicito.config.metodo='euler_implicito';implicito.config.rtol=1e-7;const ri=await hoja.resolverHoja(implicito);check(ri.estado==='resuelto','Newton acopla tres volúmenes');ri.valores.at(-1).forEach(v=>cerca(v[0],1,0.008,'Equilibrio del ciclo'));cerca(ri.valores.at(-1).reduce((s,v)=>s+v[0],0),3,1e-9,'Masa del ciclo implícito');
const noLineal=structuredClone(casos[0]);noLineal.ensamblaje.corrientes=[{id:2,nombre:'Transferencia',desde:'v1',hasta:'v2',constante:false}];noLineal.config.datos={v1__inicial_1:{texto:'1',unidad:'kg'},v2__inicial_1:{texto:'0',unidad:'kg'},s2__c1:{texto:'0.1*m_A_v1^2',unidad:'kg/s'}};noLineal.config.tiempo={texto:'10',unidad:'s'};const rn=await hoja.resolverHoja(noLineal);cerca(rn.valores.at(-1)[0][0],.5,1e-8,'Acoplamiento no lineal');cerca(rn.valores.at(-1)[1][0],.5,1e-8,'Receptor no lineal');
const incompleto=structuredClone(casos[0]);delete incompleto.config.datos.s2__c1;const a=hoja.analizarHoja(incompleto);check(a.gl===1&&a.pendientes.filter(x=>x==='s2__c1').length===1,'Corriente compartida cuenta una sola vez');
const colgante=structuredClone(casos[0]);colgante.ensamblaje.corrientes[0].hasta='v999';check(!hoja.analizarHoja(colgante).listo,'Rechazar volumen inexistente');
const conflicto=structuredClone(casos[0]);conflicto.ensamblaje.corrientes[1].id=1;check(!hoja.analizarHoja(conflicto).listo,'Rechazar identidad de corriente duplicada');
check(hoja.firmaHoja({...casos[0],volumenActivo:'v2'})===hoja.firmaHoja(casos[0]),'Seleccionar volumen no cambia la física');
const graf=cargar('datosGraficasMotor');
const rg=await hoja.resolverHoja(casos[5]),tabla=graf.datosGraficasMotor(casos[5],rg,'tiempo');
check(new Set(tabla.variables.map(v=>v.id)).size===tabla.variables.length,'Catálogo de gráficos sin identidades duplicadas');
tabla.filas.forEach((v,k)=>{cerca(v.m_v1_c1,rg.valores[k][0][0],1e-14,'Gráfica usa el estado del volumen correcto');cerca(v.dato_s1__c1,.2*v.m_v1_c1,1e-14,'Gráfica usa la misma corriente del ensamblaje');});
for(const h of casos)red.ecuacionesEnsamblaje(h.ensamblaje).forEach(v=>v.ecuaciones.forEach(q=>check(!katex.renderToString(q.latex,{throwOnError:true}).includes('katex-error'),'Ecuación acoplada renderizable')));
red.ecuacionesEnsamblaje(casos[0].ensamblaje).forEach(v=>check(v.ecuaciones[0].latex.includes('s2'),'Misma identidad de corriente en ambas ecuaciones'));
// Reverse node order and units: physics cannot depend on presentation or the choice of units.
const permutado=structuredClone(casos[4]);permutado.ensamblaje.volumenes.reverse();permutado.ensamblaje.volumenes[0].historial.pasos.at(-1).formulacion.componentes.reverse();
const ro=await hoja.resolverHoja(permutado);for(const z of r1.estadosAcoplados){const i=r1.estadosAcoplados.findIndex(v=>v.id===z.id),j=ro.estadosAcoplados.findIndex(v=>v.id===z.id);r1.valores.forEach((v,k)=>cerca(v[i][0],ro.valores[k][j][0],1e-10,'Orden de nodos y especies no cambia el estado'));}
const unidades=structuredClone(casos[0]);unidades.config.datos.s1__c1={texto:'10800',unidad:'kg/h'};unidades.config.datos.v2__inicial_1={texto:'200000',unidad:'g'};unidades.config.tiempo={texto:'600',unidad:'s'};
const ru=await hoja.resolverHoja(unidades),rc=await hoja.resolverHoja(casos[0]);check(JSON.stringify(ru.valores)===JSON.stringify(rc.valores),'Unidades equivalentes en la red dan la misma trayectoria');
// Local source times a declared volume, with independent units and no default geometry.
const fuente=structuredClone(casos[0]);fuente.ensamblaje.corrientes=[];fuente.config.datos={v1__inicial_1:{texto:'0',unidad:'kg'},v2__inicial_1:{texto:'2',unidad:'kg'},v1__volumen:{texto:'1000',unidad:'L'},v1__generacion_1:{texto:'2',unidad:'kg/(m3 s)'},v1__consumo_1:{texto:'0',unidad:'kg/s'}};fuente.config.tiempo={texto:'3',unidad:'s'};
let hv=fuente.ensamblaje.volumenes[0].historial;hv=cargar('recorridoMateria').recorridoMateria(hv,{tipo:'cambiar',titulo:'Fuente uniforme',cambios:{fija:true,generacionUniforme:true,campo:{...hv.pasos[hv.activo].formulacion.campo,sinReaccion:false}}});fuente.ensamblaje.volumenes[0].historial=hv;
const rf=await hoja.resolverHoja(fuente);cerca(rf.valores.at(-1)[0][0],6,1e-9,'Gamma por volumen, sin doble conteo');cerca(rf.valores.at(-1)[1][0],2,1e-9,'Otro volumen no cambia');
const faltaVolumen=structuredClone(fuente);delete faltaVolumen.config.datos.v1__volumen;check(hoja.analizarHoja(faltaVolumen).gl===1,'Propiedad de volumen faltante no sustituida por uno');
// Closed concentration-driven exchange: the geometric data enter only when declared.
const conc=structuredClone(noLineal);conc.ensamblaje.volumenes.forEach(v=>v.volumenDeclarado=true);conc.config.datos.v1__volumen={texto:'1',unidad:'m3'};conc.config.datos.v2__volumen={texto:'2',unidad:'m3'};conc.config.datos.s2__c1.texto='0.1*(rho_A_v1-rho_A_v2)';
const rq=await hoja.resolverHoja(conc);const esperado=1/3+2/3*Math.exp(-.15*10);cerca(rq.valores.at(-1)[0][0],esperado,1e-8,'Ley sobre concentraciones en distintos volúmenes');
const gq=graf.datosGraficasMotor(conc,rq,'tiempo');cerca(gq.filas.at(-1).rho_A_v2,rq.valores.at(-1)[1][0]/2,1e-14,'Densidad calculada del volumen correcto');
// Emptying one donor stops the entire coupled integration, without fabricating a continued solution.
const evento=structuredClone(noLineal);evento.config.datos.s2__c1={texto:'2',unidad:'kg/s'};const re=await hoja.resolverHoja(evento);check(re.estado==='parcial','Agotamiento conjunto');cerca(re.tiempos.at(-1),.5,1e-9,'Instante de vaciado del donante');cerca(re.valores.at(-1)[1][0],1,1e-9,'Receptor al agotarse el donante');
// A loop from a volume to itself has exactly zero incidence, even for a large circulation.
const propio=structuredClone(noLineal);propio.ensamblaje.corrientes[0].hasta='v1';propio.config.datos.s2__c1={texto:'1e30',unidad:'kg/s'};const rpropio=await hoja.resolverHoja(propio);cerca(rpropio.valores.at(-1)[0][0],1,1e-14,'La autocirculación no crea acumulación');
// Migration keeps each datum, and rewrites the former local flow aliases explicitly.
const hist=structuredClone(casos[0].ensamblaje.volumenes[0].historial);hist.pasos.at(-1).formulacion.fronteras.forEach(p=>p.constante=false);
const migr=red.iniciarEnsamblaje(hist,{...casos[0].config,datos:{inicial_1:{texto:'10',unidad:'kg'},entrada_1_1:{texto:'3',unidad:'kg/s'},salida_1_2:{texto:'0.1*m','unidad':'kg/s'}}});
check(migr.config.datos.s2__c1.texto==='0.1*m_A_v1','Migrar alias local de la salida a identidad de volumen');
check(red.agregarVolumen(casos[0].ensamblaje).volumenes.at(-1).historial.pasos.at(-1).formulacion.vista==='campo','Un volumen nuevo no hereda un escenario ni corrientes');
console.log(`Acoplamiento de materia: ${checks} comprobaciones. Incidencia genérica, cadenas, ramas, ciclos, especies, reacción, no linealidad y métodos conjuntos.`);
