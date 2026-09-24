"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Ya no hay clave global de unidades: viven en cada simulacion.

export interface UnidadInfo {
  simbolo: string;
  etiqueta: string;
  factor: number;
  desplazamiento: number;
  magnitud: string;
  requiere_masa_molar: boolean;
}

export interface Magnitud {
  si: string;
  unidades: UnidadInfo[];
  requiere_masa_molar: boolean;
}

export interface TablaUnidades {
  magnitudes: Record<string, Magnitud>;
  variables: Record<string, string[]>; // variable -> magnitudes compatibles
}

/** Caudal molar [mol/s] -> valor en una unidad masica, con la MW de la mezcla [g/mol]. */
export function molARepresentacionMasica(molPorSegundo: number, mwMezcla: number, unidad: UnidadInfo): number {
  return (molPorSegundo * mwMezcla) / 1000 / unidad.factor;
}

/**
 * Conversiones AFINES:  valor_SI = valor*factor + desplazamiento.
 * El desplazamiento es lo que hace funcionar las temperaturas
 * (degC -> K suma 273.15). La tabla la genera el backend con pint, asi
 * que las conversiones no se escriben a mano aqui.
 *
 * Masa <-> moles NO esta aqui a proposito: no es afin (depende de la
 * composicion de cada corriente) y por eso el caudal masico es una
 * VARIABLE del diagrama con su propia ecuacion m = F*MW_mezcla(x), no
 * una unidad alternativa de F. Ver _bloque_caudal_masico en
 * core/diagrama_corrientes.py.
 */
export function aSI(valor: number, unidad: UnidadInfo | null): number {
  if (!unidad) return valor;
  return valor * unidad.factor + unidad.desplazamiento;
}

export function desdeSI(valorSI: number, unidad: UnidadInfo | null): number {
  if (!unidad) return valorSI;
  return (valorSI - unidad.desplazamiento) / unidad.factor;
}

/**
 * preferidas / onElegir vienen de la SIMULACION abierta, no de una
 * preferencia global del navegador (ver el comentario de Simulacion.unidades:
 * al ser global, una eleccion de kg/h contaminaba las plantillas, cuyos
 * valores estan escritos en SI).
 */
export function useUnidades(
  preferidas: Record<string, string> = {},
  onElegir?: (clave: string, simbolo: string) => void,
) {
  const [tabla, setTabla] = useState<TablaUnidades | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/unidades`)
      .then((r) => r.json())
      .then(setTabla)
      .catch(() => setTabla(null));
  }, []);

  /**
   * La preferencia se guarda con la clave COMPLETA ("s1.F"), asi que
   * cada corriente puede llevar sus propias unidades: una en kg/h y
   * otra en mol/s sin que se pisen.
   */
  function elegir(clave: string, simbolo: string) {
    onElegir?.(clave, simbolo);
  }

  /** "s1.F" -> "F";  "F" -> "F". */
  function variableDe(clave: string): string {
    return clave.includes(".") ? clave.split(".").slice(1).join(".") : clave;
  }

  /** Magnitudes compatibles: los caudales admiten base molar Y masica. */
  function magnitudesDe(clave: string): Magnitud[] {
    if (!tabla) return [];
    return (tabla.variables[variableDe(clave)] ?? []).map((n) => tabla.magnitudes[n]).filter(Boolean);
  }

  function unidadDe(clave: string): UnidadInfo | null {
    const magnitudes = magnitudesDe(clave);
    if (magnitudes.length === 0) return null;
    const todas = magnitudes.flatMap((m) => m.unidades);
    // Primero la preferencia de ESA corriente; si no hay, la general.
    const simbolo = preferidas[clave] ?? preferidas[variableDe(clave)];
    return (simbolo && todas.find((u) => u.simbolo === simbolo)) || todas[0] || null;
  }

  function etiquetaDe(clave: string): string {
    return unidadDe(clave)?.etiqueta ?? "";
  }

  function esMasica(clave: string): boolean {
    return unidadDe(clave)?.magnitud === "flujo_masico";
  }

  return {
    tabla, preferidas, elegir, magnitudesDe, unidadDe, etiquetaDe, esMasica, variableDe,
    listo: tabla !== null,
  };
}

export type Unidades = ReturnType<typeof useUnidades>;
