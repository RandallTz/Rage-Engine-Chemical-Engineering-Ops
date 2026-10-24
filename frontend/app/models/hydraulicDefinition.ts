/** Data/reference contract only. Python owns admission, algebra and time integration. */
import type {ModeloComun} from '../../motores/modelo/contrato';
export type HydraulicPressure={kind:'datum';datumId:string}|{kind:'storage';volumeId:string}|{kind:'recover'};
export type HydraulicPath={volumeId:string;inletStreamId:string;outletStreamId:string;lengthId:string;areaId:string;diameterId:string;driveId:string;inletElevationId:string;outletElevationId:string;flow:{kind:'prescribed';datumId:string}|{kind:'dynamic';initialId:string};inletPressure:HydraulicPressure;outletPressure:HydraulicPressure};
export type HydraulicNetwork={format:'rage.hydraulic-network';version:1;medium:{densityId:string;viscosityId:string;temperatureId:string;minimumPressureId:string;reason:string};gravityId:string;storages:{volumeId:string;areaId:string;surfacePressureId:string;floorElevationId:string}[];paths:HydraulicPath[]};
function object(value:unknown,required:string[],optional:string[]=[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Invalid hydraulic object.');const o=value as Record<string,unknown>;if(required.some(k=>!Object.hasOwn(o,k))||Object.keys(o).some(k=>!required.includes(k)&&!optional.includes(k)))throw new Error('Unknown or missing hydraulic fields.');return o;}
function strings(value:Record<string,unknown>,keys:string[]){if(keys.some(k=>typeof value[k]!=='string'||!(value[k] as string).trim()))throw new Error('Expected hydraulic identities or datum references.');}
export function readHydraulicNetwork(value:unknown,model?:ModeloComun):HydraulicNetwork{
  const o=object(value,['format','version','medium','gravityId','storages','paths']);
  if(o.format!=='rage.hydraulic-network'||o.version!==1)throw new Error('Unsupported hydraulic network.');
  const m=object(o.medium,['densityId','viscosityId','temperatureId','minimumPressureId','reason']);strings(m,Object.keys(m));strings(o,['gravityId']);
  if(!Array.isArray(o.storages)||!Array.isArray(o.paths)||!o.paths.length||o.paths.length>160||o.storages.length>160)throw new Error('Invalid hydraulic collection.');
  const owners=new Set<string>();
  for(const value of [...o.storages,...o.paths]){if(!value||typeof value!=='object')throw new Error('Expected a hydraulic owner.');const v=value as Record<string,unknown>;if(typeof v.volumeId!=='string'||!v.volumeId.trim()||owners.has(v.volumeId))throw new Error('Repeated hydraulic owner.');owners.add(v.volumeId);}
  for(const value of o.storages){const v=object(value,['volumeId','areaId','surfacePressureId','floorElevationId']);strings(v,Object.keys(v));}
  for(const value of o.paths){const p=object(value,['volumeId','inletStreamId','outletStreamId','lengthId','areaId','diameterId','driveId','inletElevationId','outletElevationId','flow','inletPressure','outletPressure']);strings(p,Object.keys(p).filter(k=>!['flow','inletPressure','outletPressure'].includes(k)));
    const f=object(p.flow,['kind'],['datumId','initialId']);if(f.kind==='prescribed'){object(f,['kind','datumId']);strings(f,['datumId']);}else if(f.kind==='dynamic'){object(f,['kind','initialId']);strings(f,['initialId']);}else throw new Error('Unknown hydraulic flow role.');
    for(const key of ['inletPressure','outletPressure']){const b=object(p[key],['kind'],['datumId','volumeId']);if(b.kind==='datum'){object(b,['kind','datumId']);strings(b,['datumId']);}else if(b.kind==='storage'){object(b,['kind','volumeId']);strings(b,['volumeId']);}else if(b.kind==='recover')object(b,['kind']);else throw new Error('Unknown hydraulic pressure role.');}
  }
  const network=value as HydraulicNetwork;
  for(const path of network.paths){const recovered=[path.inletPressure,path.outletPressure].filter(p=>p.kind==='recover').length;if(recovered!==Number(path.flow.kind==='prescribed'))throw new Error('Hydraulic flow and recovered pressure roles are overdetermined or incomplete.');}
  if(model){
    if(owners.size!==model.volumenes.length||model.volumenes.some(v=>!owners.has(v.id)))throw new Error('Hydraulic ownership disagrees with the common model.');
    const references=[network.gravityId,network.medium.densityId,network.medium.viscosityId,network.medium.temperatureId,network.medium.minimumPressureId];
    for(const storage of network.storages)references.push(storage.areaId,storage.surfacePressureId,storage.floorElevationId);
    const storageIds=new Set(network.storages.map(s=>s.volumeId)),usedStreams=new Set<string>();
    for(const path of network.paths){
      references.push(path.lengthId,path.areaId,path.diameterId,path.driveId,path.inletElevationId,path.outletElevationId,path.flow.kind==='prescribed'?path.flow.datumId:path.flow.initialId);
      for(const [boundary,streamId,inlet] of [[path.inletPressure,path.inletStreamId,true],[path.outletPressure,path.outletStreamId,false]] as const){
        const stream=model.corrientes.find(s=>s.id===streamId);
        if(!stream||usedStreams.has(streamId)||(inlet?stream.hasta:stream.desde)!==path.volumeId)throw new Error('Invalid or reused hydraulic stream binding.');
        usedStreams.add(streamId);const adjacent=inlet?stream.desde:stream.hasta;
        if(boundary.kind==='storage'){if(!storageIds.has(boundary.volumeId)||adjacent!==boundary.volumeId)throw new Error('Hydraulic pressure storage is not adjacent to its path.');}
        else {if(adjacent!==null)throw new Error('An external hydraulic pressure cannot bypass an internal owner.');if(boundary.kind==='datum')references.push(boundary.datumId);}
      }
    }
    if(usedStreams.size!==model.corrientes.length||references.some(id=>!Object.hasOwn(model.datos,id)))throw new Error('Missing hydraulic data or unbound material streams.');
  }
  return network;
}
