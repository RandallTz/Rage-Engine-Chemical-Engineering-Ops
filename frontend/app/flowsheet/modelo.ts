import type { Edge, Node } from "@xyflow/react";
import type { InformeBloque, Inconsistencia } from "./PanelLateral";
import type { DatosDiagramaColumna } from "../components/DiagramaColumna";

export type TipoOperacion =
  | "columna" | "mezclador" | "divisor" | "bomba" | "reactor_cstr"
  | "flash" | "intercambiador" | "valvula"
  | "separador" | "compresor" | "reactor_equilibrio" | "intercambiador_doble"
  | "reactor_pfr" | "absorbedor";
export type MetodoColumna = "mccabe_thiele" | "ponchon_savarit" | "fug";

export interface DatosOperacion extends Record<string, unknown> {
  clase: "operacion";
  tipo: TipoOperacion;
  metodo?: MetodoColumna;
  P_sistema: number;
  q_fijo?: number; // ponchon_savarit y fug: ahi q NO es variable de pool
  indice_LK?: number; // solo fug: componente clave ligero
  indice_HK?: number; // solo fug: componente clave pesado
  fracciones?: string; // solo divisor
  con_balance_energia?: boolean; // solo columna: separar materia de energia
  // solo reactor_cstr: la estequiometria se escribe como texto ("-1,-1,1")
  // porque hay un coeficiente POR COMPONENTE y la lista puede cambiar.
  nu?: string;
  A?: number;
  Ea?: number;
  con_cinetica?: boolean;
  /** solo reactor_cstr: cuantas corrientes de entrada acepta (>= 1) */
  n_entradas?: number;
}

export interface DatosCorriente extends Record<string, unknown> {
  clase: "corriente";
}

export type DatosNodo = DatosOperacion | DatosCorriente;

export interface PuertosOperacion {
  entrada: string[];
  salida: string[];
}

export function puertosDe(datos: DatosOperacion): PuertosOperacion {
  switch (datos.tipo) {
    case "columna":
      return { entrada: ["alimentacion"], salida: ["destilado", "fondos"] };
    case "mezclador":
      return { entrada: ["entrada_1", "entrada_2"], salida: ["salida"] };
    case "divisor":
      return { entrada: ["entrada"], salida: ["salida_1", "salida_2"] };
    case "bomba":
      return { entrada: ["entrada"], salida: ["salida"] };
    case "flash":
      // Dos salidas que NO son intercambiables: el vapor sale por arriba
      // y el liquido por abajo, como en el equipo real.
      return { entrada: ["entrada"], salida: ["vapor", "liquido"] };
    case "intercambiador":
      return { entrada: ["entrada"], salida: ["salida"] };
    case "valvula":
      return { entrada: ["entrada"], salida: ["salida"] };
    case "separador":
      return { entrada: ["entrada"], salida: ["ligeros", "pesados"] };
    case "compresor":
      return { entrada: ["entrada"], salida: ["salida"] };
    case "intercambiador_doble":
      // Cuatro puertos: dos corrientes que se cruzan. Es el unico equipo
      // cuyas dos entradas pueden venir de ramas distintas del diagrama.
      return {
        entrada: ["caliente_entrada", "frio_entrada"],
        salida: ["caliente_salida", "frio_salida"],
      };
    case "absorbedor":
      // El gas sube y el liquido baja: cuatro puertos en contracorriente.
      return {
        entrada: ["gas_entrada", "liquido_entrada"],
        salida: ["gas_salida", "liquido_salida"],
      };
    case "reactor_pfr": {
      const np_ = Math.max(1, datos.n_entradas ?? 1);
      return {
        entrada: Array.from({ length: np_ }, (_, i) => (i === 0 ? "entrada" : `entrada_${i + 1}`)),
        salida: ["salida"],
      };
    }
    case "reactor_equilibrio": {
      const ne = Math.max(1, datos.n_entradas ?? 1);
      return {
        entrada: Array.from({ length: ne }, (_, i) => (i === 0 ? "entrada" : `entrada_${i + 1}`)),
        salida: ["salida"],
      };
    }
    case "reactor_cstr": {
      // Un reactor real recibe varias corrientes (fresca + reciclo +
      // inyeccion). Los puertos se generan segun n_entradas.
      const n = Math.max(1, datos.n_entradas ?? 1);
      return {
        entrada: Array.from({ length: n }, (_, i) => (i === 0 ? "entrada" : `entrada_${i + 1}`)),
        salida: ["salida"],
      };
    }
  }
}

