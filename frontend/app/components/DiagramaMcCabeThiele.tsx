"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

export interface DatosDiagramaMT {
  tipo?: "mccabe_thiele";
  x_equilibrio: number[];
  y_equilibrio: number[];
  escalones: number[][];
  interseccion_rol_q: number[];
  z_F: number;
  q: number;
  x_D: number;
  x_B: number;
  R: number;
  R_min: number;
  N: number;
}

interface Fila {
  x: number;
  eq?: number;
  diag?: number;
  esc?: number;
  rol?: number;
  sol?: number;
  linea_q?: number;
}

export default function DiagramaMcCabeThiele({ datos, nombreLigero }: { datos: DatosDiagramaMT; nombreLigero: string }) {
  const [xInt, yInt] = datos.interseccion_rol_q;

  // Recharts une los puntos en el ORDEN DEL ARREGLO, no por x ordenada.
  // Eso permite concatenar series con recorridos distintos (la curva de
  // equilibrio sube monotona; el escalonamiento zigzaguea y baja) y que
  // cada Line, con connectNulls, una solo sus propios puntos.
  const filas: Fila[] = [
    ...datos.x_equilibrio.map((x, i) => ({ x, eq: datos.y_equilibrio[i] })),
    { x: 0, diag: 0 },
    { x: 1, diag: 1 },
    { x: datos.x_D, rol: datos.x_D },
    { x: xInt, rol: yInt },
    { x: xInt, sol: yInt },
    { x: datos.x_B, sol: datos.x_B },
    { x: datos.z_F, linea_q: datos.z_F },
    { x: xInt, linea_q: yInt },
    ...datos.escalones.map(([x, y]) => ({ x, esc: y })),
  ];

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold">Construcción de McCabe-Thiele</h3>
        <span className="text-xs text-zinc-400">
          N = <strong className="text-zinc-100">{datos.N.toFixed(3)}</strong> etapas · R = {datos.R.toFixed(4)} · R<sub>min</sub> ={" "}
          {datos.R_min.toFixed(4)} · R/R<sub>min</sub> = {(datos.R / datos.R_min).toFixed(3)}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={filas} margin={{ top: 5, right: 12, bottom: 22, left: 0 }}>
          <CartesianGrid stroke="#27272a" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 1]}
            ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            label={{ value: `x ${nombreLigero}`, position: "insideBottom", offset: -12, fill: "#a1a1aa", fontSize: 11 }}
          />
          <YAxis domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tick={{ fill: "#a1a1aa", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
            formatter={(v: unknown) => (typeof v === "number" ? v.toFixed(4) : String(v ?? ""))}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="diag" stroke="#52525b" dot={false} strokeDasharray="4 4" connectNulls name="y = x" isAnimationActive={false} />
          <Line dataKey="eq" stroke="#34d399" dot={false} strokeWidth={2} connectNulls name="equilibrio" isAnimationActive={false} />
          <Line dataKey="rol" stroke="#60a5fa" dot={false} strokeWidth={1.5} connectNulls name="rectificación" isAnimationActive={false} />
          <Line dataKey="sol" stroke="#c084fc" dot={false} strokeWidth={1.5} connectNulls name="agotamiento" isAnimationActive={false} />
          <Line dataKey="linea_q" stroke="#fbbf24" dot={false} strokeWidth={1.5} strokeDasharray="5 3" connectNulls name="línea q" isAnimationActive={false} />
          <Line dataKey="esc" stroke="#f4f4f5" dot={false} strokeWidth={1} connectNulls name="etapas" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>

      <p className="mt-1 text-[11px] text-zinc-500">
        x<sub>D</sub> = {datos.x_D} · z<sub>F</sub> = {datos.z_F} · x<sub>B</sub> = {datos.x_B} · q = {datos.q}. Cada
        escalón es una etapa teórica; la última se cuenta fraccionaria al truncar exactamente en x<sub>B</sub>.
      </p>
    </div>
  );
}
