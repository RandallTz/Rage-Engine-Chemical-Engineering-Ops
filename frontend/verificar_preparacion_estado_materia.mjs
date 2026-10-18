import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const red=cargar('ensamblajeMateria'),hoja=cargar('modeloHojaMotor'),m=cargar('modeloNumerico'),rec=cargar('recorridoMateria'),alm=cargar('hojasMotor'),reg=cargar('reglasEstadoMateria'),int=cargar('integracionMotor');
const ejemplos=cargar('hojasPruebaAcoplamiento'),casos=[...ejemplos.crearHojasPruebaAcoplamiento(),...ejemplos.crearHojasPruebaMulticomponente()];
let checks=0;const check=(x,s)=>{checks++;assert.ok(x,s);},cerca=(a,b,t,s)=>check(Math.abs(a-b)<=t,`${s}: ${a} / ${b}`);
for(const h of casos){
  const texto=JSON.stringify(h),n=alm.normalizarHoja(h);
  check(JSON.stringify(h)===texto,'La migración no altera el documento original');
  check(n.ensamblaje.componentes.length===red.catalogoComponentes(h.ensamblaje).length,'Catálogo común');
  check(n.ensamblaje.volumenes.every(v=>v.componentesIds.length===n.ensamblaje.componentes.length),'Volúmenes referencian por ID');
  check(n.ensamblaje.corrientes.every(s=>s.componentesIds&&s.mecanismo===null&&s.datos&&!s.resultado),'Especificación separada, sin resultado inventado');
  check(!Object.keys(n.config.datos).some(k=>/^s\d+__/.test(k)),'No duplicar especificaciones en config');
  check(hoja.firmaHoja(n)===hoja.firmaHoja(h),'Conservar firma de las hojas antiguas, incluidos resultados guardados');
  const a=hoja.analizarHoja(h),b=hoja.analizarHoja(n);
  check(a.gl===b.gl&&a.variables===b.variables&&a.ecuaciones===b.ecuaciones&&b.listo,'Mismo recuento');
  const original=await hoja.resolverHoja(h),nuevo=await hoja.resolverHoja(n);
  check(JSON.stringify(original.tiempos)===JSON.stringify(nuevo.tiempos)&&JSON.stringify(original.valores)===JSON.stringify(nuevo.valores),'Trayectoria idéntica bit a bit después de migrar');
  check(JSON.stringify(original.conservacion)===JSON.stringify(nuevo.conservacion)&&original.estado===nuevo.estado,'Mismos presupuestos y eventos');
  check(nuevo.variablesNumericas.every(v=>v.restriccion==='no_negativo'&&v.unidad==='kg'),'Las masas conservan sus restricciones');
  const nn=alm.normalizarHoja(n);check(JSON.stringify(nn)===JSON.stringify(n),'Migración idempotente');
}
// Central identity wins over mutable journal display copies, and survives reordering.
const central=alm.normalizarHoja(casos[4]);central.ensamblaje.componentes[0].identidadQuimica={cas:'7732-18-5'};
central.ensamblaje.volumenes[0].historial.pasos.at(-1).formulacion.componentes[0].nombre='Copia obsoleta';
check(red.formulacionVolumen(central.ensamblaje,central.ensamblaje.volumenes[0]).componentes[0].nombre==='A','Identidad central, no copias del historial');
central.ensamblaje.volumenes.reverse();check(red.catalogoComponentes(central.ensamblaje)[0].identidadQuimica.cas==='7732-18-5','Identidad química no depende del primer volumen');
const desconocido=structuredClone(central);desconocido.ensamblaje.volumenes[0].componentesIds=[999];check(!hoja.analizarHoja(desconocido).listo,'ID inexistente rechazado');
const duplicado=structuredClone(central);duplicado.config.datos.s1__c1={texto:'99',unidad:'kg/s'};check(!hoja.analizarHoja(duplicado).listo,'Dos fuentes de especificación rechazadas');
const editable=alm.normalizarHoja(casos[0]),c=hoja.configuracionHoja(editable);c.datos.s1__c1={texto:'4',unidad:'kg/s'};
const editado={...editable,...red.actualizarDatosEnsamblaje(editable.ensamblaje,c)};
check(editado.ensamblaje.corrientes[0].datos.materia.caudales[1].texto==='4'&&!editado.config.datos.s1__c1,'Edición actualiza la única especificación');
const rEdit=await hoja.resolverHoja(editado);cerca(rEdit.valores.at(-1)[0][0],1300,1e-8,'La edición se ejecuta, no se pierde al guardar');

