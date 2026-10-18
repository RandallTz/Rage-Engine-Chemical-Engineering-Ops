import type {Componente} from './materiaEstado';
import type {DatoMotor} from './modeloNumerico';
import type {ModeloEstado,PoliticaEstado,EvaluacionEstado,FaseEstado} from './contratoTermodinamica';
import type {FormulacionMateria} from './recorridoMateria';
import type {FormulacionEnergia,ContextoEnergia} from './recorridoEnergia';
import type {MagnitudMotor} from './unidadesMotor';

/** Independent backend assembly protocol. Physics is executed only by /motor/ensamblajes. */
export type CapacidadesEnsamblaje={revision:1;disponible:boolean;motivo:string|null;modelos:ModeloEstado[];
  componentesCAS:string[];volumenes:number;componentes:number;balances:{materia:boolean;energia:boolean;momento:boolean};
  formas:{materia:'cantidad';energia:'total'};fronteras:('rigida'|'presion_prescrita')[];
  inicializaciones:Record<'rigida'|'presion_prescrita',('U'|'T')[]>;presionPrescrita:{constante:boolean;funcionSuave:boolean;discontinua:boolean};
  corrientes:{mecanismos:'convectivo'[];materia:('por_componente'|'total_y_composicion')[];presionExterior:('dato'|'continuidad')[];inversion:boolean};
  extracciones:('mezcla_homogenea'|'fase')[];fases:{monofasico:boolean;coexistenciaLiquidoVapor:boolean;eventos:boolean};
  transferencias:'calor'[];expresiones:{variables:['t'];unidadTiempo:'s';suaves:string[];noAdmitidas:string[]};
  integradores:{id:'rk45';nombre:string;tolerancias:string[]}[];muestrasMaximas:number;dinamicaApiPuntual:false};
export type ExtraccionDinamica={tipo:'mezcla_homogenea'}|{tipo:'fase';fase:FaseEstado};
export type CierreDinamico={modelo:ModeloEstado;politica:PoliticaEstado;extracciones?:Record<string,ExtraccionDinamica>;presionesCorrientes?:Record<string,'continuidad'>};
export type OrigenDato={propietarioId:string;ruta:string};
export type DatoEnsamblaje={magnitud:MagnitudMotor;funcion:'inicial'|'frontera'|'geometria'|'estudio';declaracion:DatoMotor;origen:OrigenDato};
export type FronteraDinamica=
  |{tipo:'rigida';datoId:string;presionRestriccionId?:string}
  |{tipo:'presion_prescrita';presionId:string}
  |{tipo:'sin_relacion'};
export type MateriaCorrienteDinamica=
  |{modo:'por_componente';base:'masica'|'molar';caudalIds:Record<string,string>}
  |{modo:'total_y_composicion';base:'masica'|'molar';caudalId:string;composicion:{base:'masica'|'molar';fracciones:Record<string,number>}};
export type PresionExteriorDinamica={tipo:'dato';datoId:string}|{tipo:'continuidad';volumenId:string;restriccionAdicionalId?:string};
export type CorrienteDinamica={id:number;desde:string|null;hasta:string|null;componenteIds:number[];mecanismo:'convectivo'|'selectivo'|null;materia:MateriaCorrienteDinamica;extraccion?:ExtraccionDinamica;estadoExterior?:{tipo:'TP';temperaturaId:string;presion:PresionExteriorDinamica}};
export type SolicitudEnsamblajeDinamico={
  revision:1;solicitudId:string;componentes:Componente[];
  volumen:{id:string;componenteIds:number[];balances:{materia:boolean;energia:boolean;momento:boolean};
    formulacionMateria:Omit<FormulacionMateria,'componentes'|'fronteras'>;formulacionEnergia:FormulacionEnergia;
    contextoEnergia:ContextoEnergia;cierre:CierreDinamico;frontera:FronteraDinamica;
    inicial:{masaIds:Record<string,string>;energia:{tipo:'U'|'T';datoId:string}}};
  corrientes:CorrienteDinamica[];datos:Record<string,DatoEnsamblaje>;
  transferencias:Record<string,string>;
  estudio:{tipo:'temporal';tiempoId:string;metodoSolicitado:string|null;muestras:number;rtol:number;atol:{masa:number;energia:number}};
  /** Audit trail only. Executable terms come from structured active formulations, never this LaTeX. */
  derivacion:{materia:{titulo:string;ecuaciones:string[]}[];energia:{titulo:string;ecuacion:string;relaciones:string[]}[]};
};
export type DiagnosticoPreparacion={codigo:string;estado:'incompleto'|'conflicto'|'no_soportado'|'invalido';mensaje:string;variableIds:string[];origen:OrigenDato};
export type PreparacionDinamica={solicitud:SolicitudEnsamblajeDinamico|null;diagnosticos:DiagnosticoPreparacion[];
  /** Local conservation inspection only; never sent as extra executable equations. */
  estructura?:import('./estructuraTermodinamica').EstructuraTermodinamica};
/** Counts belong to backend assembly. A local list of empty fields is NOT a DOF certificate. */
export type RecuentoDinamico={estado:'listo'|'incompleto'|'conflicto'|'redundante_compatible'|'no_evaluable';
  analisis:'estructural'|'rango_numerico'|'no_evaluable';variables:number|null;ecuacionesIndependientes:number|null;
  datosDefinidos:number|null;datosFaltantes:number|null;inicialesFaltantes:number|null;gradosLibertad:number|null;motivo?:string};
export type VariableEnsamblada={id:string;propietarioId:string;componenteId?:number;magnitud:string;unidadSI:string;
  papel:'diferencial'|'algebraica'|'dato'|'parametro';datoId?:string};
export type EcuacionEnsamblada={id:string;propietarioId:string;familia:'materia'|'energia'|'estado'|'mecanica';
  variableIds:string[];latex:string;unidadResiduo:string};
export type RespuestaValidacionDinamica={revision:1;solicitudId:string;modeloId:string|null;recuento:RecuentoDinamico;
  variables:VariableEnsamblada[];ecuaciones:EcuacionEnsamblada[];diagnosticos:DiagnosticoPreparacion[];
  inicializacion:{estado:'pendiente'|'compatible'|'incompatible'|'no_soportada';variables:Record<string,number>;estadoTermodinamico:EvaluacionEstado|null}};
export type RespuestaResolucionDinamica={validacion:RespuestaValidacionDinamica;estado:'resuelto'|'parcial'|'invalido'|'no_convergente'|'no_soportado';
  resultados:null|{metodo:string;tiempos:number[];series:{variableId:string;unidadSI:string;valores:number[]}[];
    estadosTermodinamicos:EvaluacionEstado[];eventos:{codigo:string;tiempo:number;variableIds:string[]}[];
    residuos:{ecuacionId:string;maximoEscalado:number;tolerancia:number}[]}};
