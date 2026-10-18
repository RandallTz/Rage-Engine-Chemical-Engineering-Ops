"use client";

import { useMemo } from "react";
import type { FormulacionNucleo } from "./contratoNucleo";
import { analizarCondicionesFrontera } from "./analisisCondicionesFrontera";
import FormulaLatex from "../flowsheet/FormulaLatex";

export default function PanelCondicionesFrontera({ f }: { f: FormulacionNucleo }) {
  const anal = useMemo(() => analizarCondicionesFrontera(f), [f]);

  return (
    <div className="adim-bc-panel rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-xl my-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4 mb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-sky-400 font-mono">
            Física Interfacial y de Contorno
          </span>
          <h3 className="text-lg font-medium text-zinc-100">
            Adimensionalización de Condiciones de Frontera e Iniciales
          </h3>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-sky-950/80 border border-sky-600 text-sky-300">
          {anal.condiciones.length} condiciones transformadas
        </span>
      </div>

      <p className="text-xs text-zinc-400 mb-6 leading-relaxed">
        {anal.sintesisFisica}
      </p>

      {/* Grupos adimensionales interfaciales deducidos */}
      {anal.gruposFrontera.length > 0 && (
        <div className="mb-6">
          <h4 className="text-xs font-medium text-zinc-400 mb-3 uppercase tracking-wider flex items-center gap-2">
            Invariantes Adimensionales Interfaciales Deducidos (Grupos <FormulaLatex latex="\Pi_{\partial\Omega}" lectura="Pi de frontera" />)
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {anal.gruposFrontera.map(g => (
              <div key={g.id} className="rounded-lg bg-zinc-900/60 p-4 border border-zinc-800/80">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-sky-300 font-mono">
                    <FormulaLatex latex={g.id} lectura="Identificador grupo" />
                  </span>
                  <span className="text-[11px] text-zinc-400">{g.nombre}</span>
                </div>
                <div className="overflow-x-auto my-2 text-center bg-zinc-950/60 p-2 rounded border border-zinc-800/40">
                  <FormulaLatex bloque latex={g.definicionLatex} lectura={g.nombre} />
                </div>
                <p className="text-xs text-zinc-300 mb-3">{g.significadoFisico}</p>
                <div className="border-t border-zinc-800/60 pt-2 space-y-1">
                  {g.regimenesAsintoticos.map((reg, ri) => (
                    <div key={ri} className="text-[11px] text-zinc-400">
                      <strong className="text-zinc-300"><FormulaLatex latex={reg.limite} lectura="Límite" />:</strong> {reg.interpretacion}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Condiciones transformadas paso a paso */}
      <div>
        <h4 className="text-xs font-medium text-zinc-400 mb-3 uppercase tracking-wider">
          Deducción Formal de Condiciones de Contorno Escaladas
        </h4>
        <div className="space-y-4">
          {anal.condiciones.map((c, idx) => (
            <div key={idx} className="rounded-lg bg-zinc-900/50 p-4 border border-zinc-800/70">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-200">
                  {idx + 1}. {c.descripcion}
                </span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300">
                  {c.tipo}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 my-2">
                <div className="bg-zinc-950/80 p-3 rounded border border-zinc-800/60">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">Forma Dimensional Original:</span>
                  <div className="overflow-x-auto text-xs">
                    <FormulaLatex bloque latex={c.ecuacionOriginalLatex} lectura="Ecuación original" />
                  </div>
                </div>
                <div className="bg-sky-950/20 p-3 rounded border border-sky-900/40">
                  <span className="text-[10px] text-sky-400 uppercase tracking-wider block mb-1">Forma Adimensional Invariante:</span>
                  <div className="overflow-x-auto text-xs text-sky-200">
                    <FormulaLatex bloque latex={c.ecuacionAdimensionalLatex} lectura="Ecuación adimensional" />
                  </div>
                </div>
              </div>

              <details className="mt-2 text-xs text-zinc-400">
                <summary className="cursor-pointer hover:text-zinc-200 text-[11px] text-zinc-500">
                  ▶ Ver deducción matemática paso a paso
                </summary>
                <ul className="list-disc pl-5 mt-2 space-y-1 text-zinc-300">
                  {c.deduccionPasoPaso.map((paso, pi) => (
                    <li key={pi}>{paso}</li>
                  ))}
                </ul>
              </details>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