// Total plus composition and component flows describe the same mass balance.
const mezcla=alm.normalizarHoja(casos[6]),total=structuredClone(mezcla);
total.ensamblaje.corrientes[0].mecanismo='convectivo';
total.ensamblaje.corrientes[0].datos={materia:{modo:'total_y_composicion',base:'masica',caudalTotal:{texto:'6',unidad:'kg/s'},composicion:{base:'masica',fracciones:{1:.5,2:1/3,3:1/6}}},T:{texto:'25',unidad:'degC'},P:{texto:'1',unidad:'bar'},fasesPermitidas:['liquido']};
const p=hoja.analizarHoja(total);check(p.listo&&p.totalDatos===7,'Un dato de caudal total, sin N datos duplicados');
const rTotal=await hoja.resolverHoja(total),rMezcla=await hoja.resolverHoja(mezcla);
check(JSON.stringify(rTotal.valores)===JSON.stringify(rMezcla.valores),'Total más composición da exactamente la misma física');
check(!rTotal.fases&&!total.ensamblaje.corrientes[0].resultado,'T/P y restricción no producen propiedades ni fases ficticias');
const malo=structuredClone(total);malo.ensamblaje.corrientes[0].datos.materia.composicion.fracciones[1]=.6;check(!hoja.analizarHoja(malo).listo,'Composición no normalizada rechazada');
const dosModos=structuredClone(total);dosModos.ensamblaje.corrientes[0].datos.materia.caudales={1:{texto:'2',unidad:'kg/s'}};check(!hoja.analizarHoja(dosModos).listo,'Ambos modos a la vez rechazados');
const selectivoTotal=structuredClone(total);selectivoTotal.ensamblaje.corrientes[0].mecanismo='selectivo';check(!hoja.analizarHoja(selectivoTotal).listo,'No normalizar un flujo selectivo neto');
const cf=alm.normalizarHoja(casos[7]);cf.ensamblaje.corrientes[0].mecanismo='convectivo';assert.throws(()=>hoja.compilarHoja(cf),/compartir sentido/);checks++;
cf.ensamblaje.corrientes[0].mecanismo='selectivo';check(hoja.analizarHoja(cf).listo,'Contraflujo selectivo admite sus signos');

