import { configuredClosure, thermodynamicJournalInRequest, thermodynamicJournalMatches, emptyEnergyJournal, energyJournalFromHistory, energyJournalInRequest, energyJournalMatches, energyState, sameDocument, derivationFingerprint } from './physicalDerivation';
import type {HojaMotor} from './hojasMotor';
import {duplicarHoja} from './hojasMotor';
import type {DatoV2,SolicitudEnsamblajeV2,VolumenV2,ExtraccionV2} from './contratoEnsamblajeV2';
import {volumenesControl,claveGeometria} from './volumenControl';
import {formulacionEnergiaHoja,contextoEnergiaHoja} from './estadoEnergiaHoja';
import {prepararEnsamblajeTermodinamico} from './prepararEnsamblajeTermodinamico';
import {balancesHoja} from './seleccionBalances';
import type {PropiedadPura} from './contratoCatalogo';
import { emptyMaterialJournal, journalFromHistory, journalInRequest, journalMatches } from './materialDerivation';

/** The v2 document is authoritative once explicitly adopted. Legacy derivations
 * remain archived on the worksheet; they never supply a second set of inputs. */
export type RedTermodinamica={solicitud:SolicitudEnsamblajeV2;nombres:Record<string,string>;originalesDatosPuros?:Record<string,Record<string,PropiedadPura[]>>;ultimoComponenteId?:number;ultimosElementos?:Partial<Record<'volumen'|'corriente'|'calor',number>>};
export const firmaRed=(s:SolicitudEnsamblajeV2)=>{return JSON.stringify({...s,solicitudId:'',derivacion:derivationFingerprint(s.derivacion)});};
export const solicitudRed=(h:HojaMotor,id:string):SolicitudEnsamblajeV2=>({...structuredClone(h.redTermodinamica!.solicitud),solicitudId:id});
export function cambiarRed(h:HojaMotor,fn:(r:RedTermodinamica)=>void):HojaMotor{
  if(!h.redTermodinamica)throw new Error('Sin ensamblaje multifásico.');
  const red=structuredClone(h.redTermodinamica);fn(red);
  // A deliberate mechanical-boundary edit records its material consequence.
  // Existing stale journals are never repaired from final flags automatically.
  const journal = journalInRequest(red.solicitud.derivacion), previousJournal = journalInRequest(h.redTermodinamica.solicitud.derivacion);
  if (journal && previousJournal) for (const volume of red.solicitud.volumenes) {
    const previous = h.redTermodinamica.solicitud.volumenes.find(item => item.id === volume.id);
    const entry = journal.volumes[volume.id], before = previousJournal.volumes[volume.id];
    if (previous && entry && before && previous.frontera.tipo !== volume.frontera.tipo
      && previous.formulacionMateria.fija !== volume.formulacionMateria.fija
      && JSON.stringify(entry) === JSON.stringify(before) && journalMatches(before, previous.formulacionMateria)) {
      const ids = new Set(entry.operations.map(operation => operation.id));
      let index = entry.operations.length + 1;
      while (ids.has(`mechanical-boundary-${index}`)) index++;
      entry.operations.push({ id: `mechanical-boundary-${index}`, title: 'Update the material boundary with the declared mechanical boundary', changes: { fija: volume.formulacionMateria.fija } });
    }
  }
  const energy=energyJournalInRequest(red.solicitud.derivacion),oldEnergy=energyJournalInRequest(h.redTermodinamica.solicitud.derivacion);
  if(energy&&oldEnergy)for(const volume of red.solicitud.volumenes){
    const previous=h.redTermodinamica.solicitud.volumenes.find(item=>item.id===volume.id),entry=energy.volumes[volume.id],before=oldEnergy.volumes[volume.id];
    if(previous&&entry&&before&&sameDocument(entry,before)&&energyJournalMatches(before,previous.formulacionEnergia)){
      const changes=Object.fromEntries(Object.entries(energyState(volume.formulacionEnergia)).filter(([key,value])=>!sameDocument(value,(energyState(previous.formulacionEnergia) as Record<string,unknown>)[key])));
      if(Object.keys(changes).length){let id=entry.operations.length+1;while(entry.operations.some(op=>op.id===`model-edit-${id}`))id++;entry.operations.push({id:`model-edit-${id}`,title:'Record the first-law consequence of the explicit model edit',changes});}
    }
  }
  const thermodynamics=thermodynamicJournalInRequest(red.solicitud.derivacion),oldThermodynamics=thermodynamicJournalInRequest(h.redTermodinamica.solicitud.derivacion);
  if(thermodynamics&&oldThermodynamics)for(const volume of red.solicitud.volumenes){
    const previous=h.redTermodinamica.solicitud.volumenes.find(item=>item.id===volume.id),entry=thermodynamics.volumes[volume.id],before=oldThermodynamics.volumes[volume.id];
    if(previous&&entry&&before&&sameDocument(entry,before)&&thermodynamicJournalMatches(before,previous.formulacionEnergia,configuredClosure(h.redTermodinamica.solicitud,previous))){
      const changes={...Object.fromEntries(Object.entries(volume.formulacionEnergia).filter(([key])=>['monofasico','sinCambioFase','densidadConstante','modelo'].includes(key))),closure:configuredClosure(red.solicitud,volume)};
      if(!thermodynamicJournalMatches(entry,volume.formulacionEnergia,changes.closure)){
        let id=entry.operations.length+1;while(entry.operations.some(op=>op.id===`state-edit-${id}`))id++;
        entry.operations.push({id:`state-edit-${id}`,title:'Record the explicit thermodynamic package, policy or state-assumption edit',changes});
      }
    }
  }
  const usados=new Set<string>();const recorrer=(v:unknown)=>{if(typeof v==='string'&&Object.hasOwn(red.solicitud.datos,v))usados.add(v);else if(Array.isArray(v))v.forEach(recorrer);else if(v&&typeof v==='object')Object.values(v).forEach(recorrer);};
  const {datos:_,...estructura}=red.solicitud;void _;recorrer(estructura);
  red.solicitud.datos=Object.fromEntries(Object.entries(red.solicitud.datos).filter(([id])=>usados.has(id)));
  red.solicitud.paquetes=red.solicitud.paquetes.filter(p=>red.solicitud.volumenes.some(v=>v.paqueteId===p.id));
  const cambioFisico=firmaRed(red.solicitud)!==firmaRed(h.redTermodinamica.solicitud);
  return {...h,redTermodinamica:red,...(cambioFisico?{resultado:undefined,resultadoRef:undefined}:{})};
}
export function datoRed(s:SolicitudEnsamblajeV2,id:string,magnitud:DatoV2['magnitud'],unidad:string,propietarioId:string,funcion:DatoV2['funcion']='frontera',texto=''){
  s.datos[id]={magnitud,funcion,declaracion:{texto,unidad},origen:{propietarioId,ruta:`/redTermodinamica/solicitud/datos/${id}/declaracion`}};return id;
}
export function nombreDatoRed(s:SolicitudEnsamblajeV2,id:string){
  for(const v of s.volumenes){for(const [cid,k] of Object.entries(v.inicial.cantidades.datoIds))if(k===id)return `Initial amount · ${s.componentes.find(c=>c.id===Number(cid))?.nombre??cid}`;
    if(v.inicial.energia.datoId===id)return v.inicial.energia.tipo==='T'?'Initial temperature':'Initial internal energy';
    if(v.frontera.tipo==='rigida'&&v.frontera.datoId===id)return 'Vessel volume';
    if(v.frontera.tipo==='rigida'&&v.frontera.presionRestriccionId===id)return 'Additional prescribed pressure constraint';
    if(v.frontera.tipo==='presion_prescrita'&&v.frontera.presionId===id)return 'Absolute pressure';}
  for(const c of s.corrientes)if(c.materia.modo==='por_componente')for(const [cid,k] of Object.entries(c.materia.caudalIds))if(k===id)return `Flow · ${s.componentes.find(c=>c.id===Number(cid))?.nombre??cid}`;
  const mag=s.datos[id]?.magnitud;
  return ({caudal:'Total flow',caudal_molar:'Total flow',potencia:'Heat transferred',conductancia:'Thermal conductance',tiempo:'Final time',temperatura:s.intercambiosTermicos.some(exchange=>exchange.temperaturaFronteraId===id)?'Boundary temperature':'External temperature',presion:'External pressure'} as Record<string,string>)[mag]??id;
}
export const unidadesRed=(d:DatoV2):string[]=>({cantidad:['mol','kmol'],conductancia:['W/K','kW/K'],masa:['kg','g'],energia:['J','kJ'],temperatura:['K','degC','degF'],presion:['Pa','kPa','bar'],volumen:['m3','L'],potencia:['W','kW'],tiempo:['s','min','h'],caudal:['kg/s','g/s','kg/h','g/h'],caudal_molar:['mol/s','kmol/h','mol/h']} as Record<string,string[]>)[d.magnitud]??[d.declaracion.unidad];
export function sincronizarHipotesis(v:VolumenV2){
  v.formulacionMateria.fija=v.frontera.tipo==='rigida';
  v.formulacionEnergia.presionPrescrita=v.frontera.tipo==='presion_prescrita'||v.frontera.tipo==='rigida'&&!!v.frontera.presionRestriccionId;
  if(v.formulacionEnergia.presionPrescrita)v.formulacionEnergia.presionUniforme=true;
  v.formulacionEnergia.monofasico=v.politica.cantidad==='monofasico';v.formulacionEnergia.sinCambioFase=v.politica.cambioInterno==='prohibido';
  v.formulacionMateria.reglasEstado={...v.formulacionMateria.reglasEstado,fases:{cantidad:v.politica.cantidad,cambioInterno:v.politica.cambioInterno==='prohibido'?'sin_cambio_de_fase':'sin_restriccion',evaluacion:'termodinamica'}};
}
/** An explicit copy, not a silent migration. No missing initial, heat, or stream
 * datum is filled with zero. Restrictions are retained for backend diagnostics. */
