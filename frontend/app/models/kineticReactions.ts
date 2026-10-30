/** Declaration transport only. Python verifies units and conservation. */
import type {ModeloComun} from '../../motores/modelo/contrato';
export type KineticReaction={id:string;stoichiometry:Record<string,string>;orders:Record<string,number>;rateConstantDataId:string;arrhenius?:{energyDataId:string;temperatureDataId:string}};
export type KineticVolume={volumeDataId:string;molarMassDataIds:Record<string,string>;elements:Record<string,Record<string,number>>;reactions:KineticReaction[]};
export type KineticReactions={format:'rage.kinetic-reactions';version:1;volumes:Record<string,KineticVolume>};
function object(value:unknown,required:string[],optional:string[]=[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Expected a kinetic declaration object.');
  const o=value as Record<string,unknown>;
  if(required.some(k=>!Object.hasOwn(o,k))||Object.keys(o).some(k=>!required.includes(k)&&!optional.includes(k)))throw new Error('Unknown or missing kinetic fields.');
  return o;
}
const record=(v:unknown)=>object(v,[],Object.keys(v&&typeof v==='object'&&!Array.isArray(v)?v:{}));
const same=(a:string[],b:string[])=>a.slice().sort().join('|')===b.slice().sort().join('|');
export function readKineticReactions(value:unknown,model:ModeloComun):KineticReactions{
  const root=object(value,['format','version','volumes']);
  if(root.format!=='rage.kinetic-reactions'||root.version!==1)throw new Error('Unsupported kinetic reaction format/version.');
  const volumes=record(root.volumes);
  if(Object.keys(volumes).length&&model.motores.derivedExecution&&model.motores.derivedExecution.version!==1)throw new Error('Kinetic declarations require explicit derived execution version 1.');
  if(Object.keys(volumes).length>160)throw new Error('Too many kinetic volumes.');
  const datum=(id:unknown)=>{if(typeof id!=='string'||!Object.hasOwn(model.datos,id))throw new Error('Unknown kinetic datum.');};
  for(const [owner,item] of Object.entries(volumes)){
    const volume=model.volumenes.find(v=>v.id===owner);
    if(!volume?.balances.materia)throw new Error('Kinetics requires a volume with component balances.');
    const entry=object(item,['volumeDataId','molarMassDataIds','elements','reactions']),components=volume.componenteIds.map(String);
    datum(entry.volumeDataId);const masses=record(entry.molarMassDataIds);
    if(!same(Object.keys(masses),components))throw new Error('Declare molar masses for every component.');
    Object.values(masses).forEach(datum);const elements=record(entry.elements);
    if(!Object.keys(elements).length||Object.keys(elements).length>120)throw new Error('Declare elemental composition.');
    for(const [name,values] of Object.entries(elements)){
      const row=record(values);
      if(!name.trim()||!same(Object.keys(row),components)||Object.values(row).some(n=>typeof n!=='number'||!Number.isInteger(n)||Math.abs(n)>100000||name!=='charge'&&n<0))throw new Error('Invalid elemental/charge composition.');
    }
    if(!Array.isArray(entry.reactions)||!entry.reactions.length||entry.reactions.length>100)throw new Error('Declare between one and 100 reactions.');
    const ids=new Set<string>();
    for(const item of entry.reactions){
      const r=object(item,['id','stoichiometry','orders','rateConstantDataId'],['arrhenius']);
      if(typeof r.id!=='string'||!(/^[A-Za-z][A-Za-z0-9_]{0,39}$/).test(r.id)||ids.has(r.id))throw new Error('Reaction identities must be distinct stable identifiers.');
      ids.add(r.id);datum(r.rateConstantDataId);const nu=record(r.stoichiometry),orders=record(r.orders);
      if(!same(Object.keys(nu),components)||Object.values(nu).some(n=>typeof n!=='string'||!(/^-?\d{1,8}(?:\/\d{1,8})?$/).test(n)||/\/0+$/.test(n)))throw new Error('Invalid rational stoichiometry.');
      if(Object.entries(orders).some(([c,n])=>!components.includes(c)||typeof n!=='number'||!Number.isInteger(n)||n<0||n>6))throw new Error('Invalid concentration orders.');
      if(r.arrhenius!==undefined){const a=object(r.arrhenius,['energyDataId','temperatureDataId']);datum(a.energyDataId);datum(a.temperatureDataId);}
    }
  }
  return value as KineticReactions;
}
