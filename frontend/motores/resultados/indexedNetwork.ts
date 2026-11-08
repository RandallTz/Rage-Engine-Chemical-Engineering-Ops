/** Versioned indexed publication. References existing SI series and certificate rows. */
import type {ConjuntoResultados} from './contrato';

export type IndexedNetworkPublication = {
  indexSetId:string;count:number;mode:'dynamic'|'steady';stageAxisId:string|null;
  stages:{index:number;ownerId:string;seriesIds:string[];closures:{volumeId:string;mode:'equilibrium'|'single_phase';verificationId:string}[]}[];
  endPorts:IndexedBoundaryPort[];
  profiles:{seriesId:string;stageSeriesIds:(string|null)[]}[];
}&({version:1}|{version:2;sidePorts:IndexedBoundaryPort[]}|{version:3;sidePorts:IndexedBoundaryPort[];display:IndexedDisplay[]});
/** Python-published presentation metadata (version 3): readable stage-agnostic label, default-chart rank and a group key shared by the same quantity across stages. */
export type IndexedDisplay={seriesId:string;label:string;rank:number;group:string};
export type IndexedBoundaryPort={portId:string;stage:number;kind:'material'|'heat'|'work';direction:'inlet'|'outlet';
  variables:{flow:string;composition:string[];temperature:string;pressure:string;specificEnthalpy:string}|{power:string}};

