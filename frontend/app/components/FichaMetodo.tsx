"use client";

import { useState } from "react";
import { METODOS, enlaceDoc } from "./metodos";

/**
 * Panel plegable con lo que hay detrás de un número: qué método lo
 * produjo, qué da por cierto y cuándo deja de valer.
 *
 * Decisiones de diseño:
 *
 *  - Va PLEGADO por defecto. Quien ya sabe lo que hace no quiere leerlo
 *    cada vez; quien no, lo tiene a un clic. Lo que no puede pasar es
 *    que no esté.
 *
 *  - Los LÍMITES van primero y en ámbar. Es el orden contrario al
 *    habitual (que empieza por las virtudes) y es deliberado: lo que de
 *    verdad hace falta saber antes de usar un número es cuándo no vale.
 *
 *  - Enlaza a docs/ en vez de duplicar la deducción. Dos copias de una
 *    ecuación acaban divergiendo, y la del código no es la que se lee.
 */
export default function FichaMetodo({
  metodo,
  abiertoPorDefecto = false,
}: {
  /** Clave de METODOS: "mccabe_thiele", "flash", "elv"... */
  metodo: string;
  abiertoPorDefecto?: boolean;
}) {
  const [abierto, setAbierto] = useState(abiertoPorDefecto);
  const ficha = METODOS[metodo];
  if (!ficha) return null;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/60">
      <button
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
      >
        <span className="text-xs text-zinc-400">
          <span className="text-zinc-500">Cómo se calcula esto — </span>
          <span className="font-medium text-zinc-300">{ficha.nombre}</span>
        </span>
        <span className="shrink-0 text-[10px] text-zinc-600">
          {abierto ? "ocultar ▴" : "suposiciones y límites ▾"}
        </span>
      </button>

      {abierto && (
        <div className="border-t border-zinc-800 px-3 py-3 text-xs">
          <p className="mb-3 text-zinc-400">{ficha.resumen}</p>

          <div className="mb-3">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-amber-600/90">
              Cuándo NO fiarse
            </div>
            <ul className="space-y-1">
              {ficha.limites.map((l) => (
                <li key={l} className="flex gap-2 text-amber-200/70">
                  <span className="select-none text-amber-700">·</span>
                  <span>{l}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mb-3">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">
              Qué da por cierto
            </div>
            <ul className="space-y-1">
              {ficha.suposiciones.map((s) => (
                <li key={s} className="flex gap-2 text-zinc-500">
                  <span className="select-none text-zinc-700">·</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          <a
            href={enlaceDoc(ficha)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block text-[11px] text-emerald-400 hover:text-emerald-300 hover:underline"
          >
            Ver la deducción completa en docs/{ficha.documento} →
          </a>
        </div>
      )}
    </div>
  );
}
