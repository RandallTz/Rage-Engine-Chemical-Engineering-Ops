"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { useRef, useState } from "react";
import { useSimulacion } from "./SimulacionProvider";

/**
 * Segundo nivel de navegacion: todo lo que vive DENTRO de la simulacion
 * abierta. Antes estaba todo en una sola barra plana, y no se distinguia
 * lo que es "cambiar de simulacion" de lo que es "moverse dentro de
 * esta". Con dos niveles, la barra de arriba es el archivador y esta es
 * el documento.
 *
 * Solo aparece con una simulacion abierta: sin ella no hay componentes
 * ni diagrama que mostrar.
 */

const SECCIONES = [
  { href: "/configuracion", etiqueta: "Componentes",
    descripcion: "Qué sustancias forman la mezcla y con qué modelo termodinámico" },
  { href: "/flowsheet", etiqueta: "Flowsheet",
    descripcion: "Equipos y corrientes del proceso" },
  { href: "/termodinamica", etiqueta: "Termodinámica",
    descripcion: "Equilibrio, curvas residuales, mapas ternarios y destilación reactiva" },
  { href: "/columna", etiqueta: "Columna suelta",
    descripcion: "Una columna aislada, sin diagrama" },
];

export default function BarraSimulacion() {
  const ruta = usePathname();
  const { simulacion, listo, exportar, importar, renombrar } = useSimulacion();
  const entradaArchivo = useRef<HTMLInputElement>(null);
  const [editando, setEditando] = useState(false);
  const [borrador, setBorrador] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);

  if (!listo || !simulacion) return null;

  const nComp = simulacion.componentes.length;
  const nEquipos = (simulacion.flowsheet.nodes as { type?: string }[])
    .filter((n) => n.type === "operacion").length;

  async function alSubir(archivo: File | undefined) {
    if (!archivo) return;
    const r = importar(await archivo.text());
    setAviso(r.ok ? `"${archivo.name}" cargado como simulación nueva.` : r.error);
    setTimeout(() => setAviso(null), 5000);
    if (entradaArchivo.current) entradaArchivo.current.value = "";
  }

  return (
    <div className="border-b border-zinc-800 bg-zinc-950">
      <div className="flex flex-wrap items-center gap-1 px-4 py-1.5">
        {editando ? (
          <input
            autoFocus
            className="mr-3 rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-sm text-zinc-100"
            value={borrador}
            onChange={(e) => setBorrador(e.target.value)}
            onBlur={() => { renombrar(simulacion.id, borrador); setEditando(false); }}
            onKeyDown={(e) => {
              if (e.key === "Enter") { renombrar(simulacion.id, borrador); setEditando(false); }
              if (e.key === "Escape") setEditando(false);
            }}
          />
        ) : (
          <button
            onClick={() => { setEditando(true); setBorrador(simulacion.nombre); }}
            className="mr-3 text-sm font-semibold text-zinc-100 hover:underline"
            title="Clic para renombrar la simulación"
          >
            {simulacion.nombre}
          </button>
        )}

        {SECCIONES.map((s) => {
          const activo = s.href === "/" ? ruta === "/" : ruta.startsWith(s.href);
          return (
            <Link
              key={s.href}
              href={s.href}
              title={s.descripcion}
              className={`rounded px-2.5 py-1 text-xs transition-colors ${
                activo
                  ? "bg-zinc-800 font-medium text-zinc-100"
                  : "text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300"
              }`}
            >
              {s.etiqueta}
            </Link>
          );
        })}

        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] text-zinc-600">
            {nComp === 0 ? "sin componentes" : `${nComp} componentes`} · {nEquipos}{" "}
            {nEquipos === 1 ? "equipo" : "equipos"}
          </span>
          <input
            ref={entradaArchivo}
            type="file"
            accept=".json,.simproc.json,application/json"
            className="hidden"
            onChange={(e) => alSubir(e.target.files?.[0])}
          />
          <button
            onClick={() => exportar(simulacion.id)}
            className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800"
            title="Descargar esta simulación completa (componentes, equipos, corrientes y datos) como un archivo JSON reutilizable"
          >
            ↓ Guardar JSON
          </button>
          <button
            onClick={() => entradaArchivo.current?.click()}
            className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800"
            title="Cargar un archivo .simproc.json. Entra siempre como simulación nueva: no pisa esta."
          >
            ↑ Cargar JSON
          </button>
        </div>
      </div>

      {aviso && (
        <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-1 text-[11px] text-zinc-300">
          {aviso}
        </div>
      )}
    </div>
  );
}
