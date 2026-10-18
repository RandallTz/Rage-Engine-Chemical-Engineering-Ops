import type {EvaluacionEstado} from './contratoTermodinamica';
import type {PotencialesV2,VolumenV2} from './contratoEnsamblajeV2';

/** Protocol checks, independent of a particular EOS or component count.
 * All quantities below are homogeneous: molar energy per phase, total energy
 * for the volume. This does not repeat the backend's stability calculation. */
export function verificarPotencialesComponentes(e:EvaluacionEstado,p:PotencialesV2,ids:number[],N:number){
  const fallo=(m:string):never=>{throw new Error(`Respuesta multifásica incompatible: ${m}`);};
  const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
  const claves=ids.map(String),masas=new Map(e.componentes.map(c=>[c.id,c.masaMolarKgMol]));
  let G=0,escala=0;
  for(const fase of e.fases){
    const datos=p.fases.find(f=>f.faseId===fase.id);
    if(!datos?.mu||typeof datos.mu!=='object'||Array.isArray(datos.mu)||Object.keys(datos.mu).length!==ids.length||claves.some(id=>!Object.hasOwn(datos.mu,id)))fallo(`potenciales incompletos en ${fase.id}`);
    let g=0,M=0;
    for(const id of ids){const x=fase.composicionMolar[id],mu=datos!.mu[id];
      if(mu!==null&&!fin(mu)||x>0&&!fin(mu))fallo(`potencial del componente ${id} en ${fase.id}`);
      M+=x*masas.get(id)!;if(x>0)g+=x*mu!;
    }
    const h=M*fase.propiedades.h,Ts=M*e.T*fase.propiedades.s;
    // Use the scale of both molar terms, including near g = h - Ts = 0.
    if(!fin(g)||Math.abs(g-(h-Ts))>1e-8+1e-7*Math.max(Math.abs(h),Math.abs(Ts),Math.abs(g)))fallo(`Gibbs y potenciales no reconstruyen la fase ${fase.id}`);
    G+=N*fase.fraccionMolar*g;
    escala+=N*fase.fraccionMolar*(Math.abs(h)+Math.abs(Ts));
  }
  // Old responses did not declare whether G is extensive. Keep them readable,
  // without guessing their units or manufacturing a new certificate.
  if(p.unidades&&(!fin(G)||Math.abs(G-p.G)>1e-8+1e-7*Math.max(escala,Math.abs(p.G))))fallo('G total no coincide con los potenciales por componente');
}

/** SI is part of the protocol, even if both a catalog and a series were
 * corrupted to the same wrong unit. Never reinterpret those numbers as SI. */
export function unidadesEstadoVolumen(v:VolumenV2):Record<string,string>{
  const raiz=`volumen.${v.id}.`;
  return Object.fromEntries([
    ...v.componenteIds.map(id=>[`${raiz}n.${id}`,'mol']),
    ...Object.entries({T:'K',P:'Pa',U:'J',H:'J',V:'m3',masa:'kg',S:'J/K',W:'J'}).map(([id,u])=>[raiz+id,u]),
  ]);
}
