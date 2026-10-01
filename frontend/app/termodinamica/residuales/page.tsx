"use client";

import { useState } from "react";
import Link from "next/link";
import { useSimulacion, nombresDe } from "../../components/SimulacionProvider";
import DiagramaTernario, { type CurvaTernaria } from "../../components/DiagramaTernario";
import DiagramaCuaternario from "../../components/DiagramaCuaternario";
import DescargarGrafico from "../../components/DescargarGrafico";
import EsperaCalculo from "../../components/EsperaCalculo";
import FichaMetodo from "../../components/FichaMetodo";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface RespuestaMapa {
  componentes: string[];
  curvas: { inicio: number[]; puntos: number[][]; xi: number[] }[];
  curvas_fallidas: number;
  motivo_fallos: string | null;
  aviso_balance: string | null;
  trayectorias_reactivas: number[][][];
  curva_equilibrio_quimico: number[][];
  lineas_estequiometricas: number[][][];
  polo: { equimolar: boolean; x_pi: number[] | null; direccion: number[] | null } | null;
  T_vertices: (number | null)[];
  es_reactivo: boolean;
  Da: number;
  P_sistema: number;
}

export default function ResidualesPage() {
  const { componentes, listo } = useSimulacion();
  const nombres = nombresDe(componentes);
  const n = nombres.length;

  const [P, setP] = useState("101325");
  const [nCurvas, setNCurvas] = useState("24");
  const [xiMax, setXiMax] = useState("40");
  const [mapa, setMapa] = useState<RespuestaMapa | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function calcular() {
    setCargando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/termodinamica/mapa-residual`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          componentes: nombres,
          P_sistema: Number(P),
          reaccion: null,
          Da: 0,
          n_curvas: Number(nCurvas),
          n_puntos: 120,
          xi_max: Number(xiMax),
          incluir_trayectorias_discretas: false,
        }),
      });
      const datos = await r.json();
      if (!r.ok) throw new Error(datos?.detail ?? "el servidor rechazó la petición");
      setMapa(datos);
    } catch (e) {
      setMapa(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCargando(false);
    }
  }

  const curvas: CurvaTernaria[] = (mapa?.curvas ?? []).map((c) => ({ puntos: c.puntos, inicio: c.inicio }));

  return (
    <div className="min-h-0 flex-1 overflow-auto bg-zinc-950 px-6 py-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-1 flex items-baseline gap-3">
          <Link href="/termodinamica" className="text-xs text-zinc-500 hover:text-zinc-300">← Termodinámica</Link>
        </div>
        <h1 className="mb-1 text-lg font-semibold text-zinc-100">Curvas residuales</h1>
        <p className="mb-5 max-w-3xl text-xs text-zinc-500">
          Integra <code className="text-zinc-400">dx/dξ = x − y*(x)</code>: la composición del líquido que queda en
          un alambique mientras hierve. Cada curva termina en un <strong className="text-zinc-400">nodo estable</strong>{" "}
          (el componente o azeótropo menos volátil de su región). Si el triángulo queda partido en regiones, esas
          fronteras no se pueden cruzar con destilación simple, por muchas etapas que pongas.
        </p>

        {listo && n !== 3 && n !== 4 && (
          <div className="rounded border border-amber-800 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
            Esta herramienta necesita 3 o 4 componentes; la simulación tiene {n}.{" "}
            <Link href="/configuracion" className="underline">Cámbialos aquí</Link>.
          </div>
        )}

        {(n === 3 || n === 4) && (
          <>
            <div className="mb-4 flex flex-wrap items-end gap-3 rounded border border-zinc-800 bg-zinc-900 p-3">
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">Presión [Pa]</span>
                <input
                  className="w-28 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={P} onChange={(e) => setP(e.target.value)}
                />
              </label>
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">Curvas</span>
                <input
                  className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={nCurvas} onChange={(e) => setNCurvas(e.target.value)}
                />
              </label>
              <label className="text-xs">
                <span className="mb-1 block text-zinc-400">ξ máximo</span>
                <input
                  className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-right font-mono text-xs text-zinc-100"
                  value={xiMax} onChange={(e) => setXiMax(e.target.value)}
                />
              </label>
              <button
                onClick={calcular}
                disabled={cargando}
                className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {cargando ? "Integrando…" : "Calcular mapa"}
              </button>
              <span className="text-[10px] text-zinc-600">
                Cada curva resuelve un punto de burbuja con UNIFAC en cada paso: tarda segundos, no milisegundos.
              </span>
            </div>

            <EsperaCalculo
              activa={cargando}
              titulo="Integrando trayectorias"
              detalle="Cada curva resuelve un punto de burbuja con UNIFAC en cada paso del integrador."
              segundosEsperados={25}
            />

            <div className="mb-4">
              <FichaMetodo metodo="curvas_residuales" />
            </div>

            {error && (
              <div className="mb-4 rounded border border-red-800 bg-red-950/40 px-3 py-2 text-xs text-red-200">
                {error}
              </div>
            )}

            {mapa && mapa.curvas_fallidas > 0 && (
              <div className="mb-4 rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-[11px] text-amber-200">
                {mapa.curvas_fallidas} de {mapa.curvas.length + mapa.curvas_fallidas} trayectorias no se pudieron
                integrar y no se dibujan.
                {mapa.motivo_fallos && <> Primer motivo: <span className="font-mono">{mapa.motivo_fallos}</span></>}
              </div>
            )}

            {mapa && n === 3 && (
              <DescargarGrafico nombre={`curvas-residuales-${nombres.join("-")}`}>
                <DiagramaTernario
                  componentes={mapa.componentes}
                  curvas={curvas}
                  T_vertices={mapa.T_vertices}
                  titulo="Mapa de curvas residuales"
                  subtitulo={`${mapa.curvas.length} trayectorias · ${(mapa.P_sistema / 1000).toFixed(1)} kPa · sin reacción`}
                />
              </DescargarGrafico>
            )}

            {mapa && n === 4 && (
              <DiagramaCuaternario
                componentes={mapa.componentes}
                curvas={curvas}
                titulo="Mapa de curvas residuales (4 componentes)"
                subtitulo={`${mapa.curvas.length} trayectorias · ${(mapa.P_sistema / 1000).toFixed(1)} kPa`}
              />
            )}

            {!mapa && !cargando && !error && (
              <p className="rounded border border-dashed border-zinc-800 px-4 py-10 text-center text-xs text-zinc-500">
                Pulsa «Calcular mapa» para integrar las trayectorias.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
