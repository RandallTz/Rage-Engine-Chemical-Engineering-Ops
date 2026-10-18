"use client";

import { useMemo } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import { derivarSimetriaLie } from "./analisisSimetriasLie";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function PanelSimetriasLie({ f }: { f: FormulacionNucleo }) {
  const lie = useMemo(() => derivarSimetriaLie(f), [f]);

  return (
    <div className="adim-lie-panel rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-xl my-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-amber-400 font-mono">
            Teoría de Grupos de Lie y Autosimilitud
          </span>
          <h3 className="text-lg font-medium text-zinc-100 flex items-center gap-2">
            Simetrías de Escala de Lie y Reducción Autosimilar <FormulaLatex latex="\eta = \xi / \tau^\alpha" lectura="eta igual a xi sobre tau a la alfa" />
          </h3>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/80 border border-amber-600 text-amber-300">
          Exponente canónico \(\alpha = {lie.exponenteAlfa}\)
        </span>
      </div>

      <p className="text-xs text-zinc-400 mb-6 leading-relaxed">
        {lie.fundamentacionFisica}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Columna izquierda: Generador infinitesimal y variable canónica */}
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
              Generador Infinitesimal del Grupo de Dilataciones (Álgebra de Lie)
            </h4>
            <div className="overflow-x-auto text-sm my-2">
              <FormulaLatex bloque latex={lie.generadorInfinitesimalLatex} lectura="Generador infinitesimal de Lie" />
            </div>
            <p className="text-[11px] text-zinc-500">
              Campo vectorial tangente asociado a la acción del grupo uniparamétrico de dilatación de coordenadas.
            </p>
          </div>

          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider flex items-center gap-1">
              Variable Autosimilar Canónica <FormulaLatex latex="\eta" lectura="eta" /> y Ansatz de Escala
            </h4>
            <div className="space-y-2 overflow-x-auto text-sm my-2">
              <FormulaLatex bloque latex={lie.variableSimilitudLatex} lectura="Variable de similitud" />
              <FormulaLatex bloque latex={lie.ansatzAutosimilarLatex} lectura="Ansatz autosimilar" />
            </div>
            <p className="text-[11px] text-zinc-500">
              Invariante de Riemann del subgrupo de homotecia que reduce en 1 grado de libertad el dominio continuo.
            </p>
          </div>
        </div>

        {/* Columna derecha: EDO reducida y perfil analítico */}
        <div className="space-y-4">
          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">
              Ecuación Diferencial Ordinaria Reducida (EDO de Similitud)
            </h4>
            <div className="overflow-x-auto text-sm my-2">
              <FormulaLatex bloque latex={lie.edoReducidaLatex} lectura="EDO de similitud" />
            </div>
            <p className="text-[11px] text-zinc-500">
              Colapso exacto de la ecuación en derivadas parciales en una dinámica unidimensional cerrada en \(\eta\).
            </p>
          </div>

          <div className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
            <h4 className="text-xs font-medium text-amber-400 mb-2 uppercase tracking-wider">
              Perfil Analítico Asintótico Universal
            </h4>
            <div className="overflow-x-auto text-sm my-2">
              <FormulaLatex bloque latex={lie.perfilAnaliticoLatex} lectura="Perfil analítico universal" />
            </div>
            <p className="text-[11px] text-zinc-500">
              Forma funcional estacionaria hacia la cual convergen asintóticamente todas las condiciones iniciales arbitrarias.
            </p>
          </div>
        </div>
      </div>

      {/* Diagrama Interactivo de Retrato de Fase 2D (Theta vs Theta') */}
      <div className="mt-6 p-4 rounded-lg bg-zinc-900/40 border border-zinc-800">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
              Retrato de Fase 2D de la Variedad Invariante: (Θ vs. dΘ/dη)
            </h4>
            <p className="text-[11px] text-zinc-400">
              Trayectorias del sistema dinámico reducido de Lie en el plano de fases. El perfil universal conecta el estado base con la cuenca asintótica.
            </p>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded">
            Variedad Heteroclínica Invariante
          </span>
        </div>

        <div className="flex justify-center bg-zinc-950 p-3 rounded border border-zinc-900">
          <svg viewBox="0 0 500 220" className="w-full max-w-2xl h-auto select-none" style={{ background: "#09090b" }}>
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#71717a" />
              </marker>
              <marker id="arrow-trajectory" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10b981" />
              </marker>
              <linearGradient id="traj-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="50%" stopColor="#10b981" />
                <stop offset="100%" stopColor="#f59e0b" />
              </linearGradient>
            </defs>

            {/* Ejes cartesianos */}
            <line x1="50" y1="110" x2="470" y2="110" stroke="#3f3f46" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="260" y1="20" x2="260" y2="200" stroke="#3f3f46" strokeWidth="1" strokeDasharray="3 3" />
            <text x="465" y="105" fill="#a1a1aa" fontSize="10" fontFamily="monospace">Θ</text>
            <text x="265" y="25" fill="#a1a1aa" fontSize="10" fontFamily="monospace">Θ&apos; = dΘ/dη</text>

            {/* Campo vectorial de tangentes */}
            {[-1.5, -0.75, 0, 0.75, 1.5].map((th, i) =>
              [-1, -0.5, 0.5, 1].map((thp, j) => {
                const cx = 260 + th * 100;
                const cy = 110 - thp * 70;
                // Derivada d(th)/deta = thp, d(thp)/deta ~ -th - 0.5*thp
                const dx = thp * 15;
                const dy = -(-th - 0.5 * thp) * 15;
                const len = Math.sqrt(dx * dx + dy * dy) || 1;
                const scale = 14 / len;
                return (
                  <line
                    key={`${i}-${j}`}
                    x1={cx}
                    y1={cy}
                    x2={cx + dx * scale}
                    y2={cy + dy * scale}
                    stroke="#52525b"
                    strokeWidth="1"
                    markerEnd="url(#arrow)"
                    opacity="0.6"
                  />
                );
              })
            )}

            {/* Trayectoria invariante de autosimilitud (curva heteroclínica suave) */}
            <path
              d="M 60,110 C 130,170 210,180 260,110 C 310,40 390,50 460,110"
              fill="none"
              stroke="url(#traj-grad)"
              strokeWidth="2.5"
            />
            {/* Puntos singulares / estados base */}
            <circle cx="260" cy="110" r="4.5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
            <text x="268" y="125" fill="#f59e0b" fontSize="10" fontWeight="bold">Estado Base Homogéneo</text>
            <circle cx="440" cy="110" r="3.5" fill="#10b981" />
            <circle cx="80" cy="110" r="3.5" fill="#38bdf8" />
          </svg>
        </div>
      </div>
    </div>
  );
}
