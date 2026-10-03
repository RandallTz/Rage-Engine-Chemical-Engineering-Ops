/**
 * Sacar los resultados del simulador.
 *
 * Por que hacia falta. La tabla de corrientes se podia LEER pero no sacar:
 * una herramienta cuyo resultado no puede salir de ella no se usa en un
 * informe, y acaba usandose a mano, copiando numeros de la pantalla -- que
 * es exactamente donde se cometen los errores de transcripcion que este
 * proyecto se esfuerza en no cometer por dentro.
 *
 * Dos decisiones que no son obvias:
 *
 *   1. **Se exporta lo que se ve, en las unidades que se ven.** El nucleo
 *      trabaja en SI, pero quien pide la tabla la quiere como la tiene
 *      delante: si eligio kg/h, el CSV dice kg/h y lo pone en la cabecera.
 *      Exportar SI "porque es lo correcto" obligaria a reconvertir a mano,
 *      que es volver al problema.
 *
 *   2. **El estado de cada valor viaja con el valor.** Un numero dado por
 *      el usuario y uno calculado por el simulador no son lo mismo, y en
 *      una hoja de calculo se vuelven indistinguibles. Van en una columna
 *      aparte, no con colores que el CSV no puede llevar.
 *
 * El separador es la coma y los decimales el punto. Es lo que esperan
 * pandas, R y cualquier lectura programatica; una hoja de calculo con
 * configuracion regional europea pedira elegir el separador al importar,
 * que es un clic, mientras que un CSV con punto y coma no lo lee ninguna
 * herramienta sin configurarla.
 */

export interface FilaExportada {
  /** "corriente" o "equipo" */
  ambito: string;
  /** s1, col1, ... */
  elemento: string;
  /** F, T, x0, R, ... */
  variable: string;
  /** La etiqueta legible, con el nombre del componente si es una fracción */
  etiqueta: string;
  valor: number | null;
  unidad: string;
  /** "dado" | "calculado" | "sin determinar" | "incompatible" */
  estado: string;
}

/**
 * Un campo de CSV, escapado.
 *
 * Las comillas se duplican y el campo se entrecomilla solo si hace falta.
 * Entrecomillar todo seria mas simple pero ensucia la lectura a ojo, que
 * es la mitad del valor de un CSV.
 */
function campo(valor: string | number | null): string {
  if (valor === null || valor === undefined) return "";
  const texto = String(valor);
  if (/[",\n\r]/.test(texto)) return `"${texto.replace(/"/g, '""')}"`;
  return texto;
}

/**
 * El CSV completo.
 *
 * Los números van con `toPrecision(12)` y no con el formato de la
 * pantalla. La pantalla redondea a tres decimales para que se pueda leer;
 * un CSV se lee con una máquina, y redondear ahí perdería precisión que
 * el destino puede necesitar. Es el mismo criterio que usa el proyecto
 * para los residuos: mostrar poco, guardar todo.
 */
export function aCSV(filas: FilaExportada[]): string {
  const cabecera = ["ambito", "elemento", "variable", "etiqueta", "valor", "unidad", "estado"];
  const lineas = [cabecera.join(",")];
  for (const f of filas) {
    lineas.push([
      campo(f.ambito), campo(f.elemento), campo(f.variable), campo(f.etiqueta),
      campo(f.valor === null ? "" : Number(f.valor).toPrecision(12)),
      campo(f.unidad), campo(f.estado),
    ].join(","));
  }
  return lineas.join("\n") + "\n";
}

/**
 * La misma tabla en el formato ANCHO, que es como se mira: una columna por
 * corriente y una fila por variable.
 *
 * Existen las dos porque sirven para cosas distintas. El formato largo
 * (`aCSV`) es el que una máquina quiere -- una fila por dato, sin huecos --
 * y el ancho es el que una persona reconoce, porque es la tabla que tiene
 * delante. Ofrecer solo uno obliga a pivotar a mano.
 */
export function aCSVAncho(
  filas: FilaExportada[],
  ambito: string,
): string {
  const propias = filas.filter((f) => f.ambito === ambito);
  const elementos = [...new Set(propias.map((f) => f.elemento))];
  const variables = [...new Set(propias.map((f) => f.variable))];
  const indice = new Map(propias.map((f) => [`${f.elemento}|${f.variable}`, f]));

  const lineas = [["variable", "unidad", ...elementos].map(campo).join(",")];
  for (const v of variables) {
    const deLaFila = propias.filter((f) => f.variable === v);
    const etiqueta = deLaFila[0]?.etiqueta ?? v;

    // La unidad NO es de la variable, es de CADA corriente: este
    // simulador permite dar `s1.F` en kg/h y `s2.F` en mol/s a la vez, y
    // es una decision deliberada, no un descuido.
    //
    // La primera version de esta funcion ponia la unidad de la PRIMERA
    // corriente como etiqueta de toda la fila. El resultado era un CSV que
    // decia "F, kg/h, 100, 0.1632, 0.1632" cuando los dos ultimos estaban
    // en mol/s: numeros correctos bajo una cabecera falsa, que es peor que
    // un numero mal -- un numero mal se nota.
    const unidades = [...new Set(deLaFila.map((f) => f.unidad))];
    const homogenea = unidades.length <= 1;

    const celdas = elementos.map((e) => {
      const f = indice.get(`${e}|${v}`);
      if (!f || f.valor === null) return "";
      const numero = Number(f.valor).toPrecision(12);
      // Si la fila mezcla unidades, cada celda carga la suya. Se pierde la
      // comodidad de una columna puramente numerica, y se gana que el
      // dato no mienta; para lectura programatica esta el formato largo,
      // donde cada fila lleva su unidad por construccion.
      return homogenea || !f.unidad ? numero : `${numero} ${f.unidad}`;
    });

    const unidad = homogenea ? (unidades[0] ?? "") : "varias (en cada celda)";
    lineas.push([etiqueta, unidad, ...celdas].map(campo).join(","));
  }
  return lineas.join("\n") + "\n";
}

/**
 * Descarga un texto como fichero.
 *
 * `URL.revokeObjectURL` no es opcional: sin él, cada descarga deja el blob
 * entero retenido en memoria mientras la pestaña viva. Con una tabla
 * pequeña da igual; con un barrido de 40 puntos descargado varias veces,
 * no.
 */
export function descargar(texto: string, nombreArchivo: string) {
  const blob = new Blob([texto], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombreArchivo;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Al portapapeles, con la vuelta atrás que hace falta.
 *
 * `navigator.clipboard` no existe en contexto no seguro (http que no sea
 * localhost), que es justo donde puede acabar este simulador si alguien lo
 * sirve en una red interna. Sin el respaldo, el botón no haría nada y no
 * diría por qué.
 */
export async function alPortapapeles(texto: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(texto);
      return true;
    }
  } catch {
    /* se intenta el respaldo */
  }
  try {
    const area = document.createElement("textarea");
    area.value = texto;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}

/** Un nombre de archivo que no choca y que dice de qué simulación es. */
export function nombreArchivo(nombreSimulacion: string, sufijo: string): string {
  const limpio = (nombreSimulacion || "simulacion")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "simulacion";
  const ahora = new Date();
  const sello = [
    ahora.getFullYear(),
    String(ahora.getMonth() + 1).padStart(2, "0"),
    String(ahora.getDate()).padStart(2, "0"),
    "-",
    String(ahora.getHours()).padStart(2, "0"),
    String(ahora.getMinutes()).padStart(2, "0"),
  ].join("");
  return `${limpio}_${sufijo}_${sello}.csv`;
}