// Molar inputs require declared MWs, with units and source, never a provider lookup.
const molar=alm.normalizarHoja(casos[4]);molar.ensamblaje.componentes.forEach(s=>s.masaMolar={cantidad:{valor:s.id===1?18:46,unidad:'g/mol'},fuente:'Dato de prueba explícito'});
const sm=molar.ensamblaje.corrientes[0].datos.materia;sm.base='molar';sm.caudales={1:{texto:'(0.2/0.018)*(m_A_v1-m_A_v2)',unidad:'mol/s'},2:{texto:'0',unidad:'mol/s'}};
const rm=await hoja.resolverHoja(molar),ra=await hoja.resolverHoja(casos[4]);rm.valores.forEach((y,k)=>y.forEach((v,j)=>cerca(v[0],ra.valores[k][j][0],1e-12,'Conversión molar a masa con referencia declarada')));
const sinMw=structuredClone(molar);delete sinMw.ensamblaje.componentes[0].masaMolar;check(!hoja.analizarHoja(sinMw).listo,'No inventar masa molar para componente simbólico');
const sinFuente=structuredClone(molar);sinFuente.ensamblaje.componentes[0].masaMolar.fuente='';check(!hoja.analizarHoja(sinFuente).listo,'Fuente de masa molar requerida');
const molTotal=structuredClone(total);const mw=[.018,.030,.044];molTotal.ensamblaje.componentes.forEach((s,i)=>s.masaMolar={cantidad:{valor:mw[i],unidad:'kg/mol'},fuente:'Dato explícito'});
const flujosMol=[3/.018,2/.030,1/.044],fm=flujosMol.reduce((a,b)=>a+b,0);
molTotal.ensamblaje.corrientes[0].datos.materia={modo:'total_y_composicion',base:'molar',caudalTotal:{texto:String(fm),unidad:'mol/s'},composicion:{base:'molar',fracciones:Object.fromEntries(flujosMol.map((v,i)=>[i+1,v/fm]))}};
const rtMol=await hoja.resolverHoja(molTotal);rtMol.valores.forEach((y,k)=>y.forEach((v,j)=>cerca(v[0],rTotal.valores[k][j][0],1e-10,'Total y composición molar conservan el balance másico')));
const graf=cargar('datosGraficasMotor').datosGraficasMotor(molar,rm,'tiempo');
check(graf.variables.find(v=>v.id==='dato_s1__c1').unidad==='mol/s'&&graf.variables.find(v=>v.id==='mdot_s1_c1').unidad==='kg/s','Entrada molar y tasa másica tienen magnitudes separadas');
cerca(graf.filas[0].mdot_s1_c1,graf.filas[0].dato_s1__c1*.018,1e-14,'Conversión publicada usa la masa molar declarada');
const resultadoFalso=structuredClone(total);resultadoFalso.ensamblaje.corrientes[0].resultado={firmaEstado:'obsoleto',T:{valor:999,unidad:'K'},fases:{base:'molar',valores:[],origen:'calculado',validacion:'valido',modeloId:'ficticio'}};
check(hoja.firmaHoja(resultadoFalso)===hoja.firmaHoja(total),'El resultado evaluado no se transforma en especificación');
check(JSON.stringify(hoja.compilarHoja(resultadoFalso).rhs(0,hoja.compilarHoja(resultadoFalso).inicial))===JSON.stringify(hoja.compilarHoja(total).rhs(0,hoja.compilarHoja(total).inicial)),'Los resultados térmicos no modifican la conservación');
const tiposLegados=structuredClone(casos[4]);tiposLegados.ensamblaje.volumenes[1].historial.pasos.at(-1).formulacion.componentes[0].simbolo='Z';assert.throws(()=>alm.normalizarHoja(tiposLegados),/identidades/);checks++;
check(alm.normalizarHoja(casos[0]).ensamblaje.version===2,'Esquema nuevo versionado; el antiguo sigue aceptándose');

// Rules: retained, scoped and undoable; phase evaluation is unavailable, not fulfilled.
const fase=alm.normalizarHoja(casos[0]);let hv=fase.ensamblaje.volumenes[0].historial;
hv=rec.recorridoMateria(hv,{tipo:'cambiar',titulo:'Restringir fases',cambios:{reglasEstado:{fases:{cantidad:'monofasico',cambioInterno:'sin_cambio_de_fase',evaluacion:'termodinamica'}}}});fase.ensamblaje.volumenes[0].historial=hv;
const af=hoja.analizarHoja(fase);check(af.listo&&af.evaluacionReglas[0].verificacion==='no_evaluable'&&!af.evaluacionReglas[0].aplicadaEnEcuaciones,'Materia ejecutable sin certificar fases');
const rr=await hoja.resolverHoja(fase),r0=await hoja.resolverHoja(casos[0]);check(JSON.stringify(rr.valores)===JSON.stringify(r0.valores)&&rr.evaluacionReglas[0].verificacion==='no_evaluable','Ningún cambio físico por una etiqueta de fase');
const atras=rec.recorridoMateria(hv,{tipo:'ir',indice:hv.activo-1});check(!atras.pasos[atras.activo].formulacion.reglasEstado,'Deshacer retira la elección');check(rec.recorridoMateria(atras,{tipo:'rehacer'}).pasos.at(-1).formulacion.reglasEstado.fases.cantidad==='monofasico','Rehacer restaura la elección');
const simple=cargar('hojasPruebaMateria').crearHojasPruebaMateria()[2],f=simple.historial.pasos[simple.historial.activo].formulacion;
const nueva={...f,densidadMediaConstante:false,reglasEstado:{densidades:[{variableId:'concentracion_media_c1',fuente:'dato',constanciaTemporal:'asumida'}]}};
check(rec.balanceActual(nueva)===rec.balanceActual(f),'Hipótesis explícita conserva la reducción de concentración constante');
const rn=await int.resolverMotor(nueva,simple.config),ro=await int.resolverMotor(f,simple.config);check(JSON.stringify(rn.valores)===JSON.stringify(ro.valores),'Mismo balance volumétrico con regla explícita');
const verificar={...nueva,reglasEstado:{densidades:[{variableId:'densidad_mezcla',fuente:'propiedades',constanciaTemporal:'a_verificar'}]}};
check(!reg.concentracionConstante(verificar),'Calcular propiedades no anula la derivada');
check(reg.analizarReglasEstado(verificar).evaluacion[0].verificacion==='no_evaluable','Densidad calculada no certificada');
const falsa={...verificar,reglasEstado:{densidades:[{variableId:'densidad_fase_L1',fuente:'propiedades',constanciaTemporal:'asumida'}]}};check(!m.analizarMotor(falsa,simple.config).listo,'No aplicar silenciosamente una relación de fase que no existe');

