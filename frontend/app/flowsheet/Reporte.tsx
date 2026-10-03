"use client";

import type { Node } from "@xyflow/react";
import {
  DatosNodo,
  DatosOperacion,
  variablesDeCorriente,
  variablesDeOperacion,
  etiquetaVariable,
  estadoDe,
  valorDe,
  formatear,
  UNIDAD,
} from "./modelo";
import type { Inconsistencia } from "./PanelLateral";
import { desdeSI, molARepresentacionMasica, type Unidades } from "./unidades";
import { useState } from "react";
import {
  aCSV, aCSVAncho, descargar, alPortapapeles, nombreArchivo,
  type FilaExportada,
} from "./exportar";
import DiagramaColumna, { type DatosDiagramaColumna } from "../components/DiagramaColumna";
import GraficaELV from "../components/GraficaELV";
import DescargarGrafico from "../components/DescargarGrafico";

/**
 * Tabla de corrientes al estilo de un simulador de procesos: una columna
 * por corriente, una fila por variable. Es la vista que permite ver de
 * un golpe que pasa en TODO el diagrama, en vez de ir elemento por
 * elemento.
 */
export default function Reporte({
  nodos, componentes, dados, pool, inconsistencias, diagramas, unidades, masasMolares,
  nombreSimulacion = "simulacion",
}: {
  nodos: Node<DatosNodo>[];
  componentes: string[];
  dados: Record<string, string>;
  pool: Record<string, number>;
  inconsistencias: Inconsistencia[];
  diagramas: Record<string, DatosDiagramaColumna>;
  unidades: Unidades;
  masasMolares: Record<string, number>;
  nombreSimulacion?: string;
}) {
  const corrientes = nodos.filter((n) => n.data.clase === "corriente");
  const operaciones = nodos.filter((n) => n.data.clase === "operacion");
  const variablesCorriente = variablesDeCorriente(componentes.length);
  const clavesMalas = new Set(inconsistencias.map((i) => i.variable).filter(Boolean) as string[]);

  const celda = (clave: string, variable: string) => {
    const estado = estadoDe(clave, dados, pool);
    const crudo = valorDe(clave, dados, pool);
    // Lo dado ya esta en la unidad elegida; lo calculado llega en SI.
    const unidad = unidades.unidadDe(clave);
    const nodoId = clave.split(".")[0];
    const masica = variable === "F" && unidad?.magnitud === "flujo_masico";
    const mw = masasMolares[nodoId];
    const valor =
      crudo === null ? null
      : estado === "dado" ? crudo
      : masica ? (mw ? molARepresentacionMasica(crudo, mw, unidad!) : null)
      : desdeSI(crudo, unidad);
    const malo = clavesMalas.has(clave);
    const clase = malo
      ? "text-red-400 font-semibold"
      : estado === "dado"
      ? "text-emerald-300"
      : estado === "calculado"
      ? "text-sky-300"
      : "text-amber-500";
    return (
      <td key={clave} className={`border-b border-zinc-800 px-3 py-1 text-right font-mono text-xs ${clase}`}>
        {valor === null ? "falta" : formatear(valor, variable)}
        {valor !== null && unidad ? <span className="text-zinc-600"> {unidad.etiqueta}</span> : null}
        {malo && " ⚠"}
      </td>
    );
  };

  /**
   * Las filas que se exportan.
   *
   * Se construyen con la MISMA conversion de unidades que `celda`, y no con
   * una paralela: si se duplicara, la tabla y el CSV podrian decir cosas
   * distintas sobre el mismo numero, que es el peor fallo posible en una
   * herramienta cuyo trabajo es no equivocarse al transcribir.
   */
  function filasExportadas(): FilaExportada[] {
    const filas: FilaExportada[] = [];

    const anadir = (ambito: string, elemento: string, variable: string) => {
      const clave = `${elemento}.${variable}`;
      const estado = estadoDe(clave, dados, pool);
      const crudo = valorDe(clave, dados, pool);
      const unidad = unidades.unidadDe(clave);
      const masica = variable === "F" && unidad?.magnitud === "flujo_masico";
      const mw = masasMolares[elemento];
      const valor =
        crudo === null ? null
        : estado === "dado" ? crudo
        : masica ? (mw ? molARepresentacionMasica(crudo, mw, unidad!) : null)
        : desdeSI(crudo, unidad);
      filas.push({
        ambito, elemento, variable,
        etiqueta: etiquetaVariable(variable, componentes),
        valor,
        unidad: unidad?.etiqueta ?? UNIDAD[variable] ?? "",
        estado: clavesMalas.has(clave) ? "incompatible"
          : valor === null ? "sin determinar" : estado,
      });
    };

    for (const c of corrientes) {
      for (const v of variablesCorriente) anadir("corriente", c.id, v);
    }
    for (const op of operaciones) {
      for (const v of variablesDeOperacion(op.data as DatosOperacion)) {
        anadir("equipo", op.id, v);
      }
    }
    return filas;
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-4 py-4">
      <div className="mb-4 flex flex-wrap items-center gap-4 text-[11px]">
        <span className="text-zinc-400">Leyenda:</span>
        <span className="text-emerald-300">valor que diste</span>
        <span className="text-sky-300">valor calculado</span>
        <span className="text-amber-500">sin determinar</span>
        <span className="text-red-400">incompatible con las ecuaciones</span>
      </div>

      <Exportar filas={filasExportadas} nombreSimulacion={nombreSimulacion} />

      <h2 className="mb-2 text-sm font-semibold">Corrientes</h2>
      {corrientes.length === 0 ? (
        <p className="text-xs text-zinc-500">No hay corrientes en el diagrama.</p>
      ) : (
        <table className="mb-8 w-full border-collapse">
          <thead>
            <tr className="border-b border-zinc-700">
              <th className="px-3 py-1.5 text-left text-xs font-medium text-zinc-400">Variable</th>
              {corrientes.map((c) => (
                <th key={c.id} className="px-3 py-1.5 text-right text-xs font-semibold text-zinc-100">{c.id}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variablesCorriente.map((v) => (
              <tr key={v}>
                <td className="border-b border-zinc-800 px-3 py-1 text-xs text-zinc-400">
                  {etiquetaVariable(v, componentes)}
                </td>
                {corrientes.map((c) => celda(`${c.id}.${v}`, v))}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 className="mb-2 text-sm font-semibold">Equipos</h2>
      {operaciones.length === 0 ? (
        <p className="text-xs text-zinc-500">No hay equipos en el diagrama.</p>
      ) : (
        operaciones.map((op) => {
          const datos = op.data as DatosOperacion;
          const variables = variablesDeOperacion(datos);
          return (
            <div key={op.id} className="mb-4 rounded border border-zinc-800 bg-zinc-900 p-3">
              <div className="mb-2 flex items-baseline gap-3">
                <span className="text-sm font-semibold">{op.id}</span>
                <span className="text-[11px] uppercase tracking-wide text-zinc-500">
                  {datos.tipo}{datos.metodo ? ` · ${datos.metodo}` : ""}
                </span>
                <span className="text-[11px] text-zinc-500">P = {datos.P_sistema} Pa</span>
              </div>
              {variables.length === 0 ? (
                <p className="text-xs text-zinc-500">Sin variables propias (todo vive en sus corrientes).</p>
              ) : (
                <table className="w-full border-collapse">
                  <tbody>
                    {variables.map((v) => (
                      <tr key={v}>
                        <td className="border-b border-zinc-800 px-2 py-1 text-xs text-zinc-400">
                          {v}{unidades.etiquetaDe(v) ? <span className="text-zinc-600"> [{unidades.etiquetaDe(v)}]</span> : null}
                        </td>
                        {celda(`${op.id}.${v}`, v)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}

      <h2 className="mb-2 text-sm font-semibold">Gráficas</h2>
      {Object.keys(diagramas).length === 0 ? (
        <p className="mb-6 text-xs text-zinc-500">
          Las construcciones (McCabe-Thiele o Ponchon-Savarit) aparecen aquí cuando una columna queda resuelta.
        </p>
      ) : (
        <div className="mb-6 grid gap-4 xl:grid-cols-2">
          {Object.entries(diagramas).map(([nombre, datos]) => (
            <div key={nombre}>
              <div className="mb-1 text-xs text-zinc-400">{nombre}</div>
              <DescargarGrafico nombre={`${nombre}-${datos.tipo ?? "mccabe_thiele"}`}>
                <DiagramaColumna datos={datos} nombreLigero={componentes[0] ?? "ligero"} />
              </DescargarGrafico>
            </div>
          ))}
        </div>
      )}

      {componentes.length === 2 && (
        <div className="mb-6">
          <DescargarGrafico nombre={`elv-${componentes.join("-")}`}>
            <GraficaELV nombres={componentes} />
          </DescargarGrafico>
        </div>
      )}

      {inconsistencias.length > 0 && (
        <>
          <h2 className="mb-2 text-sm font-semibold text-red-300">Ecuaciones que tus datos no cumplen</h2>
          {inconsistencias.map((inc) => (
            <div key={inc.bloque + inc.variable} className="mb-2 rounded border border-red-800 bg-red-950/40 p-2 text-xs text-red-200">
              {inc.mensaje}
            </div>
          ))}
        </>
      )}
    </div>
  );
}


/**
 * Los botones de exportación.
 *
 * Tres formas y no una, porque sirven para cosas distintas:
 *
 *   - **ancho** es la tabla que se tiene delante, una columna por
 *     corriente. Es la que se pega en un informe.
 *   - **largo** es una fila por dato. Es la que una máquina quiere leer,
 *     sin huecos y con el estado de cada valor en su propia columna.
 *   - **portapapeles** es el camino corto: pegar en una hoja de cálculo sin
 *     pasar por un fichero en Descargas.
 *
 * Y el estado de cada valor viaja con el valor. Un número que diste y uno
 * que calculó el simulador se distinguen en la pantalla por el color, y en
 * una hoja de cálculo se volverían indistinguibles: van en una columna.
 */
function Exportar({
  filas, nombreSimulacion,
}: {
  filas: () => FilaExportada[];
  nombreSimulacion: string;
}) {
  const [aviso, setAviso] = useState<string | null>(null);

  const anunciar = (texto: string) => {
    setAviso(texto);
    window.setTimeout(() => setAviso(null), 2500);
  };

  const bajar = (sufijo: string, texto: string, cuantas: number) => {
    descargar(texto, nombreArchivo(nombreSimulacion, sufijo));
    anunciar(`${cuantas} fila(s) descargadas`);
  };

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">Exportar</span>
      <button
        onClick={() => {
          const f = filas();
          bajar("corrientes", aCSVAncho(f, "corriente"),
                f.filter((x) => x.ambito === "corriente").length);
        }}
        className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:border-emerald-500 hover:text-emerald-200"
        title="La tabla tal y como se ve: una columna por corriente, en las unidades elegidas."
      >
        corrientes (CSV)
      </button>
      <button
        onClick={() => {
          const f = filas();
          bajar("todo", aCSV(f), f.length);
        }}
        className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:border-emerald-500 hover:text-emerald-200"
        title="Una fila por dato, con su unidad y su estado (dado, calculado, sin determinar). Es el formato que una máquina quiere leer."
      >
        todo, fila por dato (CSV)
      </button>
      <button
        onClick={async () => {
          const ok = await alPortapapeles(aCSVAncho(filas(), "corriente"));
          anunciar(ok ? "copiado al portapapeles"
                      : "el navegador no dejó copiar; usa la descarga");
        }}
        className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:border-emerald-500 hover:text-emerald-200"
        title="Pega directamente en una hoja de cálculo, sin pasar por un fichero."
      >
        copiar
      </button>
      {aviso && <span className="text-[11px] text-emerald-400">{aviso}</span>}
      <span className="text-[10px] text-zinc-600">
        separador coma, decimales con punto, y las unidades que ves en la tabla
      </span>
    </div>
  );
}
