/**
 * Catálogo de métodos: qué supone cada uno y cuándo NO hay que fiarse.
 *
 * Por qué existe este archivo. La parte más valiosa de este proyecto son
 * los documentos de `docs/`: la matemática de cada método con sus
 * suposiciones y sus límites explícitos. Hasta ahora eran invisibles
 * desde la aplicación -- ni un solo enlace. El usuario veía un número y
 * no tenía forma de saber de dónde salía ni cuándo deja de valer.
 *
 * Eso es exactamente lo contrario de lo que diferencia a este simulador:
 * los comerciales son cajas negras que dan una cifra y punto.
 *
 * Lo que va AQUÍ es el resumen operativo -- lo que hay que saber antes
 * de usar el número. La deducción completa sigue en `docs/`, enlazada.
 * Este archivo es DATOS, no lógica: no calcula nada.
 *
 * Regla al mantenerlo: si cambia una suposición en el código, cambia
 * aquí y en `docs/`. Un límite desactualizado es peor que ninguno,
 * porque da una confianza que no corresponde.
 */

/** Dónde vive la matemática completa. */
const REPO = "https://github.com/RandallTz/Rage-Engine-Chemical-Engineering-Ops/blob/main/docs";

export interface Metodo {
  nombre: string;
  /** Una línea: qué resuelve y con qué idea. */
  resumen: string;
  /** Lo que da por cierto. Si alguna no se cumple, el número no vale. */
  suposiciones: string[];
  /** Cuándo NO fiarse. Tan importante como lo anterior. */
  limites: string[];
  /** Documento de docs/ con la deducción. */
  documento: string;
}

