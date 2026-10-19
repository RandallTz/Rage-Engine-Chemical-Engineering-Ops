import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';import katex from 'katex';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const modelo=cargar('modeloHojaMotor'),en=cargar('modeloEnergia'),rec=cargar('recorridoEnergia'),estado=cargar('estadoEnergiaHoja'),ej=cargar('hojasPruebaEnergia');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},cerca=(v,r,t,m)=>check(Math.abs(v-r)<=t,`${m}: ${v} / ${r}`);
for(const h of ej.crearHojasPruebaEnergia()){
 const a=modelo.analizarHoja(h);check(a.listo,JSON.stringify(a));
 for(const campo of a.campos){katex.renderToString(campo.simbolo,{throwOnError:true});checks++;}
 const puertos=estado.contextoEnergiaHoja(h).puertos.length,algebraicas=1+(puertos?1:0)+puertos;
 check(a.ecuaciones===2+algebraicas,'Recuento incluye relaciones algebraicas T, V y h junto a los balances');
 for(const p of h.energia.historial.pasos){katex.renderToString(rec.ecuacionEnergia(p.formulacion,p.contexto),{throwOnError:true});checks++;for(const r of p.relaciones){katex.renderToString(r,{throwOnError:true});checks++;}}
 const s=en.compilarEnergia(h),r=await modelo.resolverHoja(h);check(r.estado==='resuelto',r.mensaje);check(s.variablesNumericas[1].unidad==='J'&&s.variablesNumericas[1].restriccion==='libre','Energía no tratada como masa');
 check(r.seriesEvaluadas.every(q=>q.valores.length===r.tiempos.length&&q.valores.every(Number.isFinite)),'Series y unidades coherentes');
 check(r.conservacion.every(v=>Math.abs(v)<1e-6),`Presupuesto: ${r.conservacion}`);
 console.log(h.nombre,r.seriesEvaluadas.find(q=>q.id==='T').valores.at(-1),r.conservacion);
}


