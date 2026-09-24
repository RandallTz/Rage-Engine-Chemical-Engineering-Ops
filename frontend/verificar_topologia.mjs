/**
 * El mapa de destilación reactiva debe traer los CUATRO elementos del
 * método original (archive/equations.py), no solo las curvas residuales:
 * trayectorias etapa a etapa, curva de equilibrio químico, líneas
 * estequiométricas y el polo π = ν/ν_tot.
 *
 * Sistema: el de las primeras pruebas -- isobutylene/methanol/mtbe,
 * ν = [-1,-1,3], A = 1e6, Ea = 6e4, Da = 5, T_ref = 350 K.
 */
import puppeteer from "puppeteer-core";
import { prepararSimulacion } from "./preparar_simulacion.mjs";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await puppeteer.launch({
  executablePath: EDGE, headless: "new",
  args: ["--no-sandbox"], defaultViewport: { width: 1700, height: 1100 },
});
const pagina = await navegador.newPage();
pagina.on("pageerror", (e) => console.log("   [pageerror]", String(e).slice(0, 140)));

await prepararSimulacion(pagina, [
  { nombre: "isobutylene", MW: 56.106 },
  { nombre: "methanol", MW: 32.042 },
  { nombre: "mtbe", MW: 88.148 },
]);
await pagina.goto("http://localhost:3000/termodinamica/reactiva", { waitUntil: "networkidle0" });
await esperar(900);

const texto = () => pagina.evaluate(() => document.body.innerText);
const escribirNu = async (valores) => {
  await pagina.evaluate((vals) => {
    const set = (i, v) => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, v);
      i.dispatchEvent(new Event("input", { bubbles: true }));
    };
    // La barra de la simulacion trae un input[type=file] oculto: hay
    // que quedarse solo con los de texto/numero del formulario.
    const inputs = [...document.querySelectorAll("input")]
      .filter((i) => i.type !== "file" && i.type !== "checkbox");
    vals.forEach((v, k) => inputs[k] && set(inputs[k], v));
  }, valores);
  await esperar(300);
};

// los 3 primeros inputs son los nu; luego A, Ea, Da
await escribirNu(["-1", "-1", "3", "1e6", "60000", "5"]);
let t = await texto();
comprobar(t.includes("⇌"), "la ecuación de reacción se muestra armada");
console.log("  ecuación:", (t.match(/[\w]+ \+ [\w]+ ⇌ .*/) ?? ["(no encontrada)"])[0]);

console.log("\n=== Comprobar la reacción ===");
await pagina.evaluate(() => [...document.querySelectorAll("button")]
  .find((b) => b.textContent.includes("Comprobar la reacción"))?.click());
for (let i = 0; i < 40 && (await texto()).includes("…"); i++) await esperar(500);
t = await texto();
comprobar(/ΔH°rxn/.test(t), "devuelve las propiedades de reacción");

console.log("\n=== Mapa de topología reactiva (cálculo caro) ===");
await pagina.evaluate(() => [...document.querySelectorAll("button")]
  .find((b) => b.textContent.trim() === "Mapa reactivo")?.click());
for (let i = 0; i < 150; i++) {
  if (!(await texto()).includes("Integrando…")) break;
  await esperar(1000);
}
t = await texto();

const capas = await pagina.evaluate(() => {
  const svg = document.querySelector("svg");
  if (!svg) return null;
  const color = (c) => [...svg.querySelectorAll("path")].filter(
    (p) => (p.getAttribute("stroke") ?? "").toLowerCase() === c).length;
  return {
    residuales: color("#38bdf8"),
    reactivas: color("#c084fc"),
    equilibrio: color("#fafafa"),
    estequiometricas: color("#f87171"),
    poloDibujado: svg.querySelectorAll("circle[stroke='#f87171']").length,
  };
});
console.log("  capas dibujadas:", capas);

comprobar(capas !== null, "se dibuja el triángulo");
comprobar((capas?.residuales ?? 0) > 3, "curvas residuales continuas");
comprobar((capas?.reactivas ?? 0) > 3, "trayectorias reactivas etapa a etapa (el mapeo del libro)");
comprobar((capas?.equilibrio ?? 0) >= 1, "curva de equilibrio químico");
comprobar((capas?.estequiometricas ?? 0) > 3, "líneas estequiométricas");

comprobar(t.includes("π = ν/ν_tot"), "el pie explica el polo geométrico");
comprobar(/\(-1\.00, -1\.00, 3\.00\)/.test(t), "y cita π = (-1, -1, 3), el valor correcto para ν=[-1,-1,3]");
comprobar(t.includes("fuera del triángulo"), "y avisa de que ese polo cae fuera, en vez de dibujarlo mal");

console.log("\n=== Las capas se pueden apagar ===");
const antes = capas?.estequiometricas ?? 0;
await pagina.evaluate(() => [...document.querySelectorAll("button")]
  .find((b) => b.textContent.includes("líneas estequiométricas"))?.click());
await esperar(400);
const despues = await pagina.evaluate(() => [...document.querySelectorAll("svg path")]
  .filter((p) => (p.getAttribute("stroke") ?? "").toLowerCase() === "#f87171").length);
comprobar(antes > 0 && despues === 0, "apagar una capa la oculta de verdad");

// muestreo de las curvas: no deben ser segmentos de 2-3 puntos
const puntosPorCurva = await pagina.evaluate(() =>
  [...document.querySelectorAll("svg path")]
    .filter((p) => (p.getAttribute("stroke") ?? "").toLowerCase() === "#38bdf8")
    .map((p) => (p.getAttribute("d") ?? "").split("L").length));
console.log("  puntos por curva residual:", puntosPorCurva.slice(0, 6), "...");
comprobar(Math.min(...puntosPorCurva) > 20,
  "las curvas vienen bien muestreadas (antes salían con 2-3 puntos, como rectas)");

// volver a encender la capa que se apagó antes, para que la captura
// muestre el mapa completo
await pagina.evaluate(() => [...document.querySelectorAll("button")]
  .find((b) => b.textContent.includes("líneas estequiométricas"))?.click());
await esperar(400);
await pagina.screenshot({ path: "verificacion-topologia.png", fullPage: true });
const svg = await pagina.$("svg");
if (svg) await svg.screenshot({ path: "verificacion-topologia-mapa.png" });
await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
