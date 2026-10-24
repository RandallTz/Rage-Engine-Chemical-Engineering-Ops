/** Numerical selection of existing equation/quantity IDs; never a cached RHS. */
export type DerivedExecution = {
  format:'rage.derived-execution';version:1;sourceSignature:string;timeId:string;
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
  function object(value:unknown,required?:string[],optional:string[]=[]):Record<string,unknown> {
    if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Invalid derived execution object.');
    const result=value as Record<string,unknown>;
    if(required&&(required.some(key=>!Object.hasOwn(result,key))||Object.keys(result).some(key=>!required.includes(key)&&!optional.includes(key))))throw new Error('Unknown or missing derived execution fields.');
    return result;
  }
  const identity=(value:unknown):value is string=>typeof value==='string'&&value.trim().length>0&&value.length<=160;
  const result=object(value,['format','version','sourceSignature','timeId','states','parameters','initialValues','initialEquations','reconstructions','checks'],['scaling']);
  if(result.format!=='rage.derived-execution'||result.version!==1||typeof result.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(result.sourceSignature)||!identity(result.timeId))throw new Error('Invalid derived execution version or source signature.');
  for(const name of ['parameters','initialValues','scaling']) {
    if(result[name]===undefined)continue;
    const mapping=object(result[name]);
    if(Object.keys(mapping).length>200||name==='scaling'&&!Object.keys(mapping).length||Object.entries(mapping).some(([key,value])=>!identity(key)||!identity(value)||data&&!Object.hasOwn(data,value)))throw new Error('Invalid derived execution data binding.');
  }
  for(const [name,fields] of [['states',['quantityId','equationId']],['reconstructions',['quantityId','equationId']],['checks',['equationId','scaleDataId']]] as const) {
    const rows=result[name];
    if(!Array.isArray(rows)||rows.length>200||name==='states'&&!rows.length)throw new Error('Invalid derived execution selection.');
    const seen=new Set<string>();
    for(const item of rows) {
      const row=object(item,[...fields]);
      if(fields.some(field=>!identity(row[field]))||seen.has(row[fields[0]] as string)||name==='checks'&&data&&!Object.hasOwn(data,row.scaleDataId as string))throw new Error('Invalid or duplicate derived execution identity.');
      seen.add(row[fields[0]] as string);
    }
  }
  if(!Array.isArray(result.initialEquations)||result.initialEquations.length>200||result.initialEquations.some(value=>!identity(value))||new Set(result.initialEquations).size!==result.initialEquations.length)throw new Error('Invalid initial equation identities.');
  const typed=result as unknown as DerivedExecution;
  const states=typed.states.map(row=>row.quantityId),rebuilt=typed.reconstructions.map(row=>row.quantityId),parameters=Object.keys(typed.parameters);
  const owned=[typed.timeId,...states,...rebuilt,...parameters];
  if(new Set(owned).size!==owned.length)throw new Error('Numerical quantity ownership must be distinct.');
  if(typed.scaling&&Object.keys(typed.scaling).sort().join('|')!==[typed.timeId,...states].sort().join('|'))throw new Error('Scaling requires exactly time and retained states.');
  return typed;
}
