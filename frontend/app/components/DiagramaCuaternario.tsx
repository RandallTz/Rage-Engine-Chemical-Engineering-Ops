"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Tetraedro de composicion para sistemas de 4 componentes, en canvas.
 *
 * Por que canvas y no SVG (al reves que el ternario): aqui hay que
 * repintar la escena entera en cada fotograma mientras se arrastra para
 * rotar, y con decenas de curvas de cientos de puntos cada una eso son
 * miles de nodos; en SVG el navegador tendria que rehacer el DOM entero
 * en cada movimiento del raton. Canvas dibuja pixeles y no guarda nada.
 *
 * La proyeccion es ortografica con dos angulos (yaw/pitch). No hace
 * falta perspectiva: en un diagrama de composicion la perspectiva
 * DISTORSIONA las proporciones, que es justo lo que se esta leyendo.
 */

export interface CurvaCuaternaria {
  puntos: number[][]; // [[a,b,c,d], ...]
  inicio?: number[];
}

// Vertices del tetraedro regular, centrados en el origen.
const VERTICES: [number, number, number][] = [
  [0, 0, 0],
  [1, 0, 0],
  [0.5, Math.sqrt(3) / 2, 0],
  [0.5, Math.sqrt(3) / 6, Math.sqrt(6) / 3],
];
const CENTRO: [number, number, number] = [
  (VERTICES[0][0] + VERTICES[1][0] + VERTICES[2][0] + VERTICES[3][0]) / 4,
  (VERTICES[0][1] + VERTICES[1][1] + VERTICES[2][1] + VERTICES[3][1]) / 4,
  (VERTICES[0][2] + VERTICES[1][2] + VERTICES[2][2] + VERTICES[3][2]) / 4,
];
const ARISTAS: [number, number][] = [[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]];

function aCartesiano(comp: number[]): [number, number, number] {
  let x = 0, y = 0, z = 0;
  for (let i = 0; i < 4; i++) {
    x += comp[i] * VERTICES[i][0];
    y += comp[i] * VERTICES[i][1];
    z += comp[i] * VERTICES[i][2];
  }
  return [x - CENTRO[0], y - CENTRO[1], z - CENTRO[2]];
}

export default function DiagramaCuaternario({
  componentes, curvas, titulo, subtitulo,
}: {
  componentes: string[];
  curvas: CurvaCuaternaria[];
  titulo?: string;
  subtitulo?: string;
}) {
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [angulo, setAngulo] = useState({ yaw: 0.6, pitch: -0.35 });
  const arrastre = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const cv = lienzo.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    // Pantallas densas: se dibuja al doble y se escala, si no las lineas
    // de 1 px salen borrosas.
    const dpr = window.devicePixelRatio || 1;
    const ancho = cv.clientWidth;
    const alto = cv.clientHeight;
    cv.width = ancho * dpr;
    cv.height = alto * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const { yaw, pitch } = angulo;
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const escala = Math.min(ancho, alto) * 0.62;

    const proyectar = ([x, y, z]: [number, number, number]) => {
      // rotacion en Z (yaw) y luego en X (pitch)
      const x1 = x * cy - y * sy;
      const y1 = x * sy + y * cy;
      const y2 = y1 * cp - z * sp;
      const z2 = y1 * sp + z * cp;
      return { x: ancho / 2 + x1 * escala, y: alto / 2 - z2 * escala, prof: y2 };
    };

    ctx.fillStyle = "#18181b";
    ctx.fillRect(0, 0, ancho, alto);

    // Aristas del tetraedro
    ctx.strokeStyle = "#52525b";
    ctx.lineWidth = 1.4;
    for (const [i, j] of ARISTAS) {
      const p1 = proyectar(aCartesiano([0, 1, 2, 3].map((k) => (k === i ? 1 : 0))));
      const p2 = proyectar(aCartesiano([0, 1, 2, 3].map((k) => (k === j ? 1 : 0))));
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    // Curvas
    ctx.lineWidth = 1.2;
    for (const curva of curvas) {
      ctx.strokeStyle = "rgba(56,189,248,0.75)";
      ctx.beginPath();
      curva.puntos.forEach((p, i) => {
        const q = proyectar(aCartesiano(p));
        if (i === 0) ctx.moveTo(q.x, q.y);
        else ctx.lineTo(q.x, q.y);
      });
      ctx.stroke();

      const ini = proyectar(aCartesiano(curva.inicio ?? curva.puntos[0]));
      ctx.fillStyle = "rgba(163,230,53,0.85)";
      ctx.beginPath();
      ctx.arc(ini.x, ini.y, 2.2, 0, Math.PI * 2);
      ctx.fill();

      const fin = proyectar(aCartesiano(curva.puntos[curva.puntos.length - 1]));
      ctx.fillStyle = "rgba(244,63,94,0.9)";
      ctx.beginPath();
      ctx.arc(fin.x, fin.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Etiquetas de los vertices
    ctx.font = "13px ui-sans-serif, system-ui, sans-serif";
    ctx.fillStyle = "#e4e4e7";
    ctx.textAlign = "center";
    for (let i = 0; i < 4; i++) {
      const q = proyectar(aCartesiano([0, 1, 2, 3].map((k) => (k === i ? 1 : 0))));
      ctx.fillText(componentes[i] ?? `C${i}`, q.x, q.y - 9);
    }
  }, [angulo, curvas, componentes]);

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900 p-3">
      {(titulo || subtitulo) && (
        <div className="mb-1 flex flex-wrap items-baseline gap-x-3">
          {titulo && <h3 className="text-sm font-semibold text-zinc-100">{titulo}</h3>}
          {subtitulo && <span className="text-xs text-zinc-400">{subtitulo}</span>}
        </div>
      )}
      <canvas
        ref={lienzo}
        className="w-full cursor-grab active:cursor-grabbing"
        style={{ height: 520 }}
        onPointerDown={(e) => {
          arrastre.current = { x: e.clientX, y: e.clientY };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!arrastre.current) return;
          const dx = e.clientX - arrastre.current.x;
          const dy = e.clientY - arrastre.current.y;
          arrastre.current = { x: e.clientX, y: e.clientY };
          setAngulo((a) => ({
            yaw: a.yaw + dx * 0.008,
            // El pitch se limita: pasado el polo la escena se ve del
            // reves y se pierde la nocion de que vertice es cual.
            pitch: Math.max(-1.45, Math.min(1.45, a.pitch + dy * 0.008)),
          }));
        }}
        onPointerUp={() => { arrastre.current = null; }}
        onPointerLeave={() => { arrastre.current = null; }}
      />
      <div className="mt-1 flex items-center justify-between">
        <p className="text-[11px] text-zinc-500">
          Arrastra para girar el tetraedro. <span className="text-lime-400">Verde</span>: dónde empieza cada
          trayectoria; <span className="text-rose-400">rojo</span>: dónde termina.
        </p>
        <button
          onClick={() => setAngulo({ yaw: 0.6, pitch: -0.35 })}
          className="rounded border border-zinc-700 px-2 py-0.5 text-[10px] text-zinc-400 hover:bg-zinc-800"
        >
          reencuadrar
        </button>
      </div>
    </div>
  );
}
