/** Read located backend requirements without interpreting physical equations. */
export type ModelDiagnostic = {ownerId:string; family:string; code:string; message:string};
export function diagnosticView(family:string){
  const views:Record<string,'materia'|'momento'|'energia'|'termodinamica'>={matter:'materia',momentum:'momento',energy:'energia',thermodynamics:'termodinamica'};
  return views[family]??'materia';
}
export function readModelDiagnostics(value:unknown):ModelDiagnostic[]{
  if(value===undefined)return [];
  if(!Array.isArray(value)||value.some(item=>!item||typeof item!=='object'||Object.keys(item).some(key=>!['ownerId','family','code','message'].includes(key))||['ownerId','family','code','message'].some(key=>typeof item[key]!=='string'||!item[key].trim())))throw new Error('Invalid model diagnostics.');
  return value as ModelDiagnostic[];
}
