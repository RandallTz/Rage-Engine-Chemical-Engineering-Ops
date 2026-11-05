/** Shared strict closure evidence reader; independent of compilation dispatch. */
export type ThermodynamicClosureReport = {volumeId:string;package:string;species:string[];mode:'single_phase'|'equilibrium';specification:'PH'|'UV'|'TP'|null;
  anchor:'gas'|'liquid'|null;liquidOnly:boolean;candidatePhases:string[];fingerprint:string;evaluations:number;inlets:Record<string,Record<string,unknown>>;source:'core.termodinamica.derived_bridge'};
const CLOSURE_KEYS=['volumeId','package','species','mode','specification','anchor','liquidOnly','candidatePhases','fingerprint','evaluations','inlets','source'];
export function readThermodynamicClosures(value: unknown): ThermodynamicClosureReport[] {
  const isText=(v:unknown)=>typeof v==='string'&&v.length>0;
  if(!Array.isArray(value)||!value.length||value.some(row=>!row||typeof row!=='object'||Array.isArray(row)
    ||Object.keys(row).length!==CLOSURE_KEYS.length||Object.keys(row).some(key=>!CLOSURE_KEYS.includes(key))
    ||!isText(row.volumeId)||!isText(row.package)||!Array.isArray(row.species)||!row.species.length||!row.species.every(isText)
    ||!['single_phase','equilibrium'].includes(row.mode)||![null,'PH','UV','TP'].includes(row.specification)||![null,'gas','liquid'].includes(row.anchor)
    ||typeof row.liquidOnly!=='boolean'||!Array.isArray(row.candidatePhases)||!row.candidatePhases.length||!row.candidatePhases.every((p:unknown)=>p==='V'||p==='L')
    ||!isText(row.fingerprint)||!Number.isSafeInteger(row.evaluations)||row.evaluations<0
    ||!row.inlets||typeof row.inlets!=='object'||Array.isArray(row.inlets)||Object.values(row.inlets).some(v=>!v||typeof v!=='object'||Array.isArray(v))
    ||row.source!=='core.termodinamica.derived_bridge'))throw new Error('Invalid thermodynamic closure report.');
  if(new Set(value.map(row=>row.volumeId)).size!==value.length)throw new Error('Duplicate thermodynamic closure volume.');
  return value as ThermodynamicClosureReport[];
}

