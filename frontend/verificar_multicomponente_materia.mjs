import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import katex from 'katex';
const cache=new Map();
function cargar(n){
  if(cache.has(n))return cache.get(n);
  const m={exports:{}};
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));
  cache.set(n,m.exports);return m.exports;
}
const red=cargar('ensamblajeMateria'),hoja=cargar('modeloHojaMotor'),graficas=cargar('datosGraficasMotor'),tablero=cargar('graficasInicialesEnsamblaje');
const casos=cargar('hojasPruebaAcoplamiento').crearHojasPruebaMulticomponente();
let checks=0;
const check=(v,m)=>{checks++;assert.ok(v,m);};
const cerca=(x,y,tol,m)=>check(Number.isFinite(x)&&Math.abs(x-y)<=tol,`${m}: ${x} / ${y}`);
const inicialTrazas=[1,2,3,4,.01,1e-4,1e-6,1e-8];
function referencia(i,t){
  if(i===0)return [10+2*t,20+1.5*t,30+.75*t,40+.75*t,50+.25*t,60];
  if(i===1){const a=1+2*Math.exp(-.45*t),b=2-2*Math.exp(-.15*t);return [a,b,2,1,3-a,6-b,4,2];}
  if(i===2){const a=Math.exp(-.1*t),b=.1*t*a,c=1-a-b,w=[Math.exp(-.2*t),.2*t*Math.exp(-.2*t),1-(1+.2*t)*Math.exp(-.2*t)];return w.flatMap(x=>[x*a,x*b,x*c,2*x]);}
  return [0,1].flatMap(v=>inicialTrazas.map((m,j)=>m/2*(1+(v===0?1:-1)*Math.exp(-2*(.1+.05*j)*t))));
}
const resultados=[];
for(const [i,h] of casos.entries()){
  const p=red.planEnsamblaje(h.ensamblaje,h.config),nv=h.ensamblaje.volumenes.length,nc=p.especies.length;
  check(p.analisis.listo,`${h.nombre}: ${JSON.stringify(p.analisis)}`);
  check(p.analisis.gl===0&&p.analisis.inicialesPendientes===0,'Todos los datos listos');
  check(p.analisis.ecuaciones===nv*nc&&p.estados.length===nv*nc,'Un balance y estado por componente y volumen');
  for(const s of h.ensamblaje.corrientes)for(const c of p.especies)check(p.analisis.campos.filter(d=>d.id===red.claveCorriente(s.id,c.id)).length===1,'Una sola variable por corriente y componente');
  for(const v of red.ecuacionesEnsamblaje(h.ensamblaje)){
    check(v.ecuaciones.length===nc,'Todas las ecuaciones por volumen');
    for(const q of v.ecuaciones)check(!katex.renderToString(q.latex,{throwOnError:true}).includes('katex-error'),'Renderizado de cada balance con KaTeX');
  }
  const r=await hoja.resolverHoja(h);resultados.push(r);
  check(r.estado==='resuelto',`${h.nombre}: ${r.mensaje}`);
  check(r.estadosAcoplados.length===nc*nv,'Resultados de todos los estados');
  for(const [k,t] of r.tiempos.entries()){
    const esperado=referencia(i,t),y=r.valores[k].map(v=>v[0]);
    y.forEach((v,j)=>cerca(v,esperado[j],i===3?inicialTrazas[j%8]*3e-7:4e-8,`${h.nombre}, t=${t}, estado ${j}`));
    check(y.every(v=>v>=0),'Sin masa negativa');
    if(i===2)cerca(y.reduce((a,b)=>a+b,0),3,1e-9,'Conversión másica e inerte: conservación total');
  }
  r.conservacionGlobal.forEach(q=>cerca(q.residuo,0,1e-9,'Presupuesto global por componente'));
  const d=graficas.datosGraficasMotor(h,r,'tiempo'),catalogo=new Set(d.variables.map(v=>v.id));
  check(catalogo.size===d.variables.length,'Catálogo único');
  for(const [j,z] of r.estadosAcoplados.entries()){
    check(catalogo.has(`m_${z.id}`),'Cada componente visible en catálogo y tabla');
    d.filas.forEach((fila,k)=>cerca(fila[`m_${z.id}`],r.valores[k][j][0],1e-30,'Gráficas y tabla usan la misma serie'));
  }
  for(const [k,fila] of d.filas.entries())for(const c of p.especies){
    const total=r.estadosAcoplados.reduce((s,z,j)=>s+(z.componenteId===c.id?r.valores[k][j][0]:0),0);
    cerca(fila[`m_global_${c.id}`],total,1e-30,'Total por componente en catálogo');
  }
  if(i===1)d.filas.forEach(f=>{
    cerca(f.dato_s1__c1,.3*(f.rho_A_v1-f.rho_A_v2),1e-14,'Corriente A representada con su ley');
    cerca(f.dato_s1__c2,.1*(f.rho_B_v1-f.rho_B_v2),1e-14,'Corriente B representada con su ley y signo contrario');
    cerca(f.dato_s1__c3,0,1e-14,'C no cruza con fuerza nula');
    cerca(f.dato_s1__c4,0,1e-30,'D no cruza por su ley');
  });
  const plots=h.tableroIniciado?h.graficas:tablero.graficasInicialesEnsamblaje(r),seleccion=plots.flatMap(g=>g.y);
  check(seleccion.length===nv*nc&&new Set(seleccion).size===nv*nc,'Gráficas iniciales muestran todos los estados una vez');
  check(plots.every(g=>g.y.length<=4),'Hasta cuatro curvas por gráfica');
  check(seleccion.every(id=>catalogo.has(id)),'Todas las curvas iniciales existen en el catálogo');
  if(i===3)for(const g of plots)check(g.y.length===2&&g.y[0].split('_c')[1]===g.y[1].split('_c')[1],'Trazas comparadas por componente, con una escala propia');
  const pendiente=structuredClone(h);delete pendiente.config.datos.s1__c1;
  check(hoja.analizarHoja(pendiente).gl===1,'Dato compartido ausente cuenta una vez');
  console.log(`${nc} componentes · ${nv} volúmenes · ${nv*nc} balances · ${plots.length} gráficas: ${h.nombre}`);
}
// Eight-component laws, equations and output labels follow identities after reordering.
const permutado=structuredClone(casos[3]);permutado.ensamblaje.volumenes.reverse();
for(const v of permutado.ensamblaje.volumenes)v.historial.pasos[v.historial.activo].formulacion.componentes.reverse();
const rp=await hoja.resolverHoja(permutado),r8=resultados[3];check(rp.estado==='resuelto','Ocho especies reordenadas resuelven');
for(const [j,z] of r8.estadosAcoplados.entries()){
  const jp=rp.estadosAcoplados.findIndex(v=>v.id===z.id);
  check(jp>=0,'Identidades preservadas');
  r8.valores.forEach((v,k)=>cerca(v[j][0],rp.valores[k][jp][0],inicialTrazas[z.componenteId-1]*1e-12,'El orden no altera la física ni los resultados'));
}
check(new Set(casos.map(h=>h.id)).size===4,'Identidades de ejemplos distintas y persistentes');
const formato=cargar('formatearNumeroMotor').formatearNumeroMotor;
for(const x of [1e-4,1e-6,1e-8,1e-20,-1e-8]){
  check(formato(x)!=='0'&&Number(formato(x))!==0,'Trazas nunca se presentan como cero');
  cerca(Number(formato(x)),x,Math.abs(x)*1e-6,'Notación científica conserva cifras significativas');
}
check(formato(0)==='0'&&formato(-0)==='0','Cero explícito sí se presenta como cero');
check(formato(.1234567)==='0.1234567','Valores normales con cifras significativas');
check(JSON.stringify(graficas.limitesGraficaMotor([{y:0},{y:1e-8}],['y']))===JSON.stringify(['auto','auto']),'Una trayectoria en trazas no se confunde con ruido');
const limitesTraza=graficas.limitesGraficaMotor([{y:1e-8},{y:1e-8+1e-22}],['y']);
check(limitesTraza[1]-limitesTraza[0]<1e-9,'El eje de una traza constante usa su propia escala');
check(JSON.stringify(graficas.limitesGraficaMotor([{y:0},{y:0}],['y']))===JSON.stringify([-.01,.01]),'Gráfica de cero conserva un eje no degenerado');
console.log(`Multicomponente: ${checks} comprobaciones. Referencias analíticas, conservación, ecuaciones, catálogo, tabla y selección inicial de todas las gráficas.`);
