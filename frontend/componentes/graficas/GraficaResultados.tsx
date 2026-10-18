"use client";

/** Gráfica de un conjunto de resultados del formato común según una especificación.
 * Cualquier motor que publique el formato común se grafica igual. */
import type { ConjuntoResultados } from "../../motores/resultados/contrato";
import { datosGrafica, type Especificacion } from "./datos";
import Grafica from "./Grafica";
import estilos from "./grafica.module.css";

const conUnidad = (etiqueta: string, unidad: string) => unidad === "1" ? etiqueta : `${etiqueta} (${unidad})`;

export default function GraficaResultados({ conjunto, especificacion, alto, limitesY }: {
  conjunto: ConjuntoResultados; especificacion: Especificacion; alto?: number; limitesY?: [number, number];
}) {
  const d = datosGrafica(conjunto, especificacion);
  if (!d.ok) return <p className={estilos.aviso}>No se puede graficar: {d.motivo}.</p>;
  return <Grafica titulo={d.titulo} alto={alto} limitesY={limitesY} ejeX={conUnidad(d.ejeX.etiqueta, d.ejeX.unidad)} ejeY={conUnidad(d.ejeY.etiqueta, d.ejeY.unidad)}
    curvas={d.curvas.map(c => ({ nombre: c.nombre, x: c.x, y: c.y }))} />;
}
