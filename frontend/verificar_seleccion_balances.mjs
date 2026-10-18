import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const seleccion=cargar('seleccionBalances'),modelo=cargar('modeloHojaMotor'),almacen=cargar('hojasMotor');
const casos=[...cargar('hojasPruebaMateria').crearHojasPruebaMateria(),...cargar('hojasPruebaAcoplamiento').crearHojasPruebaAcoplamiento(),...cargar('hojasPruebaAcoplamiento').crearHojasPruebaMulticomponente()];
let checks=0;const comprobar=(v,m)=>{checks++;assert.ok(v,m);};
for(const h of casos){
 const original=JSON.stringify(h),firma=modelo.firmaHoja(h),a=modelo.analizarHoja(h);
 comprobar(a.listo,'Cada caso original permanece listo');
 for(const vistaBalance of ['materia','energia','momento']){
  const vista={...h,vistaBalance,supuestosBalances:{energia:{estacionario:true}}};
  comprobar(modelo.firmaHoja(vista)===firma,'La navegación no cambia el modelo material');
  comprobar(modelo.analizarHoja(vista).listo,'Inspeccionar otra familia no activa su cálculo');
 }
 for(let mask=0;mask<8;mask++){
  const balances={materia:!!(mask&1),energia:!!(mask&2),momento:!!(mask&4)},cambio={...h,balances};
  comprobar(modelo.analizarHoja(cambio).listo===(mask===1),'Solo la selección material implementada es resoluble');
  comprobar((modelo.firmaHoja(cambio)===firma)===(mask===1),'Las selecciones alteran la firma; los defaults preservan identidad');
  if(mask!==1){assert.throws(()=>modelo.compilarHoja(cambio),/balance|implementada/);checks++;await assert.rejects(modelo.resolverHoja(cambio),/balance|implementada/);checks++;}
 }
 const apagada=seleccion.seleccionarBalance({...h,resultadoRef:{firma,estado:'resuelto',fecha:'test'}},'materia',false);
 comprobar(!apagada.resultadoRef,'Cambiar selección invalida el resultado anterior');
 comprobar(JSON.stringify(apagada.config)===JSON.stringify(h.config)&&JSON.stringify(apagada.historial)===JSON.stringify(h.historial)&&JSON.stringify(apagada.ensamblaje)===JSON.stringify(h.ensamblaje),'Apagar no borra datos, derivación ni topología');
 comprobar(modelo.firmaHoja(seleccion.seleccionarBalance(apagada,'materia',true))===firma,'Restaurar materia recupera el mismo modelo');
 comprobar(JSON.stringify(h)===original,'Selección y análisis no mutan la hoja original');
}
for(const h of [casos[0],casos[7],casos[8]]){
 const a=await modelo.resolverHoja(h),b=await modelo.resolverHoja({...h,balances:{...seleccion.BALANCES_LEGADOS},vistaBalance:'momento'});
 comprobar(JSON.stringify(a.valores)===JSON.stringify(b.valores)&&a.firma===b.firma,'Mismos resultados temporales, 1D y acoplados con selección explícita');
}
const memoria=new Map();globalThis.window=new EventTarget();globalThis.localStorage={getItem:k=>memoria.get(k)??null,setItem:(k,v)=>memoria.set(k,String(v))};
const h=casos[0],ref={firma:modelo.firmaHoja(h),estado:'resuelto',fecha:'test'};
almacen.guardarHoja({...h,resultadoRef:ref});
almacen.guardarHoja({...almacen.leerHojas()[0],vistaBalance:'energia'});
comprobar(almacen.leerHojas().length===1&&almacen.leerHojas()[0].resultadoRef.firma===ref.firma,'Cambiar vista no crea otra hoja ni descarta resultados');
almacen.guardarHoja(seleccion.seleccionarBalance(almacen.leerHojas()[0],'energia',true));
comprobar(almacen.leerHojas()[0].balances.energia&&!almacen.leerHojas()[0].resultadoRef,'Selección persiste e invalida resultado');
const copia=almacen.duplicarHoja(almacen.leerHojas()[0]);comprobar(copia.balances.energia&&copia.vistaBalance==='energia','Duplicar conserva balances y vista del sistema');
console.log(`${checks} comprobaciones: selección por sistema, guardas de solver, persistencia e identidad material.`);