export function readIndexedNetwork(result:ConjuntoResultados):IndexedNetworkPublication|undefined {
  if(!Object.hasOwn(result,'indexedNetwork'))return undefined;
  const value=result.indexedNetwork!;
  const fail=(path:string,message:string):never=>{throw new Error(`indexedNetwork${path}: ${message}`);};
  const obj=(row:unknown,keys:string[],path:string)=>{
    if(!row||typeof row!=='object'||Array.isArray(row)||Object.keys(row).length!==keys.length||Object.keys(row).some(k=>!keys.includes(k)))fail(path,'Unexpected fields.');
  };
  const text=(row:unknown,path:string)=>{if(typeof row!=='string'||!row.trim())fail(path,'Expected nonempty text.');};
  const array=(row:unknown,path:string)=>{if(!Array.isArray(row))fail(path,'Expected an array.');};
  obj(value,['version','indexSetId','count','mode','stageAxisId','stages','endPorts','profiles',...(value?.version===2||value?.version===3?['sidePorts']:[]),...(value?.version===3?['display']:[])],'');
  if(value.version!==1&&value.version!==2&&value.version!==3)fail('.version','Expected version 1, 2 or 3.');
  text(value.indexSetId,'.indexSetId');
  if(!Number.isSafeInteger(value.count)||value.count<=0)fail('.count','Expected a positive safe integer.');
  if(!['dynamic','steady'].includes(value.mode))fail('.mode','Expected dynamic or steady.');
  for(const key of ['stages','endPorts','profiles'] as const)array(value[key],'.'+key);
  if(value.version===2||value.version===3)array(value.sidePorts,'.sidePorts');
  if(value.stages.length!==value.count)fail('.stages','Stage count differs from n.');
  const series=new Map(result.series.map(s=>[s.id,s])),checks=new Map(result.verificaciones.map(v=>[v.id,v]));
  if(checks.size!==result.verificaciones.length)fail('.stages','Certificate identities must be unique.');
  const used=new Set<string>();
  const finiteValues=(v:unknown):boolean=>Array.isArray(v)?v.every(finiteValues):v===null||typeof v==='number'&&Number.isFinite(v);
  value.stages.forEach((stage,i)=>{
    const path=`.stages[${i}]`,owner=`${value.indexSetId}.stage.${i+1}`;
    obj(stage,['index','ownerId','seriesIds','closures'],path);
    if(stage.index!==i+1||stage.ownerId!==owner)fail(path,'Expected ordered stage index and owner.');
    array(stage.seriesIds,path+'.seriesIds');
    if(!stage.seriesIds.length||stage.seriesIds.some(k=>typeof k!=='string')||new Set(stage.seriesIds).size!==stage.seriesIds.length)fail(path,'Expected distinct stage series.');
    for(const key of stage.seriesIds){
      const row=series.get(key);
      if(!row||row.propietarioId!==owner||!key.startsWith(owner+'.')||used.has(key))fail(path,'Missing, repeated or foreign stage series.');
      if(value.mode==='steady'&&row!.ejes.length)fail(path,'Steady stage values must be scalar.');
      if(!finiteValues(row!.valores))fail(path,'Expected finite numbers or null.');
      used.add(key);
    }
    array(stage.closures,path+'.closures');
    const volumes=new Set<string>();
    stage.closures.forEach((closure,ci)=>{
      const cp=`${path}.closures[${ci}]`;
      obj(closure,['volumeId','mode','verificationId'],cp);text(closure.volumeId,cp+'.volumeId');
      if(!closure.volumeId.startsWith(owner+'.volume.')||volumes.has(closure.volumeId))fail(cp,'Expected a distinct stage-local closure volume.');
      volumes.add(closure.volumeId);
      if(!['equilibrium','single_phase'].includes(closure.mode))fail(cp,'Unknown closure mode.');
      const key='thermodynamics.closure.'+closure.volumeId,check=checks.get(key),tolerance=closure.mode==='equilibrium'?1:1e-9;
      if(closure.verificationId!==key||!check)fail(cp,'Missing closure certificate verification.');
      if(typeof check!.valor!=='number'||!Number.isFinite(check!.valor)||check!.valor<0||check!.tolerancia!==tolerance||result.estado==='resuelto'&&check!.valor>tolerance)fail(cp,'Invalid or failed certificate summary.');
    });
  });
  const ports=new Set<string>();
  const boundaries=[...value.endPorts.map((port,i)=>({port,path:`.endPorts[${i}]`,interior:false})),
    ...(value.version===2||value.version===3?value.sidePorts.map((port,i)=>({port,path:`.sidePorts[${i}]`,interior:true})):[])];
  boundaries.forEach(({port,path,interior})=>{
    obj(port,['portId','stage','kind','direction','variables'],path);text(port.portId,path+'.portId');
    if(ports.has(port.portId))fail(path,'Repeated end-port identity.');ports.add(port.portId);
    if(!Number.isInteger(port.stage)||!(interior?port.stage>1&&port.stage<value.count:[1,value.count].includes(port.stage)))fail(path,'Side ports require an interior stage; end ports require stage 1 or n.');
    if(!['material','heat','work'].includes(port.kind)||!['inlet','outlet'].includes(port.direction))fail(path,'Invalid typed end port.');
    const roles=port.kind==='material'?['flow','composition','temperature','pressure','specificEnthalpy']:['power'];
    obj(port.variables,roles,path+'.variables');
    const ids:string[]=[];
    for(const [role,binding] of Object.entries(port.variables)){
      if(role==='composition'){array(binding,path+'.variables.composition');if(!binding.length)fail(path,'Composition requires a component.');ids.push(...binding);}
      else {text(binding,path+'.variables.'+role);ids.push(binding as string);}
    }
    const stage=value.stages[port.stage-1];
    if(ids.some(k=>typeof k!=='string'||!stage.seriesIds.includes(k))||new Set(ids).size!==ids.length)fail(path,'Expected distinct series of the port stage.');
    const units:Record<string,string[]>={temperature:['K'],pressure:['Pa'],specificEnthalpy:['J/kg','J/mol'],flow:['kg/s','mol/s'],power:['W'],composition:['1']};
    for(const [role,binding] of Object.entries(port.variables))for(const key of (role==='composition'?binding:[binding]) as string[])if(!units[role].includes(series.get(key)!.unidadSI))fail(path+'.variables.'+role,'Incompatible SI units.');
    if('flow' in port.variables){const expected=series.get(port.variables.flow)!.unidadSI==='kg/s'?'J/kg':'J/mol';if(series.get(port.variables.specificEnthalpy)!.unidadSI!==expected)fail(path,'Flow and enthalpy bases differ.');}
  });
  if(value.mode==='dynamic'){
    if(value.stageAxisId!==null||value.profiles.length)fail('.profiles','Dynamic publication has no steady profiles.');
  }else{
    const axis=result.ejes.find(a=>a.id===value.stageAxisId);
    if(!axis||axis.rol!=='parametro'||axis.unidadSI!=='1'||Object.keys(axis.dimension).length||axis.valores.length!==value.count||axis.valores.some((n,i)=>n!==i+1))fail('.stageAxisId','Expected dimensionless axis j=1..n.');
    const profiles=new Set<string>();
    value.profiles.forEach((profile,i)=>{
      const path=`.profiles[${i}]`;obj(profile,['seriesId','stageSeriesIds'],path);
      const row=series.get(profile.seriesId);
      if(typeof profile.seriesId!=='string'||!row||used.has(profile.seriesId)||profiles.has(profile.seriesId))fail(path,'Missing, repeated or stage-owned profile.');
      profiles.add(profile.seriesId);array(profile.stageSeriesIds,path+'.stageSeriesIds');
      if(profile.stageSeriesIds.length!==value.count||row!.ejes.length!==1||row!.ejes[0]!==axis!.id||row!.propietarioId!==value.indexSetId)fail(path,'Invalid profile sources, owner or axis.');
      profile.stageSeriesIds.forEach((id,j)=>{
        if(id===null&&value.version===3){if((row!.valores as (number|null)[])[j]!==null)fail(path,'A stage without the quantity must publish an undefined value.');return;}
        if(typeof id!=='string'||!value.stages[j].seriesIds.includes(id))fail(path,'Sources must follow stage order.');
        const original=series.get(id as string)!;
        const dimensionKeys=Object.keys(original.dimension).sort(),otherKeys=Object.keys(row!.dimension).sort();
        const sameDimension=JSON.stringify(dimensionKeys)===JSON.stringify(otherKeys)&&dimensionKeys.every(k=>original.dimension[k].n===row!.dimension[k].n&&original.dimension[k].d===row!.dimension[k].d);
        if(original.unidadSI!==row!.unidadSI||!sameDimension||original.valores!==(row!.valores as (number|null)[])[j])fail(path,'Profile must preserve scalar source values and units.');
      });
    });
  }
  if(value.version===3){
    array(value.display,'.display');
    const needed=new Set([...used,...value.profiles.map(p=>p.seriesId)]),shown=new Set<string>();
    value.display.forEach((entry,i)=>{
      const path=`.display[${i}]`;obj(entry,['seriesId','label','rank','group'],path);
      for(const key of ['seriesId','label','group'] as const)text(entry[key],`${path}.${key}`);
      if(!needed.has(entry.seriesId)||shown.has(entry.seriesId))fail(path,'Display entries must name each stage or profile series once.');
      if(!Number.isInteger(entry.rank)||entry.rank<0||entry.rank>99)fail(path+'.rank','Expected an integer rank from 0 to 99.');
      shown.add(entry.seriesId);
    });
    if(shown.size!==needed.size)fail('.display','Every stage and profile series needs a display entry.');
  }
  return value;
}
