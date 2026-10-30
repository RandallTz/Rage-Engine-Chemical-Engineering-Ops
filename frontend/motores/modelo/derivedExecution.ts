/** Numerical selection of existing equation/quantity IDs; never a cached RHS. */
import {readSteadySelection,type SteadySelection} from './steadyContract';
export type DerivedExecution = TemporalDerivedExecution | SteadySelection;
export type TemporalDerivedExecution = {
  format:'rage.derived-execution';version:1|2|3|4;
  dae?:{stateBounds:Record<string,{lowerDataId:string;upperDataId:string}>;driftTolerance:number};sourceSignature:string;timeId:string;
  nonlinear?:{variables:Record<string,{seedDataId:string;lowerDataId:string;upperDataId:string;scaleDataId:string}>;residualScales:Record<string,string>;residualTolerance:number;stepTolerance:number;maxIterations:number;maxBacktracks:number};
  algebraic?:{quantityId:string;equationId:string}[];
  states:{quantityId:string;equationId:string}[];
  parameters:Record<string,string>;initialValues:Record<string,string>;initialEquations:string[];
  reconstructions:{quantityId:string;equationId:string}[];
  checks:{equationId:string;scaleDataId:string}[];
  scaling?:Record<string,string>;
};

export type DerivedExecutionSource={format:'rage.derived-execution-source';version:1;modelId:string;sourceSignature:string};
export function readDerivedExecutionSource(value:unknown):DerivedExecutionSource {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Invalid derived execution source.');
  const result=value as DerivedExecutionSource;
  if(result.format!=='rage.derived-execution-source'||result.version!==1||typeof result.modelId!=='string'||!result.modelId||typeof result.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(result.sourceSignature)
    ||Object.keys(result).length!==4||Object.keys(result).some(key=>!['format','version','modelId','sourceSignature'].includes(key)))throw new Error('Invalid derived execution source pin.');
  return result;
}

