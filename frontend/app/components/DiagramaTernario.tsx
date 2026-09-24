"use client";

import { useMemo, useState } from "react";

/**
 * Diagrama ternario en SVG puro. No se trajo ninguna libreria para esto
 * a proposito: un triangulo baricentrico son cuatro lineas de algebra, y
 * las alternativas (plotly) pesan megabytes y traen su propio tema que
 * habria que pelear para que encaje con el resto de la aplicacion.
 *
 *   (a,b,c) con a+b+c=1  ->  P = a*A + b*B + c*C
 *
 * A abajo-izquierda, B abajo-derecha, C arriba: la convencion habitual
 * de los mapas de curvas residuales.
 */

export interface CurvaTernaria {
  puntos: number[][];   // [[a,b,c], ...]
  inicio?: number[];
}

export interface PuntoMarcado {
  x: number[];          // [a,b,c]
  etiqueta: string;
  color?: string;
  T?: number | null;
}

const LADO = 560;
const MARGEN = 56;
const ALTO_TRI = (LADO * Math.sqrt(3)) / 2;

const A = { x: 0, y: ALTO_TRI };
const B = { x: LADO, y: ALTO_TRI };
const C = { x: LADO / 2, y: 0 };

function proyectar(comp: number[]) {
  const [a, b, c] = comp;
  return {
    x: a * A.x + b * B.x + c * C.x + MARGEN,
    y: a * A.y + b * B.y + c * C.y + MARGEN,
  };
}

