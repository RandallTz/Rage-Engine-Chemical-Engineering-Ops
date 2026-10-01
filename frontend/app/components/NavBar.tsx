"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useSimulacion } from "./SimulacionProvider";

// Primer nivel: moverse ENTRE simulaciones. Lo que se hace dentro de una
// vive en BarraSimulacion (segundo nivel), para no mezclar "cambiar de
// documento" con "moverse dentro del documento".
const MODOS = [
  { href: "/", etiqueta: "Inicio", descripcion: "Qué es esto, qué hace y qué no hace" },
  { href: "/simulaciones", etiqueta: "Mis simulaciones", descripcion: "Crear, abrir, guardar y subir simulaciones" },
];

export default function NavBar() {
  const ruta = usePathname();
  const { simulacion, listo } = useSimulacion();

  return (
    <nav className="flex items-center gap-1 border-b border-zinc-800 bg-zinc-900 px-4 py-2">
      <Link href="/" className="mr-4 text-sm font-bold text-zinc-100 hover:text-white">Simulador de Procesos</Link>
      {MODOS.map((modo) => {
        // /termodinamica tiene sub-rutas; la pestana sigue activa dentro de ellas.
        const activo = modo.href === "/" ? ruta === "/" : ruta.startsWith(modo.href);
        return (
          <Link
            key={modo.href}
            href={modo.href}
            title={modo.descripcion}
            className={`rounded px-3 py-1 text-sm transition-colors ${
              activo ? "bg-emerald-600 text-white" : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
            }`}
          >
            {modo.etiqueta}
          </Link>
        );
      })}

      <div className="ml-auto flex items-center gap-3">
        {listo &&
          (simulacion ? (
            <span className="text-xs text-zinc-600">
              {simulacion.componentes.length
                ? simulacion.componentes.map((c) => c.nombre).join(" · ")
                : "sin componentes"}
            </span>
          ) : (
            <Link
              href="/simulaciones"
              className="rounded border border-amber-700 bg-amber-950/50 px-2 py-0.5 text-xs text-amber-200 hover:bg-amber-900/50"
            >
              sin simulación abierta — crear una
            </Link>
          ))}
      </div>
    </nav>
  );
}
