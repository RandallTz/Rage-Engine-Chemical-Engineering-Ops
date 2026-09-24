"use client";

import { useRef, useState, type ReactNode } from "react";

/**
 * Descarga de graficas sin dependencias nuevas: recharts pinta un SVG de
 * verdad, asi que se serializa y se rasteriza en un canvas.
 *
 * Dos detalles que hacen falta para que la imagen salga util y no un
 * borron o un rectangulo transparente:
 *
 *  - Los estilos vienen de Tailwind, o sea de una hoja EXTERNA. Al sacar
 *    el SVG del documento pierde todo eso, asi que se copian a mano los
 *    atributos de presentacion calculados (fill, stroke, opacidades,
 *    grosores, tipografia) sobre cada nodo antes de serializar.
 *  - Un SVG no tiene fondo. Sobre un tema oscuro, exportarlo tal cual da
 *    texto gris sobre transparente, ilegible en cualquier visor que use
 *    fondo blanco -- por eso se rellena el canvas primero.
 */

const FONDO = "#18181b";
const ESCALA = 2; // suficiente para pegarla en un informe sin que se vea pixelada

const PROPIEDADES = [
  "fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity",
  "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
  "font-family", "font-size", "font-weight", "text-anchor", "opacity",
];

function incrustarEstilos(origen: Element, destino: Element) {
  const calculado = window.getComputedStyle(origen);
  const partes: string[] = [];
  for (const prop of PROPIEDADES) {
    const valor = calculado.getPropertyValue(prop);
    if (valor && valor !== "none" && valor !== "normal") partes.push(`${prop}:${valor}`);
  }
  if (partes.length) (destino as SVGElement).setAttribute("style", partes.join(";"));

  const hijosOrigen = origen.children;
  const hijosDestino = destino.children;
  for (let i = 0; i < hijosOrigen.length && i < hijosDestino.length; i++) {
    incrustarEstilos(hijosOrigen[i], hijosDestino[i]);
  }
}

async function descargarSVGComoPNG(svg: SVGSVGElement, nombre: string) {
  const rect = svg.getBoundingClientRect();
  const ancho = Math.ceil(rect.width) || 800;
  const alto = Math.ceil(rect.height) || 400;

  const copia = svg.cloneNode(true) as SVGSVGElement;
  incrustarEstilos(svg, copia);
  copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copia.setAttribute("width", String(ancho));
  copia.setAttribute("height", String(alto));
  if (!copia.getAttribute("viewBox")) copia.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);

  const texto = new XMLSerializer().serializeToString(copia);
  const url = URL.createObjectURL(new Blob([texto], { type: "image/svg+xml;charset=utf-8" }));

  try {
    const imagen = new Image();
    await new Promise<void>((resolver, rechazar) => {
      imagen.onload = () => resolver();
      imagen.onerror = () => rechazar(new Error("no se pudo rasterizar el SVG"));
      imagen.src = url;
    });

    const lienzo = document.createElement("canvas");
    lienzo.width = ancho * ESCALA;
    lienzo.height = alto * ESCALA;
    const ctx = lienzo.getContext("2d");
    if (!ctx) throw new Error("sin contexto 2d");
    ctx.fillStyle = FONDO;
    ctx.fillRect(0, 0, lienzo.width, lienzo.height);
    ctx.scale(ESCALA, ESCALA);
    ctx.drawImage(imagen, 0, 0, ancho, alto);

    const enlace = document.createElement("a");
    enlace.download = `${nombre}.png`;
    enlace.href = lienzo.toDataURL("image/png");
    enlace.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Envuelve una grafica y le pone su boton de descarga en la esquina.
 * Busca el SVG DENTRO de sus hijos, asi que sirve para cualquier grafica
 * de recharts sin que esta tenga que saber nada de esto.
 */
export default function DescargarGrafico({
  nombre, children, className = "",
}: { nombre: string; children: ReactNode; className?: string }) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [estado, setEstado] = useState<"listo" | "trabajando" | "error">("listo");

  async function descargar() {
    const svg = contenedor.current?.querySelector("svg");
    if (!svg) { setEstado("error"); return; }
    setEstado("trabajando");
    try {
      await descargarSVGComoPNG(svg as SVGSVGElement, nombre);
      setEstado("listo");
    } catch {
      setEstado("error");
    }
  }

  return (
    <div ref={contenedor} className={`group relative ${className}`}>
      <button
        onClick={descargar}
        title={estado === "error" ? "No se pudo generar la imagen" : "Descargar esta gráfica como PNG"}
        className={`absolute right-2 top-2 z-10 rounded border px-2 py-0.5 text-[10px] opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 ${
          estado === "error"
            ? "border-red-700 bg-red-950/80 text-red-200"
            : "border-zinc-700 bg-zinc-900/90 text-zinc-300 hover:bg-zinc-800"
        }`}
      >
        {estado === "trabajando" ? "generando…" : estado === "error" ? "falló" : "↓ PNG"}
      </button>
      {children}
    </div>
  );
}
