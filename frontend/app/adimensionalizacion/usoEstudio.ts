"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Modelo } from "./contrato";
import type { FormulacionNucleo, SolicitudNucleo } from "./contratoNucleo";
import type { NombreEstudio, OpcionesEstudio, RespuestaEstudio, ValorFisico } from "./contratoEstudio";
import { consultarEstudio, prepararEstudio } from "./clienteNucleo";

export type EntradaValor = { valor: string; unidad: string };
export type MapaValores = Record<string, EntradaValor>;

/** Valores por documento: comodidad local del navegador, no un resultado. */
export function useValores(documentoId: string): [MapaValores, (m: MapaValores) => void] {
  const clave = `adim.valores.${documentoId}`;
  const [valores, setValores] = useState<MapaValores>(() => {
    try { const t = typeof window === "undefined" ? null : localStorage.getItem(clave); return t ? JSON.parse(t) as MapaValores : {}; } catch { return {}; }
  });
  const guardar = useCallback((m: MapaValores) => {
    setValores(m);
    try { localStorage.setItem(clave, JSON.stringify(m)); } catch { /* sin almacenamiento: los valores siguen en memoria */ }
  }, [clave]);
  return [valores, guardar];
}

export function numeroDe(texto: string): number | null {
  const t = texto.trim().replace(",", ".").replace(/\s+/g, "").replace(/[×x]10\^/i, "e");
  if (!t) return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
}

/** Parámetros y constantes del modelo más las escalas libres de la formulación. */
export function simbolosConValor(modelo: Modelo, f: FormulacionNucleo) {
  const parametros = modelo.simbolos.filter(s => s.rol === "parametro" || s.rol === "constante").map(s => ({ id: s.id, nombre: s.nombre, unidad: s.unidad ?? "", tipo: "parametro" as const, signo: s.signo }));
  const libres = f.libres.map(id => ({ id, nombre: id, unidad: "", tipo: "escala" as const, signo: "positivo" as const }));
  return [...parametros, ...libres];
}

export function valoresParaNucleo(mapa: MapaValores, ids: string[]): ValorFisico[] {
  const r: ValorFisico[] = [];
  for (const id of ids) {
    const e = mapa[id];
    if (!e) continue;
    const v = numeroDe(e.valor);
    if (v === null) continue;
    r.push({ simboloId: id, valor: v, ...(e.unidad.trim() ? { unidad: e.unidad.trim() } : {}) });
  }
  return r;
}

export type Consulta = { estado: "inactiva" | "cargando" | "lista" | "error"; respuesta?: RespuestaEstudio; error?: string };

/** Una consulta `estudiar` cancelable; descarta respuestas tardías. */
export function useConsulta(base: SolicitudNucleo, f: FormulacionNucleo) {
  const [consulta, setConsulta] = useState<Consulta>({ estado: "inactiva" });
  const control = useRef<AbortController | null>(null);
  useEffect(() => () => control.current?.abort(), []);
  const lanzar = useCallback(async (analisis: NombreEstudio[], opciones: Omit<OpcionesEstudio, "analisis" | "objetivos">) => {
    control.current?.abort();
    const c = new AbortController(); control.current = c;
    const tiempo = setTimeout(() => c.abort(), 120000);
    setConsulta({ estado: "cargando" });
    try {
      const solicitud = prepararEstudio(base, f, { ...opciones, analisis });
      const respuesta = await consultarEstudio(solicitud, c.signal);
      if (control.current === c) setConsulta({ estado: "lista", respuesta });
    } catch (e) {
      if (control.current === c) setConsulta({ estado: "error", error: c.signal.aborted ? "Consulta cancelada o tiempo agotado." : e instanceof Error ? e.message : String(e) });
    } finally { clearTimeout(tiempo); }
  }, [base, f]);
  const cancelar = useCallback(() => control.current?.abort(), []);
  return { consulta, lanzar, cancelar };
}
