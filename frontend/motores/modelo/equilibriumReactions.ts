/** Identity/shape transport only. Python owns reaction rank and certification. */
import type {ModeloComun} from './contrato';
export type EquilibriumReactionRegion={provider:'ideal_gas'|'package';species:string[];phaseId:'vapor'|'liquido';standardState:'ideal_gas_P0'|'pure_liquid_TP';anchor:'gas'|'liquid';temperatureId:string;pressureId:string;amountIds:string[];referenceIds:string[];extentIds:string[];reactions:{id:string;stoichiometry:string[];equationId:string}[];packageId?:string};
export type EquilibriumReactions={format:'rage.equilibrium-reactions';version:1;volumes:Record<string,EquilibriumReactionRegion>};
function object(value:unknown,fields?:string[],optional:string[]=[]):Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Expected an equilibrium reaction object.');
  const row=value as Record<string,unknown>;
  if(fields&&(fields.some(k=>!Object.hasOwn(row,k))||Object.keys(row).some(k=>!fields.includes(k)&&!optional.includes(k))))throw new Error('Unknown or missing equilibrium reaction fields.');
  return row;
}
const identity=(v:unknown)=>typeof v==='string'&&v.length>0;
function ids(v:unknown):asserts v is string[]{if(!Array.isArray(v)||!v.length||v.some(q=>!identity(q))||new Set(v).size!==v.length)throw new Error('Expected distinct graph identities.');}
export function readEquilibriumReactions(value:unknown,model:ModeloComun):EquilibriumReactions{
  const root=object(value,['format','version','volumes']);
  if(root.format!=='rage.equilibrium-reactions'||root.version!==1)throw new Error('Expected equilibrium reaction version 1.');
  const regions=object(root.volumes);if(!Object.keys(regions).length)throw new Error('Declare a reaction region.');
  if(model.motores.derivedExecution&&model.motores.derivedExecution.version!==4)throw new Error('Equilibrium reactions require recorded index-one extent selection version 4.');
  for(const [owner,v] of Object.entries(regions)){
    const region=model.volumenes.find(v=>v.id===owner);
    if(!region||model.motores.kineticReactions?.volumes[owner])throw new Error('Missing or competing reaction region.');
    const r=object(v,['provider','species','phaseId','standardState','anchor','temperatureId','pressureId','amountIds','referenceIds','extentIds','reactions'],['packageId']);
    if(!['ideal_gas','package'].includes(String(r.provider))||!['vapor','liquido'].includes(String(r.phaseId))||!['gas','liquid'].includes(String(r.anchor))||!['ideal_gas_P0','pure_liquid_TP'].includes(String(r.standardState)))throw new Error('Invalid provider/reference choice.');
    // Optional since 6 November 2026 (B3): only a package provider names a declared package; Python rejects a missing one.
    if(Object.hasOwn(r,'packageId')&&(r.provider!=='package'||!model.termodinamica.paquetes.some(p=>p.id===r.packageId)))throw new Error('Only a package provider names a declared packageId.');
    ids(r.species);ids(r.amountIds);ids(r.referenceIds);ids(r.extentIds);
    const species=region.componenteIds.map(c=>model.componentes.find(v=>v.id===c)?.identidadQuimica?.cas);
    if(JSON.stringify(species)!==JSON.stringify(r.species)||r.amountIds.length!==species.length||r.referenceIds.length!==species.length||!identity(r.temperatureId)||!identity(r.pressureId))throw new Error('Reaction species and graph coordinates disagree.');
    if(!Array.isArray(r.reactions)||!r.reactions.length||r.reactions.length>100)throw new Error('Declare one to 100 reactions.');
    const names=new Set<string>();
    for(const item of r.reactions){
      const reaction=object(item,['id','stoichiometry','equationId']);
      if(typeof reaction.id!=='string'||!/^[A-Za-z][A-Za-z0-9_]{0,39}$/.test(reaction.id)||names.has(reaction.id)||!identity(reaction.equationId))throw new Error('Invalid reaction identity.');
      names.add(reaction.id);const nu=reaction.stoichiometry;
      if(!Array.isArray(nu)||nu.length!==species.length||nu.some(v=>typeof v!=='string'||!/^(?:0|-?[1-9][0-9]*)(?:\/[1-9][0-9]*)?$/.test(v)))throw new Error('Invalid exact rational stoichiometry.');
      if(!nu.some(v=>/^-[1-9]/.test(v))||!nu.some(v=>/^[1-9]/.test(v)))throw new Error('Both reactants and products are required.');
    }
  }
  return value as EquilibriumReactions;
}
