/** Solve-workspace transport record; no new Model equation or numerical solver. */
import {UNIDADES_MOTOR} from '../../app/motor/unidadesMotor';
export type InverseSpecification={format:'rage.inverse-specification';version:1;
  specifications:{id:string;quantityId:string;targetDataId:string;residualScaleDataId:string}[];
  freedInputs:{quantityId:string;seedDataId:string;lowerDataId:string;upperDataId:string;scaleDataId:string}[]};
export type InverseSolve={version:1;record:InverseSpecification;data:Record<string,{texto:string;unidad:string}>};
export type SeedRegularity={augmentedSigmaMin:number;forwardSigmaMin:number;sensitivitySigmaMin:number|null;sensitivity:number[][]|null};
export type InverseEvidence={format:'rage.inverse-specification';version:1;record:InverseSpecification;data:InverseSolve['data'];
  rows:{id:string;quantityId:string;targetSI:number;unit:string;latex:string}[];freedInputs:{quantityId:string;unit:string}[];
  seedRegularity:SeedRegularity;invalidates:['solve','results'];retains:['model','transform'];scope:string};
export function exactObject(value:unknown,fields:string[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==fields.length||fields.some(k=>!Object.hasOwn(value,k)))throw new Error('Unknown or missing inverse specification fields.');
  return value as Record<string,unknown>;
}
export function readInverseSpecification(value:unknown):InverseSpecification{
  const r=exactObject(value,['format','version','specifications','freedInputs']);
  if(r.format!=='rage.inverse-specification'||r.version!==1)throw new Error('Expected inverse specification version 1.');
  for(const [name,fields] of [['specifications',['id','quantityId','targetDataId','residualScaleDataId']],['freedInputs',['quantityId','seedDataId','lowerDataId','upperDataId','scaleDataId']]] as const){
    const rows=r[name];if(!Array.isArray(rows)||rows.length>50)throw new Error('Invalid inverse specification rows.');
    for(const row of rows)for(const v of Object.values(exactObject(row,[...fields])))if(typeof v!=='string'||!v.trim()||v.length>160)throw new Error('Invalid inverse identity.');
  }
  const record=r as unknown as InverseSpecification,s=record.specifications,f=record.freedInputs;
  if(!s.length||s.length!==f.length)throw new Error('inverse_not_square: each specification needs one freed input.');
  const unique=(xs:string[])=>new Set(xs).size===xs.length;
  if(!unique(s.map(r=>r.id))||!unique(s.map(r=>r.quantityId))||!unique(f.map(r=>r.quantityId))||s.some(r=>f.some(v=>v.quantityId===r.quantityId)))throw new Error('Duplicate or overlapping inverse quantities.');
  return record;
}
export function inverseDataIds(record:InverseSpecification):string[]{return [...new Set([...record.specifications,...record.freedInputs].flatMap(row=>Object.entries(row).filter(([k])=>k.endsWith('DataId')).map(([,v])=>v)))].sort();}
export function readInverseSolve(value:unknown):InverseSolve{
  const r=exactObject(value,['version','record','data']);if(r.version!==1)throw new Error('Unsupported inverse Solve record.');
  const record=readInverseSpecification(r.record),data=r.data;
  if(!data||typeof data!=='object'||Array.isArray(data)||JSON.stringify(Object.keys(data).sort())!==JSON.stringify(inverseDataIds(record)))throw new Error('Inverse data must exactly cover the record.');
  for(const declaration of Object.values(data))if(Object.values(exactObject(declaration,['texto','unidad'])).some(v=>typeof v!=='string'))throw new Error('Invalid inverse declaration.');
  return r as unknown as InverseSolve;
}
/** Constant declaration validation only, sharing the existing compatible unit catalog.
 * Python remains authoritative for dimensional admission and all scientific evaluation. */
export function declaredInverseSI(declaration:{texto:string;unidad:string},unit:string):number{
  const tokens=declaration.texto.match(/(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|sqrt|exp|log|pi|[()+*/^\-]/g)??[];
  if(tokens.join('')!==declaration.texto.replace(/\s/g,'')||tokens.length>500)throw new Error('Invalid inverse constant expression.');
  let i=0;
  function atom():number{const t=tokens[i++];if(t==='-')return -power();if(t==='+')return power();if(t==='pi')return Math.PI;if(t==='('){const v=sum();if(tokens[i++]!==')')throw new Error('Unclosed constant.');return v;}if(['sqrt','exp','log'].includes(t)){if(tokens[i++]!=='(')throw new Error('Expected constant function argument.');const v=sum();if(tokens[i++]!==')')throw new Error('Unclosed constant function.');return t==='sqrt'?Math.sqrt(v):t==='exp'?Math.exp(v):Math.log(v);}if(t===undefined||!/^\d|^\./.test(t))throw new Error('Expected a constant number.');return Number(t);}
  function power():number{const v=atom();if(tokens[i]==='^'){i++;return v**power();}return v;}
  function product():number{let v=power();while(tokens[i]==='*'||tokens[i]==='/'){const op=tokens[i++],w=power();v=op==='*'?v*w:v/w;}return v;}
  function sum():number{let v=product();while(tokens[i]==='+'||tokens[i]==='-'){const op=tokens[i++],w=product();v=op==='+'?v+w:v-w;}return v;}
  const v=sum();if(i!==tokens.length||!Number.isFinite(v))throw new Error('Invalid finite inverse constant.');
  if([declaration.unidad,unit].some(v=>['degC','degF','°C','°F'].includes(v)))throw new Error('Inverse specifications require absolute units.');
  const normal=(v:string)=>v.trim().replaceAll('**','^').replaceAll('³','^3').replaceAll('²','^2').replace(/\bm([23])\b/g,'m^$1').replaceAll(' ','');
  const expected=normal(unit),supplied=normal(declaration.unidad);
  let factor:number|undefined;
  // Publications use SI units; alternate input units reuse the existing catalog.
  if(supplied===expected&&/^(?:kg|mol|cd|Pa|[msKAJWN]|1|[*/^().+\-0-9])+$/.test(expected))factor=1;
  else for(const [kind,units] of Object.entries(UNIDADES_MOTOR))if(kind!=='temperatura'&&Object.entries(units).some(([u,f])=>normal(u)===expected&&f===1)){const entry=Object.entries(units).find(([u])=>normal(u)===supplied);if(entry)factor=entry[1];}
  if(factor===undefined)throw new Error('Inverse declaration requires compatible absolute SI units.');
  const si=v*factor;if(!Number.isFinite(si))throw new Error('Nonfinite inverse declaration.');return si;
}