const unidades=cargar('unidadesMotor'),materia=cargar('recorridoMateria'),red=cargar('ensamblajeMateria'),almacen=cargar('hojasMotor'),seleccion=cargar('seleccionBalances'),graficas=cargar('datosGraficasMotor');
const casos=ej.crearHojasPruebaEnergia(),param=(h,id,v,u)=>{h.energia.datos[`energia_${id}`]={texto:String(v),unidad:u};return h;};
// Los supuestos termodinámicos (fases, cambio de fase, densidad, u(T)) se declaran en la derivación termodinámica
// de la hoja, no en la de energía (cada ecuación en su lugar); el resto, en la de energía.
const termo=cargar('recorridoTermodinamico'),CLAVES_TERMO=new Set(termo.CLAVES_TERMO);
function hip(h,titulo,cambios){const t=Object.fromEntries(Object.entries(cambios).filter(([k])=>CLAVES_TERMO.has(k))),e=Object.fromEntries(Object.entries(cambios).filter(([k])=>!CLAVES_TERMO.has(k)));if(Object.keys(t).length)h.recorridoTermodinamico=termo.operarTermo(termo.recorridoTermoHoja(h),titulo,t);if(Object.keys(e).length)h.energia.historial=rec.operarEnergia(h.energia.historial,titulo,e);return h;}
function serie(r,id){return r.seriesEvaluadas.find(q=>q.id===id).valores;}
const referencia=(j,t)=>j===0?{m:10,T:293.15+1000*t/(10*4000)}:j===1?{m:10,T:293.15+30*Math.exp(-100*t/(10*4000))}:j===2?{m:100,T:333.15+(293.15-333.15)*Math.exp(-2*t/100)}:j===3?{m:100+t,T:313.15+8000/(3*4000)+(293.15-313.15-8000/(3*4000))*(100/(100+t))**3}:j===4?{m:100-t,T:283.15+(323.15-283.15)*(100-t)/100}:{m:100+t,T:333.15-40*(100/(100+t))**2};
for(let j=0;j<casos.length;j++)for(const metodo of ['rk45','euler_implicito']){
 const h=structuredClone(casos[j]);h.config.metodo=metodo;h.config.rtol=1e-9;
 const r=await modelo.resolverHoja(h);check(r.estado==='resuelto',r.mensaje);const compilado=en.compilarEnergia(h);
 r.tiempos.forEach((t,k)=>{const esperado=referencia(j,t);cerca(serie(r,'m_1')[k],esperado.m,1e-8,'Masa analítica');cerca(serie(r,'T')[k],esperado.T,metodo==='rk45'?1e-7:3e-4,'Temperatura analítica');const x=compilado.evaluarEnergia(t,r.valores[k].map(v=>v[0]));cerca(x.dU,4000*x.m*(j===0?1000/(10*4000):j===1?100*(293.15-x.T)/(10*4000):j===2?2*(333.15-x.T)/100:j===3?(3*4000*(313.15-x.T)+8000)/(4000*x.m):j===4?(283.15-x.T)/x.m:2*(333.15-x.T)/x.m)+(4000*(x.T-293.15))*x.dm,5e-7,'Producto u dm/dt + m c dT/dt');});
 console.log(`${metodo} · caso ${j+1}: error T máximo ${Math.max(...r.tiempos.map((t,k)=>Math.abs(serie(r,'T')[k]-referencia(j,t).T))).toExponential(3)} K`);
 check(r.componentes.length===1&&r.componentes[0].id===1,'U no se introduce como componente químico ficticio');
 const g=graficas.datosGraficasMotor(h,r,'tiempo');check(g.variables.find(q=>q.id==='U').unidad==='J'&&g.variables.find(q=>q.id==='T').unidad==='K','Resultados heterogéneos con unidades');check(g.filas.every(q=>Number.isFinite(q.U)&&Number.isFinite(q.T)),'Tablero y tabla usan datos evaluados');
}
// Temperature-form RK4 oracle, written independently from the U-coordinate compiler.
const nonlinear=ej.crearHojaPruebaEnergia('Nombre libre',100,3,2,323.15,303.15,'-100*(T-293.15)*abs(T-293.15)',20,true);
const nr=await modelo.resolverHoja(nonlinear);let T=323.15,t=0;
const fun=(t,T)=>(3*4000*(303.15-T)-100*(T-293.15)*Math.abs(T-293.15))/(4000*(100+t));
for(let k=1;k<nr.tiempos.length;k++){
 const fin=nr.tiempos[k];while(t<fin-1e-14){const dt=Math.min(.002,fin-t),a=fun(t,T),b=fun(t+dt/2,T+dt*a/2),c=fun(t+dt/2,T+dt*b/2),d=fun(t+dt,T+dt*c);T+=dt*(a+2*b+2*c+d)/6;t+=dt;}
 cerca(serie(nr,'T')[k],T,2e-7,'Referencia independiente escrita en T');
}
// Reference offsets may make U negative; this does not exhaust matter or change T.
const original=await modelo.resolverHoja(casos[3]),offset=structuredClone(casos[3]);param(offset,'u_ref',-2e6,'J/kg');
const ro=await modelo.resolverHoja(offset);check(ro.estado==='resuelto'&&serie(ro,'U').every(v=>v<0),'U negativa válida por referencia');
ro.tiempos.forEach((_,i)=>cerca(serie(ro,'T')[i],serie(original,'T')[i],1e-8,'Referencia energética no cambia T'));
const otraRef=structuredClone(casos[3]);param(otraRef,'T_ref',500,'K');param(otraRef,'u_ref',4000*(500-293.15),'J/kg');const rr=await modelo.resolverHoja(otraRef);rr.tiempos.forEach((_,i)=>cerca(serie(rr,'T')[i],serie(original,'T')[i],1e-8,'Referencia fuera del dominio de estados no impone estado térmico'));
const expandida=hip(structuredClone(casos[3]),'Separar transporte interno y trabajo de flujo',{entalpia:false});const re=await modelo.resolverHoja(expandida);re.tiempos.forEach((_,i)=>cerca(serie(re,'T')[i],serie(original,'T')[i],1e-9,'u + trabajo de flujo equivale a h'));
check(re.trazabilidadEnergia.terminos.some(q=>q.id==='presion_flujo_1')&&!original.trazabilidadEnergia.terminos.some(q=>q.id==='presion_flujo_1'),'Ensamblaje representa la transformación, sin doble trabajo de flujo');
// Pressure magnitude affects the individual transfers, not the cancelled thermal result.
const altaP=structuredClone(casos[3]);param(altaP,'p',50,'bar');const rp=await modelo.resolverHoja(altaP);rp.tiempos.forEach((_,i)=>cerca(serie(rp,'T')[i],serie(original,'T')[i],1e-8,'Trabajo de frontera cancela el de flujo correspondiente'));
check(serie(rp,'Wb')[0]>0,'Llenado realiza trabajo de expansión');const out=await modelo.resolverHoja(casos[4]);check(serie(out,'Wb')[0]<0,'Vaciado tiene trabajo de frontera con signo opuesto');
const equivalentes=structuredClone(casos[3]);param(equivalentes,'c',4,'kJ/(kg K)');param(equivalentes,'T0',20,'degC');param(equivalentes,'T_ref',20,'degC');param(equivalentes,'T_1',104,'degF');param(equivalentes,'p',1,'bar');param(equivalentes,'Q',8,'kW');equivalentes.config.tiempo={texto:'2',unidad:'min'};
const ru=await modelo.resolverHoja(equivalentes);ru.tiempos.forEach((_,i)=>cerca(serie(ru,'T')[i],serie(original,'T')[i],1e-9,'Unidades equivalentes con temperatura absoluta'));
cerca(unidades.convertirUnidad('temperatura',32,'degF'),273.15,1e-12,'Fahrenheit absoluto');assert.throws(()=>unidades.factorUnidad('temperatura','degC'),/desplazamiento/);checks++;
// No unnecessary mass state when matter is inactive and the volume is closed.
const solo=seleccion.seleccionarBalance(structuredClone(casos[0]),'materia',false),so=en.compilarEnergia(solo),rs=await modelo.resolverHoja(solo);
check(so.inicial.length===1&&so.variablesNumericas[0].id==='U'&&rs.balancesEjecutados.join(',')==='energia','Solo U se integra con masa cerrada como dato');check(modelo.analizarHoja(solo).totalIniciales===1,'Una condición inicial energética; masa es parámetro');
cerca(serie(rs,'T').at(-1),300.65,1e-9,'Energía sola conserva solución');
const inicialU=structuredClone(casos[0]);inicialU.energia.inicial='U';param(inicialU,'U0',0,'kJ');const rU=await modelo.resolverHoja(inicialU);cerca(serie(rU,'T').at(-1),300.65,1e-9,'U0 y T0 son especificaciones alternativas');
const adiabatico=hip(structuredClone(casos[0]),'Frontera adiabática',{adiabatico:true}),ra=await modelo.resolverHoja(adiabatico);check(serie(ra,'T').every(v=>v===293.15),'Adiabático conserva U');check(ra.trazabilidadEnergia.datosInactivos.includes('energia_Q'),'Dato de un término retirado queda identificado como inactivo');
// Finite thermal domains terminate before an invalid point is published, including t=0.
for(const metodo of ['rk45','euler_implicito']){
 const evento=structuredClone(casos[0]);evento.config.metodo=metodo;param(evento,'T_max',295.15,'K');const r=await modelo.resolverHoja(evento);
 check(r.estado==='parcial'&&r.mensaje.includes('térmico superior'),'Evento térmico');cerca(r.tiempos.at(-1),80,2e-7,'Instante analítico del límite térmico');check(serie(r,'T').every(T=>T>=273.15&&T<=295.15),'Cada muestra dentro de dominio');
 const borde=structuredClone(evento);param(borde,'T0',295.15,'K');const r0=await modelo.resolverHoja(borde);check(r0.estado==='parcial'&&r0.tiempos.length===1&&r0.tiempos[0]===0,'Salida de dominio desde la condición inicial');
}
const trabajo=hip(structuredClone(casos[0]),'Activar potencias declaradas',{sinTrabajoViscoso:false,sinFuerzasVolumen:false,sinFuenteVolumetrica:false});param(trabajo,'Wtau',100,'W');param(trabajo,'Wb',200,'W');param(trabajo,'R',300,'W');const rw=await modelo.resolverHoja(trabajo);cerca(serie(rw,'T').at(-1),293.15+1600*300/(10*4000),1e-8,'Potencias provienen de los mismos términos renderizados');
 for(const [id,v] of [['Wtau',100],['Wf',200],['R',300]])check(serie(rw,id).every(x=>x===v),'Toda potencia activa se puede visualizar y graficar');
