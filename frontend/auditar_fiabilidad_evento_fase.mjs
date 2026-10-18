// Reproduction only: the live backend resolves the unmodified physics declarations.
// This audit does not certify a trajectory or calculate thermodynamic properties.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import ts from 'typescript';
const cache=new Map();
function cargar(n){
  if(cache.has(n))return cache.get(n);
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(path.posix.join(path.posix.dirname(n),id)));return m.exports;
}
const lector=cargar('lectorEnsamblajeV2');
const fuente='../docs/ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json';
const original=JSON.parse(fs.readFileSync(fuente,'utf8'));
// New runs never overwrite the original dated evidence or earlier captures.
const destino=`.tmp/qa-fiabilidad-evento-${new Date().toISOString().replace(/[:.]/g,'-')}`;fs.mkdirSync(destino,{recursive:true});
console.log(`Captura: ${destino}`);
const modelos=['nrtl-chemsep','unifac-original-public','mezcla-ideal'];
const resultados=[];
for(const modelo of modelos){
  const s=structuredClone(original);s.solicitudId=`qa-fiabilidad-${modelo}`;s.paquetes[0].modelo={id:modelo,version:'1'};
  // The only intentional differences are the selected package and correlation ID.
  assert.deepEqual({...s,solicitudId:original.solicitudId,paquetes:original.paquetes},original);
  fs.writeFileSync(`${destino}/${modelo}-peticion.json`,JSON.stringify(s,null,2)+'\n');
  if(!process.argv.includes('--servicio'))continue;
  const tiempos={};let r;
  for(const operacion of ['validar','resolver']){
    const inicio=performance.now();
    const http=await fetch(`http://localhost:8004/motor/ensamblajes/${operacion}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s),signal:AbortSignal.timeout(600000)});
    const raw=await http.text();fs.writeFileSync(`${destino}/${modelo}-${operacion}-respuesta.json`,raw+'\n');
    assert.equal(http.ok,true,`${operacion} HTTP ${http.status}`);
    r=operacion==='resolver'?lector.leerResolucionV2(JSON.parse(raw),s):lector.leerValidacionV2(JSON.parse(raw),s);
    tiempos[operacion]=(performance.now()-inicio)/1000;
  }
  const a=r.resultados;assert.ok(a,'Expected inspectable published evidence');
  const serie=(id,unidad)=>{const v=a.series.find(v=>v.variableId===id);assert.equal(v?.unidadSI,unidad);return v.valores;};
  const H=serie('volumen.A.H','J'),U=serie('volumen.A.U','J'),V=serie('volumen.A.V','m3'),P=serie('volumen.A.P','Pa'),W=serie('volumen.A.W','J'),Q=serie('calor.q.Q','W');
  assert.ok(P.every(p=>p===101325)&&Q.every(q=>q===100),'Bookkeeping below is specific to this closed isobaric constant-heat fixture');
  const maxAbs=v=>Math.max(...v.map(Math.abs));
  const resumen={modelo,tiemposSegundos:tiempos,estado:r.estado,certificacion:a.certificacion,eventos:a.eventos,residuos:a.residuos,
    contabilidadSI:{
      advertencia:'Identidades de esta petición cerrada a P y Q constantes; no son una certificación independiente del flash ni de la cuadratura auxiliar de trabajo. W es la serie publicada, no el auxiliar interno.',
      maxErrorEntalpiaJ:maxAbs(a.tiempos.map((t,i)=>H[i]-H[0]-100*(t-a.tiempos[0]))),
      maxErrorUigualHmenosPVJ:maxAbs(U.map((u,i)=>u-H[i]+P[i]*V[i])),
      maxErrorTrabajoPublicadoJ:maxAbs(W.map((w,i)=>w-W[0]-101325*(V[i]-V[0]))),
      maxErrorPrimerPrincipioPublicadoJ:maxAbs(a.tiempos.map((t,i)=>U[i]-U[0]-100*(t-a.tiempos[0])+W[i]-W[0])),
    }};
  resultados.push(resumen);fs.writeFileSync(`${destino}/resumen.json`,JSON.stringify({fuente,fechaUTC:new Date().toISOString(),resultados},null,2)+'\n');
  console.log(`${modelo}: ${r.estado}; certificado ${a.certificacion?.estado}; trabajo ${a.residuos.find(x=>x.ecuacionId==='mecanica.A.trabajo')?.maximoEscalado}; ${tiempos.resolver.toFixed(2)} s`);
}
if(!process.argv.includes('--servicio'))console.log('Tres peticiones derivadas; solo cambian paquete e ID. Usar --servicio para guardar respuestas originales y contabilidad SI.');
