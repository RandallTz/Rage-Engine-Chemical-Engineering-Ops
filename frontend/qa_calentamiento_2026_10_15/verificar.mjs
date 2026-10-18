// Audit of the unmodified response exported from the actual worksheet UI.
// First-law and geometry checks, not an independent equation of state.
import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){
  if(cache.has(n))return cache.get(n);
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));
  return m.exports;
}
const {solicitud:s,respuesta:r}=JSON.parse(fs.readFileSync(new URL('respuesta-ui.json',import.meta.url),'utf8'));
cargar('lectorEnsamblajeTermodinamico').validarResolucionEnsamblaje(r,s);
let checks=1;
const check=(c,m)=>{checks++;assert.ok(c,m);};
check(r.estado==='resuelto','Trayectoria completa');
check(s.volumen.frontera.tipo==='rigida'&&s.corrientes.length===0,'Sistema cerrado, rígido');
check(s.volumen.cierre.modelo.id==='agua-iapws95','Cierre real seleccionado');
const a=r.resultados,serie=id=>a.series.find(q=>q.variableId===`volumen.dominio.${id}`).valores;
const m=serie('m.1'),U=serie('U'),T=serie('T'),P=serie('P'),V=serie('V'),q=serie('q'),Q=serie('Q');
check(Math.abs(T[0]-283.15)<1e-7&&Math.abs(T.at(-1)-473.15)<1e-7,'10 °C → 200 °C');
check(q[0]>0&&q[0]<.002&&q.at(-1)===1,'Inicial casi toda la masa líquida y final todo vapor');
let errorEnergia=0;
for(let k=0;k<a.tiempos.length;k++){
  check(m[k]===1&&Math.abs(V[k]-.2)<1e-12,'Masa y volumen constantes');
  check(Q[k]===2000,'Aporte constante de 2 kW');
  const error=Math.abs(U[k]-U[0]-2000*a.tiempos[k]);errorEnergia=Math.max(errorEnergia,error);
  check(error<1e-6,'U = U0 + Q t, sin trabajo de frontera');
  if(k)check(T[k]>T[k-1]&&P[k]>P[k-1],'T y P crecen durante esta trayectoria');
}
const e=a.eventos.find(e=>e.codigo==='desaparicion_fase');
check(e&&Math.abs(e.tiempo-1267.73004738544)<1e-3,'Evento frente a U de vapor saturado con v=0.2 m3/kg');
const k=a.tiempos.findIndex(t=>Math.abs(t-e.tiempo)<1e-9);
check(k>=0&&Math.abs(T[k]-451.72923715926046)<1e-5&&q[k]===1,'Muestra del evento y desaparición del líquido');
check(Math.abs(P.at(-1)-1028167.8387101918)<.01,'Estado final frente a la evaluación puntual TV');
const resumen={hojaId:'f8346222-26e0-4658-bfa0-45c6ee2832f2',estado:r.estado,muestras:a.tiempos.length,
  inicial:{T_C:T[0]-273.15,P_bar_absoluta:P[0]/1e5,fraccionMasicaVapor:q[0]},
  desaparicionLiquido:{t_s:e.tiempo,T_C:T[k]-273.15,P_bar_absoluta:P[k]/1e5},
  final:{t_s:a.tiempos.at(-1),T_C:T.at(-1)-273.15,P_bar_absoluta:P.at(-1)/1e5,fraccionMasicaVapor:q.at(-1)},
  errorEnergia_J:errorEnergia,comprobaciones:checks};
fs.writeFileSync(new URL('evidencias.json',import.meta.url),JSON.stringify(resumen,null,2)+'\n');
console.log(JSON.stringify(resumen,null,2));
