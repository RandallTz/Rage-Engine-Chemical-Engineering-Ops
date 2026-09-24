"use client";

import { useEffect, useState } from "react";

/**
 * Indicador de espera para los calculos que tardan de verdad.
 *
 * El problema que resuelve, medido contra el despliegue real: el mapa de
 * curvas residuales tarda 85 s en el plan gratuito de Render (0.1 CPU).
 * Con solo un boton que pone "Integrando...", 85 segundos sin ninguna
 * otra senal se leen como "esto se rompio", y el usuario recarga la
 * pagina justo antes de que llegue la respuesta.
 *
 * Aqui no se inventa un porcentaje: no hay forma de saber por que curva
 * va el servidor. Lo que se muestra es lo que SI se sabe -- que sigue
 * vivo, cuanto lleva, y cuanto suele tardar -- que es exactamente lo que
 * hace falta para decidir si esperar.
 *
 * Y si se pasa del tiempo esperado, se explica la causa mas probable en
 * vez de dejar al usuario adivinando.
 */
export default function EsperaCalculo({
  activa,
  titulo,
  detalle,
  segundosEsperados = 10,
  compacto = false,
}: {
  activa: boolean;
  titulo: string;
  detalle?: string;
  segundosEsperados?: number;
  /** Una sola linea, para barras de herramientas donde no cabe la tarjeta. */
  compacto?: boolean;
}) {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    if (!activa) {
      setSegundos(0);
      return;
    }
    const inicio = Date.now();
    const id = window.setInterval(
      () => setSegundos(Math.floor((Date.now() - inicio) / 1000)),
      250,
    );
    return () => window.clearInterval(id);
  }, [activa]);

  if (!activa) return null;

  const tarda = segundos > segundosEsperados;
  const muchoRato = segundos > segundosEsperados * 3;

  if (compacto) {
    return (
      <span role="status" aria-live="polite" className="flex items-center gap-2 text-xs">
        <span className="h-1 w-24 overflow-hidden rounded bg-zinc-800">
          <span className="block h-full w-1/3 animate-espera rounded bg-emerald-600" />
        </span>
        <span className="font-mono tabular-nums text-zinc-500">{segundos}s</span>
        {muchoRato ? (
          <span className="text-amber-500/80">el servidor estaba dormido, hasta 1 min</span>
        ) : tarda ? (
          <span className="text-amber-500/80">más lento de lo normal (0.1 CPU)</span>
        ) : (
          <span className="text-zinc-600">{titulo}</span>
        )}
      </span>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded border border-zinc-800 bg-zinc-900 p-4"
    >
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-zinc-200">{titulo}</span>
        <span className="font-mono text-xs tabular-nums text-zinc-500">
          {segundos}s
        </span>
      </div>

      {/* Barra indeterminada: se mueve porque el servidor sigue vivo, no
          porque se conozca el avance. Fingir un porcentaje seria mentir. */}
      <div className="h-1 w-full overflow-hidden rounded bg-zinc-800">
        <div className="h-full w-1/3 animate-espera rounded bg-emerald-600" />
      </div>

      {detalle && <p className="mt-2 text-xs text-zinc-500">{detalle}</p>}

      {tarda && !muchoRato && (
        <p className="mt-2 text-xs text-amber-500/80">
          Está tardando más de lo habitual. El servidor gratuito usa 0.1 CPU, así
          que los cálculos pesados van unas 14 veces más lentos que en local.
        </p>
      )}

      {muchoRato && (
        <p className="mt-2 text-xs text-amber-500/80">
          Si es la primera petición en un rato, el servidor estaba dormido y tarda
          hasta un minuto en despertar. Sigue esperando: no se ha perdido nada.
        </p>
      )}
    </div>
  );
}
