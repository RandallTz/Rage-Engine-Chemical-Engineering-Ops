import type {RespuestaValidacionV2} from './contratoEnsamblajeV2';
const DATOS_PAQUETE=new Set(['MOTOR_ENS_DATO_PURO_AUSENTE','MOTOR_ENS_PARAMETRO_AUSENTE','MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE','MOTOR_ENS_UNIFAC_GRUPO_DESCONOCIDO','MOTOR_ENS_UNIFAC_INTERACCION_AUSENTE']);

/** A closed structural count alone cannot certify thermodynamic initialization. */
export function estadoResolucionRed(r?:RespuestaValidacionV2){
  const diagnostico=r?.diagnosticos[0];
  const completa=!!r&&['listo','redundante_compatible'].includes(r.recuento.estado);
  const puedeResolver=completa&&!!r.modeloId&&r.inicializacion.estado==='compatible'&&!diagnostico;
  const estados:Record<string,string>={MOTOR_ENS_SUSTITUCION_INVALIDA:'Revisar propiedades del paquete',MOTOR_ENS_SUSTITUCION_NO_ADMITIDA:'Sustitución no admitida',MOTOR_ENS_REFERENCIAS_INCOMPATIBLES:'Referencias incompatibles'};
  return {puedeResolver,diagnostico,estado:!r?'Validando…':diagnostico&&estados[diagnostico.codigo]?estados[diagnostico.codigo]:diagnostico&&DATOS_PAQUETE.has(diagnostico.codigo)?'Faltan datos del paquete':diagnostico?.estado==='no_soportado'?'Modelo no disponible':completa&&r.inicializacion.estado!=='compatible'?'Inicialización pendiente':r.recuento.estado.replaceAll('_',' ')};
}
