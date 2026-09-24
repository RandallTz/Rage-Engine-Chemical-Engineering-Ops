/**
 * Datos sobre-especificados e INCOMPATIBLES: el balance total cierra
 * (100 = 20 + 80) pero el de componente no (100*0.5 = 50 frente a
 * 20*0.8 + 80*0.1 = 24). Antes el simulador decia "resuelto por
 * completo" sin quejarse.
 *
 * Nota: este script se actualizo cuando las operaciones dejaron de
 * crear sus corrientes automaticamente -- ahora hay que agregarlas y
 * conectarlas, como hace el usuario.
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

console.log("\n=== Datos incompatibles ===");
await clic("+ Columna");
await clic("+ Corriente"); await clic("+ Corriente"); await clic("+ Corriente");
await conectar("s1", null, "col1", "alimentacion");
await conectar("col1", "destilado", "s2", null);
await conectar("col1", "fondos", "s3", null);

await clicNodo("s1"); await escribir("F", "100"); await escribir("x benzene", "0.5");
await clicNodo("s2"); await escribir("F", "20"); await escribir("x benzene", "0.8");
await clicNodo("s3"); await escribir("F", "80"); await escribir("x benzene", "0.1");
await clicNodo("col1"); await escribir("q", "1"); await escribir("R", "2.5");

await clic("Resolver");
await esperar(5500);

const texto = await pagina.evaluate(() => document.body.innerText);
comprobar(/incompatibles/.test(texto), "la barra superior avisa de datos incompatibles");
comprobar(texto.includes("Datos incompatibles"), "el panel lateral detalla las incompatibilidades");
comprobar(/balance de materia/i.test(texto), "nombra la ecuacion concreta que falla");

const marcados = await pagina.$$eval(".react-flow__node", (ns) =>
  ns.filter((n) => n.innerText.includes("⚠")).map((n) => n.innerText.split("\n")[0]));
console.log(`  nodos marcados con ⚠: ${marcados.join(", ") || "(ninguno)"}`);
comprobar(marcados.length > 0, "los nodos afectados se marcan en el diagrama");
await pagina.screenshot({ path: "verificacion-incoherente.png" });

console.log("\n=== Modo Reporte ===");
await clic("Reporte");
await esperar(800);
const reporte = await pagina.evaluate(() => document.body.innerText);
comprobar(reporte.includes("Corrientes") && reporte.includes("Equipos"), "tiene tablas de corrientes y equipos");
comprobar(["s1", "s2", "s3"].every((s) => reporte.includes(s)), "lista todas las corrientes");
comprobar(reporte.includes("no cumplen"), "incluye las ecuaciones violadas");
await pagina.screenshot({ path: "verificacion-reporte.png" });

await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
