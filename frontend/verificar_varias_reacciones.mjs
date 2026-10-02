/**
 * Verificacion en navegador de VARIAS REACCIONES en un reactor.
 *
 * Que comprueba que no comprueba ninguna suite de Python. Las de Python
 * validan la fisica (`validar_varias_reacciones.py`) y la frontera HTTP.
 * Lo que solo se puede ver aqui:
 *
 *   - Que el editor permita anadir una segunda reaccion y que el pool pase
 *     a declarar ξ₀ y ξ₁. Esa regla de nombres esta escrita DOS veces -- en
 *     `clavesAvance` (TypeScript) y en `_claves_xi` (Python) -- porque la
 *     interfaz necesita los nombres ANTES de la primera resolucion. Si las
 *     dos se separaran, el diagrama pediria variables que el servidor no
 *     tiene, y esta suite es lo unico que lo cazaria.
 *   - Que con UNA reaccion siga diciendo `xi`, sin subindice. Ese nombre
 *     esta dentro de cada diagrama guardado y de cada enlace compartido.
 *   - Que Arrhenius sea POR reaccion. Es lo que decide la selectividad:
 *     tenerlo fuera sugeriria que las reacciones lo comparten.
 *   - Y que el numero de la pantalla sea el del nucleo.
 *
 * Uso:  node verificar_varias_reacciones.mjs [url]
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002";

const fallos = [];
const comprobar = (c, m, detalle = "") => {
  console.log(`  ${c ? "OK  " : "FALLA"} ${m}${detalle ? " -- " + detalle : ""}`);
  if (!c) fallos.push(m);
};
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

// MTBE con su secundaria: cuatro componentes, dos reacciones.
const COMPONENTES = [
  { nombre: "isobutene", formula: "C4H8", MW: 56.11, Tb: 266.25 },
  { nombre: "methanol", formula: "CH4O", MW: 32.04, Tb: 337.63 },
  { nombre: "mtbe", formula: "C5H12O", MW: 88.15, Tb: 328.35 },
  { nombre: "2,4,4-trimethyl-1-pentene", formula: "C8H16", MW: 112.21, Tb: 374.5 },
];

function simulacion() {
  return {
    id: "sim_reacciones", nombre: "MTBE con secundaria",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: COMPONENTES, modelo: "unifac_raoult", unidades: {},
    flowsheet: {
      nodes: [
        { id: "alim", type: "corriente", position: { x: 60, y: 200 }, data: { clase: "corriente" } },
        {
          id: "r1", type: "operacion", position: { x: 380, y: 180 },
          data: {
            clase: "operacion", tipo: "reactor_equilibrio", P_sistema: 3039750,
            con_balance_energia: true,
            // Una sola reaccion, en el formato ANTIGUO (nu/A/Ea): asi la
            // suite empieza exactamente donde esta un diagrama ya guardado.
            nu: "-1,-1,1,0", A: 1e8, Ea: 45000,
          },
        },
        { id: "prod", type: "corriente", position: { x: 700, y: 200 }, data: { clase: "corriente" } },
      ],
      edges: [
        { id: "e1", source: "alim", target: "r1", sourceHandle: null, targetHandle: "entrada" },
        { id: "e2", source: "r1", target: "prod", sourceHandle: "salida", targetHandle: null },
      ],
      dados: {
        "alim.F": "100", "alim.T": "330", "alim.P": "3039750",
        "alim.x0": "0.5", "alim.x1": "0.5", "alim.x2": "0", "alim.x3": "0",
        "r1.T": "340",
      },
    },
  };
}

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });

try {
  const pagina = await navegador.newPage();
  let ultimoEnvio = null;
  await pagina.setRequestInterception(true);
  pagina.on("request", (p) => {
    if (p.url().includes("/diagrama/resolver") && p.method() === "POST") {
      try { ultimoEnvio = JSON.parse(p.postData()); } catch { /* ignorar */ }
    }
    p.continue();
  });

  await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "domcontentloaded" });
  await pagina.evaluate((s) => {
    localStorage.setItem("simulador.simulaciones", JSON.stringify({ activa: s.id, lista: [s] }));
  }, simulacion());
  await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
  await esperar(900);

  const clicNodo = async (id) => {
    await pagina.evaluate((x) => {
      [...document.querySelectorAll(".react-flow__node")]
        .find((n) => n.innerText.startsWith(x))
        ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }, id);
    await esperar(450);
  };
  const texto = () => pagina.evaluate(() => document.body.innerText);
  const pulsar = (patron) =>
    pagina.evaluate((re) => {
      const b = [...document.querySelectorAll("button")].find((x) => new RegExp(re, "i").test(x.textContent));
      if (!b || b.disabled) return false;
      b.click();
      return true;
    }, patron);

  // ================================================================
  console.log("\n=== 1. Un diagrama guardado con UNA reacción no cambia ===");
  // ================================================================
  await clicNodo("r1");
  let t = await texto();
  comprobar(/reacci[óo]n/i.test(t) && !/reacciones \(/i.test(t),
    "El panel dice «Reacción» en singular");
  comprobar(/ξ \(avance\)|\bξ\b/.test(t) && !/ξ₀/.test(t),
    "Y el avance se llama ξ, sin subíndice");
  comprobar(/A \(Arrhenius\)/.test(t), "Arrhenius está presente");

  // ================================================================
  console.log("\n=== 2. Añadir una segunda reacción ===");
  // ================================================================
  comprobar(await pulsar("\\+ reacción"), "El botón «+ reacción» existe y se puede pulsar");
  await esperar(500);
  t = await texto();
  comprobar(/reacciones \(2\)/i.test(t), "El panel pasa a «Reacciones (2)»");
  comprobar(/ξ₀/.test(t) && /ξ₁/.test(t), "Y aparecen ξ₀ y ξ₁");

  const arrhenius = await pagina.evaluate(() =>
    [...document.querySelectorAll("label")].filter((l) => /A \(Arrhenius\)/.test(l.textContent)).length);
  comprobar(arrhenius === 2, "Hay un Arrhenius POR reacción, no uno compartido",
    `${arrhenius} campos`);

  // La segunda arranca VACIA a proposito: copiar la primera daria dos
  // reacciones indistinguibles y el sistema que reparte los avances sale
  // singular.
  comprobar(/Marca al menos un reactivo y un producto/.test(t),
    "La segunda arranca vacía, no copiando la primera");

  // ================================================================
  console.log("\n=== 3. Rellenar la secundaria: 2 isobuteno → diisobuteno ===");
  // ================================================================
  // Se escribe directamente en el estado de la simulación, que es lo que
  // el editor produce: lo que esta suite comprueba es que ESE estado
  // llegue bien al servidor y vuelva con los dos avances.
  await pagina.evaluate(() => {
    const g = JSON.parse(localStorage.getItem("simulador.simulaciones"));
    const r1 = g.lista[0].flowsheet.nodes.find((n) => n.id === "r1");
    r1.data.reacciones = [
      { nu: "-1,-1,1,0", A: 1e8, Ea: 45000 },
      { nu: "-2,0,0,1", A: 2e8, Ea: 60000 },
    ];
    r1.data.nu = "-1,-1,1,0";
    r1.data.A = 1e8;
    r1.data.Ea = 45000;
    localStorage.setItem("simulador.simulaciones", JSON.stringify(g));
  });
  await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
  await esperar(900);
  await clicNodo("r1");
  t = await texto();
  comprobar(/reacciones \(2\)/i.test(t), "Al recargar, las dos reacciones siguen ahí");
  comprobar(/2 isobutene/.test(t) || /isobutene.*→/.test(t),
    "La ecuación de la secundaria se dibuja",
    (t.match(/[^\n]*→[^\n]*/g) ?? []).join("  |  ").slice(0, 110));

  // ================================================================
  console.log("\n=== 4. Resolver: los dos avances llegan a la pantalla ===");
  // ================================================================
  comprobar(await pulsar("^Resolver$"), "Se puede lanzar el cálculo");
  try {
    await pagina.waitForFunction(
      () => /Resuelto por completo|Quedan \d+ variables|no se |faltan |Error/i
        .test(document.body.innerText),
      { timeout: 180000 },
    );
  } catch {
    const visible = (await texto()).replace(/\n+/g, " | ").slice(0, 400);
    comprobar(false, "El cálculo terminó (o dijo por qué no)", visible);
  }
  await esperar(600);

  comprobar(ultimoEnvio !== null, "Se interceptó la petición");
  if (ultimoEnvio) {
    const op = (ultimoEnvio.operaciones ?? [])[0] ?? {};
    comprobar(Array.isArray(op.reacciones) && op.reacciones.length === 2,
      "La petición manda 'reacciones' con las dos",
      `reacciones=${op.reacciones?.length}, reaccion=${JSON.stringify(op.reaccion)}`);
    comprobar(op.reaccion === null || op.reaccion === undefined,
      "Y NO manda también 'reaccion': el servidor rechazaría los dos campos");
    comprobar(
      JSON.stringify(op.reacciones?.[1]?.nu) === JSON.stringify([-2, 0, 0, 1]),
      "La estequiometría de la secundaria viaja intacta",
      JSON.stringify(op.reacciones?.[1]?.nu));
    comprobar(op.reacciones?.[1]?.A === 2e8,
      "Y su propio A, distinto del de la primera",
      `A₀=${op.reacciones?.[0]?.A}  A₁=${op.reacciones?.[1]?.A}`);
  }

  // EL NUMERO, que es lo que de verdad justifica una suite de navegador.
  // El nucleo da ξ = [8.239583, 20.151557] para este caso.
  //
  // Se buscan "8.240" y "20.152" y no "8.2395": la interfaz formatea con
  // `formatear`, que redondea a tres decimales. Comparar contra el valor
  // sin redondear fallaria por un motivo que no tiene nada que ver con lo
  // que se esta comprobando.
  await clicNodo("r1");
  const panel = await texto();
  comprobar(/\b8\.240\b/.test(panel) && /\b20\.152\b/.test(panel),
    "Los dos avances del núcleo aparecen en la pantalla",
    (panel.match(/\b(8\.240|20\.152)\b/g) ?? []).join(", ") || "no aparecen");
  // Y con sus nombres, no como dos numeros sueltos.
  comprobar(/ξ₀/.test(panel) && /ξ₁/.test(panel),
    "Etiquetados como ξ₀ y ξ₁, no como dos números sueltos");
  // Las dos K_eq tambien: son lo que explica POR QUE la secundaria gana.
  comprobar(/4\.139/.test(panel) && /487\.98/.test(panel),
    "Y las dos constantes de equilibrio",
    (panel.match(/\b(4\.139|487\.98\d*)\b/g) ?? []).join(", ") || "no aparecen");

  comprobar(/Resuelto por completo/i.test(panel),
    "Y el diagrama queda resuelto por completo");

  // ================================================================
  console.log("\n=== 5. Quitar la segunda vuelve al formato de una ===");
  // ================================================================
  await clicNodo("r1");
  comprobar(await pulsar("^quitar$"), "El botón «quitar» existe");
  await esperar(500);
  t = await texto();
  comprobar(/reacci[óo]n/i.test(t) && !/reacciones \(/i.test(t),
    "Vuelve a decir «Reacción» en singular");
  const guardado = await pagina.evaluate(() => {
    const g = JSON.parse(localStorage.getItem("simulador.simulaciones"));
    const r1 = g.lista[0].flowsheet.nodes.find((n) => n.id === "r1");
    return { reacciones: r1.data.reacciones, nu: r1.data.nu };
  });
  comprobar(guardado.reacciones === undefined || guardado.reacciones === null,
    "Y el estado vuelve al formato de una sola reacción (sin 'reacciones')",
    JSON.stringify(guardado));
  comprobar(typeof guardado.nu === "string" && guardado.nu.length > 0,
    "Conservando nu, que es lo que leen los diagramas guardados", guardado.nu);
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
