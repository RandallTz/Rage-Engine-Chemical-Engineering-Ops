/**
 * Corre TODAS las suites de verificacion de la interfaz y devuelve un
 * codigo de salida real. Es el equivalente de run_tests.py para el lado
 * del navegador.
 *
 * Por que existe. Las suites siempre fueron buenas por dentro, pero habia
 * que lanzarlas a mano una a una, y hasta ahora se leia el resultado
 * buscando "TODO OK" en la salida. Eso falla de la peor forma posible:
 * cada suite termina con un mensaje distinto ("TODO OK", "TODAS LAS
 * PLANTILLAS OK", "OK: la conversion..."), asi que un `grep` da por buena
 * una suite que en realidad acaba de reventar con otra frase. Todas
 * devuelven `process.exit(0|1)` correctamente, asi que **el codigo de
 * salida es lo unico que hay que mirar.**
 *
 * Las suites NO son todas iguales en lo que necesitan, y eso se declara
 * aqui en vez de descubrirse por un fallo raro:
 *
 *   - `logica`   : nada. Es codificacion y decodificacion pura.
 *   - `api`      : la API viva. Habla con ella directamente, sin navegador.
 *   - `navegador`: la API Y el frontend servido, y un navegador.
 *
 * Uso:
 *   node verificar_todo.mjs                  # todas
 *   node verificar_todo.mjs diseno unidades  # solo las que encajen
 *   SALTAR_NAVEGADOR=1 node verificar_todo.mjs
 *
 * Variables: URL_PRUEBAS (frontend), NEXT_PUBLIC_API_URL (API),
 * NAVEGADOR_PRUEBAS (ruta del navegador). Ver navegador.mjs.
 */
import { spawn } from "node:child_process";
import { readdirSync } from "node:fs";

const NECESITA = {
  "verificar_enlace.mjs": "logica",
  "verificar_plantillas.mjs": "api",
};

const URL_FRONTEND = process.env.URL_PRUEBAS ?? "http://localhost:3000";
const URL_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

const filtros = process.argv.slice(2);
const suites = readdirSync(".")
  .filter((f) => /^verificar_.*\.mjs$/.test(f) && f !== "verificar_todo.mjs")
  .filter((f) => filtros.length === 0 || filtros.some((x) => f.toLowerCase().includes(x.toLowerCase())))
  .sort();

if (suites.length === 0) {
  console.error(`Ninguna suite encaja con: ${filtros.join(", ")}`);
  process.exit(2);
}

/** ¿Responde? Se comprueba antes de correr nada, para no fallar 12 veces por lo mismo. */
async function responde(url) {
  try {
    const c = new AbortController();
    const t = setTimeout(() => c.abort(), 4000);
    const r = await fetch(url, { signal: c.signal });
    clearTimeout(t);
    return r.status < 500;
  } catch {
    return false;
  }
}

const necesidades = new Set(suites.map((f) => NECESITA[f] ?? "navegador"));
const apiViva = necesidades.has("api") || necesidades.has("navegador")
  ? await responde(`${URL_API}/salud`) : true;
const frontViva = necesidades.has("navegador") ? await responde(URL_FRONTEND) : true;

console.log("=".repeat(78));
console.log(`VERIFICACION DE LA INTERFAZ -- ${suites.length} suites`);
console.log(`  API      ${URL_API}  ${apiViva ? "viva" : "NO RESPONDE"}`);
console.log(`  frontend ${URL_FRONTEND}  ${frontViva ? "vivo" : "NO RESPONDE"}`);
console.log("=".repeat(78));

// Un servidor caido no es "fallan las suites", es que no se han podido
// correr. Decirlo asi, y antes, ahorra leer doce rastros de pila
// identicos para acabar descubriendo que faltaba levantar uvicorn.
if (!apiViva || !frontViva) {
  console.error(
    "\nFaltan servidores. Desde la raíz del repositorio:\n" +
    (!apiViva ? `  python -m uvicorn backend.main:app --port ${new URL(URL_API).port || 80} --reload\n` : "") +
    (!frontViva ? "  cd frontend && npm run dev\n" : "") +
    "\nO salta las que necesitan navegador:  SALTAR_NAVEGADOR=1 node verificar_todo.mjs",
  );
  process.exit(2);
}

const correr = (archivo) =>
  new Promise((resolver) => {
    const inicio = Date.now();
    const hijo = spawn(process.execPath, [archivo, URL_FRONTEND], {
      stdio: ["ignore", "pipe", "pipe"],
      env: process.env,
    });
    let salida = "";
    hijo.stdout.on("data", (d) => (salida += d));
    hijo.stderr.on("data", (d) => (salida += d));
    hijo.on("close", (codigo) =>
      resolver({ codigo, salida, segundos: (Date.now() - inicio) / 1000 }));
  });

const fallidas = [];
const saltadas = [];
let total = 0;

for (const archivo of suites) {
  const necesita = NECESITA[archivo] ?? "navegador";
  if (necesita === "navegador" && process.env.SALTAR_NAVEGADOR) {
    console.log(`[SALTA] ${archivo.padEnd(38)} necesita navegador`);
    saltadas.push(archivo);
    continue;
  }
  const { codigo, salida, segundos } = await correr(archivo);
  total += segundos;
  const marca = codigo === 0 ? "OK   " : "FALLA";
  console.log(`[${marca}] ${archivo.padEnd(38)} ${segundos.toFixed(1)}s`);
  if (codigo !== 0) {
    fallidas.push(archivo);
    // Solo la salida de las que fallan: la de las que pasan es ruido, y
    // esconder la de las que fallan obligaria a volver a correrlas.
    console.log(salida.split("\n").map((l) => "        " + l).join("\n"));
  }
}

console.log("-".repeat(78));
if (saltadas.length) console.log(`${saltadas.length} saltada(s) por SALTAR_NAVEGADOR.`);
if (fallidas.length) {
  console.log(`FALLARON ${fallidas.length} de ${suites.length - saltadas.length} en ${total.toFixed(1)}s: ` +
    fallidas.join(", "));
  process.exit(1);
}
console.log(`TODO VERDE: ${suites.length - saltadas.length} suites en ${total.toFixed(1)}s`);