const aRuta = (puntos: number[][]) =>
  puntos.map((p, i) => {
    const { x, y } = proyectar(p);
    return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");

export interface PoloGeometrico {
  equimolar: boolean;
  x_pi: number[] | null;
  direccion: number[] | null;
}

export default function DiagramaTernario({
  componentes, curvas, marcados = [], T_vertices = [], titulo, subtitulo, mostrarFlechas = true,
  trayectoriasReactivas = [], curvaEquilibrio = [], lineasEstequiometricas = [], polo = null,
}: {
  componentes: string[];
  curvas: CurvaTernaria[];
  marcados?: PuntoMarcado[];
  T_vertices?: (number | null)[];
  titulo?: string;
  subtitulo?: string;
  mostrarFlechas?: boolean;
  /** Mapeo discreto etapa a etapa (salto físico + químico) del método original. */
  trayectoriasReactivas?: number[][][];
  /** Lugar donde se cumple K_eq(T). */
  curvaEquilibrio?: number[][];
  /** Rectas de reacción pura; todas pasan por el polo. */
  lineasEstequiometricas?: number[][][];
  polo?: PoloGeometrico | null;
}) {
  const [resaltada, setResaltada] = useState<number | null>(null);
  const [capas, setCapas] = useState({
    residuales: true, reactivas: true, equilibrio: true, estequiometricas: true,
  });

  // El polo pi = nu/nu_tot cae MUY a menudo fuera del triángulo (con
  // nu=[-1,-1,3] sale en (-1,-1,3)). Dibujarlo dentro sería mentir, así
  // que solo se pinta si de verdad cae en el lienzo; si no, se cita en
  // el pie con sus coordenadas y se ven igual las rectas que apuntan a él.
  const poloProyectado = polo && !polo.equimolar && polo.x_pi ? proyectar(polo.x_pi) : null;
  const poloVisible =
    poloProyectado !== null &&
    poloProyectado.x > 0 && poloProyectado.x < LADO + MARGEN * 2 &&
    poloProyectado.y > 0 && poloProyectado.y < ALTO_TRI + MARGEN * 2;

  const rejilla = useMemo(() => {
    const lineas: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (let i = 1; i < 10; i++) {
      const f = i / 10;
      // Tres familias de paralelas, una por componente constante.
      const pares: [number[], number[]][] = [
        [[f, 1 - f, 0], [f, 0, 1 - f]],
        [[1 - f, f, 0], [0, f, 1 - f]],
        [[1 - f, 0, f], [0, 1 - f, f]],
      ];
      for (const [p1, p2] of pares) {
        const a = proyectar(p1);
        const b = proyectar(p2);
        lineas.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y });
      }
    }
    return lineas;
  }, []);

  const borde = [A, B, C].map((p) => `${p.x + MARGEN},${p.y + MARGEN}`).join(" ");

  // Punta de flecha a media curva: sin ella el mapa no dice hacia DONDE
  // avanza el residuo, que es justo la informacion que lo hace util.
  const flechas = useMemo(() => {
    if (!mostrarFlechas) return [];
    return curvas.map((c) => {
      const pts = c.puntos;
      if (pts.length < 4) return null;
      const i = Math.floor(pts.length * 0.55);
      const p1 = proyectar(pts[i - 1]);
      const p2 = proyectar(pts[i]);
      const ang = Math.atan2(p2.y - p1.y, p2.x - p1.x);
      if (!Number.isFinite(ang)) return null;
      return { x: p2.x, y: p2.y, grados: (ang * 180) / Math.PI };
    });
  }, [curvas, mostrarFlechas]);

  const etiquetaVertice = (i: number) => {
    const T = T_vertices[i];
    return T ? `${componentes[i]} · ${T.toFixed(1)} K` : componentes[i];
  };

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      {(titulo || subtitulo) && (
        <div className="mb-1 flex flex-wrap items-baseline gap-x-3">
          {titulo && <h3 className="text-sm font-semibold text-zinc-100">{titulo}</h3>}
          {subtitulo && <span className="text-xs text-zinc-400">{subtitulo}</span>}
        </div>
      )}

      <svg
        viewBox={`0 0 ${LADO + MARGEN * 2} ${ALTO_TRI + MARGEN * 2}`}
        className="w-full"
        style={{ maxHeight: 620 }}
      >
        <rect width="100%" height="100%" fill="#18181b" />

        {rejilla.map((l, i) => (
          <line key={i} {...l} stroke="#27272a" strokeWidth={1} />
        ))}
        <polygon points={borde} fill="none" stroke="#52525b" strokeWidth={1.5} />

        {/* Rectas estequiométricas: van primero, al fondo, porque son el
            MARCO de referencia sobre el que se leen las trayectorias. */}
        {capas.estequiometricas && lineasEstequiometricas.map((linea, i) => (
          <path key={`e${i}`} d={aRuta(linea)} fill="none"
            stroke="#f87171" strokeWidth={1.2} strokeOpacity={0.5} strokeDasharray="3 3" />
        ))}

        {/* Curva de equilibrio químico: donde la reacción deja de empujar. */}
        {capas.equilibrio && curvaEquilibrio.length > 1 && (
          <path d={aRuta(curvaEquilibrio)} fill="none" stroke="#fafafa" strokeWidth={2.2} strokeOpacity={0.9} />
        )}

        {/* Mapeo discreto etapa a etapa: es el que dibuja el libro. */}
        {capas.reactivas && trayectoriasReactivas.map((t, i) => (
          <g key={`r${i}`}>
            <path d={aRuta(t)} fill="none" stroke="#c084fc" strokeWidth={1.4} strokeOpacity={0.75} />
            {t.map((p, j) => {
              const q = proyectar(p);
              return <circle key={j} cx={q.x} cy={q.y} r={1.6} fill="#c084fc" fillOpacity={0.9} />;
            })}
          </g>
        ))}

        {capas.residuales && curvas.map((c, i) => (
          <path
            key={i}
            d={aRuta(c.puntos)}
            fill="none"
            stroke={resaltada === i ? "#f4f4f5" : "#38bdf8"}
            strokeWidth={resaltada === i ? 2.4 : 1.3}
            strokeOpacity={resaltada === null || resaltada === i ? 0.85 : 0.22}
            onMouseEnter={() => setResaltada(i)}
            onMouseLeave={() => setResaltada(null)}
            style={{ cursor: "crosshair" }}
          />
        ))}

        {poloVisible && poloProyectado && (
          <g>
            <circle cx={poloProyectado.x} cy={poloProyectado.y} r={5} fill="none" stroke="#f87171" strokeWidth={2} />
            <text x={poloProyectado.x + 9} y={poloProyectado.y + 4} fill="#f87171" fontSize={12}>π</text>
          </g>
        )}

        {capas.residuales && flechas.map((f, i) =>
          f ? (
            <polygon
              key={`f${i}`}
              points="0,-3.2 7,0 0,3.2"
              fill="#38bdf8"
              fillOpacity={resaltada === null || resaltada === i ? 0.9 : 0.2}
              transform={`translate(${f.x},${f.y}) rotate(${f.grados})`}
            />
          ) : null
        )}

        {/* Punto de partida de cada curva: deja ver de donde arranca el mapa. */}
        {capas.residuales && curvas.map((c, i) =>
          c.inicio ? (
            <circle
              key={`i${i}`}
              cx={proyectar(c.inicio).x}
              cy={proyectar(c.inicio).y}
              r={2}
              fill="#a3e635"
              fillOpacity={0.75}
            />
          ) : null
        )}

        {marcados.map((m, i) => {
          const p = proyectar(m.x);
          return (
            <g key={`m${i}`}>
              <circle cx={p.x} cy={p.y} r={6} fill={m.color ?? "#fbbf24"} stroke="#18181b" strokeWidth={1.5} />
              <text x={p.x + 10} y={p.y + 4} fill={m.color ?? "#fbbf24"} fontSize={12}>
                {m.etiqueta}
                {m.T ? ` (${m.T.toFixed(1)} K)` : ""}
              </text>
            </g>
          );
        })}

        <text x={MARGEN - 6} y={ALTO_TRI + MARGEN + 20} fill="#e4e4e7" fontSize={13} textAnchor="start">
          {etiquetaVertice(0)}
        </text>
        <text x={LADO + MARGEN + 6} y={ALTO_TRI + MARGEN + 20} fill="#e4e4e7" fontSize={13} textAnchor="end">
          {etiquetaVertice(1)}
        </text>
        <text x={LADO / 2 + MARGEN} y={MARGEN - 14} fill="#e4e4e7" fontSize={13} textAnchor="middle">
          {etiquetaVertice(2)}
        </text>
      </svg>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        <Capa activa={capas.residuales} color="#38bdf8" etiqueta="curvas residuales (líquido → pesado)"
          onClick={() => setCapas((c) => ({ ...c, residuales: !c.residuales }))} />
        {trayectoriasReactivas.length > 0 && (
          <Capa activa={capas.reactivas} color="#c084fc" etiqueta="líneas de destilación reactiva (vapor → ligero)"
            onClick={() => setCapas((c) => ({ ...c, reactivas: !c.reactivas }))} />
        )}
        {curvaEquilibrio.length > 1 && (
          <Capa activa={capas.equilibrio} color="#fafafa" etiqueta="equilibrio químico"
            onClick={() => setCapas((c) => ({ ...c, equilibrio: !c.equilibrio }))} />
        )}
        {lineasEstequiometricas.length > 0 && (
          <Capa activa={capas.estequiometricas} color="#f87171" etiqueta="líneas estequiométricas"
            onClick={() => setCapas((c) => ({ ...c, estequiometricas: !c.estequiometricas }))} />
        )}
      </div>

      <p className="mt-1 text-[11px] leading-snug text-zinc-500">
        Cada <span className="text-sky-400">curva residual</span> es la trayectoria del líquido que queda al
        evaporar; la flecha marca hacia dónde avanza y el <span className="text-lime-400">punto verde</span> dónde
        empieza. Terminan en el componente (o azeótropo) menos volátil de su región: si el mapa se parte en zonas
        que no se comunican, esas fronteras son las que impiden separar por destilación simple.
        {lineasEstequiometricas.length > 0 && (
          <>
            {" "}Las <span className="text-purple-400">líneas de destilación reactiva</span> son el mapeo
            etapa a etapa del método original y van en sentido CONTRARIO a las residuales: cada etapa toma el
            VAPOR en equilibrio, así que avanzan hacia el componente más volátil, mientras que el residuo se
            enriquece en el más pesado. Que apunten a vértices opuestos es lo correcto, no un error.
            {" "}Las <span className="text-red-400">líneas estequiométricas</span> son el camino que sigue la
            composición por reacción pura, sin separar nada; todas pasan por el polo{" "}
            <span className="text-red-400">π = ν/ν_tot</span>
            {polo && !polo.equimolar && polo.x_pi && (
              <>
                {" "}= ({polo.x_pi.map((v) => v.toFixed(2)).join(", ")})
                {!poloVisible && <span className="text-zinc-600"> — cae fuera del triángulo, por eso no se dibuja</span>}
              </>
            )}
            {polo?.equimolar && (
              <>
                , que aquí se va al <strong>infinito</strong> porque la reacción es equimolar (ν_tot = 0): esas
                rectas salen paralelas
              </>
            )}
            .
          </>
        )}
        {curvaEquilibrio.length > 1 && (
          <>
            {" "}La <span className="text-zinc-100">curva de equilibrio químico</span> es donde la reacción deja
            de empujar en un sentido: a cada lado de ella el avance cambia de signo.
          </>
        )}
      </p>
    </div>
  );
}

/** Conmutador de capa: el mapa lleva cuatro familias de líneas encima y
 *  conviene poder apagarlas para leer una sola. */
function Capa({ activa, color, etiqueta, onClick }: {
  activa: boolean; color: string; etiqueta: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-1.5 py-0.5 transition-opacity hover:bg-zinc-800 ${
        activa ? "opacity-100" : "opacity-40"
      }`}
      title={activa ? "Ocultar esta capa" : "Mostrar esta capa"}
    >
      <span className="inline-block h-0.5 w-4" style={{ background: color }} />
      <span className="text-zinc-400">{etiqueta}</span>
    </button>
  );
}