/** Variables propias de la operacion (las de las corrientes viven en las corrientes). */
export function variablesDeOperacion(datos: DatosOperacion): string[] {
  if (datos.tipo === "columna") {
    if (datos.metodo === "fug") {
      // En FUG no se especifican purezas sino RECUPERACIONES de los dos
      // componentes clave: las composiciones de producto son resultado
      // del metodo (el reparto de los no-clave lo decide Fenske).
      const base = ["R", "recuperacion_LK_D", "recuperacion_HK_B", "N", "N_min", "R_min", "theta"];
      return datos.con_balance_energia === false
        ? base
        : [...base, "Q_c", "Q_R", "R_int", "V_barra", "T_reflujo"];
    }
    if (datos.metodo === "ponchon_savarit") {
      // En Ponchon-Savarit la energia NO se agrega aparte: ya esta en la
      // construccion entalpica. Qc_D es el grado de libertad (el analogo
      // de R); QR_B queda atado a el por la colinealidad de los polos, y
      // R se recupera de Qc_D = (R+1)*(H_V-H_L).
      const base = ["Qc_D", "N"];
      return datos.con_balance_energia === false
        ? base
        : [...base, "QR_B", "R", "Q_c", "Q_R"];
    }
    const base = ["q", "R", "N"];
    // Si el balance de energia esta apagado, esas variables no existen
    // en el diagrama: no se muestran ni cuentan para grados de libertad.
    return datos.con_balance_energia === false ? base : [...base, "Q_c", "Q_R", "R_int", "V_barra"];
  }
  if (datos.tipo === "bomba") return ["factor_P"];
  if (datos.tipo === "flash") {
    // T y beta son RESULTADO salvo que se usen como especificacion; el
    // panel decide cual se da. Q sale siempre: es lo que cuesta.
    return ["T", "beta", "Q_por_mol", "Q"];
  }
  if (datos.tipo === "intercambiador") return ["Q_por_mol", "Q", "beta_salida"];
  if (datos.tipo === "valvula") return ["beta_salida", "caida_P"];
  if (datos.tipo === "separador") return [];  // todo queda en las corrientes
  if (datos.tipo === "compresor") return ["W", "T_ideal", "razon_P"];
  if (datos.tipo === "intercambiador_doble") return ["Q", "aproximacion"];
  if (datos.tipo === "reactor_pfr") return ["xi", "X", "V", "T"];
  if (datos.tipo === "absorbedor") return ["N", "T"];
  if (datos.tipo === "reactor_equilibrio") {
    // Sin V: el equilibrio no depende del tamano del tanque.
    return ["xi", "X", "T", "K_eq"];
  }
  if (datos.tipo === "reactor_cstr") {
    // xi (avance) y X (conversion) son dos formas de decir lo mismo y el
    // sistema convierte entre ellas; V y T solo existen si se activa la
    // cinetica, porque sin ella no hay forma de relacionar tamano y avance.
    // T siempre: un tanque tiene temperatura haya o no cinetica, y su
    // salida sale a esa T. V solo existe si hay cinetica (sin ella no hay
    // forma de relacionar tamano y avance).
    const base = ["xi", "X", "T"];
    return datos.con_cinetica === false ? base : [...base, "V"];
  }
  return [];
}

export function variablesDeCorriente(nComponentes: number): string[] {
  // Un solo caudal. Expresarlo en moles o en masa es cuestion de la
  // unidad elegida para ESA corriente, no una variable aparte.
  return ["F", "T", "P", ...Array.from({ length: nComponentes }, (_, i) => `x${i}`)];
}

export const UNIDAD: Record<string, string> = {
  F: "mol/s",
  T: "K",
  P: "Pa",
  Q_c: "W",
  Q_R: "W",
  Qc_D: "J/mol",
  QR_B: "J/mol",
  V_barra: "mol/s",
  xi: "mol/s",
  V: "m³",
  W: "W",
  Q: "W",
  T_ideal: "K",
  aproximacion: "K",
};

