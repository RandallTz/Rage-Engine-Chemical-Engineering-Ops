"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { EstudioSimulacion } from "./contratoEstudio";
import type { OrigenMotor } from "./desdeMotor";
import { compararConMotor, type Comparacion } from "./diferenciaMotor";
import { numero } from "./presentacionEstudio";
import { leerHojas } from "../motor/hojasMotor";
import { firmaHoja } from "../motor/modeloHojaMotor";
import { leerResultadoMotor } from "../motor/resultadosMotor";
import type { ResultadoMotor } from "../motor/modeloNumerico";

type Estado = { tipo: "cargando" } | { tipo: "nota"; texto: string; resolver?: boolean } | { tipo: "lista"; motor: ResultadoMotor; c: Comparacion };

/** Una línea: cuánto se separa esta simulación del resultado guardado del motor. */
export default function ComparacionMotor({ origen, fisico }: { origen: OrigenMotor; fisico: NonNullable<EstudioSimulacion["fisico"]> }) {
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });
  useEffect(() => {
    let vigente = true;
    const fijar = (e: Estado) => { if (vigente) setEstado(e); };
    (async () => {
      const hoja = leerHojas().find(h => h.id === origen.hojaId);
      if (!hoja) return fijar({ tipo: "nota", texto: "La hoja del motor ya no está en este navegador." });
      if (firmaHoja(hoja) !== origen.firmaHoja) return fijar({ tipo: "nota", texto: "La hoja del motor cambió después de importarla. Impórtala de nuevo para compararlas." });
      if (hoja.resultadoRef?.firma !== origen.firmaHoja) return fijar({ tipo: "nota", texto: "La hoja todavía no está resuelta en el motor.", resolver: true });
      const motor = await leerResultadoMotor(hoja.id, origen.firmaHoja);
      if (!motor) return fijar({ tipo: "nota", texto: "No se encontró el resultado guardado del motor.", resolver: true });
      fijar({ tipo: "lista", motor, c: compararConMotor(origen, fisico, motor) });
    })().catch(e => fijar({ tipo: "nota", texto: e instanceof Error ? e.message : String(e) }));
    return () => { vigente = false; };
  }, [origen, fisico]);

  if (estado.tipo === "cargando") return null;
  if (estado.tipo === "nota") return (
    <p className="adim-estudio-nota">Comparación con el motor: {estado.texto}{estado.resolver && <> <Link className="adim-enlace" href={`/motor/hojas/${origen.hojaId}/resolver`}>Resolver en el motor</Link></>}</p>
  );
  const { motor, c } = estado;
  return (
    <div className="adim-comparacion-motor">
      <strong>{numero(100 * c.relativa)} %</strong>
      <span>diferencia máxima con el motor, sobre {c.instantes} instantes{origen.modo === "1d" ? ` y ${motor.x.length} celdas` : ""} ({motor.metodo}).</span>
      {motor.estado === "parcial" && <small>El motor se detuvo en t = {numero(c.hasta)} s: {motor.mensaje}</small>}
    </div>
  );
}
