"use client";

import Link from "next/link";
import { useSimulacion } from "../components/SimulacionProvider";

interface Herramienta {
  href: string;
  titulo: string;
  descripcion: string;
  necesita: (n: number) => boolean;
  requisito: string;
}

const HERRAMIENTAS: Herramienta[] = [
  {
    href: "/termodinamica/elv",
    titulo: "Equilibrio líquido–vapor",
    descripcion:
      "Diagramas y–x y T–x–y de una mezcla binaria. Es lo que hay debajo de cualquier método de separación: si aquí sale un azeótropo, ninguna columna simple lo va a cruzar.",
    necesita: (n) => n === 2,
    requisito: "exactamente 2 componentes",
  },
  {
    href: "/termodinamica/residuales",
    titulo: "Curvas residuales",
    descripcion:
      "Mapa de la topología de destilación: hacia dónde va el líquido que queda al evaporar. Revela las fronteras de destilación, que son las que deciden qué separaciones son posibles y cuáles no.",
    necesita: (n) => n === 3 || n === 4,
    requisito: "3 o 4 componentes",
  },
  {
    href: "/termodinamica/reactiva",
    titulo: "Destilación reactiva",
    descripcion:
      "Curvas residuales con reacción química y búsqueda de azeótropos reactivos. La reacción deforma el mapa: puede borrar una frontera que en el sistema inerte hacía imposible la separación.",
    necesita: (n) => n === 3 || n === 4,
    requisito: "3 o 4 componentes",
  },
];

export default function TermodinamicaPage() {
  const { componentes, simulacion, listo } = useSimulacion();
  const n = componentes.length;

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-6 py-6">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-1 text-lg font-semibold text-zinc-100">Termodinámica</h1>
        <p className="mb-6 text-xs text-zinc-500">
          Todo lo de aquí se calcula con los componentes de la simulación abierta, con UNIFAC predictivo para los
          coeficientes de actividad y las propiedades de <code className="text-zinc-400">thermo</code>. Son análisis
          del <em>sistema</em>, no de un equipo: dicen qué se puede separar antes de dimensionar nada.
        </p>

        {listo && !simulacion && (
          <div className="mb-6 rounded border border-amber-800 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
            No hay ninguna simulación abierta.{" "}
            <Link href="/simulaciones" className="underline">Crea o abre una</Link> para elegir componentes.
          </div>
        )}

        {listo && simulacion && (
          <div className="mb-6 rounded border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs">
            <span className="text-zinc-500">mezcla actual: </span>
            {n === 0 ? (
              <span className="text-amber-400">
                sin componentes —{" "}
                <Link href="/configuracion" className="underline">elígelos aquí</Link>
              </span>
            ) : (
              <span className="text-zinc-200">
                {componentes.map((c) => c.nombre).join(" · ")}{" "}
                <span className="text-zinc-500">({n} componentes)</span>
              </span>
            )}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {HERRAMIENTAS.map((h) => {
            const disponible = h.necesita(n);
            const contenido = (
              <>
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-sm font-semibold text-zinc-100">{h.titulo}</h2>
                  {!disponible && (
                    <span className="shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                      necesita {h.requisito}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-[11px] leading-snug text-zinc-500">{h.descripcion}</p>
              </>
            );
            return disponible ? (
              <Link
                key={h.href}
                href={h.href}
                className="rounded border border-zinc-800 bg-zinc-900 p-3 transition-colors hover:border-emerald-700 hover:bg-zinc-800/60"
              >
                {contenido}
              </Link>
            ) : (
              <div
                key={h.href}
                className="cursor-not-allowed rounded border border-zinc-800/60 bg-zinc-900/40 p-3 opacity-60"
                title={`Esta herramienta necesita ${h.requisito}; la simulación tiene ${n}.`}
              >
                {contenido}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