/**
 * Una fraccion molar es "x" seguido de DIGITOS (x0, x1, x2...). El
 * chequeo ingenuo (startsWith("x")) rompia con el avance de reaccion del
 * reactor, 'xi', que tambien empieza por x: se mostraba como "x NaN"
 * porque Number("i") no es un numero. Mismo cuidado hace falta al
 * formatear, si no un avance de 20 mol/s saldria con 4 decimales de
 * fraccion molar.
 */
export function esFraccionMolar(variable: string): boolean {
  return /^x\d+$/.test(variable);
}

/** Metodos de columna disponibles segun cuantos componentes tenga la simulacion. */
export function metodosDisponibles(nComponentes: number): {
  valor: MetodoColumna; etiqueta: string; disponible: boolean; motivo?: string;
}[] {
  const binarioOk = nComponentes === 2;
  const motivoBinario = `es un método binario y la simulación tiene ${nComponentes} componentes`;
  return [
    { valor: "mccabe_thiele", etiqueta: "McCabe-Thiele", disponible: binarioOk,
      motivo: binarioOk ? undefined : motivoBinario },
    { valor: "ponchon_savarit", etiqueta: "Ponchon-Savarit", disponible: binarioOk,
      motivo: binarioOk ? undefined : motivoBinario },
    { valor: "fug", etiqueta: "FUG (multicomponente)", disponible: nComponentes >= 2,
      motivo: nComponentes >= 2 ? undefined : "necesita al menos 2 componentes" },
  ];
}

/** El metodo que tiene sentido por defecto para esta cantidad de componentes. */
export function metodoPorDefecto(nComponentes: number): MetodoColumna {
  return nComponentes === 2 ? "mccabe_thiele" : "fug";
}

export function etiquetaVariable(variable: string, componentes: string[]): string {
  if (esFraccionMolar(variable)) {
    const i = Number(variable.slice(1));
    return `x ${componentes[i] ?? i}`;
  }
  if (variable === "xi") return "ξ (avance)";
  if (variable === "X") return "X (conversión)";
  if (variable === "recuperacion_LK_D") return "recup. clave ligero → destilado";
  if (variable === "recuperacion_HK_B") return "recup. clave pesado → fondos";
  return variable;
}

/**
 * Traduce el grafo visual al contrato del backend. Una conexion
 * operacion->corriente significa "esa corriente es la salida de ese
 * puerto"; corriente->operacion, "esa corriente alimenta ese puerto".
 * Conectar dos operaciones es, por tanto, hacerlas compartir la MISMA
 * corriente -- que en el pool son literalmente las mismas variables.
 */
export function corrientesDeOperacion(
  nodo: Node<DatosNodo>,
  edges: Edge[]
): Record<string, string | string[]> | null {
  const datos = nodo.data as DatosOperacion;
  const puertos = puertosDe(datos);

  const entradaDe = (puerto: string) =>
    edges.find((e) => e.target === nodo.id && e.targetHandle === puerto)?.source;
  const salidaDe = (puerto: string) =>
    edges.find((e) => e.source === nodo.id && e.sourceHandle === puerto)?.target;

  if (datos.tipo === "columna") {
    const alimentacion = entradaDe("alimentacion");
    const destilado = salidaDe("destilado");
    const fondos = salidaDe("fondos");
    if (!alimentacion || !destilado || !fondos) return null;
    return { alimentacion, destilado, fondos };
  }
  if (datos.tipo === "mezclador") {
    const entradas = puertos.entrada.map(entradaDe).filter(Boolean) as string[];
    const salida = salidaDe("salida");
    if (entradas.length < 2 || !salida) return null;
    return { entradas, salida };
  }
  if (datos.tipo === "divisor") {
    const entrada = entradaDe("entrada");
    const salidas = puertos.salida.map(salidaDe).filter(Boolean) as string[];
    if (!entrada || salidas.length < 2) return null;
    return { entrada, salidas };
  }
  if (datos.tipo === "reactor_cstr") {
    const entradas = puertos.entrada.map(entradaDe).filter(Boolean) as string[];
    const salida = salidaDe("salida");
    if (entradas.length === 0 || !salida) return null;
    return { entradas, salida };
  }
  if (datos.tipo === "flash") {
    const entrada = entradaDe("entrada");
    const vapor = salidaDe("vapor");
    const liquido = salidaDe("liquido");
    if (!entrada || !vapor || !liquido) return null;
    return { entrada, vapor, liquido };
  }
  if (datos.tipo === "separador") {
    const entrada = entradaDe("entrada");
    const ligeros = salidaDe("ligeros");
    const pesados = salidaDe("pesados");
    if (!entrada || !ligeros || !pesados) return null;
    return { entrada, ligeros, pesados };
  }
  if (datos.tipo === "intercambiador_doble") {
    const ce = entradaDe("caliente_entrada");
    const cs = salidaDe("caliente_salida");
    const fe = entradaDe("frio_entrada");
    const fs = salidaDe("frio_salida");
    if (!ce || !cs || !fe || !fs) return null;
    return { caliente_entrada: ce, caliente_salida: cs, frio_entrada: fe, frio_salida: fs };
  }
  if (datos.tipo === "reactor_equilibrio" || datos.tipo === "reactor_pfr") {
    const entradas = puertos.entrada.map(entradaDe).filter(Boolean) as string[];
    const salida = salidaDe("salida");
    if (entradas.length === 0 || !salida) return null;
    return { entradas, salida };
  }
  if (datos.tipo === "absorbedor") {
    const ge = entradaDe("gas_entrada");
    const gs = salidaDe("gas_salida");
    const le = entradaDe("liquido_entrada");
    const ls = salidaDe("liquido_salida");
    if (!ge || !gs || !le || !ls) return null;
    return { gas_entrada: ge, gas_salida: gs, liquido_entrada: le, liquido_salida: ls };
  }
  const entrada = entradaDe("entrada");
  const salida = salidaDe("salida");
  if (!entrada || !salida) return null;
  return { entrada, salida };
}

