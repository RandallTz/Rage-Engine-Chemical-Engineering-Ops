/**
 * Comprueba el NUMERO de la conversion masica, no solo que la UI no se
 * queje. Benceno/tolueno 50/50 -> MW mezcla = 0.5*78.11 + 0.5*92.14 =
 * 85.125 g/mol. Entonces 30645 kg/h deben ser exactamente 100 mol/s:
 *   30645 kg/h / 3600 = 8.5125 kg/s = 8512.5 g/s
 *   8512.5 / 85.125 = 100.0 mol/s
 *
 * DONDE se hace esa division es lo que esta suite tuvo que corregir. La
 * primera version daba por hecho que la hacia el navegador y miraba
 * `valores["s1.F"]`. Ya no: masa <-> moles NO es una conversion afin
 * (depende de la composicion de ESA corriente), asi que el caudal masico
 * viaja aparte en `caudales_masicos` [kg/s] y la division es una ECUACION
 * del nucleo, m = F*MW_mezcla(x). Ver el comentario de `aSI` en
 * app/flowsheet/unidades.ts y `_bloque_caudal_masico` en
 * core/diagrama_corrientes.py.
 *
 * El cambio de contrato no debilita la comprobacion: se siguen exigiendo
 * los dos numeros, el que sale del navegador (8.5125 kg/s, conversion
 * afin) y el que sale del nucleo (100 mol/s, la que necesita la MW de la
 * mezcla). Antes solo se veia el segundo.
 */
import puppeteer from "puppeteer-core";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await puppeteer.launch({
  executablePath: EDGE, headless: "new",
  args: ["--no-sandbox"], defaultViewport: { width: 1700, height: 950 },
});
const pagina = await navegador.newPage();

let ultimoEnvio = null;
let ultimaResolucion = null;
await pagina.setRequestInterception(true);
pagina.on("request", (peticion) => {
  if (peticion.url().includes("/diagrama/") && peticion.method() === "POST") {
    try { ultimoEnvio = JSON.parse(peticion.postData()); } catch { /* ignorar */ }
  }
  peticion.continue();
});
// La respuesta de /diagrama/resolver es la que trae el numero que de
// verdad importa: el caudal en moles que el nucleo deduce de la masa.
pagina.on("response", async (respuesta) => {
  if (!respuesta.url().includes("/diagrama/resolver")) return;
  try { ultimaResolucion = await respuesta.json(); } catch { /* ignorar */ }
});

// Hace falta una simulacion ABIERTA con los dos componentes. Sin ella la
// pagina del flowsheet avisa de que no hay simulacion, "+ Corriente" no
// hace nada y no se manda ninguna peticion que interceptar -- que es
// exactamente como esta suite se quedo muda cuando las simulaciones
// pasaron a vivir en el almacenamiento del navegador.
await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "domcontentloaded" });
await pagina.evaluate(() => {
  const sim = {
    id: "sim_masa", nombre: "Masa — benceno/tolueno",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: [
      { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
      { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
    ],
    modelo: "unifac_raoult", unidades: {},
    flowsheet: { nodes: [], edges: [], dados: {} },
  };
  localStorage.setItem("simulador.simulaciones",
    JSON.stringify({ activa: sim.id, lista: [sim] }));
});
await pagina.goto("http://localhost:3000/flowsheet", { waitUntil: "networkidle0" });

const clic = async (t) => {
  await pagina.evaluate((x) => [...document.querySelectorAll("button")].find((z) => z.textContent.trim() === x)?.click(), t);
  await esperar(450);
};
const clicNodo = async (t) => {
  await pagina.evaluate((x) => {
    [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith(x))
      ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }, t);
  await esperar(320);
};
const escribir = async (etiqueta, valor) => {
  await pagina.evaluate((et, val) => {
    const filas = [...document.querySelectorAll("div")].filter(
      (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > input"));
    for (const f of filas) {
      if (f.querySelector("label").innerText.trim() === et) {
        const input = f.querySelector("input");
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(input, val);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }
    }
  }, etiqueta, valor);
  await esperar(150);
};
const elegirUnidad = async (etiqueta, opcion) =>
  pagina.evaluate((et, op) => {
    const filas = [...document.querySelectorAll("div")].filter(
      (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > select"));
    for (const f of filas) {
      if (f.querySelector("label").innerText.trim() === et) {
        const sel = f.querySelector("select");
        const o = [...sel.options].find((x) => x.text === op);
        if (!o) return false;
        Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(sel, o.value);
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
    }
    return false;
  }, etiqueta, opcion);

// Solo una corriente suelta: con una columna sin conectar, la peticion
// ni siquiera se construye (le faltan corrientes) y no habria nada que
// interceptar.
await clic("+ Corriente");
await clicNodo("s1");
await escribir("x benzene", "0.5");
await escribir("x toluene", "0.5");
await elegirUnidad("F", "kg/h");
await esperar(500);
await escribir("F", "30645");
await esperar(2800);

// Primer numero: la conversion AFIN que si hace el navegador, kg/h -> kg/s.
const enviadoMasa = ultimoEnvio?.caudales_masicos?.["s1"];
// Y no debe mandarse como valor fijo de F: eso seria decidir la division
// sin saber la composicion.
const comoValorFijo = ultimoEnvio?.valores?.["s1.F"];

console.log(`\n  escrito en la interfaz    : 30645 kg/h`);
console.log(`  enviado en caudales_masicos: ${enviadoMasa} kg/s   (esperado 8.5125)`);
console.log(`  enviado en valores.s1.F    : ${comoValorFijo}   (debe ser undefined)`);

// Segundo numero, el que necesita la masa molar de la MEZCLA: se resuelve
// y se mira lo que deduce el nucleo.
//
// Sale 99.99985 y no 100.00000, y la diferencia tiene explicacion: las MW
// de la cabecera (78.11 y 92.14) estan redondeadas, mientras que el nucleo
// usa las de 'thermo' (Chemical.MW) a propósito -- asi el caudal masico es
// una variable del sistema y no depende de que el navegador tenga la MW
// cacheada. Por eso la tolerancia es 0.01 mol/s y no cero: lo que se
// comprueba es que la division se hace con la MW de la MEZCLA, no que dos
// tablas de masas atomicas coincidan.
await clic("Resolver");
await esperar(4000);
const enMoles = ultimaResolucion?.pool?.["s1.F"];
console.log(`  deducido por el núcleo     : ${enMoles} mol/s   (esperado 100)`);

const fallos = [];
if (enviadoMasa === undefined || Math.abs(enviadoMasa - 8.5125) > 1e-6) {
  fallos.push("el caudal masico no llega como 8.5125 kg/s en caudales_masicos");
}
if (comoValorFijo !== undefined) {
  fallos.push("el caudal masico se manda como valor fijo de F, convirtiendo sin la composicion");
}
if (enMoles === undefined || Math.abs(enMoles - 100) > 0.01) {
  fallos.push("el nucleo no deduce 100 mol/s a partir de la masa y la composicion");
}

console.log(fallos.length === 0
  ? "\n  OK: la masa viaja como restriccion y el nucleo cierra con la MW de la mezcla\n"
  : "\n  FALLA:\n    - " + fallos.join("\n    - ") + "\n");

await navegador.close();
process.exit(fallos.length === 0 ? 0 : 1);
