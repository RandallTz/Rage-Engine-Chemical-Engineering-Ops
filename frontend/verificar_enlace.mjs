/**
 * Ida y vuelta del ENLACE COMPARTIBLE (app/components/enlaceCompartible.ts).
 *
 * A diferencia del resto de verificar_*.mjs, esta no abre un navegador:
 * la codificacion es logica pura y se puede probar directamente, que es
 * mas rapido y mas estricto. Lo que comprueba es que lo que sale del
 * enlace sea EXACTAMENTE lo que entro -- un enlace que pierde un decimal
 * o se come una unidad es peor que no tener enlace, porque falla en
 * manos de otro sin que quien lo mando se entere.
 *
 * Correr desde frontend/:
 *     node verificar_enlace.mjs
 */
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, renameSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// El modulo es TypeScript: se compila a un temporal y se importa. Asi la
// prueba corre sobre el MISMO fichero que usa la aplicacion, no sobre una
// copia que podria quedarse atras.
const salida = mkdtempSync(join(tmpdir(), "enlace-"));
// Se invoca el tsc instalado con el propio Node, sin pasar por npx: desde
// Node 18.20 lanzar un .cmd directamente da EINVAL en Windows, y asi la
// prueba corre igual en los tres sistemas.
try {
  execFileSync(
    process.execPath,
    ["node_modules/typescript/bin/tsc",
     "app/components/enlaceCompartible.ts", "--target", "es2022", "--module", "es2022",
     "--moduleResolution", "bundler", "--outDir", salida, "--skipLibCheck", "--noResolve"],
    { stdio: "pipe" },
  );
} catch {
  // tsc avisa (TS6142) de que el import de TIPO apunta a un .tsx sin --jsx,
  // y sale con codigo != 0 aunque SI genera el .js. El import es solo de
  // tipos, asi que se borra al compilar y no afecta. Se juzga por el
  // resultado: si el fichero esta, la compilacion sirvio.
}
const generado = join(salida, "enlaceCompartible.js");
if (!existsSync(generado)) {
  console.error("No se pudo compilar app/components/enlaceCompartible.ts");
  process.exit(1);
}
renameSync(generado, join(salida, "enlaceCompartible.mjs"));
const { codificar, decodificar, construirEnlace, LIMITE_URL } =
  await import(pathToFileURL(join(salida, "enlaceCompartible.mjs")).href);

let fallos = 0;
const check = (nombre, ok, detalle = "") => {
  console.log(`[${ok ? "OK " : "FALLA"}] ${nombre}${detalle ? " -- " + detalle : ""}`);
  if (!ok) fallos++;
};

// Una simulacion realista: reactor + columna encadenados, con nodos de
// react-flow como los que guarda de verdad el lienzo.
const nodos = [];
const aristas = [];
for (let i = 0; i < 8; i++) {
  nodos.push({
    id: `s${i}`,
    type: i % 3 === 0 ? "operacion" : "corriente",
    position: { x: 120 * i + 0.5, y: 80 * (i % 4) },
    measured: { width: 180, height: 64 },
    selected: false,
    data: {
      clase: i % 3 === 0 ? "operacion" : "corriente",
      tipo: "reactor_cstr",
      P_sistema: 101325,
      etiqueta: `Equipo ${i} — acción`,
    },
  });
  if (i) aristas.push({ id: `e${i}`, source: `s${i - 1}`, target: `s${i}`, type: "tuberia" });
}

const original = {
  id: "sim_local_1",
  nombre: "Reactor + columna (ñ, á, °C)",
  creada: "2026-10-01T10:00:00.000Z",
  modificada: "2026-10-01T10:00:00.000Z",
  componentes: [
    { nombre: "isobutene", formula: "C4H8", MW: 56.106, Tb: 266.25 },
    { nombre: "methanol", formula: "CH4O", MW: 32.042, Tb: 337.65 },
    { nombre: "mtbe", formula: "C5H12O", MW: 88.15, Tb: 328.35 },
  ],
  modelo: "unifac_raoult",
  unidades: { "s1.F": "kg/h", "s1.T": "degC", "r1.Q": "kW" },
  flowsheet: { nodes: nodos, edges: aristas, dados: { "s1.F": "100", "s1.T": "330", "r1.xi": "12" } },
};

const json = JSON.stringify(original);
const codificado = await codificar(original);
const vuelta = await decodificar(codificado);

check("1. La ida y vuelta devuelve algo", vuelta !== null);
check("2. El nombre sobrevive, con acentos y eñes",
  vuelta.nombre === original.nombre, `"${vuelta?.nombre}"`);
check("3. Los componentes sobreviven enteros",
  JSON.stringify(vuelta.componentes) === JSON.stringify(original.componentes));
check("4. Las unidades sobreviven",
  JSON.stringify(vuelta.unidades) === JSON.stringify(original.unidades));
check("5. El diagrama sobrevive entero (nodos, aristas y datos)",
  JSON.stringify(vuelta.flowsheet) === JSON.stringify(original.flowsheet),
  `${vuelta.flowsheet.nodes.length} nodos, ${vuelta.flowsheet.edges.length} aristas`);
check("6. Los decimales no se redondean",
  vuelta.flowsheet.nodes[1].position.x === 120.5);

// Lo que NO debe viajar
check("7. No viaja el id local (el enlace crea una simulación nueva)",
  vuelta.id === undefined);
check("8. No viajan los resultados: el enlace solo lleva el planteamiento",
  !JSON.stringify(vuelta).includes("resultado") && vuelta.pool === undefined);

const enlace = await construirEnlace(original, "https://ejemplo.app");
check("9. El enlace cabe en una URL", enlace.ok,
  `${enlace.largo} caracteres (tope ${LIMITE_URL})`);
check("10. Va en el fragmento, no en la query (no llega al servidor)",
  enlace.ok && enlace.url.includes("/simulaciones#s="));

console.log(`\nJSON crudo: ${json.length} caracteres`);
console.log(`Enlace:     ${enlace.largo} caracteres  (${(100 * enlace.largo / json.length).toFixed(0)} % del original)`);

// Entradas corruptas: un enlace manipulado no puede tumbar la aplicacion
for (const malo of ["", "1", "0", "1@@@no-es-base64@@@", "9zzzz", "1" + Buffer.from("no comprimido").toString("base64url")]) {
  const r = await decodificar(malo);
  check(`11. Enlace corrupto devuelve null sin reventar: ${JSON.stringify(malo.slice(0, 18))}`, r === null);
}

// Diagrama enorme: tiene que RECHAZARSE con motivo, no generar un enlace roto.
// OJO: no vale repetir el mismo nodo 400 veces para "hacerlo grande" --
// deflate se come la repeticion y 400 nodos iguales caben de sobra (medido:
// 3994 caracteres). Para ejercitar de verdad el tope hace falta contenido
// INCOMPRESIBLE, que es lo que simulan estas etiquetas aleatorias.
const azar = (n) => Array.from({ length: n }, () => Math.random().toString(36).slice(2, 10)).join("");
const enorme = { ...original, flowsheet: { ...original.flowsheet, nodes: Array.from({ length: 400 }, (_, i) => ({ ...nodos[0], id: `n${i}`, data: { ...nodos[0].data, etiqueta: azar(4) } })) } };
const r = await construirEnlace(enorme, "https://ejemplo.app");
check("12. Un diagrama demasiado grande se rechaza explicando por qué",
  !r.ok && r.error.includes(".simproc.json"), `${r.largo} caracteres`);

console.log("\n" + (fallos ? `FALLARON ${fallos}` : "TODO OK"));
process.exit(fallos ? 1 : 0);
