/**
 * Verificacion en navegador de la CAIDA DE PRESION.
 *
 * Lo que solo se ve aqui: que el numero escrito en el panel llegue al
 * servidor y vuelva convertido en una presion de salida distinta. La suite
 * de Python valida la fisica; esta valida que el camino completo exista.
 *
 * Y comprueba una cosa mas, que es la razon de que el campo lleve una nota
 * al lado: subir la caida AUMENTA la fraccion vaporizada, porque el estado
 * de salida se evalua a la presion de salida. Sin esa nota, el resultado
 * se puede leer como un error del simulador cuando es justo lo contrario.
 *
 * Uso:  node verificar_caida_presion.mjs [url]
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

function simulacion(caida) {
  return {
    id: "sim_dp", nombre: "Caída de presión",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: [
      { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
      { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
    ],
    modelo: "unifac_raoult", unidades: {},
    flowsheet: {
      nodes: [
        { id: "s1", type: "corriente", position: { x: 60, y: 200 }, data: { clase: "corriente" } },
        {
          id: "ic1", type: "operacion", position: { x: 380, y: 180 },
          data: {
            clase: "operacion", tipo: "intercambiador", P_sistema: 2 * ATM,
            spec_intercambiador: "Q_por_mol", Q_por_mol: 28000,
            caida_P: caida,
          },
        },
        { id: "s2", type: "corriente", position: { x: 700, y: 200 }, data: { clase: "corriente" } },
      ],
      edges: [
        { id: "e1", source: "s1", target: "ic1", sourceHandle: null, targetHandle: "entrada" },
        { id: "e2", source: "ic1", target: "s2", sourceHandle: "salida", targetHandle: null },
      ],
      dados: {
        "s1.F": "100", "s1.T": "350", "s1.P": String(2 * ATM),
        "s1.x0": "0.4", "s1.x1": "0.6",
      },
    },
  };
}

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });

try {
  const pagina = await navegador.newPage();
  let envio = null;
  let respuesta = null;
  await pagina.setRequestInterception(true);
  pagina.on("request", (p) => {
    if (p.url().includes("/diagrama/resolver") && p.method() === "POST") {
      try { envio = JSON.parse(p.postData()); } catch { /* ignorar */ }
    }
    p.continue();
  });
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
    await esperar(400);
  };
  const resolver = async () => {
    await pagina.evaluate(() => {
      [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Resolver")?.click();
    });
    await pagina.waitForFunction(
      () => /Resuelto por completo|Quedan \d+ variables|no es f[íi]sica|Error/i
        .test(document.body.innerText),
      { timeout: 120000 },
    );
    await esperar(500);
  };

  const medir = async (caida) => {
    respuesta = null;
    await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "domcontentloaded" });
    await pagina.evaluate((s) => {
      localStorage.setItem("simulador.simulaciones", JSON.stringify({ activa: s.id, lista: [s] }));
    }, simulacion(caida));
    await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
    await esperar(800);
    await resolver();
    const t = await texto();
    const pool = respuesta?.pool ?? {};
    return {
      texto: t,
      P: pool["s2.P"] ?? null,
      beta: pool["ic1.beta_salida"] ?? null,
      T: pool["s2.T"] ?? null,
      errores: Object.values(respuesta?.errores_bloque ?? {}).map(String),
      detalle: respuesta?.detail ?? null,
    };
  };

  // ================================================================
  console.log("\n=== 1. Sin caída: la salida está a la presión de entrada ===");
  // ================================================================
  const r = await medir(0);
  comprobar(/Resuelto por completo/i.test(r.texto), "El diagrama resuelve sin caída");
  comprobar(envio?.operaciones?.[0]?.caida_P === 0,
    "La petición manda caida_P = 0", String(envio?.operaciones?.[0]?.caida_P));
  comprobar(r.P !== null && Math.abs(r.P - 2 * ATM) < 1e-6,
    "Y la salida vuelve a la presión de entrada", `${r.P} Pa`);

  // ================================================================
  console.log("\n=== 2. Con caída: la presión baja y sale más vapor ===");
  // ================================================================
  const claves = [0, 0.5 * ATM, 0.9 * ATM];
  const medidas = {};
  for (const dP of claves) {
    const res = await medir(dP);
    comprobar(/Resuelto por completo/i.test(res.texto),
      `Resuelve con ΔP = ${(dP / ATM).toFixed(2)} atm`);
    comprobar(envio?.operaciones?.[0]?.caida_P === dP,
      `Y la petición lleva caida_P = ${dP}`, String(envio?.operaciones?.[0]?.caida_P));
    medidas[dP] = res;
    console.log(`     ΔP = ${(dP / ATM).toFixed(2)} atm   P_salida = ${res.P}   ` +
      `T = ${res.T?.toFixed(3)} K   β = ${res.beta?.toFixed(6)}`);
  }

  comprobar(claves.every((k) => medidas[k].P !== null),
    "La presión de salida vuelve en los tres casos");
  comprobar(claves.every((k) => Math.abs(medidas[k].P - (2 * ATM - k)) < 1e-6),
    "Y es exactamente P_entrada − ΔP",
    claves.map((k) => `${(medidas[k].P / ATM).toFixed(3)} atm`).join(" > "));
  comprobar(medidas[claves[2]].beta > medidas[claves[0]].beta,
    "La fracción vaporizada AUMENTA con la caída: la salida se evalúa a la presión de salida",
    claves.map((k) => medidas[k].beta.toFixed(6)).join(" < "));
  comprobar(medidas[claves[2]].T < medidas[claves[0]].T,
    "Y la temperatura de salida baja: más vapor a menos presión",
    `${medidas[claves[0]].T.toFixed(3)} K → ${medidas[claves[2]].T.toFixed(3)} K`);

  // ================================================================
  console.log("\n=== 3. El campo y su nota están en el panel ===");
  // ================================================================
  await clicNodo("ic1");
  let t = await texto();
  comprobar(/ca[íi]da de presi[óo]n/i.test(t), "El campo aparece etiquetado");
  comprobar(/presi[óo]n de .?salida.?/i.test(t) && /dos fases/i.test(t),
    "Y con caída > 0 explica a qué presión se evalúa la salida",
    (t.match(/[^\n]*dos fases[^\n]*/) ?? [""])[0].slice(0, 120));

  // Sin caída la nota no debe estorbar: es una explicación, no un aviso.
  await medir(0);
  await clicNodo("ic1");
  t = await texto();
  comprobar(!/dos fases/i.test(t), "Con caída 0 la nota no aparece");

  // ================================================================
  console.log("\n=== 4. Una caída imposible se explica, no revienta ===");
  // ================================================================
  const res = await medir(5 * ATM);
// Se buscan las LINEAS que mencionan el motivo, no el texto entero: un
  // detalle que vuelca la pagina completa (barra de navegacion incluida) no
  // dice si el mensaje es util o si la frase aparecio por casualidad.
  const motivos = [...res.errores, String(res.detalle ?? "")]
    .concat(res.texto.split(/\r?\n/))
    .filter((m) => /no es f[íi]sica/i.test(m));
  comprobar(motivos.length > 0,
    "Una caída mayor que la presión disponible dice por qué no puede ser",
    (motivos[0] ?? "no aparece el motivo").slice(0, 170));
  comprobar(motivos.some((m) => /caida de|caída de/i.test(m) && /entrada/i.test(m)),
    "Y el mensaje trae la caída pedida y la presión de la que se partía",
    (motivos[0] ?? "").slice(0, 170));
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