// Single-volume stream adapter: do not duplicate thermal inputs in config and stream.
const graph=structuredClone(casos[3]);Object.assign(graph,red.iniciarEnsamblaje(graph.historial,graph.config));graph.energia.historial=rec.operarEnergia(graph.energia.historial,'Vincular al volumen de la red',{},[],estado.contextoEnergiaHoja(graph));
const rg=await modelo.resolverHoja(graph);rg.tiempos.forEach((_,i)=>cerca(serie(rg,'T')[i],serie(original,'T')[i],1e-9,'Mismo balance a través del adaptador de corrientes'));
const guardado=estado.actualizarConfiguracionEnergia(graph,modelo.configuracionHoja(graph));check(guardado.ensamblaje.corrientes[0].datos.T&&!guardado.energia.datos.energia_T_1,'Temperatura de corriente con una única especificación');
check(modelo.analizarHoja(guardado).listo,'Reabrir especificación migrada');
const rg2=await modelo.resolverHoja(guardado);cerca(serie(rg2,'T').at(-1),serie(original,'T').at(-1),1e-9,'Especificación en corriente realmente usada');
 const totalComp=structuredClone(guardado);
 for(const s of totalComp.ensamblaje.corrientes)s.datos.materia={modo:'total_y_composicion',base:'masica',caudalTotal:s.datos.materia.caudales[1],composicion:{base:'masica',fracciones:{1:1}}};
 check(!en.camposEnergia(totalComp).some(p=>p.id==='energia_T_2'),'Salida constante con total y composición no inventa temperatura exterior');
 const rtc=await modelo.resolverHoja(totalComp);cerca(serie(rtc,'T').at(-1),serie(original,'T').at(-1),1e-9,'Caudal total y composición conserva ensamblaje energético');
 const duplicada=structuredClone(guardado);param(duplicada,'T_1',313.15,'K');check(!modelo.analizarHoja(duplicada).listo,'Dos fuentes de temperatura de entrada se diagnostican');
 const presionContraria=structuredClone(guardado);presionContraria.ensamblaje.corrientes[0].datos.P={texto:'2',unidad:'bar'};assert.throws(()=>modelo.compilarHoja(presionContraria),/presión incompatible/);checks++;
