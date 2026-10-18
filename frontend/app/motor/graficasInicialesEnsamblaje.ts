import type {GraficaMotor} from './hojasMotor';
import type {ResultadoMotor} from './modeloNumerico';

export function graficasInicialesEnsamblaje(r:ResultadoMotor):GraficaMotor[]{
  const estados=r.estadosAcoplados??[];
  const base={tipo:'tiempo' as const,x:'t',ancha:false,altura:310,instante:r.tiempos.length-1};
  if(new Set(estados.map(z=>z.componenteId)).size<=1)return [{...base,id:'ensamblaje',nombre:'Masas por volumen',y:estados.slice(0,6).map(z=>`m_${z.id}`)}];
  const volumenes=[...new Set(estados.map(z=>z.volumenId))];
  return volumenes.flatMap(id=>{
    const locales=estados.filter(z=>z.volumenId===id),grupos:GraficaMotor[]=[];
    for(let i=0;i<locales.length;i+=4){
      const grupo=locales.slice(i,i+4),sufijo=locales.length>4?` · ${grupo.map(z=>z.simbolo).join(', ')}`:'';
      grupos.push({...base,id:`masas-${id}-${i}`,nombre:`${locales[0].volumenNombre}${sufijo}`,y:grupo.map(z=>`m_${z.id}`)});
    }
    return grupos;
  });
}
