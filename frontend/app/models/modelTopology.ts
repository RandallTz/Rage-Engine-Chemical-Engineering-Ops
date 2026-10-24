/** Topology changes invalidate a numerical specialization, never the source laws.
 * Keep the previous bindings for review rather than forcing domains/components
 * to fit an old solver configuration. Display-name edits do not change topology.
 */
import type {HojaMotor} from '../motor/hojasMotor';
function topology(model:HojaMotor){const a=model.ensamblaje;return a?JSON.stringify([a.componentes?.map(c=>c.id),a.volumenes.map(v=>[v.id,v.componentesIds]),a.corrientes.map(s=>[s.id,s.desde,s.hasta,s.componentesIds])]):'';}
export function reconcileModelTopology(previous:HojaMotor,next:HojaMotor):HojaMotor{
  if(!previous.hydraulicNetwork||topology(previous)===topology(next))return next;
  return {...next,previousHydraulicNetwork:previous.hydraulicNetwork,hydraulicNetwork:undefined,resultado:undefined,resultadoRef:undefined};
}
