"use client";

import type { Expresion } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import type { EstadoEstudio, Racional, TipoTermino } from "./contratoEstudio";
import { latexExpresion, nombreLatex } from "./exportar";
import FormulaLatex from "../components/FormulaLatex";

export const NOMBRE_TIPO: Record<TipoTermino, string> = {
  acumulacion: "acumulación", inercia_temporal: "inercia temporal", difusion: "difusión", conveccion: "convección",
  reaccion: "reacción", fuente: "fuente", orden_superior: "orden superior", mixto: "derivada mixta",
  flujo: "flujo en la frontera", valor: "valor en la frontera", dato: "dato de frontera",
};

export const NOMBRE_ESTADO: Record<EstadoEstudio | "cargando", string> = {
  calculado: "Calculado", requiere_datos: "Faltan datos", no_aplicable: "No aplicable", no_soportado: "Fuera de alcance",
  no_convergente: "No convergió", rechazado: "Rechazado", cargando: "Calculando…",
};

export function Estado({ estado, motivo }: { estado: EstadoEstudio | "cargando"; motivo?: string }) {
  return <p className={`adim-estado is-${estado}`}><span>{NOMBRE_ESTADO[estado]}</span>{motivo && <small>{motivo}</small>}</p>;
}

/** Término del original o de una condición, por su id del catálogo. */
export function terminoDe(f: FormulacionNucleo, id: string): { original: Expresion; coeficiente: Expresion; nucleo: Expresion } | null {
  for (const e of f.ecuaciones) for (const t of e.terminos) if (t.id === id) return t as never;
  for (const c of f.condiciones as unknown as { terminos?: { id: string; original: Expresion; coeficiente: Expresion; nucleo: Expresion }[] }[]) {
    for (const t of c.terminos ?? []) if (t.id === id) return t;
  }
  return null;
}

export function TerminoLatex({ f, id }: { f: FormulacionNucleo; id: string }) {
  const t = terminoDe(f, id);
  if (!t) return <code>{id}</code>;
  return <FormulaLatex latex={latexExpresion(t.original)} lectura={id} />;
}

export function racional(q: Racional): string {
  return q.d === 1 ? String(q.n) : `${q.n}/${q.d}`;
}

export function racionalLatex(q: Racional): string {
  if (q.d === 1) return String(q.n);
  return `${q.n < 0 ? "-" : ""}\\tfrac{${Math.abs(q.n)}}{${q.d}}`;
}

export function Simbolo({ id }: { id: string }) {
  return <FormulaLatex latex={nombreLatex(id)} lectura={id} />;
}

export function numero(v: number | null | undefined, digitos = 4): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(digitos - 1).replace("e+", "e");
  return Number(v.toPrecision(digitos)).toLocaleString("es", { maximumSignificantDigits: digitos });
}

export function descargarArchivo(nombre: string, texto: string, tipo = "text/plain") {
  const url = URL.createObjectURL(new Blob([texto], { type: `${tipo};charset=utf-8` }));
  const a = document.createElement("a"); a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