export function readDerivedExecution(value:unknown,data?:Record<string,unknown>):DerivedExecution {
  if(value&&typeof value==='object'&&'version' in value&&value.version===5)return readSteadySelection(value,data);
  function object(value:unknown,required?:string[],optional:string[]=[]):Record<string,unknown> {
    if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Invalid derived execution object.');
    const result=value as Record<string,unknown>;
    if(required&&(required.some(key=>!Object.hasOwn(result,key))||Object.keys(result).some(key=>!required.includes(key)&&!optional.includes(key))))throw new Error('Unknown or missing derived execution fields.');
    return result;
  }
  const identity=(value:unknown):value is string=>typeof value==='string'&&value.trim().length>0&&value.length<=160;
  const result=object(value,['format','version','sourceSignature','timeId','states','parameters','initialValues','initialEquations','reconstructions','checks'],['scaling','algebraic','nonlinear','dae']);
  if(result.format!=='rage.derived-execution'||![1,2,3,4].includes(result.version as number)||typeof result.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(result.sourceSignature)||!identity(result.timeId))throw new Error('Invalid derived execution version or source signature.');
  if(result.version===1&&Object.hasOwn(result,'algebraic')||[2,3,4].includes(result.version as number)&&(!Array.isArray(result.algebraic)||!result.algebraic.length))throw new Error('Version 2 requires a nonempty coupled algebraic block.');
  for(const name of ['parameters','initialValues','scaling']) {
    if(result[name]===undefined)continue;
    const mapping=object(result[name]);
    if(Object.keys(mapping).length>200||name==='scaling'&&!Object.keys(mapping).length||Object.entries(mapping).some(([key,value])=>!identity(key)||!identity(value)||data&&!Object.hasOwn(data,value)))throw new Error('Invalid derived execution data binding.');
  }
  for(const [name,fields] of [['states',['quantityId','equationId']],['reconstructions',['quantityId','equationId']],['checks',['equationId','scaleDataId']],['algebraic',['quantityId','equationId']]] as const) {
    const rows=name==='algebraic'&&result.version===1?[]:result[name];
    if(!Array.isArray(rows)||rows.length>200||name==='states'&&!rows.length)throw new Error('Invalid derived execution selection.');
    const seen=new Set<string>();
    for(const item of rows) {
      const row=object(item,[...fields]);
      if(fields.some(field=>!identity(row[field]))||seen.has(row[fields[0]] as string)||name==='checks'&&data&&!Object.hasOwn(data,row.scaleDataId as string))throw new Error('Invalid or duplicate derived execution identity.');
      seen.add(row[fields[0]] as string);
    }
    if(name==='algebraic'&&new Set(rows.map(row=>row.equationId)).size!==rows.length)throw new Error('Algebraic block equations must be distinct.');
  }
  if(!Array.isArray(result.initialEquations)||result.initialEquations.length>200||result.initialEquations.some(value=>!identity(value))||new Set(result.initialEquations).size!==result.initialEquations.length)throw new Error('Invalid initial equation identities.');
  const typed=result as unknown as TemporalDerivedExecution;
  const states=typed.states.map(row=>row.quantityId),rebuilt=typed.reconstructions.map(row=>row.quantityId),parameters=Object.keys(typed.parameters);
  const owned=[typed.timeId,...states,...rebuilt,...parameters,...(typed.algebraic??[]).map(row=>row.quantityId)];
  if(new Set(owned).size!==owned.length)throw new Error('Numerical quantity ownership must be distinct.');
  if(typed.scaling&&Object.keys(typed.scaling).sort().join('|')!==[typed.timeId,...states].sort().join('|'))throw new Error('Scaling requires exactly time and retained states.');
  if(([3,4].includes(typed.version))!==Object.hasOwn(typed,'nonlinear'))throw new Error('Versions 3 and 4 require nonlinear settings.');
  if(typed.nonlinear){
    const config=object(typed.nonlinear,['variables','residualScales','residualTolerance','stepTolerance','maxIterations','maxBacktracks']);
    const variables=object(config.variables),scales=object(config.residualScales);
    if(Object.keys(variables).sort().join('|')!==typed.algebraic!.map(r=>r.quantityId).sort().join('|')||Object.keys(scales).sort().join('|')!==typed.algebraic!.map(r=>r.equationId).sort().join('|'))throw new Error('Nonlinear settings must cover exactly the selected rows and unknowns.');
    const datum=(value:unknown)=>{if(!identity(value)||data&&!Object.hasOwn(data,value))throw new Error('Invalid nonlinear datum.');};
    for(const value of Object.values(variables))Object.values(object(value,['seedDataId','lowerDataId','upperDataId','scaleDataId'])).forEach(datum);
    Object.values(scales).forEach(datum);
    for(const key of ['residualTolerance','stepTolerance'])if(typeof config[key]!=='number'||!Number.isFinite(config[key])||!(Number(config[key])>0))throw new Error('Invalid nonlinear tolerance.');
    for(const [key,limit] of [['maxIterations',30],['maxBacktracks',20]] as const)if(!Number.isSafeInteger(config[key])||Number(config[key])<1||Number(config[key])>limit)throw new Error('Invalid nonlinear iteration budget.');
  }
  if((typed.version===4)!==Object.hasOwn(typed,'dae'))throw new Error('Only version 4 requires DAE settings.');
  if(typed.dae){
    const config=object(typed.dae,['stateBounds','driftTolerance']);
    const bounds=object(config.stateBounds);
    if(Object.keys(bounds).sort().join('|')!==states.sort().join('|'))throw new Error('DAE state bounds must cover the states.');
    for(const item of Object.values(bounds))for(const value of Object.values(object(item,['lowerDataId','upperDataId'])))if(!identity(value)||data&&!Object.hasOwn(data,value))throw new Error('Invalid DAE bound datum.');
    if(typeof config.driftTolerance!=='number'||!Number.isFinite(config.driftTolerance)||config.driftTolerance<=0||config.driftTolerance>1e-9||typed.nonlinear!.residualTolerance>config.driftTolerance)throw new Error('Invalid DAE drift tolerance.');
  }
  return typed;
}
