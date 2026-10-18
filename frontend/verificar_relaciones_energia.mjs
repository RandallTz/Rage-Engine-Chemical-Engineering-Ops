import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import katex from 'katex';
const cache=new Map();
function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const rec=cargar('recorridoEnergia'),estado=cargar('estadoEnergiaHoja'),vol=cargar('volumenControl'),modelo=cargar('modeloHojaMotor'),energia=cargar('modeloEnergia'),final=cargar('ecuacionesSistemaEnergia'),prep=cargar('prepararEnsamblajeTermodinamico'),roles=cargar('papelesVariables');
const casos=cargar('hojasPruebaEnergia').crearHojasPruebaEnergia();
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);};
const cambiar=(h,c)=>({...h,energia:{...h.energia,historial:rec.operarEnergia(estado.historialEnergiaHoja(h),'Prueba de hipótesis',c)}});
for(const h of casos){
  const antigua=structuredClone(h);for(const p of antigua.energia.historial.pasos)delete p.formulacion.presionPrescrita;
  const firma=modelo.firmaHoja(antigua),texto=JSON.stringify(antigua),a=energia.compilarEnergia(h),b=energia.compilarEnergia(antigua);
  check(JSON.stringify(a.inicial)===JSON.stringify(b.inicial),'Compatibilidad de iniciales con hojas antiguas');
  for(const t of [0,1,10])check(JSON.stringify(a.rhs(t,a.inicial))===JSON.stringify(b.rhs(t,b.inicial)),'Compatibilidad de ecuaciones evaluadas');
  check(JSON.stringify(antigua)===texto&&modelo.firmaHoja(antigua)===firma,'Lectura no modifica datos, resultados ni identidad guardada');
  for(const q of final.relacionesSistemaEnergia(h)){
    katex.renderToString(q.latex,{throwOnError:true});checks++;
    check(a.trazabilidad.relaciones.includes(q.latex),'Vista final y procedencia usan las mismas relaciones activas');
  }
}
const uniforme=cambiar(casos[3],{presionUniforme:true,presionPrescrita:false});
check(vol.tipoVolumenControl(uniforme,'dominio')==='movil','Uniformidad no prescribe frontera de presión');
check(!energia.camposEnergia(uniforme).some(c=>c.id==='energia_p'),'Uniformidad no fabrica un dato de presión');
check(!modelo.analizarHoja(uniforme).listo,'No sustituye la presión pendiente por cero');
check(!final.relacionesSistemaEnergia(uniforme).some(q=>q.id==='relacion-presion'),'No muestra presión impuesta cuando no se eligió');
check(roles.variablesVolumen(uniforme,'dominio').find(v=>v.id==='P').papel==='Sin modelo','Presión pendiente no se etiqueta calculada');
const dada=vol.elegirVolumenControl(uniforme,'dominio','presion_dada');
check(modelo.analizarHoja(dada).listo,'Elección explícita cierra la mecánica manual');
const movil=vol.elegirVolumenControl(dada,'dominio','movil');
check(estado.formulacionEnergiaHoja(movil).presionUniforme&&!estado.formulacionEnergiaHoja(movil).presionPrescrita,'Retirar condición de frontera conserva hipótesis espacial');
check(movil.energia.datos.energia_p.texto===dada.energia.datos.energia_p.texto,'Dato inactivo conservado');
const incompat=cambiar(dada,{presionUniforme:false});check(!modelo.analizarHoja(incompat).listo,'Presión prescrita sin reducción mecánica uniforme se diagnostica');
const fijo=vol.guardarGeometria(vol.elegirVolumenControl(casos[2],'dominio','rigido'),'dominio',{texto:'100',unidad:'L'});
const vars=roles.variablesVolumen(fijo,'dominio');
check(vars.some(v=>v.id==='V'&&v.papel==='Dato')&&vars.some(v=>v.id==='V_ocupado'&&v.papel==='Por relación'),'Geometría y volumen ocupado tienen papeles distintos');
check(final.relacionesSistemaEnergia(fijo).some(q=>q.id==='relacion-compatibilidad-volumen'),'Dominio completo y densidad constante hacen visible su restricción de masa');
const base=final.relacionesSistemaEnergia(casos[3]);
check(base.find(q=>q.id==='relacion-h-1').latex.includes('T_{\\mathrm{ext},1}'),'Entrada constante usa el estado exterior');
check(base.find(q=>q.id==='relacion-h-2').latex.includes('u(T)')&&!base.find(q=>q.id==='relacion-h-2').datos.length,'Salida constante usa el estado del volumen');
const inversa=structuredClone(casos[3]);inversa.config.datos.salida_1_2={texto:'-1',unidad:'kg/s'};
check(final.relacionesSistemaEnergia(inversa).find(q=>q.id==='relacion-h-2').datos.includes('energia_T_2'),'Flujo inverso necesita estado exterior');
const variable=structuredClone(casos[3]);variable.config.datos.salida_1_2={texto:'2-t',unidad:'kg/s'};
for(const q of final.relacionesSistemaEnergia(variable)){katex.renderToString(q.latex,{throwOnError:true});checks++;}
check(final.relacionesSistemaEnergia(variable).some(q=>q.id==='relacion-donante-2'&&q.latex.includes('\\ge')),'Inversión tiene condición de donante explícita');
const adiab=cambiar(casos[3],{adiabatico:true,sinFuenteVolumetrica:true,sinTrabajoViscoso:true,sinFuerzasVolumen:true});
check(!final.relacionesSistemaEnergia(adiab).some(q=>['relacion-calor','relacion-fuente','relacion-viscoso','relacion-fuerzas'].includes(q.id)),'No muestra definiciones de términos retirados');
const sinH=cambiar(casos[3],{entalpia:false});check(final.relacionesSistemaEnergia(sinH).find(q=>q.id==='relacion-h-1').latex.includes('\\overline{(p/\\rho)}'),'Trabajo de flujo explícito cuando no se agrupa en entalpía');
const cierre={modelo:{id:'agua-iapws95',version:'1'},politica:{cantidad:'monofasico',cambioInterno:'prohibido',evaluacion:'equilibrio_estable'}};
const eos=prep.declararCierreDinamico(cargar('estadoTermodinamicoHoja').identificarComponenteEstado(uniforme,1,'7732-18-5'),'dominio',cierre);
const pe=prep.prepararEnsamblajeTermodinamico(cambiar(eos,{modelo:'sin_declarar',densidadConstante:false}),'prueba');
check(pe.solicitud.volumen.frontera.tipo==='sin_relacion','Preparación no convierte uniformidad en presión prescrita');
console.log(`${checks} comprobaciones: presión espacial/dato, compatibilidad antigua, volumen ocupado/geometría, relaciones activas, donantes y procedencia.`);
