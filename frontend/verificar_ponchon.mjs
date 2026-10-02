/**
 * Cierre de Ponchon-Savarit: el balance de energia debe DEJAR DE SER un
 * checkbox decorativo (antes se dibujaba pero solo lo leia la rama de
 * McCabe-Thiele) y la construccion entalpica debe dibujarse.
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();
import { prepararSimulacion } from "./preparar_simulacion.mjs";

const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });
const pagina = await navegador.newPage();
pagina.on("console", (m) => { if (m.type() === "error") console.log("   [consola]", m.text().slice(0, 160)); });
await prepararSimulacion(pagina);
await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });

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
  const ok = await pagina.evaluate((et, val) => {
    const filas = [...document.querySelectorAll("div")].filter(
      (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > input"));
    for (const f of filas) {
      if (f.querySelector("label").innerText.trim() === et) {
        const i = f.querySelector("input");
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, val);
        i.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      }
    }
    return false;
  }, etiqueta, valor);
  await esperar(150);
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

// Pasar la columna a Ponchon-Savarit
await clicNodo("col1");
await pagina.evaluate(() => {
  for (const sel of document.querySelectorAll("select")) {
    const o = [...sel.options].find((x) => x.value === "ponchon_savarit");
    if (o) {
      Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(sel, o.value);
      sel.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
  }
});
await esperar(500);

console.log("\n=== El balance de energia ya no es decorativo ===");
const varsConEnergia = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("col1"))?.innerText ?? "");
console.log("  col1 con balance:", varsConEnergia.replace(/\n/g, " | "));
comprobar(varsConEnergia.includes("Q_c"), "con el balance encendido aparecen las cargas (Q_c)");
comprobar(varsConEnergia.includes("QR_B"), "aparece QR_B, atado a Qc_D por colinealidad");

// apagar el checkbox
const apagado = await pagina.evaluate(() => {
  const c = [...document.querySelectorAll("input[type=checkbox]")][0];
  if (!c) return false;
  c.click();
  return true;
});
await esperar(600);
const varsSinEnergia = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("col1"))?.innerText ?? "");
comprobar(apagado && !varsSinEnergia.includes("Q_c"), "apagarlo las quita de verdad (antes no hacia nada)");
await pagina.evaluate(() => [...document.querySelectorAll("input[type=checkbox]")][0]?.click());
await esperar(600);

console.log("\n=== Resolver ===");
await clicNodo("s1"); await escribir("F", "100"); await escribir("x benzene", "0.5");
await clicNodo("s2"); await escribir("x benzene", "0.9");
await clicNodo("s3"); await escribir("x benzene", "0.1");
await clicNodo("col1");
comprobar(await escribir("Qc_D", "70000"), "se puede dar Qc_D");
await clic("Resolver");
await esperar(9000);

const texto = await pagina.evaluate(() => document.body.innerText);
comprobar(texto.includes("Resuelto por completo"), "resuelve por completo");
comprobar(!texto.includes("sin determinar") || !/\d+ sin determinar/.test(texto),
  "no quedan variables sin determinar (antes quedaban q y la T de alimentacion)");

console.log("\n=== La grafica de etapas ===");
await clic("Reporte");
await esperar(2500);
const rep = await pagina.evaluate(() => document.body.innerText);
comprobar(rep.includes("Construcción de Ponchon-Savarit"), "se dibuja la construcción de Ponchon-Savarit");
comprobar(rep.includes("líquido saturado") && rep.includes("vapor saturado"), "tiene las dos curvas de saturación");
comprobar(/Q\s*c\s*\/D|Qc\/D|kJ\/mol/.test(rep), "cita la carga del condensador en kJ/mol");
const svgs = await pagina.evaluate(() => document.querySelectorAll(".recharts-surface").length);
console.log("  gráficas dibujadas:", svgs);
comprobar(svgs >= 1, "hay al menos una gráfica renderizada");

// el reporte debe mostrar las cargas
comprobar(/Q_c/.test(rep) && /Q_R/.test(rep), "el reporte lista Q_c y Q_R");

await pagina.screenshot({ path: "verificacion-ponchon.png", fullPage: true });
await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
