/** Operación `estudiar` del núcleo (contrato §14). El navegador no calcula
 * ninguno de estos resultados: los presenta tal como llegan. */
import type { Expresion, Igualdad } from "./contrato";
import type { DiagnosticoNucleo, FormulacionNucleo, SolicitudNucleo } from "./contratoNucleo";

export type NombreEstudio = "estructura" | "sensibilidad" | "valores" | "asintotica" | "escalas" | "simetrias" | "estabilidad" | "continuacion" | "simulacion";
export const ESTUDIOS: NombreEstudio[] = ["estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias", "estabilidad", "continuacion", "simulacion"];
export type EstadoEstudio = "calculado" | "requiere_datos" | "no_aplicable" | "no_soportado" | "no_convergente" | "rechazado";

export type ValorFisico = { simboloId: string; valor: number; unidad?: string | null };
export type OpcionesEstudio = {
  objetivos?: string[];
  valores?: ValorFisico[];
  analisis?: NombreEstudio[];
  umbralAsintotico?: number;
  cajaEstados?: number;
  estabilidad?: { kMax?: number };
  continuacion?: { parametroId: string; desde: number; hasta: number; unidad?: string | null; pasosMax?: number };
  simulacion?: { tFinal?: number; tFinalSI?: number; periodica?: boolean; muestras?: number; nodos?: number; rtol?: number; atol?: number; verificarMalla?: boolean; fronteras?: { condicionId: string; extremo: "desde" | "hasta" }[] };
};
export type SolicitudEstudio = Omit<SolicitudNucleo, "operacion"> & { operacion: "estudiar"; estudio: OpcionesEstudio };

type Base = { estado: EstadoEstudio; motivo: string; faltan?: string[]; codigo?: string };
export type Racional = { n: number; d: number };

export type TipoTermino = "acumulacion" | "inercia_temporal" | "difusion" | "conveccion" | "reaccion" | "fuente" | "orden_superior" | "mixto" | "flujo" | "valor" | "dato";
export type Lectura = { termino: string; tipo?: TipoTermino | null; nombreClasico?: string; lectura: string };
export type EstudioEstructura = Base & {
  ecuaciones: { id: string; referencia: string | null; terminos: { id: string; lado: string; tipo: TipoTermino; ordenTemporal: number; ordenEspacial: number; campos: string[]; lineal: boolean | null; grupoId: string | null }[] }[];
  condiciones: { id: string; referencia: string | null; terminos: { id: string; lado: string; tipo: TipoTermino; grupoId: string | null }[] }[];
  grupos: { grupoId: string; nombreClasico: string | null; nombresClasicos: string[]; nota: string | null;
    lecturas: (Lectura & { tipoTermino?: TipoTermino | null; referencia?: string | null; tipoReferencia?: TipoTermino | null; equivalentes?: Lectura[] })[] }[];
  normalizados: { objetivo: string; terminoId: string; tipo: TipoTermino; estado: string }[];
};
export type EstudioSensibilidad = Base & { parametros: string[]; escalasLibres: string[]; grupos: { grupoId: string; exponentes: Record<string, Racional> }[]; omitidos: { grupoId: string; motivo: string }[] };
export type EstudioValores = Base & {
  escalas: { escalaId: string; estado: string; valorSI: number | null; dimension: unknown; unidadSI: string | null }[];
  grupos: { grupoId: string; valor: number | null; faltan: string[]; log10: number | null }[];
  ecuaciones: { id: string; coeficientes: { terminoId: string; lado: string; valor: number | null }[]; dispersionLog10: number | null }[];
  dispersionMaxima: number | null;
};
export type Balance = { delta: number; terminos: string[] };
export type EstudioAsintotica = Base & {
  umbral?: number;
  ecuaciones?: { id: string; magnitudes: Record<string, number>; dominantes: string[]; despreciables: string[]; reducida?: Igualdad;
    espacial: null | { ordenMaximo: number; ordenReducido: number; balances: Balance[];
      capa?: { tipo: "perturbacion_singular" | "regular"; condicionesPerdidas?: number; espesor?: number | null; balanceInterior?: string[]; nota?: string;
        ubicacion?: null | { lado: "desde" | "hasta" | "ambos" | "ninguno"; balance: string; criterio: string; en?: { variableId: string; valor: number | null } } } };
    temporal?: { balances: Balance[]; capaInicial?: { duracion: number | null; balanceInterior: string[]; nota: string } } }[];
};
export type EstudioEscalas = Base & {
  referencia?: { u: Record<string, number>; origen: string };
  tiempos?: { reaccion: number | null }; radioJacobiano?: number;
  coordenadas?: ({ coordenada: string; estado: "calculado"; difusividad: number; velocidad: number; longitud: number | null; tiempoDifusion?: number | null; tiempoConveccion?: number | null;
    longitudesInternas: { balance: string; longitud: number }[];
    malla?: { nodosPeclet: number; nodosCapas: number; nodosRecomendados: number; pecletCelda: number; criterio: string };
    pasoExplicitoMaximo?: { eulerExplicito: number; porMecanismo: Record<string, number> };
    rigidez?: { nodos: number; radioEspectral: number; lentoMasRapido: number; cociente: number; recomendacion: string; nota: string } } | { coordenada: string; estado: "no_soportado"; motivo: string })[];
};
export type EstadoHomogeneo = {
  u: Record<string, number>; jacobiano: number[][]; autovalores: { re: number; im: number }[]; homogeneo: "estable" | "marginal" | "inestable";
  espacial: ({ coordenada: string; estado: "calculado"; clase: "estable" | "turing" | "onda" | "inestable_homogenea" | "oscilatoria_homogenea";
    k: number[]; reSigma: number[]; imSigma: number[]; kCritico: number | null; sigmaMaximo: number; banda: { desde: number; hasta: number } | null;
    dominio?: { longitud: number; modosInestablesNeumann: { n: number; k: number; re: number; im: number }[]; nota: string } } | { coordenada: string; estado: "no_soportado"; motivo: string })[];
};
export type EstudioEstabilidad = Base & { campos?: string[]; caja?: [number, number][]; estados?: EstadoHomogeneo[]; continuo?: boolean; notaContinuo?: string };
export type EstudioContinuacion = Base & {
  parametroId?: string; intervaloSI?: [number, number]; campos?: string[];
  ramas?: { inicio: Record<string, number>; puntos: { p: number; u: Record<string, number>; estable: boolean; maxRe: number }[] }[];
  especiales?: { tipo: "pliegue" | "hopf"; p: number; u: Record<string, number>; frecuencia?: number }[];
};
export type Reduccion = { tipo: "semejanza" | "onda_viajera"; estado: string; motivo: string;
  variable?: { id: string; definicion: Expresion }; velocidad?: string;
  perfiles?: { campo: string; id: string; potenciaTau?: Racional }[];
  ecuaciones?: { id: string; potenciaTau?: Racional; ecuacion: Igualdad }[] };
