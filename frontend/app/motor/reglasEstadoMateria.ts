import type {FormulacionMateria} from './recorridoMateria';
import type {EvaluacionRegla} from './materiaEstado';
export const idConcentracionMedia=(id:number)=>`concentracion_media_c${id}`;
/** Only the pre-existing mean component concentration relation can be reduced.
 * A requested property evaluation is never treated as a proved identity. */
export function concentracionConstante(f:FormulacionMateria,indice?:string):boolean{
  if(f.densidadMediaConstante)return true;
  const componentes=(f.componentes??[]).filter(c=>indice===undefined||indice==='i'||c.simbolo===indice);
  return componentes.length>0&&componentes.every(c=>f.reglasEstado?.densidades?.some(r=>r.variableId===idConcentracionMedia(c.id)&&r.fuente==='dato'&&r.constanciaTemporal==='asumida'));
}
export function analizarReglasEstado(f:FormulacionMateria){
  const evaluacion:EvaluacionRegla[]=[],bloqueos:string[]=[],reglas=f.reglasEstado;
  if(!reglas)return {evaluacion,bloqueos};
  const fase=reglas.fases;
  if(fase){
    if(!['sin_restriccion','monofasico'].includes(fase.cantidad)||!['sin_restriccion','sin_cambio_de_fase'].includes(fase.cambioInterno)||!['no_solicitada','termodinamica'].includes(fase.evaluacion))bloqueos.push('Reglas de fase no válidas.');
    evaluacion.push({reglaId:'fases',aplicadaEnEcuaciones:false,verificacion:fase.evaluacion==='termodinamica'?'no_evaluable':'no_solicitada',motivo:'Las restricciones se conservan; no existe todavía una evaluación termodinámica ni balances por fase.'});
  }
  const ids=new Set<string>();
  for(const r of reglas.densidades??[]){
    if(ids.has(r.variableId)||!r.variableId||!['dato','propiedades'].includes(r.fuente)||!['sin_restriccion','asumida','a_verificar'].includes(r.constanciaTemporal))bloqueos.push('Regla de densidad inválida o repetida.');ids.add(r.variableId);
    const conocida=f.componentes?.some(c=>r.variableId===idConcentracionMedia(c.id)),aplicada=!!(conocida&&f.cantidadVolumen&&r.fuente==='dato'&&r.constanciaTemporal==='asumida');
    if(r.constanciaTemporal==='asumida'&&!aplicada)bloqueos.push(`${r.variableId}: la relación constante necesita una variable soportada y un dato explícito; las propiedades y densidades de fase no se ejecutan todavía.`);
    evaluacion.push({reglaId:r.variableId,aplicadaEnEcuaciones:aplicada,verificacion:r.fuente==='propiedades'?'no_evaluable':r.constanciaTemporal==='a_verificar'?'pendiente':'no_solicitada',motivo:aplicada?'Hipótesis explícita sobre la concentración media del componente; no es una verificación termodinámica.':'La elección se conserva sin anular derivadas ni certificar propiedades.'});
  }
  return {evaluacion,bloqueos};
}
