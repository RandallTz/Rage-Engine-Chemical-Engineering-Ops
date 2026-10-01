/**
 * Simulación empaquetada dentro de un enlace.
 *
 * El problema que resuelve: hasta ahora una simulación vivía en el
 * localStorage del navegador y la única forma de moverla era descargar
 * un .simproc.json y enviarlo. Eso basta para llevártela a otra máquina,
 * pero NO para lo que de verdad hace falta en un curso: que un profesor
 * mande un enlace con un problema planteado y el alumno lo abra y lo
 * resuelva. Un archivo adjunto se pierde; un enlace se pega en cualquier
 * sitio.
 *
 * Decisiones, y por qué:
 *
 * 1. Va en el FRAGMENTO (#) y no en la query (?). El fragmento no se
 *    envía al servidor: no acaba en los registros de Vercel ni de
 *    Render. El diagrama es del usuario, no nuestro.
 *
 * 2. Todo el estado viaja en la URL, sin guardar nada en un servidor.
 *    Así no hace falta base de datos, funciona con el frontend estático,
 *    y un enlace nunca "caduca" porque no depende de que conservemos
 *    nada. El precio es que la URL es larga; ver LIMITE_URL.
 *
 * 3. Se comprime con deflate antes de codificar. Un flowsheet es JSON
 *    con muchas claves repetidas ("position", "type", "data"...), que es
 *    justo lo que mejor comprime: se queda en torno a un cuarto.
 *
 * 4. Lo que se manda es SOLO el planteamiento (componentes, modelo,
 *    diagrama y datos), nunca los resultados. Quien abra el enlace tiene
 *    que resolverlo con el mismo núcleo validado y ver los mismos
 *    números; mandar resultados precocinados permitiría enviar un enlace
 *    con cifras que el simulador no produce.
 */

import type { Simulacion } from "./SimulacionProvider";

/**
 * Tope práctico de longitud de URL. Los navegadores aguantan bastante
 * más, pero muchos clientes de correo y chats cortan los enlaces largos
 * en silencio -- y un enlace cortado es peor que no tener enlace, porque
 * falla en manos de otro sin que el que lo mandó se entere.
 */
export const LIMITE_URL = 8000;

const MARCA_COMPRIMIDO = "1";
const MARCA_PLANO = "0";

function aBase64Url(bytes: Uint8Array): string {
  let binario = "";
  for (let i = 0; i < bytes.length; i++) binario += String.fromCharCode(bytes[i]);
  return btoa(binario).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function deBase64Url(texto: string): Uint8Array {
  const binario = atob(texto.replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  return bytes;
}

async function pasarPor(bytes: Uint8Array, transformador: "cs" | "ds"): Promise<Uint8Array | null> {
  const Disponible =
    transformador === "cs"
      ? (globalThis as { CompressionStream?: unknown }).CompressionStream
      : (globalThis as { DecompressionStream?: unknown }).DecompressionStream;
  if (!Disponible) return null; // navegador antiguo: se sigue sin comprimir
  try {
    const flujo =
      transformador === "cs"
        ? new CompressionStream("deflate-raw")
        : new DecompressionStream("deflate-raw");
    const salida = new Blob([bytes as BlobPart]).stream().pipeThrough(flujo as never);
    return new Uint8Array(await new Response(salida).arrayBuffer());
  } catch {
    return null;
  }
}

/** Lo que de verdad viaja: el planteamiento, sin resultados ni metadatos locales. */
function planteamiento(s: Simulacion) {
  return {
    n: s.nombre,
    c: s.componentes,
    m: s.modelo,
    u: s.unidades ?? {},
    f: s.flowsheet,
  };
}

/** Devuelve el fragmento codificado (sin el "#s="). */
export async function codificar(s: Simulacion): Promise<string> {
  const json = JSON.stringify(planteamiento(s));
  const crudos = new TextEncoder().encode(json);
  const comprimidos = await pasarPor(crudos, "cs");
  return comprimidos
    ? MARCA_COMPRIMIDO + aBase64Url(comprimidos)
    : MARCA_PLANO + aBase64Url(crudos);
}

/**
 * Deshace lo anterior. Devuelve algo CRUDO a propósito: quien lo reciba
 * debe pasarlo por el mismo saneador que ya usa la importación de
 * archivos. Un enlace puede venir manipulado y no se puede confiar en él
 * más que en un archivo editado a mano.
 */
export async function decodificar(fragmento: string): Promise<unknown | null> {
  try {
    const marca = fragmento.slice(0, 1);
    const cuerpo = deBase64Url(fragmento.slice(1));
    const bytes = marca === MARCA_COMPRIMIDO ? await pasarPor(cuerpo, "ds") : cuerpo;
    if (!bytes) return null;
    const datos = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
    // Se devuelve con los nombres largos que entiende sanear().
    return {
      nombre: datos.n,
      componentes: datos.c,
      modelo: datos.m,
      unidades: datos.u,
      flowsheet: datos.f,
    };
  } catch {
    return null;
  }
}

/** URL completa lista para copiar, o el motivo por el que no se puede. */
export async function construirEnlace(
  s: Simulacion,
  base?: string,
): Promise<{ ok: true; url: string; largo: number } | { ok: false; error: string; largo: number }> {
  const raiz = base ?? (typeof window !== "undefined" ? window.location.origin : "");
  const url = `${raiz}/simulaciones#s=${await codificar(s)}`;
  if (url.length > LIMITE_URL) {
    return {
      ok: false,
      largo: url.length,
      error:
        `El diagrama es demasiado grande para caber en un enlace (${url.length} caracteres, ` +
        `el tope seguro son ${LIMITE_URL}). Muchos clientes de correo cortan los enlaces largos ` +
        `sin avisar. Descarga el archivo .simproc.json y envíalo adjunto.`,
    };
  }
  return { ok: true, url, largo: url.length };
}
