/**
 * Verificacion de la EXPORTACION de resultados.
 *
 * Dos mitades, y la primera no necesita navegador: la conversion a CSV es
 * logica pura y se comprueba llamandola, igual que `verificar_enlace.mjs`
 * hace con el enlace compartible. Lo que si necesita navegador es que el
 * boton exista, que el CSV que produce lleve los numeros de la tabla, y
 * que las unidades sean las que se ven en pantalla y no las del SI.
 *
 * Lo que mas importa comprobar aqui, y es facil de pasar por alto: que el
 * CSV y la tabla digan LO MISMO. Si la exportacion tuviera su propia
 * conversion de unidades, las dos podrian divergir, y una herramienta cuyo
 * trabajo es no equivocarse al transcribir habria introducido justo ese
 * error en su salida.
 *
 * Uso:  node verificar_exportar.mjs [url]
 */
import { lanzarNavegador, urlBase } from "./navegador.mjs";

const URL_BASE = urlBase();
const ATM = 101325;

const fallos = [];
const comprobar = (c, m, detalle = "") => {
  console.log(`  ${c ? "OK  " : "FALLA"} ${m}${detalle ? " -- " + detalle : ""}`);
  if (!c) fallos.push(m);
};
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

function simulacion(unidades = {}) {
  return {
    id: "sim_exp", nombre: "Informe de prueba",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: [
      { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
      { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
    ],
    modelo: "unifac_raoult", unidades,
    flowsheet: {
      nodes: [
        { id: "alim", type: "corriente", position: { x: 60, y: 200 }, data: { clase: "corriente" } },
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "mccabe_thiele",
            P_sistema: ATM, con_balance_energia: true,
          },
        },
        { id: "dest", type: "corriente", position: { x: 680, y: 80 }, data: { clase: "corriente" } },
        { id: "fondo", type: "corriente", position: { x: 680, y: 330 }, data: { clase: "corriente" } },
      ],
      edges: [
        { id: "e1", source: "alim", target: "col1", sourceHandle: null, targetHandle: "alimentacion" },
        { id: "e2", source: "col1", target: "dest", sourceHandle: "destilado", targetHandle: null },
        { id: "e3", source: "col1", target: "fondo", sourceHandle: "fondos", targetHandle: null },
      ],
      dados: {
        "alim.F": "100", "alim.P": String(ATM), "alim.x0": "0.5",
        "dest.x0": "0.95", "fondo.x0": "0.05",
        "col1.q": "1", "col1.R": "3",
      },
    },
  };
}

const navegador = await lanzarNavegador({ defaultViewport: { width: 1700, height: 1000 } });

