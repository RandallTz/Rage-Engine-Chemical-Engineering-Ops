"use client";

/** Gráfico XY en SVG para datos calculados por el núcleo. Escala lineal,
 * marcas «redondas», viewBox adaptable al ancho y paleta sobria. No
 * transforma ni suaviza los datos. */

export type Serie = { nombre: string; x: number[]; y: number[]; color?: string; estilo?: "linea" | "discontinua" | "puntos" };
export type Marca = { x: number; y: number; etiqueta: string; color?: string };

export const PALETA = ["#425e35", "#8a5a2b", "#2f6f8f", "#7a4f8c", "#a07a1c", "#5e6b75"];

function marcasRedondas(min: number, max: number, n = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) { const d = Math.abs(min) || 1; min -= d / 2; max += d / 2; }
  const paso0 = (max - min) / n;
  const mag = 10 ** Math.floor(Math.log10(paso0));
  const paso = [1, 2, 2.5, 5, 10].map(f => f * mag).find(p => p >= paso0) ?? 10 * mag;
  const r: number[] = [];
  for (let v = Math.ceil(min / paso) * paso; v <= max + paso * 1e-9; v += paso) r.push(Math.abs(v) < paso * 1e-9 ? 0 : v);
  return r;
}

export function formatoNumero(v: number): string {
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-3) return v.toExponential(2).replace("e+", "e");
  return Number(v.toPrecision(4)).toString();
}

export default function GraficoXY({ series, marcas = [], ejeX, ejeY, titulo, alto = 320, cero = false, limitesY }: {
  series: Serie[]; marcas?: Marca[]; ejeX: string; ejeY: string; titulo: string; alto?: number; cero?: boolean; limitesY?: [number, number];
}) {
  const ancho = 640, izq = 64, der = 16, sup = 18, inf = 46;
  const xs = series.flatMap(s => s.x).concat(marcas.map(m => m.x)).filter(Number.isFinite);
  const ys = series.flatMap(s => s.y).concat(marcas.map(m => m.y)).filter(Number.isFinite);
  if (!xs.length || !ys.length) return <p className="adim-grafico-vacio">Sin datos para graficar.</p>;
  let [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  let [y0, y1] = limitesY ?? [Math.min(...ys, ...(cero ? [0] : [])), Math.max(...ys, ...(cero ? [0] : []))];
  if (x0 === x1) { x0 -= 0.5; x1 += 0.5; }
  if (y0 === y1) { const d = Math.abs(y0) || 1; y0 -= d / 2; y1 += d / 2; }
  const margenY = (y1 - y0) * 0.06; y0 -= margenY; y1 += margenY;
  const px = (x: number) => izq + (x - x0) / (x1 - x0) * (ancho - izq - der);
  const py = (y: number) => sup + (1 - (y - y0) / (y1 - y0)) * (alto - sup - inf);
  const tx = marcasRedondas(x0, x1, 6), ty = marcasRedondas(y0, y1, 5);
  return (
    <figure className="adim-grafico">
      <svg viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={titulo} preserveAspectRatio="xMidYMid meet">
        <title>{titulo}</title>
        {ty.map(v => <g key={`y${v}`}><line x1={izq} x2={ancho - der} y1={py(v)} y2={py(v)} className="adim-grafico-rejilla" /><text x={izq - 8} y={py(v) + 4} textAnchor="end" className="adim-grafico-marca">{formatoNumero(v)}</text></g>)}
        {tx.map(v => <g key={`x${v}`}><line x1={px(v)} x2={px(v)} y1={sup} y2={alto - inf} className="adim-grafico-rejilla" /><text x={px(v)} y={alto - inf + 18} textAnchor="middle" className="adim-grafico-marca">{formatoNumero(v)}</text></g>)}
        {y0 < 0 && y1 > 0 && <line x1={izq} x2={ancho - der} y1={py(0)} y2={py(0)} className="adim-grafico-cero" />}
        <line x1={izq} x2={izq} y1={sup} y2={alto - inf} className="adim-grafico-eje" />
        <line x1={izq} x2={ancho - der} y1={alto - inf} y2={alto - inf} className="adim-grafico-eje" />
        {series.map((s, i) => {
          const color = s.color ?? PALETA[i % PALETA.length];
          const puntos = s.x.map((x, j) => [x, s.y[j]] as const).filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
          if (s.estilo === "puntos") return <g key={s.nombre}>{puntos.map(([x, y], j) => <circle key={j} cx={px(x)} cy={py(y)} r={2.2} fill={color} />)}</g>;
          return <polyline key={s.nombre} fill="none" stroke={color} strokeWidth={1.8} strokeDasharray={s.estilo === "discontinua" ? "5 4" : undefined}
            points={puntos.map(([x, y]) => `${px(x).toFixed(1)},${py(y).toFixed(1)}`).join(" ")} />;
        })}
        {marcas.map((m, i) => <g key={`m${i}`}><circle cx={px(m.x)} cy={py(m.y)} r={4.5} fill="none" stroke={m.color ?? "#2d3928"} strokeWidth={1.6} /><text x={px(m.x) + 7} y={py(m.y) - 7} className="adim-grafico-etiqueta">{m.etiqueta}</text></g>)}
        <text x={(izq + ancho - der) / 2} y={alto - 8} textAnchor="middle" className="adim-grafico-titulo-eje">{ejeX}</text>
        <text x={14} y={(sup + alto - inf) / 2} textAnchor="middle" transform={`rotate(-90 14 ${(sup + alto - inf) / 2})`} className="adim-grafico-titulo-eje">{ejeY}</text>
      </svg>
      {series.length > 1 && <figcaption className="adim-grafico-leyenda">{series.map((s, i) => <span key={s.nombre}><i style={{ background: s.color ?? PALETA[i % PALETA.length], opacity: s.estilo === "discontinua" ? 0.6 : 1 }} />{s.nombre}</span>)}</figcaption>}
    </figure>
  );
}
