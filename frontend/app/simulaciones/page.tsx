"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useSimulacion, type Simulacion } from "../components/SimulacionProvider";
import { PLANTILLAS, CATEGORIAS } from "../components/plantillas";

function fecha(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function resumen(s: Simulacion) {
  const equipos = (s.flowsheet.nodes as { type?: string }[]).filter((n) => n.type === "operacion").length;
  const corrientes = (s.flowsheet.nodes as { type?: string }[]).filter((n) => n.type === "corriente").length;
  const partes = [
    s.componentes.length ? s.componentes.map((c) => c.nombre).join(" · ") : "sin componentes",
    `${equipos} equipo${equipos === 1 ? "" : "s"}`,
    `${corrientes} corriente${corrientes === 1 ? "" : "s"}`,
  ];
  return partes.join(" — ");
}

export default function SimulacionesPage() {
  const {
    listo, simulaciones, simulacion, crear, abrir, eliminar, renombrar, duplicar, exportar, importar,
  } = useSimulacion();
  const router = useRouter();

  const [nombreNuevo, setNombreNuevo] = useState("");
  const [plantilla, setPlantilla] = useState("mccabe_listo");
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState("");
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const entradaArchivo = useRef<HTMLInputElement>(null);

  function crearYAbrir() {
    crear(nombreNuevo, plantilla);
    setNombreNuevo("");
    router.push("/flowsheet");
  }

  async function alSubirArchivo(archivo: File | undefined) {
    if (!archivo) return;
    const resultado = importar(await archivo.text());
    if (resultado.ok) {
      setAviso({ tipo: "ok", texto: `"${archivo.name}" se cargó como una simulación nueva.` });
    } else {
      setAviso({ tipo: "error", texto: resultado.error });
    }
    if (entradaArchivo.current) entradaArchivo.current.value = "";
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-6 py-6">
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-1 text-lg font-semibold text-zinc-100">Simulaciones</h1>
        <p className="mb-6 text-xs text-zinc-500">
          Cada simulación guarda <strong className="text-zinc-400">sus propios componentes</strong>, el modelo
          termodinámico y el diagrama completo. Se conservan al cambiar de panel y al cerrar el navegador; para
          llevártelas a otra máquina, descárgalas.
        </p>

        {/* ------------------------------------------------ crear / importar */}
        <div className="mb-6 grid gap-4 md:grid-cols-[1fr_auto]">
          <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
            <h2 className="mb-3 text-sm font-semibold text-zinc-200">Nueva simulación</h2>
            <div className="mb-3 flex flex-wrap gap-2">
              <input
                className="min-w-[220px] flex-1 rounded border border-zinc-700 bg-zinc-800 px-2 py-1.5 text-sm text-zinc-100"
                placeholder="Nombre (opcional)"
                value={nombreNuevo}
                onChange={(e) => setNombreNuevo(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && crearYAbrir()}
              />
              <button
                onClick={crearYAbrir}
                className="rounded bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
              >
                Crear y abrir
              </button>
            </div>
            <div className="space-y-3">
              {CATEGORIAS.map((cat) => {
                const deLaCategoria = PLANTILLAS.filter((p) => p.categoria === cat.id);
                if (deLaCategoria.length === 0) return null;
                return (
                  <div key={cat.id}>
                    <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
                      {cat.etiqueta}
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {deLaCategoria.map((p) => (
                        <button
                          key={p.id}
                          onClick={() => setPlantilla(p.id)}
                          className={`rounded border p-2 text-left transition-colors ${
                            plantilla === p.id
                              ? "border-emerald-600 bg-emerald-950/40"
                              : "border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800"
                          }`}
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-medium text-zinc-200">{p.nombre}</span>
                            {p.lista && (
                              <span
                                className="rounded bg-emerald-800 px-1 py-px text-[9px] font-medium text-emerald-100"
                                title="Trae todos los datos: se abre y se pulsa Resolver"
                              >
                                lista
                              </span>
                            )}
                          </div>
                          <div className="mt-0.5 text-[10px] leading-snug text-zinc-500">{p.descripcion}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded border border-zinc-800 bg-zinc-900 p-4">
            <h2 className="mb-3 text-sm font-semibold text-zinc-200">Desde un archivo</h2>
            <input
              ref={entradaArchivo}
              type="file"
              accept=".json,.simproc.json,application/json"
              className="hidden"
              onChange={(e) => alSubirArchivo(e.target.files?.[0])}
            />
            <button
              onClick={() => entradaArchivo.current?.click()}
              className="w-full rounded border border-zinc-700 px-4 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800"
            >
              Subir simulación
            </button>
            <p className="mt-2 text-[10px] leading-snug text-zinc-500">
              Acepta los <code className="text-zinc-400">.simproc.json</code> que descargues aquí. Siempre entra como
              una simulación nueva: nunca pisa una existente.
            </p>
          </div>
        </div>

        {aviso && (
          <div
            className={`mb-4 rounded border px-3 py-2 text-xs ${
              aviso.tipo === "ok"
                ? "border-emerald-800 bg-emerald-950/40 text-emerald-200"
                : "border-red-800 bg-red-950/40 text-red-200"
            }`}
          >
            {aviso.texto}
          </div>
        )}

        {/* ------------------------------------------------------- listado */}
        <h2 className="mb-2 text-sm font-semibold text-zinc-200">
          Guardadas {listo && <span className="text-zinc-500">({simulaciones.length})</span>}
        </h2>

        {!listo ? (
          <p className="text-xs text-zinc-500">Cargando…</p>
        ) : simulaciones.length === 0 ? (
          <p className="rounded border border-dashed border-zinc-800 px-4 py-8 text-center text-xs text-zinc-500">
            Todavía no hay ninguna. Crea una arriba para empezar.
          </p>
        ) : (
          <div className="space-y-2">
            {simulaciones.map((s) => {
              const activa = simulacion?.id === s.id;
              return (
                <div
                  key={s.id}
                  className={`rounded border p-3 ${
                    activa ? "border-emerald-700 bg-emerald-950/20" : "border-zinc-800 bg-zinc-900"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {editando === s.id ? (
                      <input
                        autoFocus
                        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                        value={borrador}
                        onChange={(e) => setBorrador(e.target.value)}
                        onBlur={() => { renombrar(s.id, borrador); setEditando(null); }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") { renombrar(s.id, borrador); setEditando(null); }
                          if (e.key === "Escape") setEditando(null);
                        }}
                      />
                    ) : (
                      <button
                        className="text-sm font-medium text-zinc-100 hover:underline"
                        onClick={() => { setEditando(s.id); setBorrador(s.nombre); }}
                        title="Clic para renombrar"
                      >
                        {s.nombre}
                      </button>
                    )}
                    {activa && (
                      <span className="rounded bg-emerald-700 px-1.5 py-0.5 text-[10px] font-medium text-white">
                        abierta
                      </span>
                    )}

                    <div className="ml-auto flex items-center gap-1">
                      <button
                        onClick={() => { abrir(s.id); router.push("/flowsheet"); }}
                        className="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-200 hover:bg-zinc-800"
                      >
                        Abrir
                      </button>
                      <button
                        onClick={() => exportar(s.id)}
                        className="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800"
                        title="Descargar como archivo .simproc.json"
                      >
                        Descargar
                      </button>
                      <button
                        onClick={() => duplicar(s.id)}
                        className="rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800"
                      >
                        Duplicar
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`¿Eliminar "${s.nombre}"? Esto no se puede deshacer.`)) eliminar(s.id);
                        }}
                        className="rounded border border-zinc-800 px-2 py-1 text-[11px] text-red-400 hover:bg-red-950/50"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 text-[11px] text-zinc-500">{resumen(s)}</div>
                  <div className="text-[10px] text-zinc-600">
                    creada {fecha(s.creada)} · modificada {fecha(s.modificada)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
