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
}: {
  nodos: Node<DatosNodo>[];
  componentes: string[];
  dados: Record<string, string>;
  pool: Record<string, number>;
  inconsistencias: Inconsistencia[];
  diagramas: Record<string, DatosDiagramaColumna>;
  unidades: Unidades;
  masasMolares: Record<string, number>;
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

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-4 py-4">
      <div className="mb-4 flex flex-wrap items-center gap-4 text-[11px]">
        <span className="text-zinc-400">Leyenda:</span>
        <span className="text-emerald-300">valor que diste</span>
        <span className="text-sky-300">valor calculado</span>
        <span className="text-amber-500">sin determinar</span>
        <span className="text-red-400">incompatible con las ecuaciones</span>
      </div>

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
