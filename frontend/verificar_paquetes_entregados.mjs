// Offline protocol/presentation checks on original endpoint fixtures.
// This runner neither evaluates thermodynamics nor grants model availability.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import ts from 'typescript';
const args=process.argv.slice(2),permitidos=['--directorio','--modelo','--version'],opts={};
for(let i=0;i<args.length;i+=2){if(!permitidos.includes(args[i])||!args[i+1]||args[i+1].startsWith('--'))throw new Error('Uso: node verificar_paquetes_entregados.mjs --directorio <carpeta> [--modelo <id> --version <versión>]');opts[args[i]]=args[i+1];}
if(!opts['--directorio']||!!opts['--modelo']!==!!opts['--version'])throw new Error('Declara --directorio; el filtro requiere --modelo y --version juntos.');
const dir=path.resolve(opts['--directorio']);if(!fs.statSync(dir).isDirectory())throw new Error('La carpeta de ejemplos no existe.');
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const lector=cargar('lectorEnsamblajeV2'),termo=cargar('contratoTermodinamica'),diagramas=cargar('lectorDiagramasEquilibrio'),adapt=cargar('resultadoEnsamblajeV2'),graficas=cargar('datosGraficasMotor');
const acepta=m=>!opts['--modelo']||m.id===opts['--modelo']&&m.version===opts['--version'];
const leer=f=>JSON.parse(fs.readFileSync(path.join(dir,f),'utf8'));
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);};
const resumen={capacidades:0,estadosPuntuales:0,validaciones:0,resoluciones:0,diagramas:0,estadosPorVolumen:0,certificacion:{cumple:0,no_cumple:0,no_evaluable:0,no_publicada:0},rechazos:0};
for(const f of fs.readdirSync(dir).filter(f=>f.endsWith('.json')&&!f.endsWith('-peticion.json')&&!f.endsWith('-respuesta.json'))){
  const raw=leer(f);let modelos=[];
  if(raw.revision===2&&raw.paquetes&&raw.componentesMaximos){lector.leerCapacidadesV2(raw);modelos=raw.paquetes.map(p=>p.modelo);}
  else if(raw.revision===1&&raw.modelos){termo.validarCapacidadesEstado(raw);modelos=raw.modelos;}
  else if(raw.revision===1&&raw.trazador&&raw.perfiles){diagramas.leerCapacidadesDiagramas(raw);modelos=raw.paquetes.map(p=>p.modelo);}
  if(modelos.some(acepta)){resumen.capacidades++;checks++;}
}
for(const f of fs.readdirSync(dir).filter(f=>f.endsWith('-peticion.json'))){
  const s=leer(f),modelos=s.paquetes?.map(p=>p.modelo)??[s.declaracion?.modelo??s.modelo].filter(Boolean);
  if(!modelos.some(acepta))continue;
  const respuesta=f.replace(/-peticion\.json$/,'-respuesta.json');check(fs.existsSync(path.join(dir,respuesta)),`Falta respuesta original de ${f}`);
  const r=leer(respuesta),antes=JSON.stringify({s,r});
  if(s.revision===2&&Array.isArray(s.volumenes)){
    if(r.validacion){
      lector.leerResolucionV2(r,s);resumen.resoluciones++;
      if(r.resultados){
        const h={...cargar('hojasMotor').nuevaHoja('Verificación de entrega'),redTermodinamica:{solicitud:s,nombres:{}}};
        const out=adapt.adaptarResultadoV2(h,s,r);adapt.validarResultadoV2(out);
        const datos=graficas.datosGraficasMotor(h,out,'tiempo');
        for(const v of s.volumenes){
          resumen.estadosPorVolumen+=r.resultados.estados[v.id].length;
          for(const id of v.componenteIds)check(datos.variables.some(x=>x.id===`volumen.${v.id}.n.${id}`),`${f}: inventario ${v.id}/${id} omitido`);
        }
        for(const g of adapt.graficasInicialesV2(out))check(g.y.every(id=>datos.variables.some(x=>x.id===id)),`${f}: gráfico con variable desconocida`);
        resumen.certificacion[r.resultados.certificacion?.estado??'no_publicada']++;
      }else resumen.rechazos++;
    }else{lector.leerValidacionV2(r,s);resumen.validaciones++;if(r.diagnosticos.length)resumen.rechazos++;}
  }else if(s.revision===1&&s.declaracion){termo.validarRespuestaEstado(r,s);resumen.estadosPuntuales++;if(r.estado!=='evaluado')resumen.rechazos++;}
  else if(s.revision===1&&s.corte&&s.modelo){diagramas.leerDiagramaEquilibrio(r,s);resumen.diagramas++;if(!['completo','parcial'].includes(r.estado))resumen.rechazos++;}
  else throw new Error(`Solicitud fuera de los protocolos actuales: ${f}`);
  check(JSON.stringify({s,r})===antes,`${f}: el verificador modificó la evidencia`);
}
check(resumen.capacidades>0,'Faltan capacidades originales del modelo/versionado que se está verificando.');
check(resumen.estadosPuntuales+resumen.validaciones+resumen.resoluciones+resumen.diagramas>0,'No hay pares originales que coincidan con el filtro.');
console.log(JSON.stringify({directorio:dir,modelo:opts['--modelo']??'todos',version:opts['--version']??'todas',comprobaciones:checks,...resumen},null,2));
console.log('Lectura de contrato y presentación. No repite el flash ni certifica precisión física o experimental. No modifica archivos.');