// Donor state follows the net direction, not just the port's label.
const inversa=structuredClone(casos[3]);inversa.config.datos.entrada_1_1={texto:'-2',unidad:'kg/s'};inversa.config.datos.salida_1_2={texto:'-3',unidad:'kg/s'};param(inversa,'T_2',313.15,'K');const ri=await modelo.resolverHoja(inversa);ri.tiempos.forEach((_,i)=>cerca(serie(ri,'T')[i],serie(original,'T')[i],1e-9,'Invertir orientación y caudal conserva la física del donante'));
// Required physical choices remain explicit. Unsupported models are never silently simplified.
for(const [titulo,mutar] of [
 ['Dos componentes',h=>{h.historial=materia.recorridoMateria(h.historial,{tipo:'cambiar',titulo:'Otro componente',cambios:{componentes:[{id:1,nombre:'A',simbolo:'A'},{id:2,nombre:'B',simbolo:'B'}]}});}],
 ['Sin relación energética',h=>hip(h,'Retirar modelo',{modelo:'sin_declarar'})],
 ['Sin estado uniforme',h=>hip(h,'Retirar uniformidad',{uniforme:false})],
 ['Sin hipótesis de fase',h=>hip(h,'Retirar monofásico',{monofasico:false})],
 ['Cinética activa',h=>hip(h,'Restaurar cinética',{sinCinetica:false})],
 ['Energía estacionaria',h=>hip(h,'Retirar acumulación total',{sinAcumulacionTotal:true})],
 ['Propiedad ausente',h=>{delete h.energia.datos.energia_c;}],
 ['Unidad incompatible',h=>{h.energia.datos.energia_c.unidad='kg';}],
 ['C negativa',h=>param(h,'c',-1,'J/(kg K)')],
 ['Sin masa inicial',h=>{h.config.datos.inicial_1={texto:'',unidad:'kg'};}],
 ['Ausencia distinta de cero',h=>param(h,'Q','','W')],
 ['Temperatura inicial fuera',h=>param(h,'T0',400,'K')],
 ]){
 const h=structuredClone(casos[0]);mutar(h);check(!modelo.analizarHoja(h).listo,titulo);await assert.rejects(modelo.resolverHoja(h));checks++;
}
for(const [titulo,mutar] of [
 ['Recipiente inicialmente vacío',h=>{h.config.datos.inicial_1.texto='0';}],
 ['U0 fuera del dominio',h=>{h.energia.inicial='U';param(h,'U0',1e12,'J');}],
 ]){const h=structuredClone(casos[0]);mutar(h);check(!modelo.analizarHoja(h).listo,`${titulo}: diagnóstico antes de resolver`);assert.throws(()=>modelo.compilarHoja(h));checks++;}