/** Descripcion legible de la reaccion a partir del vector nu. */
export function ecuacionReaccion(nu: string | undefined, componentes: string[]): string | null {
  const coefs = (nu ?? "").split(",").map((v) => Number(v.trim()));
  if (coefs.length === 0 || coefs.some((v) => !Number.isFinite(v))) return null;
  const izq: string[] = [];
  const der: string[] = [];
  coefs.forEach((v, i) => {
    if (v === 0) return;
    const nombre = componentes[i] ?? `C${i}`;
    const coef = Math.abs(v) === 1 ? "" : `${Math.abs(v)} `;
    (v < 0 ? izq : der).push(`${coef}${nombre}`);
  });
  if (!izq.length || !der.length) return null;
  return `${izq.join(" + ")} → ${der.join(" + ")}`;
}

export type EstadoValor = "dado" | "calculado" | "desconocido";

export function estadoDe(clave: string, dados: Record<string, string>, pool: Record<string, number>): EstadoValor {
  if (dados[clave] !== undefined && dados[clave] !== "") return "dado";
  if (pool[clave] !== undefined) return "calculado";
  return "desconocido";
}

export function valorDe(clave: string, dados: Record<string, string>, pool: Record<string, number>): number | null {
  if (dados[clave] !== undefined && dados[clave] !== "") return Number(dados[clave]);
  if (pool[clave] !== undefined) return pool[clave];
  return null;
}

export function formatear(valor: number, variable: string): string {
  if (esFraccionMolar(variable) || variable === "X") return valor.toFixed(4);
  const magnitud = Math.abs(valor);
  // Los numeros pequenos tambien necesitan cifras significativas, no
  // decimales fijos: un caudal masico de 0.0085125 kg/s se mostraba como
  // "0.009" y perdia toda la precision.
  if (magnitud !== 0 && (magnitud >= 10000 || magnitud < 0.01)) return valor.toPrecision(5);
  return valor.toFixed(3);
}

/**
 * La parte de /diagrama/resolver que la pantalla del flowsheet consume.
 *
 * No es el esquema completo a proposito: lo que no se usa aqui no deberia
 * obligar a tocar este tipo cuando el backend anada un campo. Vive en
 * modelo.ts y no en page.tsx porque lo comparten la pagina y el panel de
 * diseno, y tenerlo en la pagina obligaria a un import circular.
 */
export interface RespuestaResolver {
  pool: Record<string, number>;
  diagnostico: InformeBloque[];
  incognitas_restantes: string[];
  completo: boolean;
  inconsistencias?: Inconsistencia[];
  diagramas?: Record<string, DatosDiagramaColumna>;
  masas_molares_mezcla?: Record<string, number>;
}
