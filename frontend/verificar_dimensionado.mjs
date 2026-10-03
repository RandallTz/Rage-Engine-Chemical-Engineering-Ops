/**
 * Verificacion en navegador del DIMENSIONADO.
 *
 * Lo que solo se ve aqui: que el diametro y el area lleguen a la pantalla
 * con sus unidades, y que la casilla que los activa no exista cuando no
 * tiene sentido.
 *
 * Y una cosa que ninguna suite de Python puede comprobar: que la LMTD se
 * muestre como una DIFERENCIA de temperatura y no como una temperatura.
 * Son magnitudes distintas -- una diferencia no lleva desplazamiento -- y
 * confundirlas convertiria 28.74 K en -244.4 C, un numero absurdo
 * presentado con toda naturalidad.
 *
 * Uso:  node verificar_dimensionado.mjs [url]
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();
const ATM = 101325;

const fallos = [];
const comprobar = (c, m, detalle = "") => {
  console.log(`  ${c ? "OK  " : "FALLA"} ${m}${detalle ? " -- " + detalle : ""}`);
  if (!c) fallos.push(m);
};
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const COMPONENTES = [
  { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
  { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
];

/** Columna binaria, con o sin dimensionado. */
function simColumna(datosExtra = {}) {
  return {
    id: "sim_dim", nombre: "Dimensionado",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: COMPONENTES, modelo: "unifac_raoult", unidades: {},
    flowsheet: {
      nodes: [
        { id: "alim", type: "corriente", position: { x: 60, y: 200 }, data: { clase: "corriente" } },
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "mccabe_thiele",
            P_sistema: ATM, con_balance_energia: true, ...datosExtra,
          },
        },
        { id: "dest", type: "corriente", position: { x: 680, y: 80 }, data: { clase: "corriente" } },
        { id: "fondo", type: "corriente", position: { x: 680, y: 330 }, data: { clase: "corriente" } },
      ],
      edges: [
        { id: "e1", source: "alim", target: "col1", sourceHandle: null, targetHandle: "alimentacion" },
        { id: "e2", source: "col1", target: "dest", sourceHandle: "destilado", targetHandle: null },
        { id: "e3", source: "col1", target: "fondo", sourceHandle: "fondos", targetHandle: null },
      ],
      dados: {
        "alim.F": "100", "alim.P": String(ATM), "alim.x0": "0.5",
        "dest.x0": "0.95", "fondo.x0": "0.05", "col1.q": "1", "col1.R": "3",
      },
    },
  };
}

/** Intercambiador de dos corrientes, con o sin U. */
function simDoble(U) {
  const datos = {
    clase: "operacion", tipo: "intercambiador_doble", P_sistema: ATM,
    spec_ic: "T_salida_caliente", T_salida_caliente: 360,
  };
  if (U !== undefined) datos.coeficiente_global_U = U;
  return {
    id: "sim_ic", nombre: "Área",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: COMPONENTES, modelo: "unifac_raoult", unidades: {},
    flowsheet: {
      nodes: [
        { id: "ce", type: "corriente", position: { x: 60, y: 120 }, data: { clase: "corriente" } },
        { id: "fe", type: "corriente", position: { x: 60, y: 320 }, data: { clase: "corriente" } },
        { id: "ic", type: "operacion", position: { x: 380, y: 200 }, data: datos },
        { id: "cs", type: "corriente", position: { x: 700, y: 120 }, data: { clase: "corriente" } },
        { id: "fs", type: "corriente", position: { x: 700, y: 320 }, data: { clase: "corriente" } },
      ],
      edges: [
        { id: "e1", source: "ce", target: "ic", sourceHandle: null, targetHandle: "caliente_entrada" },
        { id: "e2", source: "fe", target: "ic", sourceHandle: null, targetHandle: "frio_entrada" },
        { id: "e3", source: "ic", target: "cs", sourceHandle: "caliente_salida", targetHandle: null },
        { id: "e4", source: "ic", target: "fs", sourceHandle: "frio_salida", targetHandle: null },
      ],
      dados: {
        "ce.F": "100", "ce.T": "390", "ce.P": String(ATM), "ce.x0": "0.5", "ce.x1": "0.5",
        "fe.F": "120", "fe.T": "320", "fe.P": String(ATM), "fe.x0": "0.5", "fe.x1": "0.5",
      },
    },
  };
}

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1050 } });

