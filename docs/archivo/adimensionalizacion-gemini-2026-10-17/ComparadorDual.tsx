"use client";

import { useState } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";
import { clasificarFormulacion } from "./clasificadorFormulaciones";
import { auditarMallaNumerica } from "./analisisEstabilidadNumerica";
import { calcularSensibilidadParametrica } from "./analisisSensibilidad";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function ComparadorDual({
  formas,
  formaActualIndice,
}: {
  formas: FormulacionNucleo[];
  formaActualIndice: number;
}) {
  const [formaAIndice, setFormaAIndice] = useState(formaActualIndice);
  const [formaBIndice, setFormaBIndice] = useState(() => (formas.length > 1 ? (formaActualIndice === 0 ? 1 : 0) : 0));

  const formaA = formas[Math.min(formaAIndice, formas.length - 1)];
  const formaB = formas[Math.min(formaBIndice, formas.length - 1)];

  const clasifA = clasificarFormulacion(formaA, formaAIndice);
  const clasifB = clasificarFormulacion(formaB, formaBIndice);

  const audA = auditarMallaNumerica(formaA);
  const audB = auditarMallaNumerica(formaB);

  const sensA = calcularSensibilidadParametrica(formaA);

  return (
    <div className="space-y-6" aria-label="Comparador Dual y Matriz de Sensibilidad">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-zinc-900 border border-zinc-800 rounded-lg text-white">
        <div>
          <span className="text-xs uppercase tracking-wider text-emerald-400 font-semibold">
            Análisis Comparativo Asintótico Dual (Split-Screen)
          </span>
          <h3 className="text-lg font-bold text-zinc-100">Contraste Lado a Lado de Formulaciones Canónicas</h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Compara simultáneamente dos miembros del espacio asintótico para evaluar rigidez, esquemas numéricos y estabilidad.
          </p>
        </div>
      </div>

      {/* Grid de 2 columnas para el Split-Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Columna Forma A */}
        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <label htmlFor="select-forma-a" className="text-xs font-semibold text-zinc-400">
                Formulación A:
              </label>
              <select
                id="select-forma-a"
                value={formaAIndice}
                onChange={e => setFormaAIndice(Number(e.target.value))}
                className="bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1 text-xs text-zinc-100 focus:outline-none focus:border-emerald-500"
              >
                {formas.map((_, i) => (
                  <option key={i} value={i}>
                    Forma {i + 1}
                  </option>
                ))}
              </select>
            </div>
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-200">
              {clasifA.etiquetaCorta}
            </span>
          </div>

          <div className="space-y-2">
            <span className="text-xs text-zinc-400 block font-medium">Ecuaciones Diferenciales Canónicas:</span>
            <div className="space-y-2 bg-zinc-900/60 p-3 rounded border border-zinc-800">
              {formaA.ecuaciones.map((e, idx) => (
                <div key={idx} className="overflow-x-auto text-center py-1">
                  <FormulaLatex
                    bloque
                    latex={`${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`}
                    lectura={`Ecuación ${idx + 1}`}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Índice de Rigidez (S):</span>
              <strong className={audA.esRigido ? "text-amber-400 text-sm font-mono" : "text-emerald-400 text-sm font-mono"}>
                {audA.indiceRigidez.toFixed(1)}
              </strong>
              <small className="block text-zinc-400 text-[10px] mt-0.5">
                {audA.esRigido ? "Rígido (Stiff)" : "No rígido"}
              </small>
            </div>
            <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Péclet de celda:</span>
              <strong className={audA.criterioOscilacionSatisfecho ? "text-emerald-400 text-sm font-mono" : "text-rose-400 text-sm font-mono"}>
                {audA.pecletCelda.toFixed(2)}
              </strong>
              <small className="block text-zinc-400 text-[10px] mt-0.5">
                {audA.criterioOscilacionSatisfecho ? "Pe_Δξ ≤ 2 (Suave)" : "Pe_Δξ > 2 (Upwind)"}
              </small>
            </div>
          </div>

          <div className="p-2.5 bg-zinc-900/40 rounded border border-zinc-800 text-xs space-y-1">
            <span className="text-zinc-400 font-medium block">Integrador recomendado:</span>
            <p className="text-emerald-300 font-mono text-[11px]">{audA.integradorTemporalRecomendado}</p>
            <p className="text-zinc-400 text-[11px] mt-1">{clasifA.descripcionRecomendacion}</p>
          </div>
        </div>

        {/* Columna Forma B */}
        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <label htmlFor="select-forma-b" className="text-xs font-semibold text-zinc-400">
                Formulación B:
              </label>
              <select
                id="select-forma-b"
                value={formaBIndice}
                onChange={e => setFormaBIndice(Number(e.target.value))}
                className="bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1 text-xs text-zinc-100 focus:outline-none focus:border-sky-500"
              >
                {formas.map((_, i) => (
                  <option key={i} value={i}>
                    Forma {i + 1}
                  </option>
                ))}
              </select>
            </div>
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-200">
              {clasifB.etiquetaCorta}
            </span>
          </div>

          <div className="space-y-2">
            <span className="text-xs text-zinc-400 block font-medium">Ecuaciones Diferenciales Canónicas:</span>
            <div className="space-y-2 bg-zinc-900/60 p-3 rounded border border-zinc-800">
              {formaB.ecuaciones.map((e, idx) => (
                <div key={idx} className="overflow-x-auto text-center py-1">
                  <FormulaLatex
                    bloque
                    latex={`${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`}
                    lectura={`Ecuación ${idx + 1}`}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Índice de Rigidez (S):</span>
              <strong className={audB.esRigido ? "text-amber-400 text-sm font-mono" : "text-emerald-400 text-sm font-mono"}>
                {audB.indiceRigidez.toFixed(1)}
              </strong>
              <small className="block text-zinc-400 text-[10px] mt-0.5">
                {audB.esRigido ? "Rígido (Stiff)" : "No rígido"}
              </small>
            </div>
            <div className="p-2.5 rounded bg-zinc-900 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Péclet de celda:</span>
              <strong className={audB.criterioOscilacionSatisfecho ? "text-emerald-400 text-sm font-mono" : "text-rose-400 text-sm font-mono"}>
                {audB.pecletCelda.toFixed(2)}
              </strong>
              <small className="block text-zinc-400 text-[10px] mt-0.5">
                {audB.criterioOscilacionSatisfecho ? "Pe_Δξ ≤ 2 (Suave)" : "Pe_Δξ > 2 (Upwind)"}
              </small>
            </div>
          </div>

          <div className="p-2.5 bg-zinc-900/40 rounded border border-zinc-800 text-xs space-y-1">
            <span className="text-zinc-400 font-medium block">Integrador recomendado:</span>
            <p className="text-sky-300 font-mono text-[11px]">{audB.integradorTemporalRecomendado}</p>
            <p className="text-zinc-400 text-[11px] mt-1">{clasifB.descripcionRecomendacion}</p>
          </div>
        </div>
      </div>

      {/* Matriz de Sensibilidad Paramétrica Logarítmica */}
      <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-lg space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-2 border-b border-zinc-800">
          <div>
            <h4 className="text-sm font-bold text-amber-400">
              Matriz de Elasticidad y Sensibilidad Paramétrica Simbólica (S_ij)
            </h4>
            <p className="text-xs text-zinc-400 mt-0.5">
              Elasticidad analítica exacta: S_ij = ∂ ln(Π_i) / ∂ ln(p_j). Cuantifica el impacto porcentual sobre cada invariante ante variaciones en los parámetros físicos.
            </p>
          </div>
          <span className="text-xs font-mono bg-zinc-900 px-2.5 py-1 rounded border border-zinc-700 text-zinc-300">
            Pivote dominante global: <strong>{sensA.parametroMasSensibleGlobal}</strong>
          </span>
        </div>

        {sensA.grupos.length === 0 || sensA.parametrosUnicos.length === 0 ? (
          <p className="text-xs text-zinc-500 py-3 text-center">
            No se detectaron grupos con parámetros dimensionales libres en esta formulación.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/70 text-zinc-300">
                  <th className="p-2.5 font-semibold">Grupo Adimensional (Π_i)</th>
                  {sensA.parametrosUnicos.map(p => (
                    <th key={p} className="p-2.5 text-center font-mono font-semibold">
                      {p}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 font-mono">
                {sensA.grupos.map(g => (
                  <tr key={g.grupoId} className="hover:bg-zinc-900/30 transition-colors">
                    <td className="p-2.5 font-semibold text-zinc-200">
                      <span>{g.grupoId}</span>
                    </td>
                    {g.coeficientes.map(c => {
                      const e = c.elasticidad;
                      let bgClass = "text-zinc-600";
                      if (e > 0) bgClass = e >= 2 ? "bg-emerald-950/80 text-emerald-300 font-bold" : "bg-emerald-950/40 text-emerald-400";
                      else if (e < 0) bgClass = e <= -2 ? "bg-rose-950/80 text-rose-300 font-bold" : "bg-rose-950/40 text-rose-400";

                      return (
                        <td
                          key={c.parametroId}
                          className={`p-2.5 text-center border border-zinc-800/40 ${bgClass}`}
                          title={c.interpretacion}
                        >
                          {e > 0 ? `+${e}` : e}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="p-3 bg-zinc-900/40 rounded border border-zinc-800 text-xs text-zinc-300 leading-relaxed">
          <strong>Dictamen de Sensibilidad Física:</strong> {sensA.resumenFisico}
        </div>
      </div>
    </div>
  );
}
