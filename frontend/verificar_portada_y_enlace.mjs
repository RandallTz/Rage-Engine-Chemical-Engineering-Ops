/**
 * Verificacion en navegador de la Fase A: portada, fichas de metodo y
 * enlace compartible de extremo a extremo.
 *
 * Existe porque "compila sin errores" no comprueba nada de lo que
 * importa aqui: que la portada diga lo que tiene que decir, que las
 * fichas se abran, y -- sobre todo -- que un enlace generado en una
 * pestana reconstruya la simulacion en OTRA. Eso ultimo solo se puede
 * probar con un navegador de verdad: usa CompressionStream, el
 * portapapeles y el localStorage.
 *
 * Uso:  node verificar_portada_y_enlace.mjs [url]
 */
import puppeteer from "puppeteer-core";

const URL_BASE = process.argv[2] ?? "http://localhost:3100";
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const fallos = [];
const comprobar = (c, m, detalle = "") => {
  console.log(`  ${c ? "OK  " : "FALLA"} ${m}${detalle ? " -- " + detalle : ""}`);
  if (!c) fallos.push(m);
};

const navegador = await puppeteer.launch({
  executablePath: EDGE,
  headless: "new",
  args: ["--no-sandbox"],
});

try {
  // ----------------------------------------------------------- portada
  console.log(`\n=== ${URL_BASE}/ (portada) ===`);
  const p1 = await navegador.newPage();
  await p1.goto(`${URL_BASE}/`, { waitUntil: "networkidle0" });
  const textoPortada = await p1.evaluate(() => document.body.innerText);

  comprobar(/Simulador de procesos/i.test(textoPortada), "Dice qué es en el título");
  comprobar(/Qué hace/i.test(textoPortada), "Tiene la sección «Qué hace»");
  comprobar(/Qué NO hace/i.test(textoPortada), "Tiene la sección «Qué NO hace»");
  comprobar(/MESH/.test(textoPortada), "Declara el límite más importante (sin MESH)");
  comprobar(/0\.894/.test(textoPortada), "Cita una validación concreta y comprobable");

  const enlacesPortada = await p1.$$eval("a", (as) => as.map((a) => a.getAttribute("href")));
  comprobar(enlacesPortada.includes("/simulaciones"), "Lleva a las simulaciones en un clic");
  comprobar(enlacesPortada.includes("/columna"), "Lleva a la columna suelta");
  comprobar(
    enlacesPortada.some((h) => h && h.includes("12-validacion.md")),
    "Enlaza a la validación en docs/",
  );

  // --------------------------------------------- la columna sigue viva
  console.log(`\n=== ${URL_BASE}/columna (la herramienta que estaba en /) ===`);
  const p2 = await navegador.newPage();
  const resp = await p2.goto(`${URL_BASE}/columna`, { waitUntil: "networkidle0" });
  comprobar(resp.status() === 200, "La columna suelta responde en su ruta nueva",
    `HTTP ${resp.status()}`);
  const textoColumna = await p2.evaluate(() => document.body.innerText);
  comprobar(/Resolver/i.test(textoColumna), "Conserva el botón de resolver");

  // ------------------------------------------------- enlace compartible
  console.log(`\n=== enlace compartible, de una pestaña a otra ===`);
  const p3 = await navegador.newPage();
  await p3.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });

  // Se crea una simulación desde una plantilla, como haría el usuario.
  await p3.evaluate(() => {
    const botones = [...document.querySelectorAll("button")];
    botones.find((b) => /Crear y abrir/i.test(b.textContent))?.click();
  });
  await new Promise((r) => setTimeout(r, 1200));

  // Se vuelve a la lista y se pide el enlace. El portapapeles en headless
  // no es fiable, así que se llama al codificador por debajo igual que
  // hace el botón, y se comprueba el viaje completo.
  await p3.goto(`${URL_BASE}/simulaciones`, { waitUntil: "networkidle0" });
  const hayBoton = await p3.evaluate(() =>
    [...document.querySelectorAll("button")].some((b) => /Copiar enlace/i.test(b.textContent)),
  );
  comprobar(hayBoton, "El botón «Copiar enlace» existe en la lista");

  const guardado = await p3.evaluate(() => localStorage.getItem("simulador.simulaciones"));
  comprobar(!!guardado, "La simulación quedó guardada en el navegador");

  const simulacion = JSON.parse(guardado).lista[0];
  comprobar(!!simulacion, "Hay una simulación para compartir", simulacion?.nombre);

  // Se construye el fragmento con el MISMO código que la aplicación,
  // ejecutándolo dentro de la página (ahí sí hay CompressionStream).
  const fragmento = await p3.evaluate(async (sim) => {
    const json = JSON.stringify({
      n: sim.nombre, c: sim.componentes, m: sim.modelo,
      u: sim.unidades ?? {}, f: sim.flowsheet,
    });
    const bytes = new TextEncoder().encode(json);
    const flujo = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"));
    const comp = new Uint8Array(await new Response(flujo).arrayBuffer());
    let bin = "";
    for (const b of comp) bin += String.fromCharCode(b);
    return "1" + btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }, simulacion);
  comprobar(fragmento.length > 10, "Se generó el fragmento", `${fragmento.length} caracteres`);

  // OTRA pestaña, con su propio almacenamiento limpio: es el escenario
  // real de "se lo mando a alguien que nunca ha entrado".
  const contextoLimpio = await navegador.createBrowserContext();
  const p4 = await contextoLimpio.newPage();
  await p4.goto(`${URL_BASE}/simulaciones#s=${fragmento}`, { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 1500));

  const textoRecibido = await p4.evaluate(() => document.body.innerText);
  comprobar(/desde un enlace/i.test(textoRecibido), "Avisa de que llegó por enlace");

  const recibida = await p4.evaluate(() => {
    const g = localStorage.getItem("simulador.simulaciones");
    return g ? JSON.parse(g).lista[0] : null;
  });
  comprobar(!!recibida, "La simulación se reconstruyó en el navegador limpio");
  comprobar(recibida?.nombre === simulacion.nombre, "Conserva el nombre",
    `"${recibida?.nombre}"`);
  comprobar(
    JSON.stringify(recibida?.componentes) === JSON.stringify(simulacion.componentes),
    "Conserva los componentes",
    `${recibida?.componentes?.length} componentes`,
  );
  comprobar(
    JSON.stringify(recibida?.flowsheet?.nodes?.length) ===
      JSON.stringify(simulacion.flowsheet?.nodes?.length),
    "Conserva el diagrama",
    `${recibida?.flowsheet?.nodes?.length} nodos`,
  );
  comprobar(recibida?.id !== simulacion.id, "Entra como simulación NUEVA, no pisa la original");

  const hashTrasCargar = await p4.evaluate(() => window.location.hash);
  comprobar(hashTrasCargar === "", "Limpia el fragmento (recargar no duplica)");

  // ----------------------------------------------------- ficha de método
  console.log(`\n=== fichas de método ===`);
  const p5 = await navegador.newPage();
  await p5.goto(`${URL_BASE}/termodinamica/elv`, { waitUntil: "networkidle0" });
  const hayFicha = await p5.evaluate(() =>
    [...document.querySelectorAll("button")].some((b) => /Cómo se calcula esto/i.test(b.textContent)),
  );
  comprobar(hayFicha, "La ficha aparece en la página de ELV");

  await p5.evaluate(() => {
    [...document.querySelectorAll("button")]
      .find((b) => /Cómo se calcula esto/i.test(b.textContent))?.click();
  });
  await new Promise((r) => setTimeout(r, 400));
  const textoFicha = await p5.evaluate(() => document.body.innerText);
  comprobar(/Cuándo NO fiarse/i.test(textoFicha), "Al abrirla, muestra los límites primero");
  comprobar(/Qué da por cierto/i.test(textoFicha), "Muestra las suposiciones");
  const enlaceDoc = await p5.$$eval("a", (as) =>
    as.map((a) => a.getAttribute("href")).filter((h) => h && h.includes("03-termodinamica.md")),
  );
  comprobar(enlaceDoc.length > 0, "Enlaza al documento de la matemática");
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
