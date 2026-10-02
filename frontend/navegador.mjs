/**
 * Lanzamiento del navegador para las suites de verificacion.
 *
 * Por que existe. Las catorce suites llevaban la ruta de Edge escrita a
 * mano:
 *
 *     const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\...";
 *
 * Eso tiene dos consecuencias, y la segunda es la grave:
 *
 *   1. En otra maquina (otro idioma de Windows, Edge en "Program Files"
 *      sin el "(x86)", Linux, macOS) ninguna suite arranca, y el error no
 *      dice que haya que cambiar catorce ficheros.
 *   2. **En CI no se pueden correr.** Por eso el workflow ejecutaba UNA de
 *      las catorce -- la unica que no necesita navegador. Trece suites que
 *      comprueban que el numero correcto llega a la pantalla no se
 *      ejecutaban nunca automaticamente, que es tanto como no tenerlas.
 *
 * Aqui la ruta se resuelve: primero `NAVEGADOR_PRUEBAS` si esta puesta
 * (es lo que usa CI, donde el navegador lo instala una accion y la ruta
 * no se puede adivinar), y si no, la primera de una lista de sitios
 * habituales por sistema operativo.
 *
 * El error, cuando no hay ninguno, dice los sitios donde se buscó y cómo
 * arreglarlo. Un "Browser was not found at the configured executablePath"
 * con una ruta sola no deja claro si falta el navegador o si la ruta esta
 * mal escrita.
 */
import { existsSync } from "node:fs";
import { platform } from "node:process";
import puppeteer from "puppeteer-core";

const CANDIDATOS = {
  win32: [
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  ],
  linux: [
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/microsoft-edge",
    "/snap/bin/chromium",
  ],
  darwin: [
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ],
};

/** La ruta del navegador, o un error que dice qué hacer. */
export function rutaNavegador() {
  const delEntorno = process.env.NAVEGADOR_PRUEBAS;
  if (delEntorno) {
    if (!existsSync(delEntorno)) {
      throw new Error(
        `NAVEGADOR_PRUEBAS apunta a "${delEntorno}", que no existe. ` +
        "Corrige la variable o quítala para que se busque en los sitios habituales.",
      );
    }
    return delEntorno;
  }

  const lista = CANDIDATOS[platform] ?? [];
  const encontrada = lista.find((r) => existsSync(r));
  if (encontrada) return encontrada;

  throw new Error(
    `No se encontró un navegador con el que correr las pruebas en ${platform}.\n` +
    "Se buscó en:\n" + lista.map((r) => `  - ${r}`).join("\n") +
    "\n\nPon la ruta en la variable NAVEGADOR_PRUEBAS, por ejemplo:\n" +
    '  NAVEGADOR_PRUEBAS="/usr/bin/chromium" node verificar_ui.mjs',
  );
}

/**
 * La URL contra la que se verifica.
 *
 * Orden: el argumento de la linea de ordenes, luego `URL_PRUEBAS`, y por
 * ultimo localhost:3000. El argumento va primero porque es lo mas
 * explicito: quien lo escribe lo esta diciendo para esta ejecucion
 * concreta.
 */
export function urlBase(porDefecto = "http://localhost:3000") {
  return process.argv[2] ?? process.env.URL_PRUEBAS ?? porDefecto;
}

/**
 * Lanza el navegador con los ajustes que necesitan estas suites.
 *
 * `--no-sandbox` hace falta dentro de un contenedor de CI, donde el
 * sandbox de Chromium no puede crear su propio espacio de nombres de
 * usuario. No es un ajuste de comodidad: sin el, en CI no arranca.
 */
export async function lanzarNavegador(opciones = {}) {
  return puppeteer.launch({
    executablePath: rutaNavegador(),
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
    ...opciones,
  });
}
