"use client";

import DiagramaMcCabeThiele, { type DatosDiagramaMT } from "./DiagramaMcCabeThiele";
import DiagramaPonchonSavarit, { type DatosDiagramaPS } from "./DiagramaPonchonSavarit";

/**
 * El backend manda una union discriminada por 'tipo' (ver
 * DiagramaColumna en backend/schemas.py), asi que aqui no hay que
 * adivinar el metodo mirando que campos vinieron: se despacha por
 * etiqueta. Los diagramas viejos, guardados antes de que existiera el
 * campo, se tratan como McCabe-Thiele, que es lo unico que habia.
 */
export type DatosDiagramaColumna = DatosDiagramaMT | DatosDiagramaPS;

export default function DiagramaColumna({
  datos, nombreLigero,
}: { datos: DatosDiagramaColumna; nombreLigero: string }) {
  if (datos.tipo === "ponchon_savarit") {
    return <DiagramaPonchonSavarit datos={datos} nombreLigero={nombreLigero} />;
  }
  return <DiagramaMcCabeThiele datos={datos} nombreLigero={nombreLigero} />;
}