export function copiarARed(h:HojaMotor):HojaMotor{
  const out=duplicarHoja(h),vs=volumenesControl(h),fe=formulacionEnergiaHoja(h),ctx=contextoEnergiaHoja(h),p=prepararEnsamblajeTermodinamico(h,'configuracion').solicitud;
  const catalogo=new Map<number,NonNullable<typeof vs[number]['f']['componentes']>[number]>();
  for(const v of vs)for(const c of v.f.componentes??[]){const previo=catalogo.get(c.id);if(previo&&JSON.stringify(previo)!==JSON.stringify(c))throw new Error(`El componente ${c.id} tiene declaraciones distintas entre volúmenes. Unifica su identidad antes de copiar.`);catalogo.set(c.id,c);}
  const s:SolicitudEnsamblajeV2={revision:2,solicitudId:'configuracion',componentes:structuredClone([...catalogo.values()]),paquetes:[],volumenes:[],corrientes:[],intercambiosTermicos:[],datos:{},estudio:{tipo:'temporal',tiempoId:'estudio.tf',metodoSolicitado:h.config.metodo,muestras:h.config.muestras,rtol:h.config.rtol,atol:{cantidad:1e-10,energia:h.energia?.atol??1e-6}}};
  const nombres:Record<string,string>={estudio:'Estudio'};
  for(const v of vs){const {componentes:cs,fronteras:_,...fm}=v.f;void _;const id=v.id,c=h.cierresDinamicos?.[id],pid=`paquete-${id}`;s.paquetes.push({id:pid,modelo:structuredClone(c?.modelo??{id:'',version:''})});
    const cantidades=Object.fromEntries((cs??[]).map(c=>{const k=`volumen.${id}.n0.${c.id}`,d=h.config.datos[h.ensamblaje?`${id}__inicial_${c.id}`:`inicial_${c.id}`];datoRed(s,k,'masa',d?.unidad??'kg',`volumen:${id}`,'inicial',d?.texto??'');return [c.id,k];}));
    const T=h.energia?.inicial??'T',d=vs.length===1?h.energia?.datos[T==='T'?'energia_T0':'energia_U0']:undefined,energiaId=datoRed(s,`volumen.${id}.${T}0`,T==='T'?'temperatura':'energia',d?.unidad??(T==='T'?'K':'J'),`volumen:${id}`,'inicial',d?.texto??'');
    const geometria=h.config.datos[claveGeometria(h,id)],P=vs.length===1?h.energia?.datos.energia_p:undefined;
    const frontera=v.f.fija?{tipo:'rigida' as const,datoId:datoRed(s,`volumen.${id}.V`,'volumen',geometria?.unidad??'m3',`volumen:${id}`,'geometria',geometria?.texto??''),...(fe.presionPrescrita&&id===ctx.volumenId?{presionRestriccionId:datoRed(s,`volumen.${id}.Prestriccion`,'presion',P?.unidad??'Pa',`volumen:${id}`,'frontera',P?.texto??'')}: {})}:fe.presionPrescrita?{tipo:'presion_prescrita' as const,presionId:datoRed(s,`volumen.${id}.P`,'presion',P?.unidad??'Pa',`volumen:${id}`,'frontera',P?.texto??'')}:{tipo:'sin_relacion' as const};
    const vol:VolumenV2={id,componenteIds:(cs??[]).map(c=>c.id),balances:balancesHoja(h),formulacionMateria:fm,formulacionEnergia:structuredClone(fe),paqueteId:pid,politica:structuredClone(c?.politica??{cantidad:fe.monofasico?'monofasico':'sin_restriccion',cambioInterno:fe.sinCambioFase?'prohibido':'permitido',evaluacion:'equilibrio_estable'}),frontera,inicial:{cantidades:{base:'masica',datoIds:cantidades},energia:{tipo:T,datoId:energiaId}}};
    sincronizarHipotesis(vol);s.volumenes.push(vol);nombres[`volumen:${id}`]=v.nombre;
  }
  if(p){for(const [id,d] of Object.entries(p.datos))if(id.startsWith('corriente.'))s.datos[id]=structuredClone(d);
    s.corrientes=p.corrientes.map(c=>{if(c.materia.modo==='total_y_composicion')throw new Error('La composición de una corriente interna debe proceder del donante. Convierte primero a caudal total.');let x:ExtraccionV2|undefined;if(c.extraccion?.tipo==='mezcla_homogenea')x=c.extraccion;else if(c.extraccion?.tipo==='fase'){const fase=c.extraccion.fase;if(fase==='solido')throw new Error('La extracción dinámica de sólidos todavía no está disponible.');x={tipo:'fase',fase};}return {id:String(c.id),desde:c.desde,hasta:c.hasta,componenteIds:c.componenteIds,mecanismo:c.mecanismo,materia:c.materia,estadoExterior:c.estadoExterior,...(x?{extraccion:Object.fromEntries([c.desde,c.hasta].filter((id):id is string=>!!id).map(id=>[id,x]))}:{})};});
  }else if(h.ensamblaje){for(const c of h.ensamblaje.corrientes){const m=c.datos?.materia,ids=c.componentesIds??s.componentes.map(c=>c.id),caudalIds:Record<string,string>={};
      if(m?.modo==='total_y_composicion')throw new Error('Convierte explícitamente la corriente a un caudal desde el donante antes de migrar esta red.');
      for(const cid of ids){const d=m?.caudales[cid];caudalIds[cid]=datoRed(s,`corriente.${c.id}.F.${cid}`,m?.base==='molar'?'caudal_molar':'caudal',d?.unidad??'kg/s',`corriente:${c.id}`,'frontera',d?.texto??'');}
      s.corrientes.push({id:String(c.id),desde:c.desde,hasta:c.hasta,componenteIds:ids,mecanismo:c.mecanismo??null,materia:{modo:'por_componente',base:m?.base??'masica',caudalIds}});nombres[`corriente:${c.id}`]=c.nombre;}}
  for(const v of s.volumenes)if(!v.formulacionEnergia.adiabatico&&vs.length===1){const d=h.energia?.datos.energia_Q,id=`Q-${v.id}`;s.intercambiosTermicos.push({id,desde:null,hasta:v.id,ley:{tipo:'impuesto',potenciaId:datoRed(s,`calor.${id}.Q`,'potencia',d?.unidad??'W',`calor:${id}`,'frontera',d?.texto??'')}});}
  datoRed(s,'estudio.tf','tiempo',h.config.tiempo.unidad,'estudio','estudio',h.config.tiempo.texto);
  for(const [id,d] of Object.entries(s.datos))d.origen.ruta=`/redTermodinamica/solicitud/datos/${id}/declaracion`;
  const material = emptyMaterialJournal();
  for (const volume of s.volumenes) {
    const source = h.ensamblaje?.volumenes.find(item => item.id === volume.id)?.historial ?? h.historial;
    const entry = journalFromHistory(source);
    if (!journalMatches(entry, volume.formulacionMateria)) throw new Error('The adopted network changes material assumptions without a recorded operation.');
    material.volumes[volume.id] = entry;
  }
  const energy=emptyEnergyJournal();
  if(h.energia){const entry=energyJournalFromHistory(h.energia.historial);if(entry)for(const volume of s.volumenes)if(energyJournalMatches(entry,volume.formulacionEnergia))energy.volumes[volume.id]=structuredClone(entry);}
  s.derivacion = { materialDerivation: material, ...(Object.keys(energy.volumes).length?{energyDerivation:energy}:{}) };
  return {...out,nombre:`${h.nombre} · multifásico`,redTermodinamica:{solicitud:s,nombres},graficas:[],tableroIniciado:false};
}