try {
  const pagina = await navegador.newPage();
  const texto = () => pagina.evaluate(() => document.body.innerText);
  const pulsar = (patron) =>
    pagina.evaluate((re) => {
      const b = [...document.querySelectorAll("button")].find((x) => new RegExp(re, "i").test(x.textContent));
      if (!b || b.disabled) return false;
      b.click();
      return true;
    }, patron);

  const abrir = async (unidades) => {
    await pagina.goto(`${URL_BASE}/simulaciones`, { waitUntil: "domcontentloaded" });
    await pagina.evaluate((s) => {
      localStorage.setItem("simulador.simulaciones", JSON.stringify({ activa: s.id, lista: [s] }));
    }, simulacion(unidades));
    await pagina.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
    await esperar(900);
    await pulsar("^Resolver$");
    await pagina.waitForFunction(
      () => /Resuelto por completo|Quedan \d+ variables|Error/i.test(document.body.innerText),
      { timeout: 120000 },
    );
    await esperar(400);
    await pagina.evaluate(() => {
      [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Reporte")?.click();
    });
    await esperar(600);
  };

  /**
   * Se interceptan las descargas leyendo el href del <a> que `descargar`
   * crea, en vez de dejar que el navegador escriba un fichero: en headless
   * la carpeta de descargas es un detalle del entorno, y lo que se quiere
   * comprobar es el CONTENIDO.
   */
  const capturarCSV = async (patronBoton) => {
    await pagina.evaluate(() => {
      window.__csv = null;
      const original = HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click = function () {
        if (this.download && this.href.startsWith("blob:")) {
          window.__pendiente = fetch(this.href).then((r) => r.text()).then((t) => {
            window.__csv = t;
          });
          window.__nombre = this.download;
          return;
        }
        return original.call(this);
      };
    });
    await pulsar(patronBoton);
    await pagina.evaluate(async () => { if (window.__pendiente) await window.__pendiente; });
    await esperar(200);
    return pagina.evaluate(() => ({ csv: window.__csv, nombre: window.__nombre }));
  };

  // ================================================================
  console.log("\n=== 1. Los botones están en el informe ===");
  // ================================================================
  await abrir({});
  let t = await texto();
  comprobar(/Exportar/i.test(t), "Hay una sección de exportación");
  comprobar(/corrientes \(CSV\)/i.test(t) && /fila por dato/i.test(t) && /copiar/i.test(t),
    "Con las tres formas: ancho, largo y portapapeles");
  comprobar(/separador coma/i.test(t) && /unidades que ves/i.test(t),
    "Y dice el formato y en qué unidades sale");

  // ================================================================
  console.log("\n=== 2. El CSV ancho es la tabla que se ve ===");
  // ================================================================
  const ancho = await capturarCSV("corrientes \\(CSV\\)");
  comprobar(!!ancho.csv, "Se descarga algo", ancho.nombre ?? "");
  if (ancho.csv) {
    const lineas = ancho.csv.trim().split("\n");
    comprobar(lineas[0].startsWith("variable,unidad,"),
      "La cabecera lleva variable y unidad antes de las corrientes", lineas[0]);
    comprobar(lineas[0].includes("alim") && lineas[0].includes("dest") && lineas[0].includes("fondo"),
      "Y una columna por corriente, con su nombre");
    // El caudal de alimentación es un dato: 100 mol/s.
    const filaF = lineas.find((l) => l.startsWith("F,"));
    comprobar(!!filaF && /(^|,)100(\.0+)?(,|$)/.test(filaF.replace(/100\.000000000/, "100")),
      "El caudal dado aparece con su valor", (filaF ?? "").slice(0, 80));
    // La temperatura de burbuja de la alimentación la CALCULÓ el simulador:
    // 365.5157 K, el número que el proyecto compara bit a bit.
    const filaT = lineas.find((l) => l.startsWith("T,"));
    comprobar(!!filaT && /365\.51569/.test(filaT),
      "Y un valor calculado sale con precisión, no redondeado a la pantalla",
      (filaT ?? "").slice(0, 90));
    comprobar(!!filaT && !/365\.516(,|$)/.test(filaT),
      "La pantalla redondea a 3 decimales; el CSV no");
  }
  comprobar(/fila\(s\) descargadas/i.test(await texto()), "Y avisa de que descargó");

  // ================================================================
  console.log("\n=== 3. El CSV largo lleva el estado de cada valor ===");
  // ================================================================
  const largo = await capturarCSV("fila por dato");
  comprobar(!!largo.csv, "Se descarga algo", largo.nombre ?? "");
  if (largo.csv) {
    const lineas = largo.csv.trim().split("\n");
    comprobar(lineas[0] === "ambito,elemento,variable,etiqueta,valor,unidad,estado",
      "La cabecera es la esperada", lineas[0]);
    const dado = lineas.find((l) => l.startsWith("corriente,alim,F,"));
    const calculado = lineas.find((l) => l.startsWith("corriente,alim,T,"));
    comprobar(!!dado && dado.trim().endsWith("dado"),
      "Un valor que dio el usuario se marca 'dado'", (dado ?? "").slice(0, 70));
    comprobar(!!calculado && calculado.trim().endsWith("calculado"),
      "Y uno del simulador, 'calculado'", (calculado ?? "").slice(0, 70));
    comprobar(lineas.some((l) => l.startsWith("equipo,col1,")),
      "Los equipos también salen, con su ámbito");
    // Las etiquetas de las fracciones llevan el nombre del componente: sin
    // eso, "x0" no significa nada fuera de la aplicacion.
    comprobar(lineas.some((l) => /x benzene/.test(l)),
      "Y las fracciones llevan el nombre del componente, no solo x0",
      (lineas.find((l) => /x benzene/.test(l)) ?? "").slice(0, 70));
  }

  // ================================================================
  console.log("\n=== 4. Las unidades son las de la pantalla, no las del SI ===");
  // ================================================================
  // La decisión que de verdad importa: quien eligió kg/h quiere el CSV en
  // kg/h. Exportar SI "porque es lo correcto" obliga a reconvertir a mano.
  // Se elige kg/h SOLO para la alimentación, que es el caso interesante:
  // este simulador permite que cada corriente tenga su unidad, y entonces
  // una fila del formato ancho mezcla unidades.
  await abrir({ "alim.F": "kg/h" });
  const masico = await capturarCSV("corrientes \\(CSV\\)");
  if (masico.csv) {
    const filaF = masico.csv.trim().split("\n").find((l) => l.startsWith("F,"));
    comprobar(!!filaF && /kg\/h/.test(filaF),
      "La unidad elegida aparece en el CSV", (filaF ?? "").slice(0, 90));

    // Y aquí está lo que esta comprobación encontró. La fila MEZCLA
    // unidades: la alimentación en kg/h y los productos en mol/s, porque
    // la preferencia se guardó solo para `alim.F`. Una etiqueta única para
    // toda la fila diría kg/h sobre tres números de los que dos están en
    // mol/s: números correctos bajo una cabecera falsa, que es peor que un
    // número mal, porque un número mal se nota.
    comprobar(!!filaF && /varias \(en cada celda\)/.test(filaF),
      "Y si la fila mezcla unidades, lo DICE en vez de etiquetarla con una",
      (filaF ?? "").slice(0, 100));
    comprobar(!!filaF && /100\S* kg\/h/.test(filaF) && /mol\/s/.test(filaF),
      "Cada celda carga entonces su propia unidad",
      (filaF ?? "").slice(0, 100));

    // Y el número: 100 kg/h de benceno/tolueno 50/50 (MW mezcla 85.125)
    // son 0.32632 mol/s, así que cada producto se lleva la mitad.
    comprobar(!!filaF && /0\.16315/.test(filaF),
      "El núcleo convierte la masa a moles con la MW de la mezcla",
      "100 kg/h → 0.32632 mol/s → 0.16316 por producto");

    // Una fila que NO mezcla unidades sigue siendo puramente numérica: la
    // legibilidad del caso común no se sacrifica por el caso raro.
    const filaT = masico.csv.trim().split("\n").find((l) => l.startsWith("T,"));
    comprobar(!!filaT && /^T,K,[\d.,]+$/.test(filaT.trim()),
      "Y una fila homogénea conserva una sola unidad y celdas numéricas",
      (filaT ?? "").slice(0, 80));
  } else {
    comprobar(false, "La unidad elegida aparece en el CSV", "no se descargó nada");
  }

  // ================================================================
  console.log("\n=== 5. El nombre del archivo dice de qué simulación es ===");
  // ================================================================
  comprobar(/^Informe-de-prueba_corrientes_\d{8}-\d{4}\.csv$/.test(masico.nombre ?? ""),
    "Lleva el nombre de la simulación y un sello de tiempo", masico.nombre ?? "");
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
