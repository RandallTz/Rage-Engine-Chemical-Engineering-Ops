/**
 * Comprueba el NUMERO de la conversion masica, no solo que la UI no se
 * queje. Benceno/tolueno 50/50 -> MW mezcla = 0.5*78.11 + 0.5*92.14 =
 * 85.125 g/mol. Entonces 30645 kg/h deben ser exactamente 100 mol/s:
 *   30645 kg/h / 3600 = 8.5125 kg/s = 8512.5 g/s
 *   8512.5 / 85.125 = 100.0 mol/s
 * Se verifica interceptando lo que el frontend manda al backend.
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
await pagina.setRequestInterception(true);
pagina.on("request", (peticion) => {
  if (peticion.url().includes("/diagrama/") && peticion.method() === "POST") {
    try { ultimoEnvio = JSON.parse(peticion.postData()); } catch { /* ignorar */ }
  }
  peticion.continue();
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

const enviado = ultimoEnvio?.valores?.["s1.F"];
console.log(`\n  escrito en la interfaz : 30645 kg/h`);
console.log(`  enviado al backend     : ${enviado} mol/s`);
console.log(`  esperado               : 100 mol/s`);
const ok = enviado !== undefined && Math.abs(enviado - 100) < 0.01;
console.log(ok ? "\n  OK: la conversion masica usa la masa molar de la mezcla\n"
               : "\n  FALLA: la conversion no da el valor esperado\n");

await navegador.close();
process.exit(ok ? 0 : 1);
