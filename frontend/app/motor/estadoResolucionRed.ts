import type {RespuestaValidacionV2} from './contratoEnsamblajeV2';
const DATOS_PAQUETE=new Set(['MOTOR_ENS_DATO_PURO_AUSENTE','MOTOR_ENS_PARAMETRO_AUSENTE','MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE','MOTOR_ENS_UNIFAC_GRUPO_DESCONOCIDO','MOTOR_ENS_UNIFAC_INTERACCION_AUSENTE']);

/** A closed structural count alone cannot certify thermodynamic initialization. */
export function estadoResolucionRed(r?:RespuestaValidacionV2){
  const diagnostico=r?.diagnosticos[0];
  const completa=!!r&&['listo','redundante_compatible'].includes(r.recuento.estado);
  const puedeResolver=completa&&!!r.modeloId&&r.inicializacion.estado==='compatible'&&!diagnostico;
  const estados:Record<string,string>={MOTOR_ENS_SUSTITUCION_INVALIDA:'Review package properties',MOTOR_ENS_SUSTITUCION_NO_ADMITIDA:'Unsupported substitution',MOTOR_ENS_REFERENCIAS_INCOMPATIBLES:'Incompatible references'};
  const counts:Record<string,string>={listo:'Ready',redundante_compatible:'Compatible redundant constraints',incompleto:'Incomplete',incompatible:'Incompatible',no_soportado:'Unsupported'};
  return {puedeResolver,diagnostico,estado:!r?'Validating…':diagnostico&&estados[diagnostico.codigo]?estados[diagnostico.codigo]:diagnostico&&DATOS_PAQUETE.has(diagnostico.codigo)?'Missing package data':diagnostico?.estado==='no_soportado'?'Model unavailable':completa&&r.inicializacion.estado!=='compatible'?'Initialization pending':counts[r.recuento.estado]??r.recuento.estado.replaceAll('_',' ')};
}
