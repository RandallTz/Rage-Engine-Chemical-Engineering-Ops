/** Display precision only: CSV and solver values retain their original numbers. */
export function formatearNumeroMotor(v:number,cifras=7):string{
  if(!Number.isFinite(v))return '—';
  if(v===0)return '0';
  if(Math.abs(v)<.001||Math.abs(v)>=1e7)return Number(v.toPrecision(cifras)).toExponential();
  return v.toLocaleString('es-MX',{maximumSignificantDigits:cifras});
}
