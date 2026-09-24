"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceDot } from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface RespuestaELV {
  nombres: string[];
  x: number[];
  y: number[];
  T: number[];
  Tb_ligero: number;
  Tb_pesado: number;
  azeotropo: { x: number; T: number } | null;
}

/**
 * Curva de equilibrio del par de componentes del diagrama, para tenerla
 * junto al reporte sin ir a otra pantalla. Se pide una sola vez por par
 * (cada punto es un calculo de burbuja completo con UNIFAC).
 */
export default function GraficaELV({ nombres, P = 101325 }: { nombres: string[]; P?: number }) {
  const [datos, setDatos] = useState<RespuestaELV | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (nombres.length !== 2) return;
    setDatos(null);
    setError(null);
    fetch(`${API_URL}/elv/binario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombres, P, n_puntos: 50 }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("no se pudo calcular el ELV"))))
      .then(setDatos)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [nombres.join(","), P]);

  if (nombres.length !== 2) return null;
  if (error) return <p className="text-xs text-red-400">{error}</p>;
  if (!datos) return <p className="text-xs text-zinc-500">Calculando el equilibrio de {nombres.join(" / ")}…</p>;

  const filas = datos.x.map((x, i) => ({ x, y: datos.y[i], diagonal: x }));

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-4">
        <h3 className="text-sm font-semibold">Equilibrio líquido-vapor · {datos.nombres.join(" / ")}</h3>
        {datos.azeotropo ? (
          <span className="text-xs text-amber-300">
            Azeótropo en x = {datos.azeotropo.x.toFixed(4)} ({(datos.azeotropo.T - 273.15).toFixed(1)} °C) — no se
            puede cruzar por destilación simple
          </span>
        ) : (
          <span className="text-xs text-emerald-400">Sin azeótropo</span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={filas} margin={{ top: 5, right: 10, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#27272a" />
          <XAxis dataKey="x" type="number" domain={[0, 1]} tick={{ fill: "#a1a1aa", fontSize: 11 }}
            label={{ value: `x ${datos.nombres[0]}`, position: "insideBottom", offset: -10, fill: "#a1a1aa", fontSize: 11 }} />
          <YAxis domain={[0, 1]} tick={{ fill: "#a1a1aa", fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
            formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(4) : String(v ?? ""))} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="diagonal" stroke="#52525b" dot={false} strokeDasharray="4 4" name="y = x" isAnimationActive={false} />
          <Line dataKey="y" stroke="#34d399" dot={false} strokeWidth={2} name="equilibrio" isAnimationActive={false} />
          {datos.azeotropo && <ReferenceDot x={datos.azeotropo.x} y={datos.azeotropo.x} r={5} fill="#fbbf24" stroke="none" />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
