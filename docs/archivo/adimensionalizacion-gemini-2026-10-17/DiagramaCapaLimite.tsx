"use client";

import { useId, useMemo, useState } from "react";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function DiagramaCapaLimite({ peNominal = 10 }: { peNominal?: number }) {
  const baseId = useId();
  const [epsilon, setEpsilon] = useState(() => Math.min(0.2, Math.max(0.01, 1 / Math.max(1, peNominal))));
  const [ubicacionFrontera, setUbicacionFrontera] = useState<"inicio" | "final">("inicio");
  const [mostrarComponentes, setMostrarComponentes] = useState(true);

  // Espesor de capa límite asintótico
  const delta = epsilon; // delta ~ O(epsilon) para convección-difusión
  const peEquivalente = 1 / epsilon;

  // Cálculo de perfiles
  const puntos = useMemo(() => {
    const N = 120;
    const datos: Array<{ x: number; outer: number; inner: number; composite: number }> = [];

    for (let i = 0; i <= N; i++) {
      const x = i / N;

      if (ubicacionFrontera === "inicio") {
        // Capa límite en x = 0: phi(0) = 0, phi(1) = 1
        // Ecuación: eps*phi'' + phi' + phi = 0
        const phiOuter = Math.exp(1 - x);
        const phiInner = Math.exp(1) * (1 - Math.exp(-x / epsilon));
        const phiMatch = Math.exp(1);
        const phiComp = phiOuter + phiInner - phiMatch;

        datos.push({
          x,
          outer: Math.max(0, Math.min(3, phiOuter)),
          inner: Math.max(0, Math.min(3, phiInner)),
          composite: Math.max(0, Math.min(3, phiComp))
        });
      } else {
        // Capa límite en x = 1: phi(0) = 1, phi(1) = 0
        // Ecuación: eps*phi'' - phi' + phi = 0
        const phiOuter = Math.exp(x);
        const Y = (1 - x) / epsilon;
        const phiInner = Math.exp(1) * (1 - Math.exp(-Y));
        const phiMatch = Math.exp(1);
        const phiComp = phiOuter - Math.exp(1 - Y);

        datos.push({
          x,
          outer: Math.max(0, Math.min(3, phiOuter)),
          inner: Math.max(0, Math.min(3, phiInner)),
          composite: Math.max(0, Math.min(3, phiComp))
        });
      }
    }
    return datos;
  }, [epsilon, ubicacionFrontera]);

  // Dimensiones SVG
  const width = 560;
  const height = 240;
  const padL = 45;
  const padR = 20;
  const padT = 20;
  const padB = 35;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const maxY = 3.0;

  const toSvgX = (x: number) => padL + x * plotW;
  const toSvgY = (y: number) => padT + (1 - y / maxY) * plotH;

  const pathOuter = puntos.map((p, i) => `${i === 0 ? "M" : "L"} ${toSvgX(p.x).toFixed(1)} ${toSvgY(p.outer).toFixed(1)}`).join(" ");
  const pathInner = puntos.map((p, i) => `${i === 0 ? "M" : "L"} ${toSvgX(p.x).toFixed(1)} ${toSvgY(p.inner).toFixed(1)}`).join(" ");
  const pathComp = puntos.map((p, i) => `${i === 0 ? "M" : "L"} ${toSvgX(p.x).toFixed(1)} ${toSvgY(p.composite).toFixed(1)}`).join(" ");

  // Coordenadas de la franja de capa límite delta
  const xBordeL = ubicacionFrontera === "inicio" ? toSvgX(0) : toSvgX(1 - delta);
  const wBorde = delta * plotW;

  return (
    <div className="adim-group-pill p-5 mt-6 border border-zinc-700 bg-zinc-950/80 rounded-xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <h4 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
            <span>🔬</span>
            <span>Diagrama Asintótico de Capa Límite (Matched Asymptotics)</span>
          </h4>
          <p className="text-xs text-zinc-400 mt-0.5">
            Visualización interactiva de expansiones asintóticas acopladas conforme ε = 1/Pe → 0.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className={`adim-button text-xs py-1 px-2.5 ${ubicacionFrontera === "inicio" ? "is-active font-semibold" : ""}`}
            onClick={() => setUbicacionFrontera("inicio")}
          >
            Frontera Inicial (x = 0)
          </button>
          <button
            type="button"
            className={`adim-button text-xs py-1 px-2.5 ${ubicacionFrontera === "final" ? "is-active font-semibold" : ""}`}
            onClick={() => setUbicacionFrontera("final")}
          >
            Frontera Salida (x = 1)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-6 items-center">
        {/* Gráfico SVG Vectorial */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 overflow-hidden">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto block select-none">
            {/* Fondo y cuadrícula */}
            <rect x={padL} y={padT} width={plotW} height={plotH} fill="#09090b" />

            {/* Franja de espesor de capa límite delta */}
            <rect
              x={xBordeL}
              y={padT}
              width={wBorde}
              height={plotH}
              fill="rgba(234, 88, 12, 0.15)"
              stroke="rgba(234, 88, 12, 0.4)"
              strokeDasharray="3 3"
            />

            {/* Líneas de rejilla */}
            {[0, 1, 2, 3].map(val => (
              <g key={val}>
                <line
                  x1={padL}
                  y1={toSvgY(val)}
                  x2={width - padR}
                  y2={toSvgY(val)}
                  stroke="#27272a"
                  strokeWidth="1"
                />
                <text x={padL - 6} y={toSvgY(val) + 3} fill="#71717a" fontSize="10" textAnchor="end" fontFamily="monospace">
                  {val.toFixed(1)}
                </text>
              </g>
            ))}

            {[0, 0.25, 0.5, 0.75, 1.0].map(val => (
              <g key={val}>
                <line
                  x1={toSvgX(val)}
                  y1={padT}
                  x2={toSvgX(val)}
                  y2={height - padB}
                  stroke="#27272a"
                  strokeWidth="1"
                />
                <text x={toSvgX(val)} y={height - padB + 14} fill="#71717a" fontSize="10" textAnchor="middle" fontFamily="monospace">
                  {val.toFixed(2)}
                </text>
              </g>
            ))}

            {/* Curvas */}
            {mostrarComponentes && (
              <>
                {/* Solución Exterior (Outer) */}
                <path d={pathOuter} fill="none" stroke="#38bdf8" strokeWidth="1.8" strokeDasharray="5 3" />
                {/* Solución Interior (Inner) */}
                <path d={pathInner} fill="none" stroke="#fb923c" strokeWidth="1.8" strokeDasharray="3 3" />
              </>
            )}

            {/* Solución Compuesta Acoplada */}
            <path d={pathComp} fill="none" stroke="#10b981" strokeWidth="2.8" />

            {/* Etiquetas de los ejes */}
            <text x={padL + plotW / 2} y={height - 6} fill="#a1a1aa" fontSize="11" textAnchor="middle">
              Coordenada espacial x ∈ [0, 1]
            </text>

            <text
              x={14}
              y={padT + plotH / 2}
              fill="#a1a1aa"
              fontSize="11"
              textAnchor="middle"
              transform={`rotate(-90, 14, ${padT + plotH / 2})`}
            >
              Perfil de Concentración ϕ(x)
            </text>
          </svg>

          {/* Leyenda */}
          <div className="flex flex-wrap items-center justify-center gap-4 mt-2 text-xs">
            <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <span className="w-3 h-0.5 bg-emerald-400 inline-block"></span>
              Compuesta: ϕ_comp(x)
            </span>
            {mostrarComponentes && (
              <>
                <span className="flex items-center gap-1.5 text-sky-400 font-medium">
                  <span className="w-3 h-0.5 bg-sky-400 border-b border-dashed inline-block"></span>
                  Exterior: ϕ_out(x)
                </span>
                <span className="flex items-center gap-1.5 text-amber-400 font-medium">
                  <span className="w-3 h-0.5 bg-amber-400 border-b border-dotted inline-block"></span>
                  Interior: ϕ_in(x/ε)
                </span>
              </>
            )}
            <span className="flex items-center gap-1.5 text-orange-400 font-medium">
              <span className="w-2.5 h-2.5 bg-orange-500/20 border border-orange-500/40 inline-block"></span>
              Espesor δ ~ ε = {delta.toFixed(3)}
            </span>
          </div>
        </div>

        {/* Panel de Controles y Métricas Asintóticas */}
        <div className="space-y-4 text-xs bg-zinc-900/60 p-4 rounded-lg border border-zinc-800">
          <div>
            <div className="flex justify-between items-baseline mb-1">
              <span className="text-zinc-300 font-semibold">Parámetro Perturbativo ε:</span>
              <span className="font-mono text-amber-400 font-bold">{epsilon.toFixed(3)}</span>
            </div>
            <input
              id={`${baseId}-slider-epsilon`}
              aria-label="Parámetro perturbativo epsilon"
              type="range"
              min="0.01"
              max="0.40"
              step="0.005"
              value={epsilon}
              onChange={e => setEpsilon(parseFloat(e.target.value))}
              className="w-full accent-amber-500 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-zinc-500 mt-0.5">
              <span>ε → 0 (Capa fina, Pe={peEquivalente.toFixed(0)})</span>
              <span>ε = 0.40 (Difusivo)</span>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-zinc-300">
            <input
              type="checkbox"
              checked={mostrarComponentes}
              onChange={e => setMostrarComponentes(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-950 text-cyan-500"
            />
            <span>Mostrar sub-soluciones (Outer / Inner)</span>
          </label>

          <div className="border-t border-zinc-800 pt-3 space-y-2">
            <h5 className="font-semibold uppercase tracking-wider text-cyan-400 text-[11px]">
              Directrices de Malla para Codex (/motor)
            </h5>
            <div className="space-y-1.5 text-[11px] text-zinc-300">
              <p>
                • <strong>Espesor de Capa Límite:</strong> <span className="font-mono text-amber-300">δ ≈ {delta.toFixed(3)} L</span>
              </p>
              <p>
                • <strong>Gradiente en la Pared:</strong> <span className="font-mono text-cyan-300">∂ϕ/∂x ~ 1/ε = {peEquivalente.toFixed(1)}</span>
              </p>
              <p>
                • <strong>Malla Uniforme Mínima:</strong> <span className="font-mono text-emerald-300">N ≥ {Math.ceil(3 / delta)} celdas</span> para resolver la capa con al menos 3 nodos.
              </p>
              <p className="text-[10px] text-zinc-400 mt-1 italic">
                Sugerencia AMR: Aplicar refinamiento geométrico (razón r = 1.2) en la frontera para evitar sobredimensionar el interior del dominio.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
