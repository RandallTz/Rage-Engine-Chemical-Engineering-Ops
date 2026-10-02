/**
 * Dos cosas:
 *
 * 1. Las unidades son de CADA simulación. El fallo que lo destapó: haber
 *    elegido kg/h una vez hacía que toda simulación futura leyera F en
 *    kg/h, incluidas las plantillas -- cuyos valores están escritos en SI.
 *    El "100" de la plantilla de reciclo se leía como 100 kg/h = 0.63
 *    mol/s y un avance de 5 mol/s resultaba imposible.
 *
 * 2. Renombrar cualquier elemento debe arrastrar aristas, datos y unidades.
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();

const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });
const pagina = await navegador.newPage();
pagina.on("pageerror", (e) => console.log("   [pageerror]", String(e).slice(0, 140)));

const texto = () => pagina.evaluate(() => document.body.innerText);
const clic = async (t, ms = 600) => {
  await pagina.evaluate((x) => [...document.querySelectorAll("button, a")]
    .find((z) => z.textContent.trim() === x)?.click(), t);
  await esperar(ms);
};
const abrirPlantilla = async (fragmento) => {
  await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });
  await esperar(500);
  await pagina.evaluate((f) => {
    [...document.querySelectorAll("button")].find((b) => b.innerText.includes(f))?.click();
  }, fragmento);
  await esperar(300);
  await clic("Crear y abrir", 3000);
};
const clicNodo = async (t) => {
  await pagina.evaluate((x) => {
    [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith(x))
      ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }, t);
  await esperar(400);
};

// ============ 1. Contaminar la preferencia de unidades a propósito
console.log("=== Se elige kg/h en una simulación ===");
await abrirPlantilla("Columna McCabe-Thiele (lista)");
await clicNodo("s1");
const cambio = await pagina.evaluate(() => {
  const filas = [...document.querySelectorAll("div")].filter(
    (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > select"));
  for (const f of filas) {
    if (f.querySelector("label").innerText.trim() === "F") {
      const sel = f.querySelector("select");
      const o = [...sel.options].find((x) => x.text === "kg/h");
      if (!o) return false;
      Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(sel, o.value);
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }
  }
  return false;
});
await esperar(700);
comprobar(cambio, "se puede elegir kg/h en esta simulación");
let t = await texto();
comprobar(/kg\/h/.test(t), "y la simulación lo muestra en kg/h");

// ============ 2. Otra simulación NO debe heredar esa unidad
console.log("\n=== Una simulación nueva NO hereda esa unidad ===");
await abrirPlantilla("Reactor con recirculación (listo)");
await esperar(1500);
const unidadFresco = await pagina.evaluate(() => {
  const n = [...document.querySelectorAll(".react-flow__node")].find((x) => x.innerText.startsWith("fresco"));
  return n?.innerText ?? "";
});
console.log("  fresco:", unidadFresco.replace(/\n/g, " | ").slice(0, 90));
comprobar(/mol\/s/.test(unidadFresco), "la plantilla arranca en mol/s (sus valores están en SI)");
comprobar(!/kg\/h/.test(unidadFresco), "NO se cuela el kg/h de la otra simulación");

// ============ 3. La plantilla de reciclo resuelve
console.log("\n=== La plantilla de reciclo resuelve ===");
await clic("Resolver", 10000);
t = await texto();
for (let i = 0; i < 25 && t.includes("Resolviendo"); i++) { await esperar(1000); t = await texto(); }
comprobar(t.includes("Resuelto por completo"), "resuelve por completo");
comprobar(!/incompatibles/.test(t), "sin datos incompatibles");
if (/incompatibles/.test(t)) console.log("   [diagnóstico]", t.slice(0, 400).replace(/\n/g, " | "));

const mezcla = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("mezcla"))?.innerText ?? "");
console.log("  mezcla:", mezcla.replace(/\n/g, " | ").slice(0, 80));
comprobar(/480\.000/.test(mezcla), "mezcla.F = 480 mol/s (100 frescos + 380 reciclados)");

// ============ 4. Renombrar elementos
console.log("\n=== Renombrar elementos ===");
await clicNodo("fresco");
const renombrar = async (nuevo) => {
  await pagina.evaluate(() => {
    const b = [...document.querySelectorAll("aside button")]
      .find((x) => x.title?.includes("renombrar"));
    b?.click();
  });
  await esperar(300);
  await pagina.evaluate((v) => {
    const i = document.querySelector("aside input");
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, v);
    i.dispatchEvent(new Event("input", { bubbles: true }));
    i.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  }, nuevo);
  await esperar(800);
};
await renombrar("alimentacion_fresca");
const hayNuevo = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].some((n) => n.innerText.startsWith("alimentacion_fresca")));
const hayViejo = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].some((n) => n.innerText.startsWith("fresco")));
comprobar(hayNuevo, "el elemento aparece con el nombre nuevo");
comprobar(!hayViejo, "y ya no con el viejo");

const conservaDatos = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("alimentacion_fresca"))?.innerText ?? "");
console.log("  tras renombrar:", conservaDatos.replace(/\n/g, " | ").slice(0, 80));
comprobar(/100\.000/.test(conservaDatos), "conserva sus datos (F = 100)");

const aristas = await pagina.evaluate(() => document.querySelectorAll(".react-flow__edge").length);
comprobar(aristas === 8, `conserva sus conexiones (${aristas} aristas)`);

// y sigue resolviendo
await clic("Resolver", 10000);
t = await texto();
for (let i = 0; i < 25 && t.includes("Resolviendo"); i++) { await esperar(1000); t = await texto(); }
comprobar(t.includes("Resuelto por completo"), "sigue resolviendo después de renombrar");

console.log("\n=== Nombres inválidos se rechazan ===");
await clicNodo("mezcla");
await renombrar("r1");
t = await texto();
comprobar(/Ya hay un elemento/.test(t), "un nombre repetido se rechaza diciendo por qué");
await pagina.keyboard.press("Escape");
await esperar(300);

await pagina.screenshot({ path: "verificacion-nombres.png", fullPage: true });
await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
