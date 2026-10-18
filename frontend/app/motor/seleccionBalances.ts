import type {HojaMotor} from './hojasMotor';
import type {FamiliaBalance} from './familiasBalance';

export type SeleccionBalances=Record<FamiliaBalance,boolean>;
/** Legacy sheets solve matter only. Viewing a balance is independent of selecting it. */
export const BALANCES_LEGADOS:SeleccionBalances={materia:true,energia:false,momento:false};
export const balancesHoja=(h:Pick<HojaMotor,'balances'>):SeleccionBalances=>({...BALANCES_LEGADOS,...h.balances});
export function bloqueosBalances(h:Pick<HojaMotor,'balances'>):string[]{
  const b=balancesHoja(h);
  if(!Object.values(b).some(Boolean))return ['Activa un balance para resolver este sistema.'];
  const pendientes=[b.momento?'momento':''].filter(Boolean);
  return pendientes.length?[`La resolución de ${pendientes.join(' y ')} todavía no está implementada. Desactiva ${pendientes.length===1?'ese balance':'esos balances'} para resolver materia.`]:[];
}
export function seleccionarBalance(h:HojaMotor,familia:FamiliaBalance,activo:boolean):HojaMotor{
  const balances=balancesHoja(h);
  if(balances[familia]===activo)return h;
  return {...h,balances:{...balances,[familia]:activo},resultado:undefined,resultadoRef:undefined};
}
