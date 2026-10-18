import type {ResultadoMotor,SerieEvaluadaMotor} from './modeloNumerico';

/** Presentation only: aggregate the certified phase fractions, never infer liquid
 * from 1-q (a supercritical fluid is neither liquid nor vapor). No flash here.
 * Derived series stay outside the original, immutable backend series. */
export function fraccionesFaseGraficas(r:ResultadoMotor):SerieEvaluadaMotor[]{
  const e=r.ensamblajeTermodinamico,a=e?.respuesta.resultados;
  if(!e||!a)return [];
  const tipos=['liquido','solido','fluido'] as const;
  const nombres={liquido:'líquido',solido:'sólido',fluido:'fluido supercrítico'};
  return tipos.filter(tipo=>tipo==='liquido'||a.estadosTermodinamicos.some(e=>e.fases.some(f=>f.tipo===tipo))).map(tipo=>({
    id:`volumen.${e.solicitud.volumen.id}.fraccionMasica.${tipo}`,
    nombre:`Fracción másica de ${nombres[tipo]}`,unidad:'1',grupo:'Fases · fracción másica',
    valores:a.estadosTermodinamicos.map(e=>e.fases.filter(f=>f.tipo===tipo).reduce((s,f)=>s+f.fraccionMasica,0)),
  }));
}
