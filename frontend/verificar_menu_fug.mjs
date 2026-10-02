/**
 * Las cinco cosas pedidas:
 *  1. menú de dos niveles (archivador arriba, simulación abajo)
 *  2. guardar/cargar JSON desde dentro de la simulación
 *  3. procesos ya armados que resuelven con un clic
 *  4. FUG en el flowsheet y métodos binarios bloqueados con >2 componentes
 *  5. líneas rectas en el diagrama
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();
import fs from "node:fs";
import path from "node:path";

const DESCARGAS = path.resolve("./_descargas_menu");
const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

fs.rmSync(DESCARGAS, { recursive: true, force: true });
fs.mkdirSync(DESCARGAS, { recursive: true });

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });
const pagina = await navegador.newPage();
const cdp = await pagina.createCDPSession();
await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DESCARGAS });
pagina.on("pageerror", (e) => console.log("   [pageerror]", String(e).slice(0, 140)));

const texto = () => pagina.evaluate(() => document.body.innerText);
const clic = async (t, ms = 600) => {
  await pagina.evaluate((x) => [...document.querySelectorAll("button, a")]
    .find((z) => z.textContent.trim() === x)?.click(), t);
  await esperar(ms);
};
const elegirPlantilla = async (fragmento) => {
  await pagina.evaluate((f) => {
    [...document.querySelectorAll("button")].find((b) => b.innerText.includes(f))?.click();
  }, fragmento);
  await esperar(300);
};

// ============================================== 3. procesos ya armados
const LISTAS = [
  { plantilla: "Columna McCabe-Thiele (lista)", espera: /N\s*=|9\.07/ },
  { plantilla: "Columna multicomponente FUG (lista)", espera: /11\.5|N/ },
  { plantilla: "Reactor CSTR (listo)", espera: /0\.400|X/ },
  { plantilla: "Reactor + columna en serie (listo)", espera: /45\.1|N/ },
];

for (const caso of LISTAS) {
  console.log(`\n=== Proceso listo: ${caso.plantilla} ===`);
  await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });
  await esperar(500);
  await elegirPlantilla(caso.plantilla);
  await clic("Crear y abrir", 3000);

  const nodos = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
  console.log(`   nodos en el lienzo: ${nodos}`);
  comprobar(nodos >= 3, "la plantilla trae el diagrama montado");

  // resolver SIN escribir nada
  await clic("Resolver", 12000);
  let t = await texto();
  for (let i = 0; i < 25 && t.includes("Resolviendo"); i++) { await esperar(1000); t = await texto(); }
  comprobar(t.includes("Resuelto por completo"),
    "resuelve de un clic, sin escribir ningún dato");
  if (!t.includes("Resuelto por completo")) {
    console.log("   [diagnóstico]", t.slice(0, 300).replace(/\n/g, " | "));
  }
}

// ============================================= 1. menú de dos niveles
console.log("\n=== Menú de dos niveles ===");
let t = await texto();
comprobar(t.includes("Mis simulaciones"), "arriba está el archivador de simulaciones");
const secciones = await pagina.evaluate(() =>
  [...document.querySelectorAll("a")].map((a) => a.textContent.trim()));
console.log("   enlaces visibles:", [...new Set(secciones)].filter(Boolean).slice(0, 10).join(" | "));
for (const s of ["Componentes", "Flowsheet", "Termodinámica"]) {
  comprobar(secciones.includes(s), `dentro de la simulación está «${s}»`);
}

// ======================================== 2. guardar / cargar JSON
console.log("\n=== Guardar y cargar JSON desde dentro de la simulación ===");
comprobar(t.includes("Guardar JSON"), "hay botón de guardar en la barra de la simulación");
comprobar(t.includes("Cargar JSON"), "y de cargar");
await pagina.evaluate(() => [...document.querySelectorAll("button")]
  .find((b) => b.textContent.includes("Guardar JSON"))?.click());
await esperar(2000);
const archivos = fs.readdirSync(DESCARGAS).filter((f) => f.endsWith(".json"));
console.log("   descargado:", archivos);
comprobar(archivos.length >= 1, "el archivo se descarga");
if (archivos.length) {
  const datos = JSON.parse(fs.readFileSync(path.join(DESCARGAS, archivos[0]), "utf-8"));
  const fs_ = datos.simulacion?.flowsheet;
  console.log(`   contiene: ${datos.simulacion?.componentes?.length} componentes, ` +
              `${fs_?.nodes?.length} nodos, ${fs_?.edges?.length} aristas, ` +
              `${Object.keys(fs_?.dados ?? {}).length} datos`);
  comprobar((fs_?.nodes ?? []).length >= 3 && Object.keys(fs_?.dados ?? {}).length > 0,
    "el JSON lleva el flowsheet COMPLETO con sus datos");

  const entrada = await pagina.$('input[type="file"]');
  await entrada.uploadFile(path.join(DESCARGAS, archivos[0]));
  await esperar(2500);
  t = await texto();
  comprobar(t.includes("cargado como simulación nueva"), "subirlo lo acepta como simulación nueva");
}

// ========================================= 4. FUG y guarda de métodos
console.log("\n=== FUG y bloqueo de métodos binarios con >2 componentes ===");
await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });
await esperar(500);
await elegirPlantilla("Columna multicomponente FUG (lista)");
await clic("Crear y abrir", 3000);
await pagina.evaluate(() => {
  [...document.querySelectorAll(".react-flow__node")].find((n) => n.innerText.startsWith("col1"))
    ?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
});
await esperar(600);

const opciones = await pagina.evaluate(() => {
  const sel = [...document.querySelectorAll("select")]
    .find((s) => [...s.options].some((o) => o.value === "fug"));
  if (!sel) return null;
  return { valor: sel.value, opciones: [...sel.options].map((o) => ({ v: o.value, txt: o.text, off: o.disabled })) };
});
console.log("   selector de método:", JSON.stringify(opciones?.opciones));
comprobar(opciones !== null, "el selector ofrece FUG");
comprobar(opciones?.valor === "fug", "la plantilla multicomponente viene en FUG");
const mt = opciones?.opciones.find((o) => o.v === "mccabe_thiele");
comprobar(mt?.off === true, "McCabe-Thiele queda deshabilitado con 4 componentes");
comprobar(/binario/.test(mt?.txt ?? ""), "y la opción dice POR QUÉ está deshabilitado");

t = await texto();
comprobar(t.includes("clave ligero") && t.includes("clave pesado"),
  "aparecen los selectores de componentes clave");
comprobar(t.includes("recup"), "y las recuperaciones como variables");

// ============================================= 5. líneas rectas
console.log("\n=== Líneas del diagrama ===");
const aristas = await pagina.evaluate(() =>
  [...document.querySelectorAll(".react-flow__edge-path")].map((p) => p.getAttribute("d")));
console.log("   ejemplo de trazado:", (aristas[0] ?? "").slice(0, 80));
comprobar(aristas.length > 0, "hay aristas dibujadas");
// Una Bezier usa comandos C/S; un trazado ortogonal usa L (y M).
const conCurvas = aristas.filter((d) => /[CS]/.test(d ?? "")).length;
console.log(`   aristas con curvas Bézier: ${conCurvas}/${aristas.length}`);
comprobar(conCurvas === 0, "ninguna arista usa curvas: son tramos rectos");
comprobar(aristas.every((d) => /L/.test(d ?? "")), "todas usan segmentos de recta (L)");

await pagina.screenshot({ path: "verificacion-menu.png", fullPage: true });
await navegador.close();
fs.rmSync(DESCARGAS, { recursive: true, force: true });
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
