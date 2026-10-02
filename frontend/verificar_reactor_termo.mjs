/**
 * Reactor CSTR dentro del flowsheet (debe resolver hacia adelante y
 * hacia atras, como el resto) y modulo de termodinamica.
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();

const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });
const pagina = await navegador.newPage();
pagina.on("console", (m) => { if (m.type() === "error") console.log("   [consola]", m.text().slice(0, 150)); });
pagina.on("pageerror", (e) => console.log("   [pageerror]", String(e).slice(0, 150)));

const texto = () => pagina.evaluate(() => document.body.innerText);
const clic = async (t, ms = 500) => {
  await pagina.evaluate((x) => [...document.querySelectorAll("button, a")]
    .find((z) => z.textContent.trim() === x)?.click(), t);
  await esperar(ms);
};
const clicNodo = async (t) => {
  await pagina.evaluate((x) => {
    [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith(x))
      ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }, t);
  await esperar(350);
};
const escribirPorEtiqueta = async (parcial, valor) => {
  return await pagina.evaluate((et, val) => {
    const filas = [...document.querySelectorAll("div")].filter(
      (d) => d.querySelector(":scope > label") && d.querySelector(":scope > div > input, :scope > input"));
    for (const f of filas) {
      if (f.querySelector("label").innerText.trim().includes(et)) {
        const i = f.querySelector("input");
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, val);
        i.dispatchEvent(new Event("input", { bubbles: true }));
        return true;
      }
    }
    return false;
  }, parcial, valor);
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
    const p1 = buscar(a, "source", b); const p2 = buscar(cc, "target", dd);
    return p1 && p2 ? { p1, p2 } : null;
  }, no, po, nd, pd);
  if (!c) return false;
  await pagina.mouse.move(c.p1.x, c.p1.y);
  await pagina.mouse.down();
  await pagina.mouse.move(c.p1.x - 20, c.p1.y + 10, { steps: 4 });
  await pagina.mouse.move(c.p2.x, c.p2.y, { steps: 15 });
  await esperar(120); await pagina.mouse.up(); await esperar(350);
  return true;
};

// ---- simulacion nueva, ternaria (MTBE)
console.log("=== Preparar una simulación ternaria ===");
await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });
await pagina.evaluate(() => {
  const i = document.querySelector('input[placeholder="Nombre (opcional)"]');
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, "Reactor MTBE");
  i.dispatchEvent(new Event("input", { bubbles: true }));
  [...document.querySelectorAll("button")].find((b) => b.innerText.includes("En blanco"))?.click();
});
await esperar(400);
await clic("Crear y abrir", 2200);

// componentes desde localStorage: mas fiable que pelear con el buscador
await pagina.evaluate(() => {
  const clave = "simulador.simulaciones";
  const a = JSON.parse(localStorage.getItem(clave));
  const s = a.lista.find((x) => x.id === a.activa);
  s.componentes = [
    { nombre: "isobutene", MW: 56.106 },
    { nombre: "methanol", MW: 32.042 },
    { nombre: "mtbe", MW: 88.148 },
  ];
  localStorage.setItem(clave, JSON.stringify(a));
});
await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
await esperar(1500);
let t = await texto();
comprobar(t.includes("isobutene") && t.includes("mtbe"), "la simulación tiene los 3 componentes");

console.log("\n=== El reactor CSTR existe en el catálogo ===");
comprobar(t.includes("Reactor CSTR"), "aparece «Reactor CSTR» entre los equipos");

await clic("+ Reactor CSTR", 700);
await clic("+ Corriente", 500); await clic("+ Corriente", 500);
const hayReactor = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].some((n) => n.innerText.startsWith("r1")));
comprobar(hayReactor, "se añade el reactor al lienzo");

comprobar(await conectar("s1", null, "r1", "entrada"), "se conecta la entrada");
comprobar(await conectar("r1", "salida", "s2", null), "se conecta la salida");

console.log("\n=== Configurar la reacción ===");
await clicNodo("r1");
// El editor de reaccion ya no es un campo de texto: cada componente
// tiene su papel (reactivo/producto/no entra) y su coeficiente.
const puestos = await pagina.evaluate(() => {
  const selects = [...document.querySelectorAll("select")].filter(
    (s) => [...s.options].some((o) => o.value === "reactivo"));
  const poner = (sel, v) => {
    const o = [...sel.options].find((x) => x.value === v);
    if (!o) return false;
    Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set.call(sel, v);
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };
  if (selects.length < 3) return 0;
  let n = 0;
  if (poner(selects[0], "reactivo")) n++;
  if (poner(selects[1], "reactivo")) n++;
  if (poner(selects[2], "producto")) n++;
  return n;
});
await esperar(500);
comprobar(puestos === 3, "se define la estequiometría con el editor por componente");
const ecuacionVisible = await pagina.evaluate(() => document.body.innerText);
console.log("  ecuación mostrada:", (ecuacionVisible.match(/\w+ \+ \w+ → \w+/) ?? ["(no)"])[0]);
comprobar(/→/.test(ecuacionVisible), "la ecuación de la reacción se muestra escrita");
await esperar(400);
const varsReactor = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("r1"))?.innerText ?? "");
console.log("  r1:", varsReactor.replace(/\n/g, " | "));
comprobar(varsReactor.includes("ξ") && varsReactor.includes("conversión"),
  "el reactor expone ξ y X con etiquetas legibles");
comprobar(!varsReactor.includes("NaN"),
  "ninguna variable sale como NaN (xi empieza por 'x' y se confundía con una fracción molar)");
comprobar(/\bV\b/.test(varsReactor), "y V, porque la cinética está activada");

console.log("\n=== Resolver hacia ADELANTE ===");
await clicNodo("s1");
await escribirPorEtiqueta("F", "100");
await escribirPorEtiqueta("x isobutene", "0.5");
await escribirPorEtiqueta("x methanol", "0.5");
await escribirPorEtiqueta("T", "340");
await escribirPorEtiqueta("P", "101325");
await clicNodo("r1");
await escribirPorEtiqueta("X", "0.4");
await escribirPorEtiqueta("T", "340");
await clic("Resolver", 8000);

t = await texto();
const s2 = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("s2"))?.innerText ?? "");
console.log("  s2:", s2.replace(/\n/g, " | ").slice(0, 130));
comprobar(/80\.000/.test(s2), "la salida sale 80 mol/s (100 con nu_tot=-1 y xi=20)");
comprobar(/0\.2500/.test(s2), "y x_MTBE = 0.2500");
if (!/80\.000/.test(s2)) console.log("   [diagnóstico]", t.slice(0, 500));

console.log("\n=== Módulo de termodinámica ===");
await pagina.goto(`${URL_BASE}/termodinamica`, { waitUntil: "networkidle0" });
await esperar(900);
t = await texto();
comprobar(t.includes("Curvas residuales"), "el índice ofrece curvas residuales");
comprobar(t.includes("Destilación reactiva"), "y destilación reactiva");
comprobar(t.includes("Equilibrio líquido–vapor"), "y el ELV de siempre");
comprobar(t.includes("isobutene"), "muestra la mezcla de la simulación abierta");

console.log("\n=== Curvas residuales (es el cálculo caro: puede tardar) ===");
await pagina.goto(`${URL_BASE}/termodinamica/residuales`, { waitUntil: "networkidle0" });
await esperar(700);
await pagina.evaluate(() => {
  const inputs = [...document.querySelectorAll("input")]
    .filter((i) => i.type !== "file" && i.type !== "checkbox");
  const set = (i, v) => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, v);
    i.dispatchEvent(new Event("input", { bubbles: true }));
  };
  if (inputs[1]) set(inputs[1], "8");   // menos curvas, para que el test no eternice
});
await esperar(300);
await clic("Calcular mapa", 1000);
for (let i = 0; i < 90; i++) {
  const txt = await texto();
  if (!txt.includes("Integrando…")) break;
  await esperar(1000);
}
t = await texto();
const rutas = await pagina.evaluate(() => document.querySelectorAll("svg path").length);
console.log("  trayectorias dibujadas (paths):", rutas);
comprobar(t.includes("Mapa de curvas residuales") || rutas > 5, "se dibuja el mapa ternario");
comprobar(!t.includes("No se pudo integrar ninguna"), "el mapa no sale vacío");

await pagina.screenshot({ path: "verificacion-termo.png", fullPage: true });
await navegador.close();
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
