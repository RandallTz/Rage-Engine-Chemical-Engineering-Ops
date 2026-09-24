/**
 * Lo que pidio el usuario tras ver "F" y "m" como variables separadas:
 *   - UNA sola variable de caudal por corriente.
 *   - Poder elegir la unidad POR CORRIENTE (una en kg/h, otra en mol/s)
 *     y que la conversion se haga por dentro.
 */
import puppeteer from "puppeteer-core";
import { prepararSimulacion } from "./preparar_simulacion.mjs";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await puppeteer.launch({
  executablePath: EDGE, headless: "new",
  args: ["--no-sandbox"], defaultViewport: { width: 1700, height: 980 },
});
const pagina = await navegador.newPage();
let envio = null;
pagina.on("request", (r) => {
  if (r.url().includes("/diagrama/resolver")) { try { envio = JSON.parse(r.postData()); } catch { /* */ } }
});
await prepararSimulacion(pagina);
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
        const i = f.querySelector("input");
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, val);
        i.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }
    }
  }, etiqueta, valor);
  await esperar(140);
};
const elegirUnidad = async (etiqueta, opcion) => {
  const ok = await pagina.evaluate((et, op) => {
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
  await esperar(300);
  return ok;
};
const conectar = async (no, po, nd, pd) => {
  const c = await pagina.evaluate((a, b, cc, dd) => {
    const buscar = (id, papel, puerto) => {
      const n = [...document.querySelectorAll(".react-flow__node")].find((x) => x.innerText.startsWith(id));
      const h = (puerto && n?.querySelector(`.react-flow__handle.${papel}[data-handleid="${puerto}"]`))
        || n?.querySelector(`.react-flow__handle.${papel}`);
      if (!h) return null;
      const r = h.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    };
    const p1 = buscar(a, "source", b);
    const p2 = buscar(cc, "target", dd);
    return p1 && p2 ? { p1, p2 } : null;
  }, no, po, nd, pd);
  if (!c) return false;
  await pagina.mouse.move(c.p1.x, c.p1.y);
  await pagina.mouse.down();
  await pagina.mouse.move(c.p1.x - 20, c.p1.y + 10, { steps: 4 });
  await pagina.mouse.move(c.p2.x, c.p2.y, { steps: 15 });
  await esperar(120);
  await pagina.mouse.up();
  await esperar(320);
  return true;
};

await clic("+ Columna");
await clic("+ Corriente"); await clic("+ Corriente"); await clic("+ Corriente");
await conectar("s1", null, "col1", "alimentacion");
await conectar("col1", "destilado", "s2", null);
await conectar("col1", "fondos", "s3", null);

console.log("\n=== Una sola variable de caudal ===");
await clicNodo("s1");
const variables = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("s1"))?.innerText ?? "");
console.log("  s1 muestra:", variables.replace(/\n/g, " | "));
comprobar(!variables.includes("másico"), "ya no existe una variable 'm' aparte");
comprobar((variables.match(/\bF\b/g) ?? []).length === 1, "hay exactamente una F");

console.log("\n=== Unidades distintas en cada corriente ===");
// s1 en kg/h; s2 se queda en mol/s.
const puedeMasa = await elegirUnidad("F", "kg/h");
comprobar(puedeMasa, "la F de una corriente ofrece unidades masicas");
await escribir("F", "30645");            // 30645 kg/h, MW mezcla 85.125 -> 100 mol/s
await escribir("x benzene", "0.5");
await clicNodo("s2");
const unidadS2 = await pagina.evaluate(() => {
  const filas = [...document.querySelectorAll("div")].filter(
    (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > select"));
  for (const f of filas) if (f.querySelector("label").innerText.trim() === "F") return f.querySelector("select").value;
  return null;
});
console.log("  unidad de s2.F tras poner s1 en kg/h:", unidadS2);
comprobar(unidadS2 === "mol/s", "cambiar la unidad de una corriente NO afecta a las demas");
await escribir("x benzene", "0.95");
await clicNodo("s3"); await escribir("x benzene", "0.05");
await clicNodo("col1"); await escribir("q", "1"); await escribir("R", "3.06");

await clic("Resolver");
await esperar(5000);

console.log("\n=== La conversion se hace por dentro ===");
console.log("  enviado en 'valores'          :", JSON.stringify(envio?.valores));
console.log("  enviado en 'caudales_masicos' :", JSON.stringify(envio?.caudales_masicos));
comprobar(envio?.caudales_masicos?.s1 !== undefined, "el caudal masico viaja aparte, no como F en mol/s inventado");
comprobar(envio?.valores?.["s1.F"] === undefined, "no se manda s1.F convertido a ciegas");

const s1 = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("s1"))?.innerText ?? "");
const s2 = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("s2"))?.innerText ?? "");
console.log("  s1:", s1.replace(/\n/g, " | ").slice(0, 90));
console.log("  s2:", s2.replace(/\n/g, " | ").slice(0, 90));
comprobar(s1.includes("kg/h"), "s1 muestra su caudal en kg/h");
comprobar(s2.includes("mol/s"), "s2 muestra el suyo en mol/s, a la vez");
const texto = await pagina.evaluate(() => document.body.innerText);
comprobar(texto.includes("Resuelto por completo"), "el diagrama resuelve con unidades mezcladas");

await pagina.screenshot({ path: "verificacion-unaF.png" });
await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
