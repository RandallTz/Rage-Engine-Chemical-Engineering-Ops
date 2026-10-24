import type {HojaMotor} from './hojasMotor';
import type {CierreDinamico,DatoEnsamblaje,DiagnosticoPreparacion,PreparacionDinamica,CorrienteDinamica,MateriaCorrienteDinamica} from './contratoEnsamblajeTermodinamico';
import type {DatoMotor} from './modeloNumerico';
import {balancesHoja} from './seleccionBalances';
import {volumenesControl,claveGeometria} from './volumenControl';
import {contextoEnergiaHoja,historialEnergiaHoja,formulacionEnergiaHoja} from './estadoEnergiaHoja';
import {balancesComponentes,terminosTotalesMateria} from './recorridoMateria';
import {ecuacionEnergia,terminosEnergia,tienePresionPrescrita} from './recorridoEnergia';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {UNIDADES_MOTOR} from './unidadesMotor';
import {claveCorriente} from './ensamblajeMateria';
import {estructuraSolicitudDinamica} from './estructuraTermodinamica';
import {ensureInventoryExecution} from '../models/dynamicDefinition';
export function puedeExtraerDinamica(c:CorrienteDinamica,volumenId:string,datos:Record<string,DatoEnsamblaje>){
  const ids=c.materia.modo==='por_componente'?Object.values(c.materia.caudalIds):[c.materia.caudalId],signo=c.hasta===volumenId?1:-1;
  return ids.some(id=>{try{return signo*evaluarExpresion(analizarExpresion(datos[id].declaracion.texto,[]),{})<0;}catch{return true;}});
}

/** Explicit closure selection contains no copied TP/UV query data or evaluated properties. */
export function declararCierreDinamico(h:HojaMotor,volumenId:string,cierre:CierreDinamico|null):HojaMotor{
  if(!volumenesControl(h).some(v=>v.id===volumenId))throw new Error('Volumen del cierre no disponible.');
  const cierres={...h.cierresDinamicos};if(cierre)cierres[volumenId]=structuredClone(cierre);else delete cierres[volumenId];
  return {...h,cierresDinamicos:Object.keys(cierres).length?cierres:undefined,resultado:undefined,resultadoRef:undefined};
}
/** Draft serializer only. No property evaluation, algebraic initialization, rank or integration here.
 * It reads current declarations, preserves units and exposes absent data instead of inventing them. */
