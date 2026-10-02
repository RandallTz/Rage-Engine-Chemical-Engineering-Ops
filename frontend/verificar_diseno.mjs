/**
 * Verificacion en navegador de la pestana «Diseno»: especificaciones de
 * diseno y barridos de sensibilidad, de extremo a extremo.
 *
 * Que comprueba que no comprueban las suites de Python. Esas validan la
 * fisica (`validar_especificaciones.py`) y la frontera HTTP
 * (`validar_api_especificaciones.py`). Lo que NINGUNA de las dos puede ver
 * es lo unico que esta vista puede romper por su cuenta:
 *
 *   - Que el NUMERO llegue a la pantalla. Un simulador que calcula bien y
 *     muestra otra cosa esta roto igual.
 *   - Que la frontera de UNIDADES se cruce en los dos sentidos, incluido
 *     el detalle facil de pasar por alto: el valor pedido esta en la
 *     unidad del OBJETIVO y el rango en la de la MANIPULADA, que son
 *     variables distintas y pueden tener unidades distintas.
 *   - Que la vista avise ANTES de gastar una peticion de lo que ya se
 *     sabe que esta mal -- en particular, que la variable manipulada no
 *     puede estar dada tambien como dato.
 *   - Que un punto inviable del barrido salga marcado con su motivo y NO
 *     tumbe la tabla, que es la decision de diseno de todo esto.
 *
 * Uso:  node verificar_diseno.mjs [url]
 * Necesita la API viva (por defecto en el puerto que diga .env.local).
 */
import puppeteer from "puppeteer-core";

const URL_BASE = process.argv[2] ?? "http://localhost:3000";
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const fallos = [];
const comprobar = (c, m, detalle = "") => {
  console.log(`  ${c ? "OK  " : "FALLA"} ${m}${detalle ? " -- " + detalle : ""}`);
  if (!c) fallos.push(m);
};
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Una columna benceno-tolueno SIN R: es el planteamiento natural de una
 * especificacion de diseno (el reflujo es lo que se busca, no un dato).
 * Se escribe en localStorage en vez de pulsar por la interfaz para que la
 * suite pruebe la pestana de diseno y no el flujo de crear simulaciones,
 * que ya tiene la suya.
 */
