/**
 * Lo que pidio el usuario: "cada vez que cambio de panel se borra la
 * simulacion". Se comprueba que YA NO, que los componentes viven dentro
 * de la simulacion, y que se puede descargar y volver a subir.
 */
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import path from "node:path";

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const DESCARGAS = path.resolve("./_descargas_test");
const fallos = [];
const comprobar = (c, m) => { console.log(c ? `  OK   ${m}` : `  FALLA ${m}`); if (!c) fallos.push(m); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

fs.rmSync(DESCARGAS, { recursive: true, force: true });
fs.mkdirSync(DESCARGAS, { recursive: true });

const navegador = await puppeteer.launch({
  executablePath: EDGE, headless: "new",
  args: ["--no-sandbox"], defaultViewport: { width: 1700, height: 1000 },
});
const pagina = await navegador.newPage();
const cdp = await pagina.createCDPSession();
await cdp.send("Page.setDownloadBehavior", { behavior: "allow", downloadPath: DESCARGAS });
pagina.on("console", (m) => { if (m.type() === "error") console.log("   [consola]", m.text().slice(0, 150)); });

const clic = async (t, ms = 500) => {
  await pagina.evaluate((x) => [...document.querySelectorAll("button, a")]
    .find((z) => z.textContent.trim() === x)?.click(), t);
  await esperar(ms);
};
const texto = () => pagina.evaluate(() => document.body.innerText);

console.log("=== Crear una simulación ===");
await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "networkidle0" });
await pagina.evaluate(() => {
  const i = document.querySelector('input[placeholder="Nombre (opcional)"]');
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, "Caso de prueba");
  i.dispatchEvent(new Event("input", { bubbles: true }));
});
await esperar(200);
// plantilla "Columna binaria ya montada"
await pagina.evaluate(() => {
  [...document.querySelectorAll("button")].find((b) => b.innerText.includes("Columna binaria ya montada"))?.click();
});
await esperar(300);
await clic("Crear y abrir", 2500);

let t = await texto();
comprobar(t.includes("Caso de prueba"), "la simulación creada queda abierta y con su nombre en la barra");
const nodosTrasCrear = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
console.log("  nodos en el lienzo:", nodosTrasCrear);
comprobar(nodosTrasCrear === 4, "la plantilla trae la columna y sus tres corrientes ya conectadas");

console.log("\n=== Cambiar de panel NO debe borrarla (el bug reportado) ===");
await pagina.goto("http://localhost:3000/termodinamica", { waitUntil: "networkidle0" });
await esperar(600);
await pagina.goto("http://localhost:3000/configuracion", { waitUntil: "networkidle0" });
await esperar(600);
await pagina.goto("http://localhost:3000/flowsheet", { waitUntil: "networkidle0" });
await esperar(2000);
const nodosTrasNavegar = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
console.log("  nodos tras pasear por tres paneles:", nodosTrasNavegar);
comprobar(nodosTrasNavegar === 4, "el diagrama sigue ahí después de cambiar de panel");
t = await texto();
comprobar(t.includes("benzene") && t.includes("toluene"), "los componentes siguen siendo los de ESTA simulación");

console.log("\n=== Y tampoco al recargar del todo ===");
await pagina.reload({ waitUntil: "networkidle0" });
await esperar(2200);
const nodosTrasRecargar = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
comprobar(nodosTrasRecargar === 4, "sobrevive a recargar el navegador");

console.log("\n=== Dos simulaciones con componentes distintos ===");
await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "networkidle0" });
await pagina.evaluate(() => {
  const i = document.querySelector('input[placeholder="Nombre (opcional)"]');
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(i, "Segunda, en blanco");
  i.dispatchEvent(new Event("input", { bubbles: true }));
});
await esperar(200);
await pagina.evaluate(() => {
  [...document.querySelectorAll("button")].find((b) => b.innerText.includes("En blanco"))?.click();
});
await esperar(300);
await clic("Crear y abrir", 2500);
const nodosVacia = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
comprobar(nodosVacia === 0, "la simulación nueva arranca vacía, sin heredar la anterior");
t = await texto();
comprobar(t.includes("sin componentes"), "y sin componentes: son propios de cada simulación");

console.log("\n=== Volver a la primera la recupera intacta ===");
await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "networkidle0" });
await esperar(500);
await pagina.evaluate(() => {
  const fila = [...document.querySelectorAll("div")].find(
    (d) => d.innerText?.startsWith("Caso de prueba")
      && [...d.querySelectorAll("button")].some((b) => b.textContent.trim() === "Abrir"));
  [...(fila?.querySelectorAll("button") ?? [])].find((b) => b.textContent.trim() === "Abrir")?.click();
});
await esperar(2500);
const nodosVuelta = await pagina.evaluate(() => document.querySelectorAll(".react-flow__node").length);
comprobar(nodosVuelta === 4, "al reabrir la primera vuelve su diagrama completo");

console.log("\n=== Descargar y volver a subir ===");
await pagina.goto("http://localhost:3000/simulaciones", { waitUntil: "networkidle0" });
await esperar(500);
await pagina.evaluate(() => {
  const fila = [...document.querySelectorAll("div")].find(
    (d) => d.innerText?.startsWith("Caso de prueba")
      && [...d.querySelectorAll("button")].some((b) => b.textContent.trim() === "Descargar"));
  [...(fila?.querySelectorAll("button") ?? [])].find((b) => b.textContent.trim() === "Descargar")?.click();
});
await esperar(1800);
const archivos = fs.readdirSync(DESCARGAS).filter((f) => f.endsWith(".json"));
console.log("  descargado:", archivos);
comprobar(archivos.length === 1, "se descarga un archivo de simulación");

if (archivos.length) {
  const ruta = path.join(DESCARGAS, archivos[0]);
  const datos = JSON.parse(fs.readFileSync(ruta, "utf-8"));
  console.log("  formato:", datos.formato, "| componentes:", datos.simulacion?.componentes?.map((c) => c.nombre));
  comprobar(Array.isArray(datos.simulacion?.componentes) && datos.simulacion.componentes.length === 2,
    "el archivo lleva los componentes DENTRO de la simulación");
  comprobar((datos.simulacion?.flowsheet?.nodes ?? []).length === 4, "y también el diagrama completo");

  const entradas = await pagina.$$('input[type="file"]');
  const entrada = entradas[entradas.length - 1];
  await entrada.uploadFile(ruta);
  await esperar(2000);
  t = await texto();
  comprobar(t.includes("se cargó como una simulación nueva"), "subir el archivo lo acepta");
  const cuantas = await pagina.evaluate(() =>
    [...document.querySelectorAll("div")].filter((d) => d.innerText?.startsWith("Caso de prueba")).length);
  comprobar(cuantas >= 1, "la importada aparece en la lista sin pisar la original");
}

console.log("\n=== Un archivo que no es una simulación se rechaza ===");
const basura = path.join(DESCARGAS, "basura.json");
fs.writeFileSync(basura, '{"hola":"que tal"}');
const entradas2 = await pagina.$$('input[type="file"]');
const entrada2 = entradas2[entradas2.length - 1];
await entrada2.uploadFile(basura);
await esperar(1200);
t = await texto();
comprobar(t.includes("no parece una simulación"), "un JSON cualquiera se rechaza con un mensaje claro");

await pagina.screenshot({ path: "verificacion-simulaciones.png", fullPage: true });
await navegador.close();
fs.rmSync(DESCARGAS, { recursive: true, force: true });
console.log(fallos.length === 0 ? "\nTODO OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