export function prepararEnsamblajeTermodinamico(h:HojaMotor,solicitudId:string):PreparacionDinamica{
  const vs=volumenesControl(h),diagnosticos:DiagnosticoPreparacion[]=[],owner=vs[0]?.id??'dominio';
  const problema=(codigo:string,estado:DiagnosticoPreparacion['estado'],mensaje:string,ruta:string,variableIds:string[]=[],propietarioId=`volumen:${owner}`)=>diagnosticos.push({codigo,estado,mensaje,variableIds,origen:{propietarioId,ruta}});
  try{ensureInventoryExecution(h);}catch(error){problema('MOTOR_ENS_INVENTORY_CONSTRAINT','no_soportado',(error as Error).message,'/dynamicDefinition');return {solicitud:null,diagnosticos};}
  if(vs.length!==1){problema('MOTOR_ENS_ALCANCE','no_soportado','El primer contrato dinámico admite un volumen; no se omiten los otros.','/ensamblaje/volumenes');return {solicitud:null,diagnosticos};}
  const v=vs[0],f=v.f,e=formulacionEnergiaHoja(h),ctx=contextoEnergiaHoja(h),cierre=h.cierresDinamicos?.[v.id],balances=balancesHoja(h);
  if(!cierre){problema('MOTOR_ENS_CIERRE_PENDIENTE','incompleto','Selecciona un cierre dinámico explícito; una consulta no lo selecciona.',`/cierresDinamicos/${v.id}`);return {solicitud:null,diagnosticos};}
  if(!cierre.modelo.id||!cierre.modelo.version)problema('MOTOR_ENS_MODELO_PENDIENTE','incompleto','Modelo y versión sin declarar.',`/cierresDinamicos/${v.id}/modelo`);
  if(!balances.materia||!balances.energia||balances.momento)problema('MOTOR_ENS_BALANCES','no_soportado','Primera entrega: materia y energía activas, momento no ejecutado.','/balances');
  if((f.componentes??[]).length!==1)problema('MOTOR_ENS_COMPONENTES','no_soportado','La primera entrega física admite un componente.','/componentes');
  for(const c of f.componentes??[])if(!c.identidadQuimica?.cas&&!c.identidadQuimica?.proveedorId)problema('MOTOR_ENS_IDENTIDAD','incompleto','Identidad química sin declarar; no se deduce del nombre.',`/componentes/${c.id}/identidadQuimica`);
  if(f.vista!=='cantidad'||f.cantidadVolumen||e.forma!=='total')problema('MOTOR_ENS_FORMA','no_soportado','Se necesitan las formas totales de cantidades y energía; no se reducen campos automáticamente.','/formulacion');
  if(e.modelo==='u_lineal')problema('MOTOR_ENS_DOS_CIERRES','conflicto','La relación manual u(T) y el cierre termodinámico no pueden determinar el mismo estado.','/energia/historial');
  if(e.densidadConstante||f.densidadMediaConstante||f.densidadComunPuertos||f.reglasEstado?.densidades?.some(d=>d.constanciaTemporal!=='sin_restriccion'))problema('MOTOR_ENS_DENSIDAD','conflicto','La densidad declarada constante debe tratarse como restricción adicional, no como sustituto de la EOS.','/formulacion/densidades');
  if(f.reglasEstado?.fases){const p=f.reglasEstado.fases;if((p.cantidad==='monofasico')!==(cierre.politica.cantidad==='monofasico')||(p.cambioInterno==='sin_cambio_de_fase')!==(cierre.politica.cambioInterno==='prohibido'))problema('MOTOR_ENS_POLITICA','conflicto','Las hipótesis de materia y del cierre de fase discrepan.','/formulacionMateria/reglasEstado/fases');}
  if(e.monofasico!==(cierre.politica.cantidad==='monofasico')||e.sinCambioFase!==(cierre.politica.cambioInterno==='prohibido'))problema('MOTOR_ENS_POLITICA','conflicto','Las hipótesis de energía y del cierre de fase discrepan.','/energia/historial');
  if(!e.uniforme||!e.sinCinetica||!e.separarPresion||!e.sinTrabajoViscoso||!e.sinFuerzasVolumen||!e.sinFuenteVolumetrica||e.trabajoTotalHeredado)problema('MOTOR_ENS_TERMINOS','no_soportado','El primer régimen dinámico requiere estado uniforme y una primera ley sin cinética, esfuerzos viscosos ni otras fuentes sin modelo.','/formulacionEnergia');
  if(e.estacionario||e.sinAcumulacionTotal||f.sinAcumulacion||f.campo.estacionario)problema('MOTOR_ENS_ESTACIONARIO','no_soportado','Este primer contrato es temporal; no convierte un estacionario en condición inicial.','/formulacion/acumulacion');
  if(!ctx.restoCerrado||terminosTotalesMateria(f).some(t=>['generacion','consumo'].includes(t.rol)))problema('MOTOR_ENS_FUENTES','no_soportado','El primer régimen no ejecuta intercambio restante ni fuentes materiales sin energía asociada.','/formulacionMateria');
  if(JSON.stringify(historialEnergiaHoja(h).pasos.at(-1)!.contexto)!==JSON.stringify(ctx))problema('MOTOR_ENS_CONTEXTO','conflicto','El desglose energético no corresponde al volumen y puertos actuales.','/energia/historial');
  const datos:Record<string,DatoEnsamblaje>={};
  function agregar(id:string,magnitud:DatoEnsamblaje['magnitud'],funcion:DatoEnsamblaje['funcion'],dato:DatoMotor|undefined,ruta:string,propietarioId=`volumen:${v.id}`){
    const declaracion=structuredClone(dato??{texto:'',unidad:Object.keys(UNIDADES_MOTOR[magnitud])[0]});
    if(Object.hasOwn(datos,id))throw new Error(`Dato repetido: ${id}`);
    datos[id]={magnitud,funcion,declaracion,origen:{propietarioId,ruta}};
    if(!declaracion.texto.trim())problema('MOTOR_ENS_DATO_PENDIENTE','incompleto','Dato sin declarar.',ruta,[id],propietarioId);
    else if(!Object.hasOwn(UNIDADES_MOTOR[magnitud],declaracion.unidad))problema('MOTOR_ENS_UNIDAD','invalido','Unidad incompatible con la magnitud.',ruta,[id],propietarioId);
    return id;
  }
  const masaIds=Object.fromEntries((f.componentes??[]).map(c=>{const key=h.ensamblaje?`${v.id}__inicial_${c.id}`:`inicial_${c.id}`;return [c.id,agregar(`volumen.${v.id}.m0.${c.id}`,'masa','inicial',h.config.datos[key],`/config/datos/${key}`)];}));
  const inicial=h.energia?.inicial??'T',keyInicial=inicial==='T'?'energia_T0':'energia_U0';
  const datoId=agregar(`volumen.${v.id}.${inicial}0`,inicial==='T'?'temperatura':'energia','inicial',h.energia?.datos[keyInicial],`/energia/datos/${keyInicial}`);
  const dada=tienePresionPrescrita(e,ctx);
  const frontera=f.fija?{tipo:'rigida' as const,datoId:agregar(`volumen.${v.id}.V`,'volumen','geometria',h.config.datos[claveGeometria(h,v.id)],`/config/datos/${claveGeometria(h,v.id)}`),...(dada?{presionRestriccionId:agregar(`volumen.${v.id}.Prestriccion`,'presion','frontera',h.energia?.datos.energia_p,'/energia/datos/energia_p')}: {})}:dada?{tipo:'presion_prescrita' as const,presionId:agregar(`volumen.${v.id}.Pext`,'presion','frontera',h.energia?.datos.energia_p,'/energia/datos/energia_p')}:{tipo:'sin_relacion' as const};
  if(dada&&!e.presionUniforme)problema('MOTOR_ENS_P_UNIFORME','conflicto','La frontera de presión prescrita necesita equilibrio mecánico con presión uniforme.','/formulacionEnergia/presionUniforme');
  if(frontera.tipo==='rigida'&&frontera.presionRestriccionId)problema('MOTOR_ENS_P_RIGIDA','conflicto','La presión prescrita es una restricción adicional al cierre UV; requiere compatibilidad, no se descarta.', '/energia/datos/energia_p',[frontera.presionRestriccionId]);
  if(frontera.tipo==='sin_relacion')problema('MOTOR_ENS_MECANICA','incompleto','La frontera móvil necesita su relación mecánica.','/formulacionMateria/fija');
  const corrientes:CorrienteDinamica[]=[];
  const fuentes=h.ensamblaje?.corrientes??f.fronteras.map(p=>({id:p.id,desde:p.sentido==='entrada'?null:v.id,hasta:p.sentido==='salida'?null:v.id,mecanismo:null,componentesIds:(f.componentes??[]).map(c=>c.id),datos:undefined}));
  for(const [indice,s]of fuentes.entries()){
    const propietarioId=`corriente:${s.id}`,root=h.ensamblaje?`/ensamblaje/corrientes/${indice}/datos`:'/config/datos',ids=s.componentesIds??(f.componentes??[]).map(c=>c.id),m=s.datos?.materia;
    if(s.desde===s.hasta||s.desde!==v.id&&s.hasta!==v.id)problema('MOTOR_ENS_TOPOLOGIA','invalido','Corriente sin conexión válida al volumen.',root,[],propietarioId);
    if(s.mecanismo==='selectivo')problema('MOTOR_ENS_SELECTIVO','no_soportado','La transferencia selectiva requiere una ley energética propia.',root,[],propietarioId);
    let materia:MateriaCorrienteDinamica;
    if(m&&ids.some(id=>!!h.config.datos[claveCorriente(s.id,id)])||m&&h.config.datos[`s${s.id}__total`])problema('MOTOR_ENS_F_DUPLICADO','conflicto','El caudal está declarado en la corriente y en el banco legado.',root,[],propietarioId);
    if(m?.modo==='total_y_composicion')materia={modo:m.modo,base:m.base,caudalId:agregar(`corriente.${s.id}.F`,m.base==='molar'?'caudal_molar':'caudal','frontera',m.caudalTotal,`${root}/materia/caudalTotal`,propietarioId),composicion:structuredClone(m.composicion)};
    else materia={modo:'por_componente',base:m?.base??'masica',caudalIds:Object.fromEntries(ids.map(id=>{const key=h.ensamblaje?claveCorriente(s.id,id):`${s.hasta===v.id?'entrada':'salida'}_${id}_${s.id}`;const dato=m?.modo==='por_componente'?m.caudales[id]:h.config.datos[key];return [id,agregar(`corriente.${s.id}.F.${id}`,m?.base==='molar'?'caudal_molar':'caudal','frontera',dato,m?`${root}/materia/caudales/${id}`:`/config/datos/${key}`,propietarioId)];}))};
    const caudales=materia.modo==='por_componente'?Object.values(materia.caudalIds):[materia.caudalId];
    // Only a provably outward constant stream can omit an exterior donor state.
    const signo=s.hasta===v.id?1:-1;
    const requiereExterior=caudales.some(id=>{try{const flujo=evaluarExpresion(analizarExpresion(datos[id].declaracion.texto,[]),{});return !Number.isFinite(flujo)||signo*flujo>0;}catch{return true;}});
    let estadoExterior:CorrienteDinamica['estadoExterior'];
    if(requiereExterior){
      const Tlegacy=h.energia?.datos[`energia_T_${s.id}`];
      if(s.datos?.T&&Tlegacy)problema('MOTOR_ENS_T_DUPLICADA','conflicto','La temperatura está declarada en la corriente y en energía.',`${root}/T`,[],propietarioId);
      const P=s.datos?.P??(!h.ensamblaje?h.config.datos[`corriente_${s.id}_P`]:undefined),rutaP=h.ensamblaje?`${root}/P`:`/config/datos/corriente_${s.id}_P`;
      const continuidad=cierre.presionesCorrientes?.[s.id]==='continuidad';
      const Pid=!continuidad||P?agregar(`corriente.${s.id}.Pext`,'presion','frontera',P,rutaP,propietarioId):undefined;
      if(continuidad&&Pid)problema('MOTOR_ENS_P_DUPLICADA','conflicto','La presión está vinculada por continuidad y además declarada como dato.',rutaP,[Pid],propietarioId);
      estadoExterior={tipo:'TP',temperaturaId:agregar(`corriente.${s.id}.Text`,'temperatura','frontera',s.datos?.T??Tlegacy,s.datos?.T?`${root}/T`:`/energia/datos/energia_T_${s.id}`,propietarioId),presion:continuidad?{tipo:'continuidad',volumenId:v.id,...(Pid?{restriccionAdicionalId:Pid}:{})}:{tipo:'dato',datoId:Pid!}};
    }
    const extraccion=cierre.extracciones?.[s.id];
    const corriente:CorrienteDinamica={id:s.id,desde:s.desde,hasta:s.hasta,componenteIds:ids,mecanismo:s.mecanismo??null,materia,...(extraccion?{extraccion:structuredClone(extraccion)}:{}),...(estadoExterior?{estadoExterior}:{})};
    if(cierre.politica.cantidad!=='monofasico'&&puedeExtraerDinamica(corriente,v.id,datos)&&!extraccion)problema('MOTOR_ENS_EXTRACCION','incompleto','Si hay varias fases, declara cómo se extrae materia del volumen.',`/cierresDinamicos/${v.id}/extracciones/${s.id}`,[],propietarioId);
    corrientes.push(corriente);
  }
  const transferencias:Record<string,string>={};
  for(const t of terminosEnergia(e,ctx))if(t.id==='calor')transferencias[t.id]=agregar(`volumen.${v.id}.Q`,'potencia','frontera',h.energia?.datos.energia_Q,'/energia/datos/energia_Q');
  const tiempoId=agregar('estudio.tfinal','tiempo','estudio',h.config.tiempo,'/config/tiempo','estudio');
  const {componentes:_,fronteras:__,...formulacionMateria}=f;void _;void __;
  const hm=h.ensamblaje?h.ensamblaje.volumenes[0].historial:h.historial;
  const solicitud={revision:1 as const,solicitudId,componentes:structuredClone(f.componentes??[]),volumen:{id:v.id,componenteIds:(f.componentes??[]).map(c=>c.id),balances,formulacionMateria:structuredClone(formulacionMateria),formulacionEnergia:structuredClone(e),contextoEnergia:structuredClone(ctx),cierre:structuredClone(cierre),frontera,inicial:{masaIds,energia:{tipo:inicial,datoId}}},corrientes,datos,transferencias,estudio:{tipo:'temporal' as const,tiempoId,metodoSolicitado:h.config.metodo,muestras:h.config.muestras,rtol:h.config.rtol,atol:{masa:h.config.atol,energia:h.energia?.atol??1e-6}},derivacion:{materia:hm.pasos.slice(0,hm.activo+1).map(p=>({titulo:p.titulo,ecuaciones:balancesComponentes(p.formulacion).map(q=>q.latex)})),energia:historialEnergiaHoja(h).pasos.map(p=>({titulo:p.titulo,ecuacion:ecuacionEnergia(p.formulacion,p.contexto),relaciones:structuredClone(p.relaciones)}))}};
  return {solicitud,diagnosticos,estructura:estructuraSolicitudDinamica(solicitud)};
}
