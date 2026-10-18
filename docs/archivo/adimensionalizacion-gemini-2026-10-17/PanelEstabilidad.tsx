"use client";

import { useMemo } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import { derivarEstabilidadLineal } from "./analisisEstabilidad";
import FormulaLatex from "../flowsheet/FormulaLatex";
import PanelBifurcaciones from "./PanelBifurcaciones";

export default function PanelEstabilidad({ f }: { f: FormulacionNucleo }) {
  const est = useMemo(() => derivarEstabilidadLineal(f), [f]);

  // Coordenadas para renderizar el gráfico SVG de dispersión
  const puntosSvg = useMemo(() => {
    const ancho = 460;
    const alto = 180;
    const pad = 30;
    const pts = est.puntosCurvaDispersion;
    if (pts.length === 0) {
      return {
        d: "",
        yCero: 90,
        ancho,
        alto,
        pad,
        minSigma: -1,
        maxSigma: 1,
        maxK: 1
      };
    }
    const minK = 0;
    const maxK = Math.max(...pts.map(p => p.k), 1);
    const sigmas = pts.map(p => p.sigmaReal);
    const minSigma = Math.min(...sigmas, -2);
    const maxSigma = Math.max(...sigmas, 1);
    const rangoSigma = maxSigma - minSigma || 1;

    const coords = pts.map(p => {
      const x = pad + (p.k / maxK) * (ancho - 2 * pad);
      const y = alto - pad - ((p.sigmaReal - minSigma) / rangoSigma) * (alto - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const yCero = alto - pad - ((0 - minSigma) / rangoSigma) * (alto - 2 * pad);

    return {
      d: `M ${coords.join(" L ")}`,
      yCero,
      ancho,
      alto,
      pad,
      minSigma,
      maxSigma,
      maxK
    };
  }, [est]);

  return (
    <div className="adim-stability-panel rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-xl my-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 font-mono">
            Análisis Espectral de Estabilidad
          </span>
          <h3 className="text-lg font-medium text-zinc-100 flex items-center gap-2">
            Relación de Dispersión Adimensional <FormulaLatex latex="\sigma(k)" lectura="sigma de k" /> y Bifurcaciones
          </h3>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-semibold ${
            est.tipoBifurcacion === "inestabilidad_espacial"
              ? "bg-amber-950/80 border border-amber-600 text-amber-300"
              : est.tipoBifurcacion === "hopf_oscilatorio"
              ? "bg-purple-950/80 border border-purple-600 text-purple-300"
              : "bg-emerald-950/80 border border-emerald-600 text-emerald-300"
          }`}
        >
          {est.tipoBifurcacion === "inestabilidad_espacial"
            ? "Inestabilidad Espacial de Onda Finita"
            : est.tipoBifurcacion === "hopf_oscilatorio"
            ? "Bifurcación de Hopf (Oscilaciones)"
            : "Estado Homogéneo Asintóticamente Estable"}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        {/* Lado izquierdo: Formulaciones matemáticas */}
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
              Operadores Jacobiano y Difusivo en el Estado Base
            </h4>
            <div className="space-y-2 overflow-x-auto">
              <FormulaLatex bloque latex={est.matrizJacobianaLatex} lectura="Matriz Jacobiana" />
              <FormulaLatex bloque latex={est.matrizDifusionLatex} lectura="Matriz de Difusión" />
            </div>
          </div>

          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
              Ecuación Característica de Dispersión
            </h4>
            <div className="overflow-x-auto text-sm">
              <FormulaLatex bloque latex={est.relacionDispersionLatex} lectura="Relación de dispersión" />
            </div>
            {est.dimensionSistema > 1 && (
              <div className="mt-3 space-y-1 text-xs text-zinc-400">
                <FormulaLatex bloque latex={est.trazaLatex} lectura="Traza de M(k)" />
                <FormulaLatex bloque latex={est.determinanteLatex} lectura="Determinante de M(k)" />
              </div>
            )}
          </div>

          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
              Criterios de Estabilidad de Lyapunov
            </h4>
            <div className="space-y-2 text-xs text-zinc-300">
              <p><FormulaLatex latex={est.criterioHomogeneoLai} lectura="Criterio homogéneo" /></p>
              <p><FormulaLatex latex={est.criterioInestabilidadEspacialLatex} lectura="Criterio inestabilidad" /></p>
              {est.esInestable && (
                <p className="text-amber-400 font-medium">
                  Modo crítico de máxima amplificación: <FormulaLatex latex={est.numeroOndaCriticoLatex} lectura="Número de onda crítico" />
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Lado derecho: Curva espectral de dispersión y diagnóstico físico */}
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider flex items-center gap-1">
                Espectro de Dispersión <FormulaLatex latex="\operatorname{Re}(\sigma)" lectura="parte real de sigma" /> vs. <FormulaLatex latex="k" lectura="k" />
              </h4>
              <span className="text-[11px] text-zinc-500 font-mono">k_max = {puntosSvg.maxK}</span>
            </div>

            {/* SVG Curva de dispersión */}
            <div className="w-full flex justify-center bg-zinc-950/80 rounded-md border border-zinc-800/50 p-2">
              <svg
                viewBox={`0 0 ${puntosSvg.ancho} ${puntosSvg.alto}`}
                className="w-full h-auto max-h-[190px]"
              >
                {/* Ejes */}
                <line
                  x1={puntosSvg.pad}
                  y1={puntosSvg.yCero}
                  x2={puntosSvg.ancho - puntosSvg.pad}
                  y2={puntosSvg.yCero}
                  stroke="#ef4444"
                  strokeWidth="1.2"
                  strokeDasharray="4 3"
                />
                <text
                  x={puntosSvg.ancho - puntosSvg.pad + 4}
                  y={puntosSvg.yCero + 3}
                  fill="#ef4444"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  σ = 0
                </text>

                {/* Curva sigma(k) */}
                <path
                  d={puntosSvg.d}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />

                {/* Etiquetas de ejes */}
                <text
                  x={puntosSvg.ancho / 2}
                  y={puntosSvg.alto - 6}
                  fill="#71717a"
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="sans-serif"
                >
                  Número de onda adimensional k
                </text>
                <text
                  x={12}
                  y={puntosSvg.pad}
                  fill="#71717a"
                  fontSize="10"
                  fontFamily="sans-serif"
                >
                  Re(σ)
                </text>
              </svg>
            </div>
            <p className="text-[11px] text-zinc-500 mt-2 text-center flex items-center justify-center gap-1">
              La zona por encima de la línea discontinua roja (<FormulaLatex latex="\sigma > 0" lectura="sigma mayor a cero" />) representa modos espacialmente inestables.
            </p>
          </div>

          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-emerald-400 mb-2 uppercase tracking-wider">
              Diagnóstico Físico Asintótico
            </h4>
            <p className="text-xs text-zinc-300 leading-relaxed">
              {est.diagnosticoFisico}
            </p>
          </div>
        </div>
      </div>

      <PanelBifurcaciones daNominal={2.0} />
    </div>
  );
}