const fija=structuredClone(casos[3]);fija.historial=materia.recorridoMateria(fija.historial,{tipo:'cambiar',titulo:'Fijar frontera',cambios:{fija:true}});fija.energia.historial=rec.operarEnergia(fija.energia.historial,'Actualizar geometría',{},[],estado.contextoEnergiaHoja(fija));assert.throws(()=>modelo.compilarHoja(fija),/densidad constante/);checks++;
const sinRetorno=structuredClone(inversa);delete sinRetorno.energia.datos.energia_T_2;check(!modelo.analizarHoja(sinRetorno).listo,'No inventar temperatura exterior en inversión');
const q0=structuredClone(casos[0]);param(q0,'Q',0,'W');check(modelo.analizarHoja(q0).listo,'Cero explícito cuenta como dato');
// Mathematical journal: raw first equation, identities, stationary frame distinction, undo and redo.
const ctx=estado.contextoEnergiaHoja(casos[3]),raw=rec.iniciarEnergia(ctx),total=rec.transformarEnergia(raw,'total');
check(total.pasos.length===4&&total.pasos[1].titulo.includes('Gauss')&&total.pasos[2].titulo.includes('Reynolds'),'Llegar a total conserva todos los pasos intermedios');
const cancelado=rec.volverEnergia(total,1);check(cancelado.pasos.length===2&&cancelado.rehacer.length===2,'Pasos cancelados se eliminan, no quedan transparentes');check(rec.rehacerEnergia(cancelado).pasos.length===3,'Rehacer conserva la derivación');
const derivacion=rec.operarEnergia(cancelado,'Otra hipótesis',{adiabatico:true});check(!derivacion.rehacer.length,'Una nueva operación sustituye los pasos descartados');
const localAdiab=rec.operarEnergia(raw,'Frontera adiabática',{adiabatico:true});check(rec.ecuacionEnergia(rec.actualEnergia(localAdiab).formulacion,ctx).includes('mathbf q'),'Adiabático no elimina conducción local');
const macroAdiab=rec.transformarEnergia(localAdiab,'total');check(!rec.terminosEnergia(rec.actualEnergia(macroAdiab).formulacion,ctx).some(t=>t.id==='calor'),'Frontera adiabática elimina Q total');
const est={...rec.ENERGIA_FUNDAMENTAL,forma:'total',estacionario:true};check(rec.ecuacionEnergia(est,ctx).startsWith('\\frac{dE}'),'Estacionario local no anula acumulación de dominio móvil');check(rec.ecuacionEnergia(est,{...ctx,fija:true}).startsWith('0='),'Dominio fijo permite deducir acumulación total nula');
// Independent RTT/Gauss reference on a moving 1D control interval, without solving a PDE.
for(const t of [0,.2,.8,1.5]){
 const L=t=>1+.3*t,a=t=>2+t*t,b=t=>1+.2*t,E=t=>a(t)*L(t)**3/3+b(t)*L(t),dt=1e-5;
 const local=2*t*L(t)**3/3+.2*L(t),frontera=(a(t)*L(t)**2+b(t))*.3;
 cerca((E(t+dt)-E(t-dt))/(2*dt),local+frontera,2e-8,'Reynolds con frontera móvil');
 const F=x=>x*x*x+2*x,dF=x=>3*x*x+2;let integral=0,n=1000,dx=L(t)/n;for(let j=0;j<n;j++)integral+=dF((j+.5)*dx)*dx;
 cerca(integral,F(L(t))-F(0),1e-6,'Gauss 1D en referencia independiente');
}
for(let mask=0;mask<128;mask++)for(const forma of ['local','integrada','integral','total'])for(const fija of [false,true]){
 const f={...rec.ENERGIA_FUNDAMENTAL,forma,separarPresion:true,entalpia:!!(mask&1),sinCinetica:!!(mask&2),sinTrabajoViscoso:!!(mask&4),sinFuerzasVolumen:!!(mask&8),sinFuenteVolumetrica:!!(mask&16),adiabatico:!!(mask&32),estacionario:!!(mask&64)};
 katex.renderToString(rec.ecuacionEnergia(f,{...ctx,fija}),{throwOnError:true});checks++;
 for(const r of rec.relacionesEnergia(f,{...ctx,fija})){katex.renderToString(r,{throwOnError:true});checks++;}
}
// Persistence, sharing of component IDs, and material compatibility with inactive energy.
const memoria=new Map();globalThis.window=new EventTarget();globalThis.localStorage={getItem:k=>memoria.get(k)??null,setItem:(k,v)=>memoria.set(k,String(v))};
const legado=cargar('hojasPruebaMateria').crearHojasPruebaMateria()[0],firma=modelo.firmaHoja(legado),agregado={...legado,energia:structuredClone(casos[0].energia)};
check(modelo.firmaHoja(agregado)===firma,'Energía inactiva no cambia el modelo material anterior');
almacen.guardarHoja(casos[3]);const antes=almacen.leerHojas()[0];const copia=almacen.duplicarHoja(antes);check(copia.energia.historial.pasos.length===antes.energia.historial.pasos.length&&copia.balances.energia,'Duplicar conserva ambos balances en la misma hoja');
almacen.guardarHoja({...antes,vistaBalance:'materia'});check(almacen.leerHojas()[0].energia.datos.energia_c.texto==='4000','Cambiar vista conserva especificaciones energéticas');
const reabierta=await modelo.resolverHoja(almacen.leerHojas()[0]);cerca(serie(reabierta,'T').at(-1),serie(original,'T').at(-1),1e-9,'Reabrir y resolver da el mismo resultado');
const llenado=casos[5],rl=await modelo.resolverHoja(llenado);
check(llenado.tableroIniciado&&llenado.graficas[0].y[0]==='m_1'&&llenado.graficas[1].y[0]==='T','Caso nuevo: masa y temperatura visibles en paralelo');
cerca(serie(rl,'m_1').at(-1),200,1e-9,'Caso nuevo: masa acumulada a 100 s');
cerca(serie(rl,'T').at(-1),323.15,1e-7,'Caso nuevo: temperatura a 100 s');
cerca(serie(rl,'V').at(-1),.2,1e-12,'Caso nuevo: volumen aumenta con la masa');
check(rl.trazabilidadEnergia.datosUsados.includes('energia_T_1'),'Caso nuevo: energía de entrada declarada, sin añadir calor externo');
almacen.guardarHoja(casos[0]);const conservada=almacen.leerHojas().find(h=>h.id===casos[0].id);check(almacen.guardarHojasNuevas(casos)===4,'Añadir ejemplos agrega solo los documentos nuevos');
check(almacen.leerHojas().find(h=>h.id===conservada.id).actualizada===conservada.actualizada,'Añadir llenado conserva las hojas ya guardadas');
console.log(`${checks} comprobaciones: fundamentos, transformaciones, presupuestos, referencias independientes, unidades, eventos, selección y compatibilidad material.`);
