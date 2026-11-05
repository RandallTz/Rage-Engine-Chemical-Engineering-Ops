import type {ModeloComun} from './contrato';

export type StageIndex='first'|'last'|number;
export type IndexSet={format:'rage.index-set';version:1;id:string;index:string;countDataId:string;
  templates:Record<string,ModeloComun>;genericStage:string;variants:{at:StageIndex;template:string}[];
  connections:{outlet:string;inlet:string;offset:1|-1}[];
  exposures:{id:string;port:string;at:StageIndex|'each'}[]};
export const fail=(path:string,message:string):never=>{throw new Error(`indexSet.${path}: ${message}`);};
const object=(value:unknown,path:string):Record<string,unknown>=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:fail(path,'Expected an object.');
export function keys(value:unknown,path:string,expected:string[]){const o=object(value,path);if(Object.keys(o).length!==expected.length||expected.some(k=>!Object.hasOwn(o,k)))fail(path,'Unknown or missing fields.');return o;}
export const text=(value:unknown,path:string)=>{if(typeof value!=='string'||!value.trim())fail(path,'Nonempty text required.');};

/** Structural validation only; Python owns replay, identities and expansion. */
export function readIndexSet(model:ModeloComun,readModel:(value:unknown)=>ModeloComun):IndexSet{
  const r=keys(model.indexSet,'',['format','version','id','index','countDataId','templates','genericStage','variants','connections','exposures']) as unknown as IndexSet;
  if(r.format!=='rage.index-set'||r.version!==1)fail('version','Expected rage.index-set version 1.');
  for(const k of ['id','index','countDataId','genericStage'] as const)text(r[k],k);
  const datum=model.datos[r.countDataId];
  if(!datum||datum.funcion!=='estudio'||datum.declaracion.unidad!=='1')fail('countDataId','The count requires a dimensionless Solve datum (estudio, unit 1).');
  const literal=datum.declaracion.texto;
  if(typeof literal!=='string'||literal.match(/^\+?[0-9]+(?:\.0*)?$/)?.[0]!==literal)fail('countDataId','The count must be a positive integer literal.');
  const n=Number(literal);if(!Number.isInteger(n)||n<1||n>256)fail('countDataId','Version 1 admits one to 256 stages.');
  const templates=object(r.templates,'templates');if(!Object.keys(templates).length)fail('templates','At least one embedded template document is required.');
  for(const [key,source]of Object.entries(templates)){
    text(key,'templates');if(Object.hasOwn(object(source,`templates.${key}`),'indexSet'))fail(`templates.${key}`,'Nested index sets are not admitted.');
    const parsed=readModel(source);if(!parsed.template?.equipment)fail(`templates.${key}`,'A stage requires an equipment-marked recorded template.');
  }
  if(!Object.hasOwn(templates,r.genericStage))fail('genericStage','Unknown template reference.');
  const canonical=(v:unknown):string=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))):x);
  const generic=r.templates[r.genericStage];
  for(const field of ['componentes','termodinamica','volumenes','corrientes','intercambios','matematico','motores','template','restricciones','observables','verificaciones'] as const)if(canonical(model[field])!==canonical(generic[field]))fail('genericStage','The worksheet must retain the generic template physical definition: '+field);
  if(Object.hasOwn(generic.datos,r.countDataId)||canonical(Object.fromEntries(Object.entries(model.datos).filter(([key])=>key!==r.countDataId)))!==canonical(generic.datos))fail('countDataId','The worksheet data must be the generic defaults plus the separate stage-count datum.');
  for(const k of ['variants','connections','exposures'] as const)if(!Array.isArray(r[k]))fail(k,'Expected a list.');
  const indices=(at:unknown,path:string):number[]=>at==='each'?Array.from({length:n},(_,i)=>i+1):at==='first'?[1]:at==='last'?[n]:typeof at==='number'&&Number.isInteger(at)&&at>=1&&at<=n?[at]:fail(path,'Expected first, last, each or an existing integer index.');
  const stages=Array.from({length:n},()=>r.genericStage),changed=new Set<number>();
  r.variants.forEach((v,i)=>{const p=`variants[${i}]`;keys(v,p,['at','template']);if((v.at as unknown)==='each'||typeof v.template!=='string'||!Object.hasOwn(templates,v.template))fail(p,'A variant requires one index and an existing template.');const j=indices(v.at,p)[0];if(changed.has(j))fail(p,'Overlapping variants.');changed.add(j);stages[j-1]=v.template;});
  const ports=new Map(stages.flatMap((key,i)=>r.templates[key].template!.ports.map(p=>[JSON.stringify([i+1,p.id]),p] as const))),used=new Set<string>(),ids=new Set<string>();
  const take=(j:number,id:string,path:string)=>{const key=JSON.stringify([j,id]),p=ports.get(key);if(!p)fail(path,'Port does not exist on the selected stage template.');if(used.has(key))fail(path,'A stage port is bound more than once.');used.add(key);return p!;};
  r.connections.forEach((rule,i)=>{
    const p=`connections[${i}]`;keys(rule,p,['outlet','inlet','offset']);if(rule.offset!==1&&rule.offset!==-1)fail(p,'A connection offset must be -1 or +1.');
    for(let j=1;j<=n;j++){
      for(const direction of ['outlet','inlet'] as const){const port=ports.get(JSON.stringify([j,rule[direction]]));if(!port||port.direction!==direction)fail(p,'Unknown port or incompatible direction.');}
      const a=ports.get(JSON.stringify([j,rule.outlet]))!,b=ports.get(JSON.stringify([j,rule.inlet]))!;
      if(a.kind!==b.kind||canonical(a.variables)!==canonical(b.variables))fail(p,'Connected ports require identical kinds and SI variable contracts.');
    }
    for(let j=1;j<=n;j++){const k=j+rule.offset;if(k<1||k>n)continue;const a=take(j,rule.outlet,p),b=take(k,rule.inlet,p);if(a.kind!==b.kind||canonical(a.variables)!==canonical(b.variables))fail(p,'Connected ports require identical kinds and SI variable contracts.');if(a.kind==='material'&&canonical(r.templates[stages[j-1]].componentes)!==canonical(r.templates[stages[k-1]].componentes))fail(p,'Connected material stages require the same ordered component declarations.');}
  });
  r.exposures.forEach((rule,i)=>{const p=`exposures[${i}]`;keys(rule,p,['id','port','at']);text(rule.id,p+'.id');if(ids.has(rule.id))fail(p,'Duplicate exposed-port identity.');ids.add(rule.id);for(const j of indices(rule.at,p))take(j,rule.port,p);});
  if(used.size!==ports.size)fail('connections','Every stage port must be connected or explicitly exposed.');
  return r;
}

