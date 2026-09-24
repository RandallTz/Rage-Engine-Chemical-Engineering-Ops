/**
 * Verificacion real en navegador (Edge headless via puppeteer-core).
 * Existe porque varios bugs seguidos -- panel invisible por contraste,
 * canvas de altura cero -- solo eran detectables abriendo la pagina, y
 * "compila sin errores" no los veia.
 *
 * Uso:  node verificar_ui.mjs [url]
 */
import puppeteer from "puppeteer-core";
import { prepararSimulacion } from "./preparar_simulacion.mjs";

const URL_BASE = process.argv[2] ?? "http://localhost:3000";
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const fallos = [];
const avisos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await puppeteer.launch({
  executablePath: EDGE, headless: "new",
  args: ["--no-sandbox"], defaultViewport: { width: 1600, height: 950 },
});
const pagina = await navegador.newPage();
pagina.on("console", (m) => { if (m.type() === "error" || m.text().includes("[React Flow]")) avisos.push(m.text()); });
pagina.on("pageerror", (e) => avisos.push(`pageerror: ${e.message}`));

const clic = async (texto) => {
  await pagina.evaluate((t) => [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === t)?.click(), texto);
  await esperar(400);
};
const clicNodo = async (texto) => {
  await pagina.evaluate((t) => {
    [...document.querySelectorAll(".react-flow__node")].find((x) => x.innerText.startsWith(t))
      ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }, texto);
  await esperar(300);
};
const escribir = async (etiqueta, valor) => {
  const ok = await pagina.evaluate((et, val) => {
    const filas = [...document.querySelectorAll("div")].filter(
      (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > input"));
    for (const f of filas) {
      if (f.querySelector("label").innerText.trim() === et) {
        const input = f.querySelector("input");
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(input, val);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      }
    }
    return false;
  }, etiqueta, valor);
  if (!ok) avisos.push(`no se encontro el campo ${etiqueta}`);
  return ok;
};
/**
 * Conecta arrastrando de un handle de origen a uno de destino.
 * Ojo con los selectores: React Flow pone la POSICION en la clase
 * (handle-left / handle-right) y el papel en una clase suelta
 * (source / target). No existe ".react-flow__handle-source" -- usarlo
 * hacia que este helper no encontrara nada y el test diera un falso
 * fallo de "no se puede conectar".
 */
const conectar = async (nodoOrigen, puertoOrigen, nodoDestino, puertoDestino) => {
  const caja = await pagina.evaluate((no, po, nd, pd) => {
    const buscar = (id, papel, puerto) => {
      const nodo = [...document.querySelectorAll(".react-flow__node")].find((x) => x.innerText.startsWith(id));
      if (!nodo) return null;
      const h = (puerto && nodo.querySelector(`.react-flow__handle.${papel}[data-handleid="${puerto}"]`))
        || nodo.querySelector(`.react-flow__handle.${papel}`);
      if (!h) return null;
      const r = h.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    };
    const a = buscar(no, "source", po);
    const b = buscar(nd, "target", pd);
    return a && b ? { a, b } : null;
  }, nodoOrigen, puertoOrigen, nodoDestino, puertoDestino);
  if (!caja) { avisos.push(`no se encontraron los puertos ${nodoOrigen}->${nodoDestino}`); return false; }
  await pagina.mouse.move(caja.a.x, caja.a.y);
  await pagina.mouse.down();
  // Un movimiento corto primero: es lo que arranca la linea de conexion.
  await pagina.mouse.move(caja.a.x - 20, caja.a.y + 10, { steps: 4 });
  await pagina.mouse.move(caja.b.x, caja.b.y, { steps: 15 });
  await esperar(120);
  await pagina.mouse.up();
  await esperar(350);
  return true;
};

console.log(`\n=== ${URL_BASE}/flowsheet ===`);
await prepararSimulacion(pagina);
await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });

const caja = await pagina.$eval(".react-flow", (el) => {
  const r = el.getBoundingClientRect();
  return { ancho: Math.round(r.width), alto: Math.round(r.height) };
});
console.log(`  canvas: ${caja.ancho} x ${caja.alto} px`);
comprobar(caja.ancho > 400 && caja.alto > 300, "el canvas tiene ancho y alto reales");

