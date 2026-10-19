/** Modelo común v0 (docs/CONTRATO_MODELO_COMUN.md). Tipos del lado del cliente.
 * El lector canónico es core/modelo/lector.py; lector.ts aplica las mismas reglas
 * estructurales para rechazar en el cliente lo que el servidor rechazaría. */
import type { Modelo as ModeloMatematico, Expresion } from "../../app/adimensionalizacion/contrato";
import type { Forma, ConfigExploracion } from "../../app/adimensionalizacion/contrato";
import type { Componente } from "../../app/motor/materiaEstado";
import type { FormulacionMateria } from "../../app/motor/recorridoMateria";
import type { FormulacionEnergia } from "../../app/motor/recorridoEnergia";
import type { PoliticaEstado } from "../../app/motor/contratoTermodinamica";
import type { PaqueteV2, CorrienteV2, IntercambioTermicoV2 } from "../../app/motor/contratoEnsamblajeV2";

export const VERSION_MODELO = 0;

export type Dato = {
  magnitud: string;
  funcion: "inicial" | "frontera" | "geometria" | "estudio" | "parametro";
  declaracion: { texto: string; unidad: string };
  origen: { propietarioId: string; ruta: string };
};

/** La termodinámica siempre presente: todo volumen declara su cierre. */
export type Cierre =
  | { tipo: "equilibrio"; paqueteId: string; politica: PoliticaEstado }
  | { tipo: "supuesto"; supuesto: "fase_no_evaluada" | "u_lineal"; motivo: string;
      /** u(T) = u_ref + c (T - T_ref), válida en [T_min, T_max]; rho si la energía de flujo o el volumen la necesitan. */
      parametros?: { cId: string; uRefId: string; TRefId: string; TMinId: string; TMaxId: string; rhoId?: string } };

export type Frontera =
  | { tipo: "rigida"; datoId: string; presionRestriccionId?: string }
  | { tipo: "presion_prescrita"; presionId: string }
  | { tipo: "sin_relacion" }
  | { tipo: "malla_1d" };

export type Volumen = {
  id: string; componenteIds: number[];
  balances: { materia: boolean; energia: boolean; momento: boolean };
  /** Indicadores de reducción del motor: entrada del motor de supuestos. */
  supuestos: { materia: Omit<FormulacionMateria, "componentes" | "fronteras">; energia: FormulacionEnergia | null };
  frontera: Frontera;
  inicial: { cantidades: { base: "masica" | "molar"; datoIds: Record<string, string> }; energia?: { tipo: "U" | "T"; datoId: string } } | { tipo: "por_datos" };
  termodinamica: Cierre;
  /** Datos de los términos que conservan los supuestos (motor de balances, core/balances):
   * "generacion.<componenteId>", "consumo.<id>", "resto.<id>", "calor", "trabajo_viscoso", "fuerzas", "fuente". */
  terminos?: Record<string, string>;
  /** Volumen del dominio como dato (constante o función de t). */
  volumenDatoId?: string;
};

/** Corriente de la revisión 2 del ensamblaje, más los puertos del motor TS. */
export type Corriente = Omit<CorrienteV2, "materia"> & {
  materia:
    | { modo: "por_componente"; base: "masica" | "molar" | "volumetrica"; caudalIds: Record<string, string> }
    | { modo: "total_desde_donante"; base: "masica" | "molar" | "volumetrica"; caudalId: string }
    | { modo: "total_y_composicion"; base: "masica" | "molar"; caudalId: string; fracciones: Record<string, number> };
  constante?: boolean;
};

export type Estudio = {
  tipo: "temporal"; tiempoId: string; metodoSolicitado: string | null; muestras: number; rtol: number;
  atol: { cantidad: number; energia?: number };
  espacial?: { celdas: number; frontera: "periodica" | "valores" | "sin_flujo" | "" };
  cierreMasico?: "densidad" | "volumen" | "";
};

export type ConfigAdimensionalizacion = { version: 1 | 2; formas: Forma[]; activaId: string; exploracion?: ConfigExploracion };

export type Procedencia = { tipo: "documento_adimensional" | "ensamblaje_v2" | "hoja_motor_materia" | "nuevo"; [clave: string]: unknown };

export type Restriccion = { simboloId: string; tipo: "no_negativo" }
  /** Una expresión de las variables que debe mantenerse >= 0 (dominio de validez de un supuesto). */
  | { expresion: Expresion; tipo: "no_negativo"; descripcion: string };
export type ModeloComun = {
  formato: "rage.modelo"; version: typeof VERSION_MODELO;
  id: string; nombre: string;
  componentes: Componente[];
  termodinamica: { paquetes: PaqueteV2[] };
  volumenes: Volumen[];
  corrientes: Corriente[];
  intercambios: IntercambioTermicoV2[];
  datos: Record<string, Dato>;
  matematico: ModeloMatematico | null;
  /** Dominio de las variables de `matematico`: el cálculo se detiene en el
   * instante en que una de ellas lo abandonaría (agotamiento). */
  restricciones?: Restriccion[];
  /** Magnitudes derivadas de las variables de `matematico`, publicadas como series «observable.<id>». */
  observables?: { id: string; nombre: string; unidadSI: string; expresion: Expresion }[];
  /** Expresiones que deben ser ~0 en cada muestra (cierres de presupuesto): max|expresion| / max|escala|. */
  verificaciones?: { id: string; descripcion: string; expresion: Expresion; escala: Expresion; tolerancia?: number }[];
  estudio: Estudio | null;
  motores: { adimensionalizacion?: ConfigAdimensionalizacion };
  procedencia: Procedencia;
};
