"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const PARES_COMUNES = [
  { nombres: ["benzene", "toluene"], etiqueta: "Benceno / Tolueno", nota: "casi ideal, sin azeótropo" },
  { nombres: ["ethanol", "water"], etiqueta: "Etanol / Agua", nota: "azeótropo clásico ~89% mol" },
  { nombres: ["acetone", "chloroform"], etiqueta: "Acetona / Cloroformo", nota: "azeótropo de máxima T" },
  { nombres: ["methanol", "water"], etiqueta: "Metanol / Agua", nota: "sin azeótropo" },
];

interface RespuestaELV {
  nombres: string[];
  P: number;
  x: number[];
  y: number[];
  T: number[];
  Tb_ligero: number;
  Tb_pesado: number;
  azeotropo: { x: number; T: number } | null;
}

export default function ELVPage() {
  const [ligero, setLigero] = useState("ethanol");
  const [pesado, setPesado] = useState("water");
  const [presion, setPresion] = useState(101325);
  const [nPuntos, setNPuntos] = useState(60);

  const [datos, setDatos] = useState<RespuestaELV | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function calcular(nombreLigero = ligero, nombrePesado = pesado, P = presion, n = nPuntos) {
    setCargando(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/elv/binario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombres: [nombreLigero, nombrePesado], P, n_puntos: n }),
      });
      if (!resp.ok) {
        const detalle = await resp.json().catch(() => null);
        throw new Error(detalle?.detail ?? `Error HTTP ${resp.status}`);
      }
      setDatos(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setDatos(null);
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    calcular();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const datosYX = datos ? datos.x.map((xi, i) => ({ x: xi, y: datos.y[i], diagonal: xi })) : [];

  // T-x-y: la curva de burbuja es (x_i, T_i) y la de rocío es (y_i, T_i).
  // Como x e y difieren punto a punto, se arma un solo arreglo con huecos
  // y se conectan con connectNulls (cada serie une solo sus propios puntos).
  const datosTxy = datos
    ? [
        ...datos.x.map((xi, i) => ({ c: xi, Tburbuja: datos.T[i], Trocio: null as number | null })),
        ...datos.y.map((yi, i) => ({ c: yi, Tburbuja: null as number | null, Trocio: datos.T[i] })),
      ].sort((a, b) => a.c - b.c)
    : [];

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6">
      <h1 className="text-xl font-bold">Equilibrio líquido-vapor</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Cada punto es un cálculo completo de punto de burbuja con UNIFAC (γ predictivo) + presiones de saturación de{" "}
        <code className="text-zinc-300">thermo</code> — no una correlación ajustada.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {PARES_COMUNES.map((par) => (
          <button
            key={par.etiqueta}
            title={par.nota}
            onClick={() => {
              setLigero(par.nombres[0]);
              setPesado(par.nombres[1]);
              calcular(par.nombres[0], par.nombres[1]);
            }}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs hover:border-emerald-500"
          >
            {par.etiqueta}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <label className="block text-[11px] text-zinc-400">componente ligero</label>
          <input className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5 text-sm" value={ligero} onChange={(e) => setLigero(e.target.value)} />
        </div>
        <div>
          <label className="block text-[11px] text-zinc-400">componente pesado</label>
          <input className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5 text-sm" value={pesado} onChange={(e) => setPesado(e.target.value)} />
        </div>
        <div>
          <label className="block text-[11px] text-zinc-400">P [Pa]</label>
          <input type="number" className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5 text-sm" value={presion} onChange={(e) => setPresion(Number(e.target.value))} />
        </div>
        <div>
          <label className="block text-[11px] text-zinc-400">puntos</label>
          <input type="number" className="w-full rounded border border-zinc-700 bg-zinc-800 p-1.5 text-sm" value={nPuntos} onChange={(e) => setNPuntos(Number(e.target.value))} />
        </div>
      </div>

      <button
        onClick={() => calcular()}
        disabled={cargando}
        className="mt-3 rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {cargando ? "Calculando..." : "Calcular"}
      </button>

      {error && <p className="mt-3 rounded border border-red-800 bg-red-950/50 p-2 text-sm text-red-300">{error}</p>}

      {datos && (
        <>
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-zinc-400">
            <span>
              Tb {datos.nombres[0]}: <strong className="text-zinc-200">{datos.Tb_ligero.toFixed(2)} K</strong> ({(datos.Tb_ligero - 273.15).toFixed(1)} °C)
            </span>
            <span>
              Tb {datos.nombres[1]}: <strong className="text-zinc-200">{datos.Tb_pesado.toFixed(2)} K</strong> ({(datos.Tb_pesado - 273.15).toFixed(1)} °C)
            </span>
            {datos.azeotropo ? (
              <span className="text-amber-300">
                Azeótropo en x = {datos.azeotropo.x.toFixed(4)}, T = {datos.azeotropo.T.toFixed(2)} K (
                {(datos.azeotropo.T - 273.15).toFixed(1)} °C)
              </span>
            ) : (
              <span className="text-emerald-400">Sin azeótropo en este rango</span>
            )}
          </div>

          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
              <h2 className="mb-2 text-sm font-semibold">y — x ({datos.nombres[0]})</h2>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={datosYX} margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
                  <CartesianGrid stroke="#27272a" />
                  <XAxis
                    dataKey="x"
                    type="number"
                    domain={[0, 1]}
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    label={{ value: `x ${datos.nombres[0]}`, position: "insideBottom", offset: -10, fill: "#a1a1aa", fontSize: 11 }}
                  />
                  <YAxis domain={[0, 1]} tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
                    formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(4) : String(v ?? ""))}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="diagonal" stroke="#52525b" dot={false} strokeDasharray="4 4" name="y = x" />
                  <Line type="monotone" dataKey="y" stroke="#34d399" dot={false} strokeWidth={2} name="equilibrio" />
                  {datos.azeotropo && (
                    <ReferenceDot x={datos.azeotropo.x} y={datos.azeotropo.x} r={5} fill="#fbbf24" stroke="none" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
              <h2 className="mb-2 text-sm font-semibold">T — x — y</h2>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={datosTxy} margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
                  <CartesianGrid stroke="#27272a" />
                  <XAxis
                    dataKey="c"
                    type="number"
                    domain={[0, 1]}
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    label={{ value: `fracción molar ${datos.nombres[0]}`, position: "insideBottom", offset: -10, fill: "#a1a1aa", fontSize: 11 }}
                  />
                  <YAxis domain={["auto", "auto"]} tick={{ fill: "#a1a1aa", fontSize: 11 }} unit=" K" width={62} />
                  <Tooltip
                    contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
                    formatter={(v: unknown) => (typeof v === "number" ? `${v.toFixed(2)} K` : String(v ?? ""))}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Tburbuja" stroke="#60a5fa" dot={false} strokeWidth={2} connectNulls name="burbuja (líquido)" />
                  <Line type="monotone" dataKey="Trocio" stroke="#f472b6" dot={false} strokeWidth={2} connectNulls name="rocío (vapor)" />
                  {datos.azeotropo && (
                    <ReferenceDot x={datos.azeotropo.x} y={datos.azeotropo.T} r={5} fill="#fbbf24" stroke="none" />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <p className="mt-3 text-[11px] text-zinc-500">
            El azeótropo se estima interpolando dónde y(x) cruza la diagonal en este barrido. El cálculo riguroso
            (incluyendo azeótropos reactivos) vive en <code>core/analisis_nodos.py</code> y todavía no está expuesto aquí.
          </p>
        </>
      )}
    </div>
  );
}