// Una operacion ya NO trae corrientes: nace sola.
await clic("+ Columna");
let nodos = await pagina.$$eval(".react-flow__node", (ns) => ns.map((n) => n.innerText.split("\n")[0]));
console.log(`  tras + Columna: ${nodos.join(", ")}`);
comprobar(nodos.length === 1, "la operacion se agrega sola, sin corrientes automaticas");

// Las corrientes se agregan y conectan a mano.
await clic("+ Corriente");
await clic("+ Corriente");
await clic("+ Corriente");
nodos = await pagina.$$eval(".react-flow__node", (ns) => ns.map((n) => n.innerText.split("\n")[0]));
comprobar(nodos.length === 4, `hay 4 nodos tras agregar 3 corrientes (${nodos.join(", ")})`);

await conectar("s1", null, "col1", "alimentacion");
await conectar("col1", "destilado", "s2", null);
await conectar("col1", "fondos", "s3", null);
const aristas = await pagina.$$eval(".react-flow__edge", (es) => es.length);
comprobar(aristas === 3, `las 3 conexiones se hacen arrastrando (hay ${aristas})`);

// Unidades: cambiar T a grados Celsius.
await clicNodo("s1");
const cambioUnidad = await pagina.evaluate(() => {
  const filas = [...document.querySelectorAll("div")].filter(
    (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > select"));
  for (const f of filas) {
    if (f.querySelector("label").innerText.trim() === "T") {
      const sel = f.querySelector("select");
      const opcion = [...sel.options].find((o) => o.text === "°C");
      if (!opcion) return false;
      Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(sel, opcion.value);
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }
  }
  return false;
});
comprobar(cambioUnidad, "cada variable con dimension ofrece selector de unidades");

await escribir("F", "100");
await escribir("x benzene", "0.40");
await clicNodo("s2"); await escribir("x benzene", "0.95");
await clicNodo("s3"); await escribir("x benzene", "0.05");
await clicNodo("col1"); await escribir("q", "1"); await escribir("R", "3.06");

// Contador de grados de libertad en vivo, SIN pulsar Resolver.
await esperar(2500);
let barra = await pagina.evaluate(() => document.body.innerText);
console.log(`  grados de libertad en vivo: ${(barra.match(/GL = [^\u00b7]*\u00b7 [^\n]*/) ?? ["(no aparece)"])[0]}`);
comprobar(/GL = /.test(barra), "el contador de grados de libertad aparece sin resolver");

await clic("Resolver");
await esperar(5000);
barra = await pagina.evaluate(() => document.body.innerText);
comprobar(barra.includes("Resuelto por completo"), "el diagrama se resuelve por completo");

// La T de s1 debe mostrarse en °C (95.4 aprox), no en K (368.6).
const textoS1 = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("s1"))?.innerText ?? "");
console.log(`  s1 tras resolver: ${textoS1.replace(/\n/g, " | ")}`);
comprobar(/9[0-9]\.\d+ °C/.test(textoS1), "la temperatura calculada se muestra convertida a °C");

await pagina.screenshot({ path: "verificacion-resuelto.png" });

// Graficas dentro del reporte.
await clic("Reporte");
await esperar(3500);
const reporte = await pagina.evaluate(() => document.body.innerText);
comprobar(reporte.includes("Gráficas"), "el reporte tiene seccion de graficas");
comprobar(reporte.includes("McCabe-Thiele"), "el reporte incluye la construccion de McCabe-Thiele");
comprobar(reporte.includes("Equilibrio líquido-vapor"), "el reporte incluye el diagrama ELV");
const graficas = await pagina.$$eval(".recharts-wrapper", (g) => g.length);
console.log(`  graficas dibujadas: ${graficas}`);
comprobar(graficas >= 2, "se dibujan al menos dos graficas");
await pagina.screenshot({ path: "verificacion-reporte.png", fullPage: true });

await navegador.close();

const errores = avisos.filter((a) => a.includes("[React Flow]") || a.startsWith("pageerror"));
if (errores.length) {
  console.log(`\n  AVISOS (${errores.length}):`);
  console.log("   ", [...new Set(errores)].slice(0, 5).join("\n    "));
}
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
