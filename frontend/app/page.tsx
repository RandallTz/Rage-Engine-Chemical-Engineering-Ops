"use client";

import Link from "next/link";
import { useSimulacion } from "./components/SimulacionProvider";

/**
 * Portada.
 *
 * Antes la raíz era directamente la herramienta de "columna suelta"
 * (ahora en /columna). Eso significaba que alguien que llegaba por un
 * enlace aterrizaba en un formulario de parámetros sin saber qué era
 * esto, qué hace ni si puede fiarse. Con el enlace compartible, llegar
 * de fuera deja de ser la excepción y pasa a ser el caso normal.
 *
 * Lo que esta página tiene que lograr, en este orden:
 *   1. Decir qué es y para quién, en una frase.
 *   2. Llevar a algo que funcione en un clic.
 *   3. Decir qué NO hace, antes de que alguien lo descubra solo.
 *
 * El punto 3 no es modestia: es lo mismo que hace docs/12-validacion.md.
 * Un simulador que no declara sus límites invita a usar un número donde
 * no vale.
 */

const CAPACIDADES = [
  {
    titulo: "Columnas de destilación",
    detalle:
      "McCabe-Thiele y Ponchon-Savarit para binarios, FUG para multicomponente. Resuelven en cualquier dirección: dado el reflujo calculan las etapas, o al revés.",
  },
  {
    titulo: "Diagramas de proceso completos",
    detalle:
      "Reactores, flashes, intercambiadores, válvulas, mezcladores y divisores encadenados, con detección automática de reciclos.",
  },
  {
    titulo: "Termodinámica predictiva",
    detalle:
      "UNIFAC a partir de los grupos funcionales: funciona con mezclas sin datos binarios ajustados. Equilibrio, curvas residuales y azeótropos reactivos.",
  },
  {
    titulo: "Te dice qué te falta",
    detalle:
      "Cuenta los grados de libertad del diagrama y señala dónde faltan datos y dónde sobran. No falla en silencio: explica por qué no puede resolver.",
  },
];

const LIMITES = [
  "Sin columna rigurosa plato a plato (MESH) todavía: hay métodos de atajo y de etapa única.",
  "Solo estado estacionario, sin dinámica ni control.",
  "Una sola reacción; sin equilibrio líquido-líquido; sin caída de presión.",
  "Etapas teóricas, no una columna comprable: no hay dimensionado ni costes.",
];

export default function Portada() {
  const { listo, simulaciones } = useSimulacion();
  const tieneTrabajo = listo && simulaciones.length > 0;

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-bold text-zinc-100">
          Simulador de procesos de destilación
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">
          Resuelve columnas, reactores y diagramas de proceso completos en el
          navegador, sin instalar nada. A diferencia de un simulador comercial,{" "}
          <strong className="text-zinc-300">
            enseña las ecuaciones que usa, lo que supone y cuándo deja de valer
          </strong>
          .
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/simulaciones"
            className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            {tieneTrabajo ? "Ir a mis simulaciones" : "Empezar con un ejemplo resuelto"}
          </Link>
          <Link
            href="/columna"
            className="rounded border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-900"
          >
            Resolver una columna suelta
          </Link>
        </div>

        {!tieneTrabajo && (
          <p className="mt-3 text-xs text-zinc-600">
            Hay plantillas listas —McCabe-Thiele, Ponchon-Savarit, FUG, un reactor de
            MTBE, procesos combinados— que resuelven de un clic. No hace falta
            registrarse ni configurar nada.
          </p>
        )}

        {/* ---------------------------------------------------- capacidades */}
        <h2 className="mt-10 text-sm font-semibold text-zinc-200">Qué hace</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {CAPACIDADES.map((c) => (
            <div key={c.titulo} className="rounded border border-zinc-800 bg-zinc-900 p-3">
              <div className="text-xs font-medium text-zinc-200">{c.titulo}</div>
              <p className="mt-1 text-xs leading-relaxed text-zinc-500">{c.detalle}</p>
            </div>
          ))}
        </div>

        {/* -------------------------------------------------------- límites */}
        <h2 className="mt-8 text-sm font-semibold text-zinc-200">Qué NO hace</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Saber dónde se acaba la validez de un número es parte de poder usarlo.
        </p>
        <ul className="mt-3 space-y-1.5">
          {LIMITES.map((l) => (
            <li key={l} className="flex gap-2 text-xs text-amber-200/70">
              <span className="select-none text-amber-700">·</span>
              <span>{l}</span>
            </li>
          ))}
        </ul>

        {/* ----------------------------------------------------- validación */}
        <h2 className="mt-8 text-sm font-semibold text-zinc-200">Cómo se valida</h2>
        <p className="mt-2 text-xs leading-relaxed text-zinc-500">
          Una regla, en todo el proyecto:{" "}
          <em className="text-zinc-400">que un método corra no es que funcione</em>. Cada
          resultado se contrasta contra algo independiente — una fórmula cerrada, un
          balance que debe cerrar, o un valor de literatura. El azeótropo etanol/agua sale
          en x = 0.894, el balance de energía de una planta con reciclo cierra a 4·10⁻¹²
          relativo, y el líquido que sale de un flash está en su punto de burbuja con un
          error de 10⁻⁹ K.
        </p>
        <a
          href="https://github.com/RandallTz/Rage-Engine-Chemical-Engineering-Ops/blob/main/docs/12-validacion.md"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-xs text-emerald-400 hover:text-emerald-300 hover:underline"
        >
          Qué está comprobado, contra qué, y qué no hace →
        </a>

        <p className="mt-10 border-t border-zinc-900 pt-4 text-[11px] text-zinc-600">
          Las simulaciones se guardan en este navegador. Para llevarte una a otra máquina
          o enviársela a alguien, usa «Copiar enlace» o descárgala como archivo.
        </p>
      </div>
    </div>
  );
}