try {
  const pagina = await navegador.newPage();
  let respuesta = null;
  pagina.on("response", async (r) => {
    if (!r.url().includes("/diagrama/resolver")) return;
    try { respuesta = await r.json(); } catch { /* ignorar */ }
  });

  const texto = () => pagina.evaluate(() => document.body.innerText);
  const clicNodo = async (id) => {
    await pagina.evaluate((x) => {
      [...document.querySelectorAll(".react-flow__node")]
        .find((n) => n.innerText.startsWith(x))
        ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }, id);
    await esperar(420);
  };
  const abrir = async (sim) => {
    respuesta = null;
    await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "domcontentloaded" });
    await pagina.evaluate((s) => {
      localStorage.setItem("simulador.simulaciones", JSON.stringify({ activa: s.id, lista: [s] }));
    }, sim);
    await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
    await esperar(900);
    await pagina.evaluate(() => {
      [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Resolver")?.click();
    });
    await pagina.waitForFunction(
      () => /Resuelto por completo|Quedan \d+ variables|Error|no es f/i.test(document.body.innerText),
      { timeout: 150000 },
    );
    await esperar(500);
  };

  // ================================================================
  console.log("\n=== 1. La casilla existe, y apagada no publica geometría ===");
  // ================================================================
  await abrir(simColumna());
  await clicNodo("col1");
  let t = await texto();
  comprobar(/calcular el di[áa]metro/i.test(t), "La casilla «calcular el diámetro» está");
  comprobar(!/espaciado de platos/i.test(t),
    "Y apagada no muestra sus parámetros: no estorban a quien no los quiere");
  comprobar(respuesta?.pool?.["col1.diametro"] === undefined,
    "Ni publica diámetro en el pool",
    `diametro = ${respuesta?.pool?.["col1.diametro"]}`);

  // ================================================================
  console.log("\n=== 2. Encendida, el diámetro llega a la pantalla ===");
  // ================================================================
  await abrir(simColumna({ con_dimensionado: true }));
  const pool = respuesta?.pool ?? {};
  comprobar(pool["col1.diametro"] !== undefined,
    "El pool trae el diámetro", `${pool["col1.diametro"]?.toFixed(4)} m`);
  comprobar(pool["col1.diametro_cabeza"] !== undefined && pool["col1.diametro_cola"] !== undefined,
    "Y los dos extremos por separado",
    `cabeza ${pool["col1.diametro_cabeza"]?.toFixed(4)} m, cola ${pool["col1.diametro_cola"]?.toFixed(4)} m`);
  // Con q = 1 manda la cola: mismo caudal de vapor, pero el fondo está
  // más caliente y sus propiedades son menos favorables.
  comprobar(
    Math.abs(pool["col1.diametro"] - pool["col1.diametro_cola"]) < 1e-9,
    "Con q = 1 manda la COLA, y el diámetro publicado es el mayor de los dos",
    `${pool["col1.diametro"]?.toFixed(4)} m = cola`);

  await clicNodo("col1");
  t = await texto();
  comprobar(/espaciado de platos/i.test(t) && /fracci[óo]n de inundaci[óo]n/i.test(t),
    "Los parámetros aparecen al encenderla");
  comprobar(/dos extremos/i.test(t) && /mil[íi]metros/i.test(t),
    "Y el panel explica lo que no se ve: los dos extremos y las unidades del espaciado");
  comprobar(/di[áa]metro/i.test(t) && /\d+\.\d+/.test(t),
    "El diámetro se muestra en el panel del equipo");

  // ================================================================
  console.log("\n=== 3. En el informe, con su unidad ===");
  // ================================================================
  await pagina.evaluate(() => {
    [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Reporte")?.click();
  });
  await esperar(700);
  t = await texto();
  comprobar(/D \(di[áa]metro\)/i.test(t),
    "La etiqueta es legible, no el nombre de la variable");
  comprobar(/secci[óo]n de la columna/i.test(t) && /u de inundaci[óo]n/i.test(t),
    "Y el resto de la geometría también");
  comprobar(/\bm\b/.test(t), "Con unidad");

  // ================================================================
  console.log("\n=== 4. El área del intercambiador, solo si se da U ===");
  // ================================================================
  await abrir(simDoble(undefined));
  comprobar(respuesta?.pool?.["ic.area"] === undefined,
    "Sin U no hay área, y el diagrama resuelve igual",
    `completo = ${respuesta?.completo}`);
  await clicNodo("ic");
  t = await texto();
  comprobar(/Sin U no hay [áa]rea/i.test(t),
    "Y el panel dice por qué, en vez de dejar un hueco mudo");

  await abrir(simDoble(250));
  const pool2 = respuesta?.pool ?? {};
  comprobar(pool2["ic.area"] !== undefined && pool2["ic.lmtd"] !== undefined,
    "Con U aparecen el área y la LMTD",
    `A = ${pool2["ic.area"]?.toFixed(2)} m², LMTD = ${pool2["ic.lmtd"]?.toFixed(3)} K`);
  comprobar(
    Math.abs(pool2["ic.area"] - Math.abs(pool2["ic.Q"]) / (250 * pool2["ic.lmtd"])) < 1e-6,
    "Y cuadran: A = |Q|/(U·LMTD)");

  // ================================================================
  console.log("\n=== 5. La LMTD es una DIFERENCIA de temperatura ===");
  // ================================================================
  // Lo que ninguna suite de Python puede ver. Si la interfaz la tratara
  // como una temperatura, al pedirla en Celsius restaría 273.15 y los
  // 28.74 K saldrían como -244.4 °C.
  const magnitudes = await pagina.evaluate(async (base) => {
    const r = await fetch(`${base}/unidades`);
    const t = await r.json();
    return {
      lmtd: t.variables["lmtd"],
      delta: t.magnitudes["temperatura_diferencia"]?.unidades?.map(
        (u) => [u.simbolo, u.factor, u.desplazamiento]),
      temp: t.magnitudes["temperatura"]?.unidades?.map(
        (u) => [u.simbolo, u.factor, u.desplazamiento]),
    };
  }, process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8004");

  comprobar(JSON.stringify(magnitudes.lmtd) === JSON.stringify(["temperatura_diferencia"]),
    "La LMTD se declara como diferencia de temperatura, no como temperatura",
    JSON.stringify(magnitudes.lmtd));
  const deltaC = (magnitudes.delta ?? []).find((u) => u[0].includes("delta_degC"));
  const degC = (magnitudes.temp ?? []).find((u) => u[0] === "degC");
  comprobar(deltaC && deltaC[2] === 0,
    "La diferencia NO lleva desplazamiento",
    deltaC ? `${deltaC[0]}: factor ${deltaC[1]}, desplazamiento ${deltaC[2]}` : "no está");
  comprobar(degC && Math.abs(degC[2] - 273.15) < 1e-9,
    "Y la temperatura sí: ahí está la diferencia entre las dos magnitudes",
    degC ? `${degC[0]}: factor ${degC[1]}, desplazamiento ${degC[2]}` : "no está");
  comprobar((magnitudes.delta ?? []).length >= 2,
    "Hay más de una unidad de diferencia para elegir",
    (magnitudes.delta ?? []).map((u) => u[0]).join(", "));
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
