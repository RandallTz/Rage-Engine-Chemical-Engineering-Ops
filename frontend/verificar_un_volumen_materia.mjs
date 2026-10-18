import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const cache = new Map();
function cargar(nombre) {
  if (cache.has(nombre)) return cache.get(nombre);
  const modulo = {exports:{}};
  const codigo = ts.transpileModule(fs.readFileSync(`app/motor/${nombre}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('exports','module','require',codigo)(modulo.exports,modulo,r=>cargar(r.replace('./','')));
  cache.set(nombre,modulo.exports); return modulo.exports;
}
const m = cargar('recorridoMateria'), op = cargar('operadores');
const base = {...m.iniciarRecorrido().pasos[0].formulacion, componentes:[{id:1,nombre:'Agua',simbolo:'A'}]};
const sinFuentes = {...base.campo,sinGeneracion:true,sinConsumo:true};
let comprobaciones = 0, contrastes = 0, errorMaximo = 0;
function comprobar(condicion, titulo) { comprobaciones++; assert.ok(condicion,titulo); }
function cerca(valor, referencia, titulo, tol=1e-9) {
  contrastes++; const error = Math.abs(valor-referencia)/Math.max(1,Math.abs(referencia));
  errorMaximo = Math.max(errorMaximo,error); comprobar(error<tol,`${titulo}: ${valor} frente a ${referencia}`);
}
const render = l => katex.renderToString(String.raw`\displaystyle ${l}`,{throwOnError:true,strict:'error'});
// Independent polynomial quadrature, only for verification, never an app solver.
function integral(f,a,b,n=100) { const h=(b-a)/n; let s=f(a)+f(b); for(let i=1;i<n;i++)s+=(i%2?4:2)*f(a+i*h);return s*h/3; }
// Evaluate the structured total terms consumed by the displayed equation.
// Reference fields and flux values below are written independently of the editor.
function rhs(f,{puertos={},resto=0,generacion=0,consumo=0,V=1,rho=1}={}) {
  return m.terminosTotalesMateria(f,'A').reduce((sum,t)=> {
    let valor = t.rol==='entrada'||t.rol==='salida' ? puertos[t.puertoId]
      : t.rol==='resto' ? resto : t.rol==='generacion' ? generacion : consumo;
    assert.ok(Number.isFinite(valor),'La referencia debe aportar cada término activo');
    if(t.forma==='tasa_por_volumen')valor*=V;
    if(f.cantidadVolumen&&f.densidadMediaConstante&&f.densidadComunPuertos)valor/=rho;
    return sum+t.signo*valor;
  },0);
}
const puertos=[{id:1,sentido:'entrada',constante:false},{id:2,sentido:'salida',constante:false}];
const abierto={...base,vista:'cantidad',fronteras:puertos,restoImpermeable:true,campo:sinFuentes};
comprobar(m.balancesComponentes(abierto).length===1,'Un volumen, una especie: una conservación');
for(const difusion of ['flujo','fick','laplaciano'])for(const vista of Object.keys(m.FORMAS_MATERIA))for(const coordenadas of Object.keys(op.COORDENADAS)) {
  const f={...base,vista,coordenadas,campo:{...base.campo,difusion}};
  const latex=m.balanceActual(f,'A');render(latex);m.relacionesFormulacion(f).forEach(render);
  comprobar(!latex.includes('j_{A}')&&!latex.includes('D_{A}')&&!latex.includes('nabla^2'),'Una especie no difunde respecto a su velocidad media en masa');
  comprobar(m.relacionesFormulacion(f).includes(String.raw`\mathbf j_{A}=\mathbf0`),'La identidad que elimina la difusión queda visible');
}
comprobar(m.campoEfectivo({...base,componentes:[]}).sinDifusion===false,'i genérico no presupone fluido puro');
comprobar(m.campoEfectivo({...base,componentes:[...base.componentes,{id:2,nombre:'B',simbolo:'B'}]}).sinDifusion===false,'No imponer identidad pura a una mezcla');
// Filling, emptying and variable boundary flows: no preset in runtime.
for(const [Fin,Fout] of [[3,1],[1,3],[2,2],[0,0]])for(const t of [0,0.5,2]) {
  const derivada=Fin-Fout;
  const masa=t=>100+(Fin-Fout)*t;
  cerca(rhs(abierto,{puertos:{1:Fin,2:Fout}}),derivada,'Entrada menos salida');
  cerca((masa(t+1e-4)-masa(t-1e-4))/2e-4,derivada,'Referencia independiente de m(t)',1e-8);
}
for(const t of [0,0.5,2])cerca(rhs(abierto,{puertos:{1:3+t,2:1+2*t}}),2-t,'Fronteras variables en tiempo');
// A known port plus complement must count an undeclared outlet once.
const entrada={...abierto,fronteras:[puertos[0]],restoImpermeable:false};
comprobar(m.terminosTotalesMateria(entrada,'A').length===2,'Puerto declarado + complemento, sin sumatoria fantasma');
cerca(rhs(entrada,{puertos:{1:3},resto:1}),2,'Salida sin clasificar incluida una sola vez en Phi');
const sinPuertos={...abierto,fronteras:[],restoImpermeable:false};
comprobar(m.terminosTotalesMateria(sinPuertos,'A')[0].rol==='resto','Sin puertos, toda la frontera sigue desconocida');
cerca(rhs(sinPuertos,{resto:-2}),2,'Phi negativo representa entrada');
cerca(rhs(sinPuertos,{resto:2}),-2,'Phi positivo representa salida');
comprobar(!m.balanceTotal(sinPuertos,'A').includes('sum_'),'No duplicar toda la superficie con puertos inexistentes');
const cerrado={...sinPuertos,restoImpermeable:true};
comprobar(m.balanceTotal(cerrado,'A')===String.raw`\frac{dm_{A}}{dt}=0`,'Frontera completa impermeable conserva masa');
const quieto={...sinPuertos,fija:true,campo:{...sinFuentes,sinConveccion:true}};
comprobar(m.terminosTotalesMateria(quieto,'A').length===0,'v=0, j=0 y frontera fija anulan transporte');
comprobar(m.balanceTotal(quieto,'A')==='0=0','La ausencia de fuentes y transporte deduce acumulación nula');
comprobar(!m.balanceIntegrado(quieto,'A').includes('oint'),'No queda una integral de flujo cero');
// Local stationarity does not imply constant mass of a moving domain.
// rho(x)=2+x; x in [0,L(t)], L=1+t. v=0 and no sources.
const movil={...sinPuertos,campo:{...sinFuentes,sinConveccion:true,estacionario:true}};
for(const t of [0,0.5,2]) {
  const L=1+t, dM=2+L, phi=-(2+L);
  const masa=t=>integral(x=>2+x,0,1+t);
  cerca(rhs(movil,{resto:phi}),dM,'Reynolds: transporte debido a frontera móvil');
  cerca((masa(t+1e-4)-masa(t-1e-4))/2e-4,dM,'Derivada de integral en dominio móvil',1e-8);
}
comprobar(m.acumulacionTotalNula(movil)===false,'No anular acumulación global por estacionario local en dominio móvil');
comprobar(m.balanceIntegrado(movil,'A').startsWith(String.raw`\frac{d}{dt}`),'Conservar derivada total');
comprobar(m.balanceIntegrado(movil,'A').includes('v_b'),'Conservar velocidad de frontera');
comprobar(m.acumulacionTotalNula({...movil,fija:true})===true,'Estacionario local en dominio fijo implica acumulación total nula');
// Moving right surface: rho=2, v=3, Ldot=0.75. The relative outflow is 4.5,
// not rho*v=6. Local accumulation is zero, total mass derivative is 1.5.
cerca(rhs(abierto,{puertos:{1:2*3,2:2*(3-0.75)}}),2*0.75,'Caudal relativo al puerto móvil');
// Product rule with independently differentiated rho_bar(t)*V(t).
for(const t of [0,0.5,2]) {
  const V=3+2*t,rho=2+t,dM=2*rho+V;
  const f={...base,vista:'cantidad',fronteras:[],restoImpermeable:true,cantidadVolumen:true,expandirProducto:true};
  cerca(rhs(f,{generacion:dM+2,consumo:2}),dM,'Masa variable conserva los dos términos del producto');
  comprobar(m.balanceTotal(f,'A').includes(String.raw`V(t)\frac{d\bar\rho_{A}}{dt}`),'Mantener V d(rho_media)/dt');
  comprobar(m.balanceTotal({...f,fija:true},'A').startsWith(String.raw`V\frac{d\bar\rho_{A}}{dt}`),'Volumen fijo mantiene derivada de densidad');
}
const volumen={...abierto,cantidadVolumen:true,densidadMediaConstante:true,densidadComunPuertos:true};
comprobar(m.balanceTotal(volumen,'A')===String.raw`\frac{dV}{dt}=Q_{1}(t)-Q_{2}(t)`,'Reducción a volumen procede de relaciones declaradas');
comprobar(m.unidadBalance(volumen)==='m³/s','Convertir unidad de TODOS los términos al dividir por densidad');
for(const [Qin,Qout] of [[3,1],[1,3],[2,2]])cerca(rhs(volumen,{puertos:{1:1000*Qin,2:1000*Qout},rho:1000}),Qin-Qout,'Masa y volumen representan el mismo balance');
const conFuente={...volumen,campo:base.campo};
cerca(rhs(conFuente,{puertos:{1:3000,2:1000},rho:1000,generacion:500,consumo:100}),2.4,'Dividir también fuentes por densidad');
comprobar(m.acumulacionTotalNula({...volumen,fija:true})===true,'Volumen fijo + densidad media constante produce restricción de flujos');
// Spatially varying generation: gamma=x² on [0,3]. Simpson is exact here.
const fuentes={...base,vista:'cantidad',fija:true,campo:{...base.campo,sinConveccion:true,sinConsumo:true}};
const G=integral(x=>x*x,0,3);
cerca(G,9,'Integral de fuente variable');
cerca(rhs(fuentes,{generacion:G}),9,'Usar tasa integrada, no tasa de un punto por volumen');
comprobar(m.balanceIntegrado(fuentes,'A').includes(String.raw`\gamma_{A}(\mathbf x,t)`),'Conservar dependencia espacial de la tasa');
comprobar(!m.balanceIntegrado(fuentes,'A').includes(String.raw`\gamma_{A}(t)V`),'No introducir uniformidad');
comprobar(Math.abs(1.5**2*3-G)>2,'La referencia detecta el atajo incorrecto');
cerca(rhs({...fuentes,generacionUniforme:true},{generacion:2,V:3}),6,'Solo fuente uniforme permite gamma V');
const brutas={...cerrado,campo:base.campo};
cerca(rhs(brutas,{generacion:8,consumo:8}),0,'Neto cero mantiene ambas tasas brutas');
comprobar(m.terminosTotalesMateria(brutas,'A').some(t=>t.rol==='generacion')&&m.terminosTotalesMateria(brutas,'A').some(t=>t.rol==='consumo'),'No borrar generación y consumo por un neto cero');
// Pure-species local and total conservation for v=a*x and rho(t)=2 exp(-3 a t).
// Independent Cartesian reference has div(rho*v)=3 a rho. Compare metric data
// used by production rendering in each coordinate system and surface flux.
const a=0.2,h=1e-5;
function deriv(f,q,axis) {const p=[...q],n=[...q];p[axis]+=h;n[axis]-=h;return(f(p)-f(n))/(2*h);}
function factor(f,q){return q[0]**f.r*Math.sin(q[1])**f.seno;}
for(const coordenadas of Object.keys(op.COORDENADAS))for(const t of [0,0.5,2]) {
  const rho=2*Math.exp(-3*a*t),q=[1.3,0.8,1.1];
  const velocidad=p=>coordenadas==='cartesianas'?p.map(x=>a*x):coordenadas==='cilindricas'?[a*p[0],0,a*p[2]]:[a*p[0],0,0];
  const div=op.terminosMetricos(coordenadas,1).reduce((s,k)=>s+factor(k.exterior,q)*deriv(p=>factor(k.interior,p)*rho*velocidad(p)[k.a],q,k.a),0);
  cerca(div,3*a*rho,`${coordenadas}: conservación local de especie pura`);
  const V=coordenadas==='cartesianas'?8:coordenadas==='cilindricas'?Math.PI*2**2*3:4*Math.PI*2**3/3;
  const phi=3*a*rho*V; // Independent flux integral for cube/cylinder/sphere.
  cerca(rhs({...sinPuertos,fija:true,coordenadas},{resto:phi}),-3*a*rho*V,`${coordenadas}: conservación integral y total`);
}
console.log(`Un volumen / una especie: ${comprobaciones} comprobaciones, ${contrastes} contrastes independientes; error relativo máximo ${errorMaximo.toExponential(2)}. Sin ejecutar el solver ni importar el laboratorio.`);
