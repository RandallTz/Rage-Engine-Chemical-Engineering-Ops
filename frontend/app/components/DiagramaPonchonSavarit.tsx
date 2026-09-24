"use client";

import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, ReferenceDot,
} from "recharts";

export interface DatosDiagramaPS {
  tipo: "ponchon_savarit";
  x_saturacion: number[];
  H_liquido: number[];
  H_vapor: number[];
  escalera: number[][];
  tie_lines: number[][];
  lineas_operativas: number[][];
  x_delta_D: number;
  H_delta_D: number;
  x_delta_B: number;
  H_delta_B: number;
  z_F: number;
  H_F: number;
  x_D: number;
  x_B: number;
  Qc_D: number;
  QR_B: number;
  Qc_D_min: number | null;
  N: number;
}

// El nucleo trabaja en J/mol; a la vista le sientan mejor los kJ/mol
// (los polos andan en decenas de miles y los ejes se vuelven ilegibles).
const kJ = (j: number) => j / 1000;

interface Fila {
  x: number;
  liq?: number;
  vap?: number;
  esc?: number;
}

export default function DiagramaPonchonSavarit({
  datos, nombreLigero,
}: { datos: DatosDiagramaPS; nombreLigero: string }) {
  // Los polos quedan MUY lejos de las curvas de saturacion (aqui, +78 y
  // -57 kJ/mol contra 8..48): mostrarlos es la esencia del metodo, pero
  // aplasta la zona donde de verdad se leen las etapas. Por eso se puede
  // alternar, en vez de elegir una sola escala y perder la otra mitad.
  const [verPolos, setVerPolos] = useState(true);

  const filas: Fila[] = [
    ...datos.x_saturacion.map((x, i) => ({ x, liq: kJ(datos.H_liquido[i]) })),
    ...datos.x_saturacion.map((x, i) => ({ x, vap: kJ(datos.H_vapor[i]) })),
    ...datos.escalera.map(([x, H]) => ({ x, esc: kJ(H) })),
  ];

  const Hs = [...datos.H_liquido, ...datos.H_vapor].map(kJ);
  const minSat = Math.min(...Hs);
  const maxSat = Math.max(...Hs);
  const margen = (maxSat - minSat) * 0.12;

  const dominioY: [number, number] = verPolos
    ? [kJ(datos.H_delta_B) - margen, kJ(datos.H_delta_D) + margen]
    : [minSat - margen, maxSat + margen];

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="text-sm font-semibold">Construcción de Ponchon-Savarit</h3>
        <span className="text-xs text-zinc-400">
          N = <strong className="text-zinc-100">{datos.N.toFixed(3)}</strong> etapas · Q<sub>c</sub>/D ={" "}
          {kJ(datos.Qc_D).toFixed(2)} kJ/mol
          {datos.Qc_D_min !== null && (
            <>
              {" "}· mínimo {kJ(datos.Qc_D_min).toFixed(2)} ·{" "}
              {(datos.Qc_D / datos.Qc_D_min).toFixed(3)}× el mínimo
            </>
          )}
        </span>
        <button
          onClick={() => setVerPolos((v) => !v)}
          className="ml-auto rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800"
          title="Los polos están muy lejos de las curvas de saturación: verlos completos encoge la zona de las etapas."
        >
          {verPolos ? "Acercar a las etapas" : "Ver los polos"}
        </button>
      </div>

      <ResponsiveContainer width="100%" height={430}>
        <LineChart data={filas} margin={{ top: 5, right: 16, bottom: 22, left: 8 }}>
          <CartesianGrid stroke="#27272a" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 1]}
            ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            label={{ value: `x, y ${nombreLigero}`, position: "insideBottom", offset: -12, fill: "#a1a1aa", fontSize: 11 }}
          />
          <YAxis
            type="number"
            domain={dominioY}
            allowDataOverflow
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            tickFormatter={(v: number) => v.toFixed(0)}
            label={{ value: "H [kJ/mol]", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
            formatter={(v: unknown) => (typeof v === "number" ? `${v.toFixed(2)} kJ/mol` : String(v ?? ""))}
            labelFormatter={(x: unknown) => `x = ${typeof x === "number" ? x.toFixed(4) : x}`}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />

          {/* Rectas de reparto: unen cada liquido con SU vapor en equilibrio.
              Van como ReferenceLine porque son segmentos sueltos, no una
              serie continua -- meterlas en el mismo 'data' obligaria a
              intercalar huecos y recharts las uniria mal. */}
          {datos.tie_lines.map(([x, HL, y, HV], i) => (
            <ReferenceLine
              key={`t${i}`}
              segment={[{ x, y: kJ(HL) }, { x: y, y: kJ(HV) }]}
              stroke="#34d399"
              strokeWidth={1}
              strokeOpacity={0.55}
              ifOverflow="hidden"
            />
          ))}

          {/* Rectas operativas: del polo activo al punto de la etapa. */}
          {datos.lineas_operativas.map(([xp, Hp, , , y, HV], i) => (
            <ReferenceLine
              key={`o${i}`}
              segment={[{ x: xp, y: kJ(Hp) }, { x: y, y: kJ(HV) }]}
              stroke="#60a5fa"
              strokeWidth={1}
              strokeOpacity={0.4}
              strokeDasharray="3 3"
              ifOverflow="hidden"
            />
          ))}

          {/* La recta global Delta_D -- F -- Delta_B: es el balance de
              energia de toda la columna hecho geometria. */}
          <ReferenceLine
            segment={[
              { x: datos.x_delta_D, y: kJ(datos.H_delta_D) },
              { x: datos.x_delta_B, y: kJ(datos.H_delta_B) },
            ]}
            stroke="#fbbf24"
            strokeWidth={1.5}
            strokeDasharray="6 3"
            ifOverflow="hidden"
          />

          <Line dataKey="liq" stroke="#38bdf8" dot={false} strokeWidth={2} connectNulls name="líquido saturado" isAnimationActive={false} />
          <Line dataKey="vap" stroke="#fb7185" dot={false} strokeWidth={2} connectNulls name="vapor saturado" isAnimationActive={false} />
          <Line dataKey="esc" stroke="#f4f4f5" dot={false} strokeWidth={1.2} connectNulls name="etapas" isAnimationActive={false} />

          <ReferenceDot x={datos.x_delta_D} y={kJ(datos.H_delta_D)} r={4} fill="#fbbf24" stroke="none" ifOverflow="hidden" />
          <ReferenceDot x={datos.x_delta_B} y={kJ(datos.H_delta_B)} r={4} fill="#fbbf24" stroke="none" ifOverflow="hidden" />
          <ReferenceDot x={datos.z_F} y={kJ(datos.H_F)} r={4} fill="#a3e635" stroke="none" ifOverflow="hidden" />
        </LineChart>
      </ResponsiveContainer>

      <p className="mt-1 text-[11px] text-zinc-500">
        Polos <span className="text-amber-400">Δ</span>: Δ<sub>D</sub> = ({datos.x_delta_D},{" "}
        {kJ(datos.H_delta_D).toFixed(1)} kJ/mol) y Δ<sub>B</sub> = ({datos.x_delta_B},{" "}
        {kJ(datos.H_delta_B).toFixed(1)}). Que Δ<sub>D</sub>, F y Δ<sub>B</sub> caigan en una recta{" "}
        <span className="text-amber-400">no es un adorno</span>: es el balance de energía global de la columna.
        Las <span className="text-emerald-400">rectas de reparto</span> son equilibrio líquido-vapor; las{" "}
        <span className="text-sky-400">operativas</span> salen del polo activo, que cambia de Δ<sub>D</sub> a
        Δ<sub>B</sub> al pasar la alimentación.
      </p>
    </div>
  );
}
