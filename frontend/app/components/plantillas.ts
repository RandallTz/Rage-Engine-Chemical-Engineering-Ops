import type { Componente, EstadoFlowsheet } from "./SimulacionProvider";

/**
 * Procesos de arranque. Los marcados como "listos" traen TODOS los datos
 * puestos: se abren y se pulsa Resolver, sin escribir nada. Son la forma
 * mas rapida de ver que hace el simulador y de tener un punto de partida
 * que ya funciona para modificarlo.
 *
 * Los valores de cada uno estan verificados contra el backend (ver
 * verificar_plantillas.mjs): cada plantilla "lista" resuelve por completo
 * y sin datos sobrantes.
 */

export interface Plantilla {
  id: string;
  nombre: string;
  descripcion: string;
  categoria: "vacia" | "separacion" | "reaccion" | "combinado";
  /** true si trae todos los datos y resuelve de una. */
  lista: boolean;
  componentes: Componente[];
  modelo: string;
  flowsheet: EstadoFlowsheet;
}

const C = {
  benceno: { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
  tolueno: { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
  pentano: { nombre: "n-pentane", formula: "C5H12", MW: 72.15, Tb: 309.22 },
  hexano: { nombre: "n-hexane", formula: "C6H14", MW: 86.18, Tb: 341.88 },
  heptano: { nombre: "n-heptane", formula: "C7H16", MW: 100.2, Tb: 371.53 },
  octano: { nombre: "n-octane", formula: "C8H18", MW: 114.23, Tb: 398.77 },
  isobuteno: { nombre: "isobutene", formula: "C4H8", MW: 56.11, Tb: 266.25 },
  metanol: { nombre: "methanol", formula: "CH4O", MW: 32.04, Tb: 337.63 },
  mtbe: { nombre: "mtbe", formula: "C5H12O", MW: 88.15, Tb: 328.35 },
};

const corriente = (id: string, x: number, y: number) => ({
  id, type: "corriente", position: { x, y }, data: { clase: "corriente" },
});

const arista = (id: string, source: string, target: string,
                sourceHandle?: string, targetHandle?: string) => ({
  id, source, target,
  ...(sourceHandle ? { sourceHandle } : {}),
  ...(targetHandle ? { targetHandle } : {}),
});

export const PLANTILLAS: Plantilla[] = [
  // ------------------------------------------------------------ vacías
  {
    id: "vacia",
    nombre: "En blanco",
    descripcion: "Sin componentes ni equipos. Empiezas eligiendo la mezcla.",
    categoria: "vacia",
    lista: false,
    componentes: [],
    modelo: "unifac_raoult",
    flowsheet: { nodes: [], edges: [], dados: {} },
  },
  {
    id: "binaria_vacia",
    nombre: "Benceno–tolueno, lienzo vacío",
    descripcion: "Los dos componentes cargados y el diagrama en blanco, para montarlo tú.",
    categoria: "vacia",
    lista: false,
    componentes: [C.benceno, C.tolueno],
    modelo: "unifac_raoult",
    flowsheet: { nodes: [], edges: [], dados: {} },
  },

  // -------------------------------------------------------- separación
  {
    id: "mccabe_listo",
    nombre: "Columna McCabe-Thiele (lista)",
    descripcion:
      "Benceno–tolueno, 100 mol/s al 50 %, destilado 95 % y fondos 5 %, R = 3 y alimentación líquida saturada. Resuelve de una.",
    categoria: "separacion",
    lista: true,
    componentes: [C.benceno, C.tolueno],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 60, 200),
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "mccabe_thiele",
            P_sistema: 101325, con_balance_energia: true,
          },
        },
        corriente("s2", 680, 80),
        corriente("s3", 680, 330),
      ],
      edges: [
        arista("e1", "s1", "col1", undefined, "alimentacion"),
        arista("e2", "col1", "s2", "destilado"),
        arista("e3", "col1", "s3", "fondos"),
      ],
      dados: {
        "s1.F": "100", "s1.x0": "0.5",
        "s2.x0": "0.95", "s3.x0": "0.05",
        "col1.q": "1", "col1.R": "3",
      },
    },
  },
  {
    id: "valvula_flash_listo",
    nombre: "Válvula + flash (listo)",
    descripcion:
      "Un líquido a presión se calienta, se expande por una válvula y se separa en un flash adiabático. La válvula no le quita calor a nadie: la expansión vaporiza parte de la corriente y el calor latente sale de ella misma, así que SE ENFRÍA de 434.6 K a 369.6 K.",
    categoria: "separacion",
    lista: true,
    componentes: [C.benceno, C.tolueno],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 40, 200),
        {
          id: "e1", type: "operacion", position: { x: 230, y: 180 },
          data: {
            clase: "operacion", tipo: "intercambiador", P_sistema: 101325,
            spec_intercambiador: "Q_por_mol", Q_por_mol: 18000,
          },
        },
        corriente("s2", 430, 200),
        {
          id: "v1", type: "operacion", position: { x: 600, y: 180 },
          data: {
            clase: "operacion", tipo: "valvula", P_sistema: 101325,
            P_salida: 101325,
          },
        },
        corriente("s3", 790, 200),
        {
          id: "fl1", type: "operacion", position: { x: 960, y: 170 },
          data: {
            clase: "operacion", tipo: "flash", P_sistema: 101325,
            spec_flash: "adiabatico", Q_por_mol: 0,
          },
        },
        corriente("s4", 1180, 80),
        corriente("s5", 1180, 320),
      ],
      edges: [
        arista("a1", "s1", "e1", undefined, "entrada"),
        arista("a2", "e1", "s2", "salida", undefined),
        arista("a3", "s2", "v1", undefined, "entrada"),
        arista("a4", "v1", "s3", "salida", undefined),
        arista("a5", "s3", "fl1", undefined, "entrada"),
        arista("a6", "fl1", "s4", "vapor", undefined),
        arista("a7", "fl1", "s5", "liquido", undefined),
      ],
      dados: {
        "s1.F": "100", "s1.T": "330", "s1.P": "607950", "s1.x0": "0.45",
      },
    },
  },
  {
    id: "ponchon_listo",
    nombre: "Columna Ponchon-Savarit (lista)",
    descripcion:
      "La misma mezcla resuelta por el método entálpico: en vez de R se da Qc/D = 70 kJ/mol. Dibuja el diagrama H–x con sus polos.",
    categoria: "separacion",
    lista: true,
    componentes: [C.benceno, C.tolueno],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 60, 200),
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "ponchon_savarit",
            P_sistema: 101325, q_fijo: 1, con_balance_energia: true,
          },
        },
        corriente("s2", 680, 80),
        corriente("s3", 680, 330),
      ],
      edges: [
        arista("e1", "s1", "col1", undefined, "alimentacion"),
        arista("e2", "col1", "s2", "destilado"),
        arista("e3", "col1", "s3", "fondos"),
      ],
      dados: {
        "s1.F": "100", "s1.x0": "0.5",
        "s2.x0": "0.9", "s3.x0": "0.1",
        "col1.Qc_D": "70000",
      },
    },
  },
  {
    id: "fug_listo",
    nombre: "Columna multicomponente FUG (lista)",
    descripcion:
      "Cuatro alcanos (C5–C8). Claves: hexano/heptano con 98 % de recuperación cada uno, R = 2. Es el caso que los métodos binarios no pueden tocar.",
    categoria: "separacion",
    lista: true,
    componentes: [C.pentano, C.hexano, C.heptano, C.octano],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 60, 200),
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "fug",
            P_sistema: 101325, q_fijo: 1, con_balance_energia: true,
            indice_LK: 1, indice_HK: 2,
          },
        },
        corriente("s2", 680, 80),
        corriente("s3", 680, 330),
      ],
      edges: [
        arista("e1", "s1", "col1", undefined, "alimentacion"),
        arista("e2", "col1", "s2", "destilado"),
        arista("e3", "col1", "s3", "fondos"),
      ],
      dados: {
        "s1.F": "100",
        "s1.x0": "0.25", "s1.x1": "0.25", "s1.x2": "0.25",
        "col1.R": "2",
        "col1.recuperacion_LK_D": "0.98",
        "col1.recuperacion_HK_B": "0.98",
      },
    },
  },

  // ---------------------------------------------------------- reacción
  {
    id: "cstr_listo",
    nombre: "Reactor CSTR (listo)",
    descripcion:
      "Síntesis de MTBE: isobuteno + metanol → MTBE, 100 mol/s equimolar, 40 % de conversión a 340 K. Calcula el volumen de tanque necesario.",
    categoria: "reaccion",
    lista: true,
    componentes: [C.isobuteno, C.metanol, C.mtbe],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 60, 200),
        {
          id: "r1", type: "operacion", position: { x: 380, y: 180 },
          data: {
            clase: "operacion", tipo: "reactor_cstr", P_sistema: 101325,
            // Solo balance de MATERIA. Encender la energía aquí exigiría
            // la T y P de entrada, y además a 1 atm este reactor de MTBE
            // estaría hirviendo (el núcleo lo rechaza, con razón).
            con_balance_energia: false,
            nu: "-1,-1,1", A: 1e4, Ea: 45000, con_cinetica: true,
          },
        },
        corriente("s2", 700, 200),
      ],
      edges: [
        arista("e1", "s1", "r1", undefined, "entrada"),
        arista("e2", "r1", "s2", "salida"),
      ],
      dados: {
        "s1.F": "100", "s1.x0": "0.5", "s1.x1": "0.5",
        "s1.T": "330", "s1.P": "101325",
        "r1.X": "0.4", "r1.T": "340",
      },
    },
  },

  // --------------------------------------------------------- combinado
  {
    id: "reactor_columna",
    nombre: "Reactor + columna en serie (listo)",
    descripcion:
      "El CSTR de MTBE alimentando una columna FUG que separa el producto. Dos equipos encadenados por una corriente compartida.",
    categoria: "combinado",
    lista: true,
    componentes: [C.isobuteno, C.metanol, C.mtbe],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 40, 220),
        {
          id: "r1", type: "operacion", position: { x: 300, y: 200 },
          data: {
            clase: "operacion", tipo: "reactor_cstr", P_sistema: 101325,
            // Solo balance de MATERIA. Encender la energía aquí exigiría
            // la T y P de entrada, y además a 1 atm este reactor de MTBE
            // estaría hirviendo (el núcleo lo rechaza, con razón).
            con_balance_energia: false,
            nu: "-1,-1,1", A: 1e4, Ea: 45000, con_cinetica: true,
          },
        },
        corriente("s2", 580, 220),
        {
          id: "col1", type: "operacion", position: { x: 830, y: 180 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "fug",
            P_sistema: 101325, q_fijo: 1, con_balance_energia: true,
            // MTBE (Tb 328 K) es MAS volátil que el metanol (338 K), así
            // que el clave ligero es el MTBE. Al revés, Fenske da un
            // número de etapas negativo.
            indice_LK: 2, indice_HK: 1,
          },
        },
        corriente("s3", 1130, 90),
        corriente("s4", 1130, 350),
      ],
      edges: [
        arista("e1", "s1", "r1", undefined, "entrada"),
        arista("e2", "r1", "s2", "salida"),
        arista("e3", "s2", "col1", undefined, "alimentacion"),
        arista("e4", "col1", "s3", "destilado"),
        arista("e5", "col1", "s4", "fondos"),
      ],
      dados: {
        "s1.F": "100", "s1.x0": "0.5", "s1.x1": "0.5",
        "s1.T": "330", "s1.P": "101325",
        "r1.X": "0.4", "r1.T": "340",
        // MTBE y metanol hierven muy cerca (328 vs 338 K), así que el
        // reflujo mínimo de esta separación es alto: R_min ≈ 3.35.
        "col1.R": "5",
        "col1.recuperacion_LK_D": "0.95",
        "col1.recuperacion_HK_B": "0.95",
      },
    },
  },
  {
    id: "columna_reactor",
    nombre: "Columna + reactor de acabado (listo)",
    descripcion:
      "La topología inversa: primero se separa y después se reacciona. La columna hace un corte suave (80 % de recuperación), así que el destilado se lleva los DOS reactivos todavía juntos, y un reactor de acabado convierte lo que queda.",
    categoria: "combinado",
    lista: true,
    componentes: [C.isobuteno, C.metanol, C.mtbe],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("s1", 40, 220),
        {
          id: "col1", type: "operacion", position: { x: 300, y: 180 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "fug",
            P_sistema: 101325, q_fijo: 1, con_balance_energia: true,
            // MTBE (328 K) como clave ligero frente al metanol (338 K).
            // El isobuteno, mucho más volátil, se va entero por el domo.
            indice_LK: 2, indice_HK: 1,
          },
        },
        corriente("s2", 600, 100),
        corriente("s3", 600, 360),
        {
          id: "r1", type: "operacion", position: { x: 860, y: 90 },
          data: {
            clase: "operacion", tipo: "reactor_cstr", P_sistema: 101325,
            // Solo balance de MATERIA. Encender la energía aquí exigiría
            // la T y P de entrada, y además a 1 atm este reactor de MTBE
            // estaría hirviendo (el núcleo lo rechaza, con razón).
            con_balance_energia: false,
            nu: "-1,-1,1", A: 1e4, Ea: 45000, con_cinetica: true,
          },
        },
        corriente("s4", 1150, 110),
      ],
      edges: [
        arista("e1", "s1", "col1", undefined, "alimentacion"),
        arista("e2", "col1", "s2", "destilado"),
        arista("e3", "col1", "s3", "fondos"),
        arista("e4", "s2", "r1", undefined, "entrada"),
        arista("e5", "r1", "s4", "salida"),
      ],
      dados: {
        "s1.F": "100", "s1.x0": "0.45", "s1.x1": "0.45",
        // NO se dan T ni P de la alimentación: con q = 1 la columna ya
        // las determina (su punto de burbuja). Darlas sobraría.
        "col1.R": "1.5",
        "col1.recuperacion_LK_D": "0.8",
        "col1.recuperacion_HK_B": "0.8",
        "r1.X": "0.3", "r1.T": "340",
      },
    },
  },
  {
    id: "reciclo",
    nombre: "Reactor con recirculación (listo)",
    descripcion:
      "La configuración clásica: lo que no reaccionó vuelve al reactor. El 80 % de la salida se recircula y el 20 % sale como producto. El lazo se resuelve cortando la corriente de reciclo e iterando hasta cerrarlo.",
    categoria: "combinado",
    lista: true,
    componentes: [C.isobuteno, C.metanol, C.mtbe],
    modelo: "unifac_raoult",
    flowsheet: {
      nodes: [
        corriente("fresco", 40, 200),
        {
          id: "mez1", type: "operacion", position: { x: 280, y: 180 },
          data: { clase: "operacion", tipo: "mezclador", P_sistema: 101325 },
        },
        corriente("mezcla", 540, 200),
        {
          id: "r1", type: "operacion", position: { x: 780, y: 180 },
          data: {
            clase: "operacion", tipo: "reactor_cstr", P_sistema: 101325,
            // Solo balance de MATERIA. Encender la energía aquí exigiría
            // la T y P de entrada, y además a 1 atm este reactor de MTBE
            // estaría hirviendo (el núcleo lo rechaza, con razón).
            con_balance_energia: false,
            nu: "-1,-1,1", A: 1e4, Ea: 45000, con_cinetica: false, n_entradas: 1,
          },
        },
        corriente("salida_r", 1040, 200),
        {
          id: "div1", type: "operacion", position: { x: 1280, y: 180 },
          data: { clase: "operacion", tipo: "divisor", P_sistema: 101325, fracciones: "0.2,0.8" },
        },
        corriente("producto", 1540, 90),
        corriente("reciclo", 1540, 340),
      ],
      edges: [
        arista("e1", "fresco", "mez1", undefined, "entrada_1"),
        arista("e2", "reciclo", "mez1", undefined, "entrada_2"),
        arista("e3", "mez1", "mezcla", "salida"),
        arista("e4", "mezcla", "r1", undefined, "entrada"),
        arista("e5", "r1", "salida_r", "salida"),
        arista("e6", "salida_r", "div1", undefined, "entrada"),
        arista("e7", "div1", "producto", "salida_1"),
        arista("e8", "div1", "reciclo", "salida_2"),
      ],
      dados: {
        "fresco.F": "100", "fresco.x0": "0.5", "fresco.x1": "0.5",
        "fresco.T": "330", "fresco.P": "101325",
        "r1.xi": "5", "r1.T": "340",
      },
    },
  },
];

export const PLANTILLAS_POR_ID = Object.fromEntries(PLANTILLAS.map((p) => [p.id, p]));

export const CATEGORIAS: { id: Plantilla["categoria"]; etiqueta: string }[] = [
  { id: "vacia", etiqueta: "Empezar de cero" },
  { id: "separacion", etiqueta: "Separación" },
  { id: "reaccion", etiqueta: "Reacción" },
  { id: "combinado", etiqueta: "Procesos combinados" },
];