// General vector metadata: a signed energy-like coordinate is not a mass.
const cfg={...m.iniciarConfiguracion(),tiempo:{texto:'2',unidad:'s'},muestras:11,rtol:1e-7,atol:1e-9};
const sistema={modo:'temporal',unidadEstado:'kg',inicial:[1,-100],x:[],dx:1,n:1,nc:2,tfinal:2,rhs:()=>[0,-1],balance:()=>[0,-1],limitePaso:()=>.2,observacion:(_t,y)=>y.map(v=>[v]),variablesNumericas:[{id:'m',propietarioId:'v1',magnitud:'masa',unidad:'kg',rol:'diferencial',restriccion:'no_negativo',toleranciaAbsoluta:1e-12},{id:'U',propietarioId:'v1',magnitud:'energia',unidad:'J',rol:'diferencial',restriccion:'libre',toleranciaAbsoluta:1e-5}]};
for(const metodo of ['rk45','euler_implicito']){const r=await int.resolverSistemaMotor(sistema,{...cfg,metodo},{componentes:[{id:1,nombre:'m',simbolo:'A'},{id:2,nombre:'U de prueba',simbolo:'U'}],firma:'prueba-generica'});check(r.estado==='resuelto','Variable libre negativa no agota el sistema');cerca(r.valores.at(-1)[1][0],-102,1e-9,'Coordenada libre integrada');check(r.variablesNumericas[1].unidad==='J'&&r.variablesNumericas[1].toleranciaAbsoluta===1e-5,'Unidades y tolerancia por variable');}
const vaciado={...sistema,rhs:()=>[-1,-1],balance:()=>[-1,-1]};const rv=await int.resolverSistemaMotor(vaciado,cfg,{componentes:[],firma:'vaciado'});check(rv.estado==='parcial','La masa sí detiene por agotamiento');cerca(rv.tiempos.at(-1),1,1e-9,'Evento de la variable restringida');
const erroneo=structuredClone(sistema.variablesNumericas);erroneo[1].toleranciaAbsoluta=0;await assert.rejects(int.resolverSistemaMotor({...sistema,variablesNumericas:erroneo},cfg,{componentes:[],firma:'mal'}),/Descriptores/);checks++;

// Persistence uses canonical inputs, with existing IDs and result references intact.
const memoria=new Map();globalThis.window=new EventTarget();globalThis.localStorage={getItem:k=>memoria.get(k)??null,setItem:(k,v)=>memoria.set(k,String(v))};
const guardada=alm.guardarHoja({...casos[0],resultadoRef:{firma:hoja.firmaHoja(casos[0]),estado:'resuelto',fecha:'2026-10-13'}});check(hoja.firmaHoja(guardada)===guardada.resultadoRef.firma,'Resultado guardado vigente después de migrar');
const vuelta=alm.leerHojas()[0];check(hoja.analizarHoja(vuelta).listo&&vuelta.ensamblaje.corrientes[0].datos,'La hoja guardada vuelve completa');
check(alm.guardarHojasNuevas([casos[0]])===0,'Sin duplicar documentos anteriores');
delete globalThis.window;delete globalThis.localStorage;
console.log(`Preparación estructural de materia: ${checks} comprobaciones. Compatibilidad bit a bit, catálogo, especificaciones, reglas, variables y persistencia.`);
