"use client";

import { useEffect, useState } from "react";
import { useConfiguracion, type Componente } from "../components/SimulacionProvider";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ComponenteInfo {
  consulta: string;
  encontrado: boolean;
  nombre?: string;
  formula?: string;
  MW?: number;
  CAS?: string;
  Tb?: number;
  apto_unifac: boolean;
  mensaje?: string;
}

interface ModeloTermodinamico {
  id: string;
  nombre: string;
  descripcion: string;
  disponible: boolean;
}

const SUGERENCIAS = ["benzene", "toluene", "ethanol", "water", "n-butane", "n-pentane", "acetone", "methanol"];

export default function ConfiguracionPage() {
  const { componentes, modelo, setComponentes, setModelo } = useConfiguracion();

  const [consulta, setConsulta] = useState("");
  const [encontrado, setEncontrado] = useState<ComponenteInfo | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [modelos, setModelos] = useState<ModeloTermodinamico[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/modelos-termodinamicos`)
      .then((r) => r.json())
      .then(setModelos)
      .catch(() => setModelos([]));
  }, []);

  async function buscar(texto = consulta) {
    if (!texto.trim()) return;
    setBuscando(true);
    setEncontrado(null);
    try {
      const resp = await fetch(`${API_URL}/componentes/buscar?q=${encodeURIComponent(texto)}`);
      setEncontrado(await resp.json());
    } catch {
      setEncontrado({ consulta: texto, encontrado: false, apto_unifac: false, mensaje: "No se pudo conectar con el backend." });
    } finally {
      setBuscando(false);
    }
  }

  function agregar(info: ComponenteInfo) {
    if (!info.nombre || componentes.some((c) => c.nombre === info.nombre)) return;
    const nuevo: Componente = { nombre: info.nombre, formula: info.formula, MW: info.MW, Tb: info.Tb };
    setComponentes([...componentes, nuevo]);
    setEncontrado(null);
    setConsulta("");
  }

  function quitar(nombre: string) {
    setComponentes(componentes.filter((c) => c.nombre !== nombre));
  }

  function mover(indice: number, delta: number) {
    const destino = indice + delta;
    if (destino < 0 || destino >= componentes.length) return;
    const copia = [...componentes];
    [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
    setComponentes(copia);
  }

  function ordenarPorVolatilidad() {
    // Tb creciente ~ de mas volatil a menos volatil. Es la aproximacion
    // estandar (el orden real de volatilidad puede invertirse con la
    // composicion, pero rara vez en el rango de una columna) y la misma
    // que usa AnalizadorFUG para clasificar componentes.
    setComponentes([...componentes].sort((a, b) => (a.Tb ?? Infinity) - (b.Tb ?? Infinity)));
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <h1 className="text-xl font-bold">Configuración de la simulación</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Define una sola vez los componentes y el modelo termodinámico. El flowsheet los usa para todas las
        operaciones y corrientes — así no puede haber listas distintas en cada sitio.
      </p>

      <section className="mt-6">
        <h2 className="mb-2 font-semibold">Componentes</h2>

        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-zinc-700 bg-zinc-800 p-2 text-sm"
            placeholder="nombre, fórmula o CAS (ej. ethanol, C6H6, 64-17-5)"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
          />
          <button
            onClick={() => buscar()}
            disabled={buscando}
            className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {buscando ? "..." : "Buscar"}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGERENCIAS.filter((s) => !componentes.some((c) => c.nombre === s)).map((s) => (
            <button
              key={s}
              onClick={() => { setConsulta(s); buscar(s); }}
              className="rounded-full border border-zinc-700 px-2.5 py-0.5 text-[11px] text-zinc-400 hover:border-emerald-500 hover:text-zinc-100"
            >
              {s}
            </button>
          ))}
        </div>

        {encontrado && (
          <div
            className={`mt-3 rounded border p-3 text-sm ${
              !encontrado.encontrado
                ? "border-red-800 bg-red-950/40"
                : encontrado.apto_unifac
                ? "border-emerald-700 bg-emerald-950/30"
                : "border-amber-700 bg-amber-950/30"
            }`}
          >
            {encontrado.encontrado ? (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <strong>{encontrado.nombre}</strong>{" "}
                    <span className="text-zinc-400">
                      {encontrado.formula} · MW {encontrado.MW?.toFixed(2)} · CAS {encontrado.CAS}
                      {encontrado.Tb ? ` · Tb ${encontrado.Tb.toFixed(2)} K` : ""}
                    </span>
                  </div>
                  {encontrado.apto_unifac && (
                    <button onClick={() => agregar(encontrado)} className="rounded bg-emerald-600 px-3 py-1 text-xs text-white hover:bg-emerald-500">
                      Agregar
                    </button>
                  )}
                </div>
                {encontrado.mensaje && <p className="mt-1 text-xs text-amber-200">{encontrado.mensaje}</p>}
              </>
            ) : (
              <p className="text-xs text-red-200">{encontrado.mensaje}</p>
            )}
          </div>
        )}

        <div className="mt-4 rounded border border-zinc-800 bg-zinc-900">
          <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
            <span className="text-xs text-zinc-400">
              {componentes.length} componente{componentes.length === 1 ? "" : "s"} · el orden importa (índice 0 = más ligero por convención)
            </span>
            <button onClick={ordenarPorVolatilidad} className="text-xs text-emerald-400 hover:text-emerald-300">
              ordenar por Tb
            </button>
          </div>
          {componentes.length === 0 ? (
            <p className="px-3 py-4 text-sm text-zinc-500">Ningún componente todavía.</p>
          ) : (
            componentes.map((c, i) => (
              <div key={c.nombre} className="flex items-center gap-3 border-b border-zinc-800 px-3 py-2 last:border-b-0">
                <span className="w-6 font-mono text-xs text-zinc-500">{i}</span>
                <div className="flex-1">
                  <div className="text-sm">{c.nombre}</div>
                  <div className="text-[11px] text-zinc-500">
                    {c.formula}
                    {c.Tb ? ` · Tb ${c.Tb.toFixed(2)} K (${(c.Tb - 273.15).toFixed(1)} °C)` : ""}
                  </div>
                </div>
                <button onClick={() => mover(i, -1)} disabled={i === 0} className="px-1 text-zinc-500 hover:text-zinc-100 disabled:opacity-30">↑</button>
                <button onClick={() => mover(i, 1)} disabled={i === componentes.length - 1} className="px-1 text-zinc-500 hover:text-zinc-100 disabled:opacity-30">↓</button>
                <button onClick={() => quitar(c.nombre)} className="px-1 text-red-400 hover:text-red-300">×</button>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 font-semibold">Modelo termodinámico</h2>
        {modelos.map((m) => (
          <label
            key={m.id}
            className={`mb-2 flex cursor-pointer gap-3 rounded border p-3 ${
              modelo === m.id ? "border-emerald-600 bg-emerald-950/20" : "border-zinc-800 bg-zinc-900"
            }`}
          >
            <input type="radio" name="modelo" checked={modelo === m.id} onChange={() => setModelo(m.id)} className="mt-1" />
            <div>
              <div className="text-sm font-medium">{m.nombre}</div>
              <div className="text-xs text-zinc-400">{m.descripcion}</div>
            </div>
          </label>
        ))}
        <p className="text-[11px] text-zinc-500">
          Hoy hay un solo modelo implementado. Agregar NRTL, Wilson o una ecuación de estado significa una rama nueva
          en <code>ProveedorTermodinamico</code>, no un cambio en esta pantalla.
        </p>
      </section>
    </div>
  );
}
