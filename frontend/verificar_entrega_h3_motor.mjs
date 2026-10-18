// Uses real endpoint examples. Mutation fixtures exercise the reader, not a new flash algorithm.
import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const c=cargar('contratoTermodinamica'),estado=cargar('estadoTermodinamicoHoja');
const leer=n=>JSON.parse(fs.readFileSync(`../docs/ejemplos/motor-termodinamica-${n}.json`,'utf8'));
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=(fn,m)=>{checks++;assert.throws(fn,undefined,m);},cerca=(a,b,m)=>check(Math.abs(a-b)<=1e-9+1e-8*Math.max(Math.abs(a),Math.abs(b)),m);
const cap=c.validarCapacidadesEstado(leer('capacidades')).modelos.find(x=>x.id==='agua-iapws95');
check(['TP','PH','UP','UV'].every(t=>cap.especificaciones.includes(t))&&!cap.dinamica,'H3 publica inversos estáticos sin habilitar dinámica');
const casos=['ph-bifasico-1bar','ph-vapor-sobrecalentado-10bar','up-liquido-calentado-1bar','uv-recipiente-rigido-bifasico','uv-recipiente-rigido-molar','uv-supercritico','uv-monofasico-incompatible','uv-energia-bajo-el-punto-triple'];
for(const nombre of casos){const s=leer(`${nombre}-peticion`),r=leer(`${nombre}-respuesta`);check(c.validarRespuestaEstado(r,s,cap)===r,`${nombre}: respuesta real`);if(r.estado!=='evaluado'){check(r.evaluacion===null,'Rechazo sin estado antiguo');continue;}check(!c.analizarSolicitudEstado(s).length,'Datos reales aceptados');const e=r.evaluacion;
  for(const f of e.fases){cerca(f.fraccionMolar,f.fraccionMasica,'Agua pura: bases molar/másica coinciden');cerca(f.fraccionVolumen,f.fraccionMasica*f.propiedades.v/e.mezcla.v,'Base volumétrica reconstruida');}
  if(e.fases.length===2){check(e.mezcla.cp===undefined&&e.mezcla.cv===undefined,'No inventa capacidad global bifásica');check(e.fases.every(f=>f.propiedades.cp>0&&f.propiedades.cv>0),'Capacidades pertenecen a cada fase');}
}
const s=leer('uv-recipiente-rigido-bifasico-peticion'),r=leer('uv-recipiente-rigido-bifasico-respuesta'),e=r.evaluacion;
cerca(10*e.mezcla.u,c.normalizarCantidad(s.declaracion.especificacion.U,'U'),'Energía UV reconstruida');cerca(10*e.mezcla.v,1,'Volumen UV reconstruido');
const rm=leer('uv-recipiente-rigido-molar-respuesta').evaluacion;for(const k of ['T','P'])cerca(e[k],rm[k],'Moles y masa: mismo estado');for(const k of ['u','h','v','s'])cerca(e.mezcla[k],rm.mezcla[k],'Mismas propiedades con unidades/bases equivalentes');
const vapor=e.fases.find(f=>f.tipo==='vapor');check(vapor.fraccionVolumen>vapor.fraccionMasica,'Volumen de vapor no se presenta como calidad másica');
for(const alterar of [x=>x.evaluacion.mezcla.u+=1,x=>x.evaluacion.mezcla.v*=1.01,x=>x.evaluacion.fases[1].fraccionVolumen=x.evaluacion.fases[1].fraccionMasica,x=>x.evaluacion.mezcla.cp=4000,x=>x.evaluacion.componentes[0].masaMolarKgMol=.018]){const x=structuredClone(r);alterar(x);rechaza(()=>c.validarRespuestaEstado(x,s,cap),'No acepta reconstrucción o propiedades falsas');}
// Adapt an actual phase to a protocol endpoint. No claim of independent physical validation.
const liquido=e.fases.find(f=>f.tipo==='liquido'),extremo=structuredClone(r),sx=structuredClone(s);
sx.declaracion.especificacion={tipo:'PH',P:{valor:e.P,unidad:'Pa'},h:{valor:liquido.propiedades.h,unidad:'J/kg'},composicion:{base:'molar',fracciones:{1:1}}};
extremo.evaluacion.mezcla=Object.fromEntries(['u','h','v','s'].map(k=>[k,liquido.propiedades[k]]));extremo.evaluacion.fases=[{...structuredClone(liquido),fraccionMolar:1,fraccionMasica:1,fraccionVolumen:1}];
check(c.validarRespuestaEstado(extremo,sx,cap)===extremo,'Lector admite extremo con una fase y verificación de equilibrio');
for(const prop of ['cp','cv']){const x=structuredClone(extremo);x.evaluacion.mezcla[prop]=liquido.propiedades[prop];rechaza(()=>c.validarRespuestaEstado(x,sx,cap),'Capacidad de fase no es capacidad global en el extremo');}
const sat=leer('saturacion-indeterminada-respuesta');check(sat.estado==='incompleto'&&sat.evaluacion===null,'TP en saturación no escoge calidad');check(sat.diagnosticos.some(d=>d.alternativas?.some(a=>a.includes('V')))&&sat.diagnosticos.some(d=>d.alternativas?.some(a=>a.includes('h'))),'Alternativas UV/PH publicadas');
const uv=s.declaracion.especificacion,up=estado.cambiarTipoEstado(uv,'UP',[1]);check(up.U===uv.U&&up.cantidades===uv.cantidades&&up.P.valor===null,'UV a UP conserva datos comunes y deja P pendiente');check(estado.cambiarTipoEstado(uv,'UV',[1])===uv,'Clic en tipo activo no borra datos');
for(const tipo of ['TP','PH']){const nuevo=estado.cambiarTipoEstado(uv,tipo,[1]);check(nuevo.composicion.fracciones[1]===1,'Una especie no añade un dato ficticio al cambiar tipo');check(nuevo.P.valor===null,'No copia la presión del resultado UV a un dato');}
check(!Object.keys(estado.cambiarTipoEstado(uv,'TP',[1,2]).composicion.fracciones).length,'No fabrica composición de mezclas');
console.log(`${checks} comprobaciones H3: ejemplos reales, reconstrucción UV, bases de fase, límites de Cp/Cv y cambios de especificación.`);