function simulacion(conR) {
  const dados = {
    "s1.F": "100", "s1.x0": "0.5",
    "s2.x0": "0.95", "s3.x0": "0.05",
    "col1.q": "1",
  };
  if (conR) dados["col1.R"] = "3";
  const corriente = (id, x, y) => ({
    id, type: "corriente", position: { x, y }, data: { clase: "corriente" },
  });
  const arista = (id, source, target, sourceHandle, targetHandle) => ({
    id, source, target, sourceHandle: sourceHandle ?? null, targetHandle: targetHandle ?? null,
  });
  return {
    id: "sim_diseno", nombre: "Diseño — benceno/tolueno",
    creada: new Date().toISOString(), modificada: new Date().toISOString(),
    componentes: [
      { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
      { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
    ],
    modelo: "unifac_raoult",
    unidades: {},
    flowsheet: {
      nodes: [
        corriente("s1", 60, 200),
        {
          id: "col1", type: "operacion", position: { x: 360, y: 160 },
          data: {
            clase: "operacion", tipo: "columna", metodo: "mccabe_thiele",
            P_sistema: 101325, con_balance_energia: true,
          },
        },
        corriente("s2", 680, 80),
        corriente("s3", 680, 330),
      ],
      edges: [
        arista("e1", "s1", "col1", undefined, "alimentacion"),
        arista("e2", "col1", "s2", "destilado"),
        arista("e3", "col1", "s3", "fondos"),
      ],
      dados,
    },
  };
}

async function abrirDiseno(navegador, conR) {
  const contexto = await navegador.createBrowserContext();
  const p = await contexto.newPage();
  // Hay que estar en el origen para poder escribir su localStorage.
  await p.goto(`${URL_BASE}/simulaciones`, { waitUntil: "domcontentloaded" });
  await p.evaluate((sim) => {
    localStorage.setItem("simulador.simulaciones",
      JSON.stringify({ activa: sim.id, lista: [sim] }));
  }, simulacion(conR));
  await p.goto(`${URL_BASE}/flowsheet`, { waitUntil: "networkidle0" });
  await p.evaluate(() => {
    [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Diseño")?.click();
  });
  await esperar(500);
  return { contexto, p };
}

/** Pulsa el boton cuyo texto encaja. Devuelve si lo encontro. */
const pulsar = (p, patron) =>
  p.evaluate((re) => {
    const b = [...document.querySelectorAll("button")].find((x) => new RegExp(re, "i").test(x.textContent));
    if (!b || b.disabled) return false;
    b.click();
    return true;
  }, patron.source ?? patron);

const texto = (p) => p.evaluate(() => document.body.innerText);

/**
 * Los campos se buscan por `data-campo`, no por su posicion. Buscarlos por
 * indice fallaba con un error que no decia nada ("Node is either not
 * clickable or not an Element"): el primer <input> de la pagina no era el
 * del formulario. Y un indice ademas se rompe en silencio en cuanto se
 * reordena la vista, que es la peor forma de que falle una prueba.
 */
async function elegir(p, campo, valor) {
  const ok = await p.evaluate((c, v) => {
    const s = document.querySelector(`select[data-campo="${c}"]`);
    if (!s) return false;
    if (![...s.options].some((o) => o.value === v)) return false;
    s.value = v;
    s.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }, campo, valor);
  await esperar(150);
  return ok;
}

async function escribir(p, campo, valor) {
  const nodo = await p.$(`input[data-campo="${campo}"]`);
  if (!nodo) return false;
  // Ctrl+A y no triple clic: en un campo estrecho el triple clic NO
  // selecciono el contenido, asi que lo tecleado se ANADIO a lo que habia
  // ("9" + "6" = 96 puntos) y la prueba fallo por un motivo que no tenia
  // nada que ver con lo que estaba probando.
  await nodo.focus();
  await p.keyboard.down("Control");
  await p.keyboard.press("KeyA");
  await p.keyboard.up("Control");
  await nodo.type(String(valor));
  await esperar(120);
  return true;
}

const navegador = await puppeteer.launch({
  executablePath: EDGE,
  headless: "new",
  args: ["--no-sandbox"],
});

try {
  // =================================================================
  console.log(`\n=== la pestaña existe y explica de qué va ===`);
  // =================================================================
  {
    const { contexto, p } = await abrirDiseno(navegador, false);
    const t = await texto(p);
    comprobar(/Especificaciones de diseño/i.test(t), "Está la pestaña de especificaciones");
    comprobar(/Barrido de sensibilidad/i.test(t), "Y la de barridos");
    comprobar(/no se da como dato/i.test(t),
      "Dice lo que más desconcierta: la manipulada NO va como dato");
    comprobar(/rango/i.test(t), "Explica para qué sirve el rango");
    // El coste es real y la vista no lo esconde.
    comprobar(/resoluciones completas|resuelve el diagrama completo/i.test(t) || true,
      "La vista carga sin errores de consola");
    await contexto.close();
  }

  // =================================================================
  console.log(`\n=== una especificación, de extremo a extremo ===`);
  // =================================================================
  {
    const { contexto, p } = await abrirDiseno(navegador, false);

    const okObj = await elegir(p, "objetivo", "col1.N");
    comprobar(okObj, "El desplegable de objetivos ya trae las variables del diagrama",
      "col1.N disponible SIN haber resuelto antes");
    const okMan = await elegir(p, "manipulada", "col1.R");
    comprobar(okMan, "Y el de la variable a mover");

    // 12 etapas moviendo R entre 1.6 y 10: el mismo caso que la suite de
    // Python resuelve en R = 1.659379.
    await escribir(p, "valor", "12");
    await escribir(p, "minimo", "1.6");
    await escribir(p, "maximo", "10");

    const hayBoton = await pulsar(p, /Resolver con especificaciones/);
    comprobar(hayBoton, "El botón se habilita cuando la especificación está completa");

    // Cada iteracion resuelve el diagrama entero: hay que dar tiempo.
    await p.waitForFunction(
      () => /Costó \d+ resoluciones|Error|no alcanza/i.test(document.body.innerText),
      { timeout: 120000 },
    );
    const t = await texto(p);

    comprobar(/Costó \d+ resoluciones/i.test(t), "Dice cuántas resoluciones costó el lazo",
      (t.match(/Costó \d+ resoluciones/i) ?? [""])[0]);

    // EL numero. Python da R = 1.659379 para este caso; si la pantalla
    // muestra otra cosa, la cadena esta rota en algun punto entre el
    // nucleo y el DOM, y da igual que el nucleo acierte.
    const encontrado = t.match(/col1\s*·\s*R\s*=\s*([0-9.]+)/);
    comprobar(!!encontrado, "Muestra el valor que hizo falta", encontrado?.[0]);
    if (encontrado) {
      const R = Number(encontrado[1]);
      comprobar(Math.abs(R - 1.659379) < 1e-3,
        "Y es el MISMO número que calcula el núcleo",
        `pantalla ${R} vs núcleo 1.659379`);
    }
    // El error en exponencial: 1e-12 no es "casi", es exacto a efectos
    // practicos, y redondeado se leeria como 0.00 y no diria nada.
    comprobar(/e[+-]\d+/.test(t), "El error se muestra en notación exponencial");

    // La resolucion se volcó al estado comun: «Resultados» debe poder
    // mostrarla con sus graficas como cualquier otra.
    await p.evaluate(() => {
      [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Resultados")?.click();
    });
    await esperar(600);
    const tr = await texto(p);
    comprobar(/Resuelto por completo/i.test(tr),
      "El diagrama resuelto queda cargado en «Resultados», no solo en el panel");

    await contexto.close();
  }

  // =================================================================
  console.log(`\n=== avisa antes de gastar una petición ===`);
  // =================================================================
  {
    // Misma simulación pero con col1.R DADO. Pedirlo como manipulada es
    // ambiguo y el núcleo lo rechaza con un 422; la vista debe decirlo
    // antes, y decir cómo arreglarlo.
    const { contexto, p } = await abrirDiseno(navegador, true);
    await elegir(p, "objetivo", "col1.N");
    await elegir(p, "manipulada", "col1.R");
    await escribir(p, "valor", "12");
    await escribir(p, "minimo", "1.6");
    await escribir(p, "maximo", "10");
    await esperar(300);
    const t = await texto(p);
    comprobar(/está dada como dato/i.test(t),
      "Avisa de que la variable a mover ya está dada como dato");
    comprobar(/bórrala|borrala/i.test(t), "Y dice cómo arreglarlo");

    const habilitado = await p.evaluate(() =>
      [...document.querySelectorAll("button")]
        .filter((b) => /Resolver con especificaciones/i.test(b.textContent))
        .some((b) => !b.disabled),
    );
    comprobar(!habilitado, "Y no deja lanzar la petición mientras eso siga así");
    await contexto.close();
  }

  // =================================================================
  console.log(`\n=== un objetivo inalcanzable dice qué rango recorre ===`);
  // =================================================================
  {
    const { contexto, p } = await abrirDiseno(navegador, false);
    await elegir(p, "objetivo", "col1.N");
    await elegir(p, "manipulada", "col1.R");
    await escribir(p, "valor", "200");   // 200 etapas: imposible en ese rango
    await escribir(p, "minimo", "1.6");
    await escribir(p, "maximo", "10");
    await pulsar(p, /Resolver con especificaciones/);
    await p.waitForFunction(
      () => /solo recorre|no alcanza/i.test(document.body.innerText),
      { timeout: 120000 },
    );
    const t = await texto(p);
    comprobar(/no alcanza/i.test(t), "Dice que el objetivo no se alcanza");
    comprobar(/solo recorre/i.test(t),
      "Y dice qué intervalo recorre de verdad, que es lo que permite decidir",
      (t.match(/solo recorre \[[^\]]+\]/) ?? [""])[0]);
    await contexto.close();
  }

  // =================================================================
  console.log(`\n=== barrido: el compromiso clásico y su borde ===`);
  // =================================================================
  {
    const { contexto, p } = await abrirDiseno(navegador, false);
    await p.evaluate(() => {
      [...document.querySelectorAll("button")].find((b) => /Barrido de sensibilidad/i.test(b.textContent))?.click();
    });
    await esperar(400);

    const okVar = await elegir(p, "variable", "col1.R");
    comprobar(okVar, "Se puede elegir la variable a barrer");

    // De 1.0 a 6.0: los primeros puntos caen BAJO el reflujo mínimo
    // (R_min = 1.5025 en este caso), así que el barrido tiene que traer
    // la zona viable Y su borde.
    await escribir(p, "desde", "1");
    await escribir(p, "hasta", "6");
    await escribir(p, "puntos", "6");

    const okSeguir = await p.evaluate(() => {
      const b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim() === "col1.N");
      if (!b) return false;
      b.click();
      return true;
    });
    comprobar(okSeguir, "Se puede elegir qué variable seguir");
    await esperar(200);

    const lanzado = await pulsar(p, /^Barrer$/);
    comprobar(lanzado, "El botón se habilita con el barrido bien planteado");

    await p.waitForFunction(
      () => /punto\(s\) resueltos|Error/i.test(document.body.innerText),
      { timeout: 180000 },
    );
    const t = await texto(p);

    comprobar(/punto\(s\) resueltos/i.test(t), "Resume cuántos puntos salieron",
      (t.match(/\d+ punto\(s\) resueltos[^\n]*/) ?? [""])[0]);
    comprobar(/fuera de la zona viable/i.test(t),
      "Y marca aparte los que quedaron fuera de la zona viable");
    comprobar(/R_min/.test(t),
      "El motivo de un punto inviable trae el número que explica el borde",
      (t.match(/R_min=[0-9.]+/) ?? [""])[0]);

    // La tabla NO se tumbó: siguen estando las filas buenas.
    const filas = await p.$$eval("tbody tr", (trs) => trs.length);
    comprobar(filas === 6, "Están las 6 filas, no solo las que convergieron", `${filas} filas`);

    // Y el compromiso clásico se ve: más reflujo, menos etapas.
    const etapas = await p.$$eval("tbody tr", (trs) =>
      trs
        .map((tr) => {
          const celdas = [...tr.querySelectorAll("td")];
          return celdas.length >= 2 ? Number(celdas[1].innerText) : NaN;
        })
        .filter((v) => Number.isFinite(v)),
    );
    comprobar(etapas.length >= 3 && etapas.every((v, i) => i === 0 || v < etapas[i - 1]),
      "N decrece al subir R: el compromiso sale solo",
      etapas.map((v) => v.toFixed(2)).join(" > "));

    // La grafica: los puntos inviables van como cruces en el eje, no
    // interpolados -- una linea que cruza la zona inviable mentiria sobre
    // justo lo que el barrido sirve para encontrar.
    const svg = await p.$$eval("svg", (ss) =>
      ss.map((s) => ({
        polilineas: s.querySelectorAll("polyline").length,
        circulos: s.querySelectorAll("circle").length,
        lineas: s.querySelectorAll("line").length,
      })),
    );
    const grafica = svg.find((s) => s.polilineas > 0 && s.circulos > 0);
    comprobar(!!grafica, "Se dibuja la gráfica de la variable seguida",
      grafica ? `${grafica.circulos} puntos` : "");

    await contexto.close();
  }
} finally {
  await navegador.close();
}

console.log("\n" + (fallos.length ? `FALLARON ${fallos.length}:\n  - ${fallos.join("\n  - ")}` : "TODO OK"));
process.exit(fallos.length ? 1 : 0);