export const METODOS: Record<string, Metodo> = {
  mccabe_thiele: {
    nombre: "McCabe-Thiele",
    resumen:
      "Escalonamiento gráfico-numérico entre la curva de equilibrio y las rectas de operación. Trata el problema como UNA ecuación sobre seis variables, así que resuelve en cualquier dirección: dado R calcula N, o dado N calcula R.",
    suposiciones: [
      "Mezcla BINARIA: se construye sobre un solo par x–y.",
      "Flujo molar constante (CMO): los caudales de líquido y vapor no cambian de etapa a etapa.",
      "Equilibrio en cada etapa, salvo que se dé una eficiencia de Murphree.",
      "Las cargas térmicas se calculan bajo CMO; el tratamiento riguroso de entalpía es Ponchon-Savarit.",
    ],
    limites: [
      "No cruza azeótropos: ninguna cantidad de etapas ni de reflujo lo hace. El simulador lo detecta y lo dice.",
      "CMO se cae cuando los calores latentes de los dos componentes difieren apreciablemente.",
      "Con R ≤ R_min hacen falta infinitas etapas; se rechaza antes de escalonar.",
      "Son etapas TEÓRICAS, no platos reales ni una columna comprable.",
    ],
    documento: "06-mccabe-thiele.md",
  },

  ponchon_savarit: {
    nombre: "Ponchon-Savarit",
    resumen:
      "El mismo problema binario pero en el plano entalpía-composición, sin suponer flujo molar constante. La energía entra en la construcción geométrica (los polos Δ), no como un cálculo aparte.",
    suposiciones: [
      "Mezcla BINARIA.",
      "Mezcla ideal en la entalpía: no hay calor de mezcla (sin entalpía de exceso).",
      "Δ_D, la alimentación y Δ_B son colineales — es el balance de energía global escrito como geometría.",
    ],
    limites: [
      "Q_R/B no es libre: dado Q_c/D, la colinealidad lo determina. El método tiene UN grado de libertad.",
      "H_F derivado de q es aproximado: usa H_V en z_F en vez del punto de rocío real.",
      "Q_c/D mínimo no tiene fórmula cerrada; se localiza por bisección.",
    ],
    documento: "07-ponchon-savarit.md",
  },

  fug: {
    nombre: "FUG (Fenske-Underwood-Gilliland)",
    resumen:
      "Método de atajo para mezclas multicomponente: Fenske da las etapas mínimas, Underwood el reflujo mínimo y Gilliland correlaciona el caso real entre ambos.",
    suposiciones: [
      "Volatilidad relativa promediada entre cima, alimentación y fondo.",
      "Dos componentes CLAVE, que deberían ser adyacentes en volatilidad.",
      "Distribución de los no-clave estimada y luego refinada con la razón de Fenske.",
    ],
    limites: [
      "Gilliland es una correlación EMPÍRICA: ±10–20 % en el número de etapas.",
      "No detecta azeótropos.",
      "Con claves NO adyacentes puede dar R_min negativo — implementado, pero sin la misma confianza. Usar caso por caso.",
      "Es un método de estimación inicial, no de diseño final.",
    ],
    documento: "08-fug.md",
  },

  flash: {
    nombre: "Flash líquido-vapor",
    resumen:
      "Separador en equilibrio de una etapa. Es, literalmente, el sistema MESH completo con N=1: las cuatro ecuaciones se reducen a una incógnita escalar con Rachford-Rice.",
    suposiciones: [
      "Equilibrio de fases alcanzado: vapor y líquido salen a la misma T y P.",
      "K_i = γ_i(T,x)·Psat_i(T)/P — Raoult modificada, con UNIFAC para γ.",
      "La fase se deduce de (T, P, z) comparando con los puntos de burbuja y rocío; no es un dato.",
    ],
    limites: [
      "Una sola fase líquida: sin equilibrio líquido-líquido. Un sistema que se separe en dos (agua/hidrocarburo) está fuera de alcance.",
      "Sustituciones sucesivas sobre γ: se atasca en mezclas muy no ideales, y en ese caso lo dice en vez de devolver un número malo.",
    ],
    documento: "05-flash.md",
  },

  reactor_cstr: {
    nombre: "Reactor CSTR",
    resumen:
      "Tanque agitado en estado estacionario. Balance por componente con el avance de reacción, cinética evaluada en la composición de SALIDA (que es la del tanque), y balance de energía con el calor de reacción.",
    suposiciones: [
      "Mezclado perfecto: la composición del tanque es la de salida.",
      "Estado estacionario.",
      "Tanque LÍQUIDO monofásico: la cinética usa actividades de fase líquida.",
      "Una sola reacción.",
    ],
    limites: [
      "Si el balance da una T por encima del punto de burbuja, el tanque estaría hirviendo y el modelo deja de valer: se rechaza en vez de devolver el número.",
      "Un CSTR exotérmico puede tener varios estados estacionarios. Se detectan y se reportan, pero saber cuál es ESTABLE necesita el modelo dinámico, que no está implementado.",
      "Sin reacciones en paralelo ni en serie.",
    ],
    documento: "09-reactor-cstr.md",
  },

  curvas_residuales: {
    nombre: "Mapas de curvas residuales",
    resumen:
      "Trayectorias de la composición del líquido en una destilación simple, integradas con el equilibrio real en cada paso. Con reacción, se integran en el espacio transformado de Barbosa-Doherty o con control cinético vía el número de Damköhler.",
    suposiciones: [
      "Destilación diferencial: el vapor se retira en equilibrio instantáneo con el líquido.",
      "Mapeo isotermo en el salto discreto reactivo.",
      "Una sola reacción.",
    ],
    limites: [
      "El mapa inerte no marca los puntos singulares (nodos y sillas) automáticamente.",
      "Las trayectorias que tocan la frontera del simplex se detienen y se informan: no se extrapola fuera del dominio físico.",
      "Es análisis de FACTIBILIDAD, no dimensionado: dice si una separación es posible, no cuántas etapas cuesta.",
    ],
    documento: "10-destilacion-reactiva.md",
  },

  elv: {
    nombre: "Equilibrio líquido-vapor (UNIFAC)",
    resumen:
      "Ley de Raoult modificada: fase líquida no ideal con coeficientes de actividad de UNIFAC predictivo, fase vapor ideal.",
    suposiciones: [
      "y_i·P = x_i·γ_i(T,x)·Psat_i(T).",
      "γ de UNIFAC predictivo puro, a partir de los grupos funcionales: sin parámetros binarios ajustados.",
      "Fase vapor ideal.",
    ],
    limites: [
      "Fase vapor ideal: malo a presiones altas (más de ~10 bar) o cerca del punto crítico.",
      "UNIFAC predictivo es menos exacto que un modelo ajustado para ese par concreto.",
      "Sin equilibrio líquido-líquido.",
    ],
    documento: "03-termodinamica.md",
  },
};

export function enlaceDoc(metodo: Metodo): string {
  return `${REPO}/${metodo.documento}`;
}