export type EstudioSimetrias = Base & { variables?: string[]; generadores?: { exponentes: Record<string, Racional> }[]; traslaciones?: string[]; reducciones?: Reduccion[]; nota?: string; notaReduccion?: string };
export type EstudioSimulacion = Base & {
  metodo?: { integrador: string; rtol: number; atol: number; nodos: number; evaluaciones: number; jacobianos: number; tFinal: number; frontera?: "periodica" };
  coordenada?: string | null; xi?: number[] | null; tiempos?: number[]; campos?: Record<string, number[][]>;
  avisoMalla?: string;
  verificacionMalla?: { nodosRefinados?: number; diferenciaMaxima?: number; diferenciaRelativa?: number | null; nota?: string; estado?: string; motivo?: string };
  fisico?: { tiempo: { variableId: string | null; valoresSI: number[] | null }; coordenada?: { variableId: string; valoresSI: number[] | null }; campos: Record<string, number[][] | null>; faltan: string[]; nota: string };
  codigoPython?: string | null; codigoMotivo?: string;
  /** La misma trayectoria en el formato común de resultados (docs/FORMATO_RESULTADOS.md). */
  resultados?: import("../../motores/resultados/contrato").ConjuntoResultados;
};
export type ResultadosEstudio = Partial<{
  estructura: EstudioEstructura; sensibilidad: EstudioSensibilidad; valores: EstudioValores; asintotica: EstudioAsintotica; escalas: EstudioEscalas;
  simetrias: EstudioSimetrias; estabilidad: EstudioEstabilidad; continuacion: EstudioContinuacion; simulacion: EstudioSimulacion;
}>;
export type RespuestaEstudio = {
  formato: "adimensionalizacion.resultado"; version: 1; operacion: "estudiar";
  estado: "correcto" | "rechazado" | "no_soportado" | "requiere_datos"; nucleo: string;
  diagnosticos: DiagnosticoNucleo[];
  vinculo: null | { documentoId: string; modeloId: string; modeloRevision: number; estudio: OpcionesEstudio; firma: string; [k: string]: unknown };
  formulacion?: FormulacionNucleo; estudio?: ResultadosEstudio;
};
