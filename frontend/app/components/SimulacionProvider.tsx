"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { PLANTILLAS } from "./plantillas";
import { construirEnlace, decodificar } from "./enlaceCompartible";

export interface Componente {
  nombre: string; // nombre canonico, el que entiende el backend
  formula?: string;
  MW?: number;
  Tb?: number;
}

/** Lo que el lienzo del flowsheet necesita para reconstruirse tal cual. */
export interface EstadoFlowsheet {
  nodes: unknown[];
  edges: unknown[];
  dados: Record<string, string>;
}

/**
 * Una simulacion es el DOCUMENTO completo: los componentes ya no son una
 * preferencia global del navegador sino parte de ella. Eso es lo que
 * permite tener varios procesos guardados, cada uno con su propia
 * mezcla, en vez de una unica configuracion que se pisa sola.
 */
export interface Simulacion {
  id: string;
  nombre: string;
  creada: string;      // ISO
  modificada: string;  // ISO
  componentes: Componente[];
  modelo: string;
  flowsheet: EstadoFlowsheet;
  /**
   * Unidad elegida para cada variable ("s1.F" -> "kg/h").
   *
   * Vive AQUI, dentro de la simulacion, y no en una preferencia global
   * del navegador. La razon es un fallo real: al ser global, haber
   * elegido kg/h una vez hacia que CUALQUIER simulacion futura leyera F
   * en kg/h -- incluidas las plantillas, cuyos valores estan escritos en
   * SI. El "100" de la plantilla de reciclo se interpretaba como 100
   * kg/h = 0.63 mol/s, y entonces un avance de 5 mol/s era imposible.
   * Los numeros de una simulacion no significan nada sin sus unidades,
   * asi que las unidades son parte del documento.
   */
  unidades?: Record<string, string>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CLAVE = "simulador.simulaciones";
const CLAVE_VIEJA = "simulador.configuracion"; // formato anterior, de una sola config global
export const FORMATO_ARCHIVO = "simulador-procesos/simulacion@1";

const FLOWSHEET_VACIO: EstadoFlowsheet = { nodes: [], edges: [], dados: {} };

const BENCENO_TOLUENO: Componente[] = [
  { nombre: "benzene", formula: "C6H6", MW: 78.11, Tb: 353.22 },
  { nombre: "toluene", formula: "C7H8", MW: 92.14, Tb: 383.75 },
];

// Las plantillas viven en ./plantillas.ts (son datos, no logica de estado)
// y se re-exportan aqui para no romper lo que ya las importaba de aqui.
export { PLANTILLAS, PLANTILLAS_POR_ID, CATEGORIAS, type Plantilla } from "./plantillas";

interface Almacen {
  activa: string | null;
  lista: Simulacion[];
}

interface Contexto {
  listo: boolean;
  simulaciones: Simulacion[];
  simulacion: Simulacion | null;
  crear: (nombre: string, plantillaId?: string) => string;
  abrir: (id: string) => void;
  eliminar: (id: string) => void;
  renombrar: (id: string, nombre: string) => void;
  duplicar: (id: string) => void;
  actualizar: (cambio: Partial<Omit<Simulacion, "id">>) => void;
  elegirUnidad: (clave: string, simbolo: string) => void;
  guardarFlowsheet: (estado: EstadoFlowsheet) => void;
  exportar: (id: string) => void;
  importar: (texto: string) => { ok: true; id: string } | { ok: false; error: string };
  /** URL con la simulacion entera dentro, para compartirla sin adjuntar nada. */
  compartir: (id: string) => Promise<{ ok: true; url: string; largo: number } | { ok: false; error: string; largo: number }>;
  /** Nombre de la simulacion que acaba de entrar por un enlace, si la hubo. */
  reciboEnlace: string | null;
  // Compatibilidad con el codigo que ya existia: apuntan a la simulacion activa.
  componentes: Componente[];
  modelo: string;
  setComponentes: (c: Componente[]) => void;
  setModelo: (m: string) => void;
}

const Ctx = createContext<Contexto | null>(null);

const ahora = () => new Date().toISOString();
const nuevoId = () =>
  `sim_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;

/** Acepta lo que venga de disco sin confiar en ello: un archivo editado a mano no debe tumbar la app. */
function sanear(bruto: unknown, nombreSugerido?: string): Simulacion | null {
  if (typeof bruto !== "object" || bruto === null) return null;
  const s = bruto as Record<string, unknown>;
  const fs = (typeof s.flowsheet === "object" && s.flowsheet !== null ? s.flowsheet : {}) as Record<string, unknown>;
  const componentes = Array.isArray(s.componentes)
    ? (s.componentes.filter((c) => typeof c === "object" && c !== null && typeof (c as Componente).nombre === "string") as Componente[])
    : [];
  return {
    id: typeof s.id === "string" ? s.id : nuevoId(),
    nombre: nombreSugerido ?? (typeof s.nombre === "string" && s.nombre.trim() ? s.nombre : "Sin nombre"),
    creada: typeof s.creada === "string" ? s.creada : ahora(),
    modificada: typeof s.modificada === "string" ? s.modificada : ahora(),
    componentes,
    modelo: typeof s.modelo === "string" ? s.modelo : "unifac_raoult",
    unidades: typeof s.unidades === "object" && s.unidades !== null
      ? (s.unidades as Record<string, string>) : {},
    flowsheet: {
      nodes: Array.isArray(fs.nodes) ? fs.nodes : [],
      edges: Array.isArray(fs.edges) ? fs.edges : [],
      dados: typeof fs.dados === "object" && fs.dados !== null ? (fs.dados as Record<string, string>) : {},
    },
  };
}

export function SimulacionProvider({ children }: { children: ReactNode }) {
  const [almacen, setAlmacen] = useState<Almacen>({ activa: null, lista: [] });
  const [listo, setListo] = useState(false);
  const [reciboEnlace, setReciboEnlace] = useState<string | null>(null);

  // Se lee despues del primer render a proposito: tocar localStorage
  // durante el render rompe la hidratacion (el servidor no lo tiene).
  useEffect(() => {
    let inicial: Almacen = { activa: null, lista: [] };
    try {
      const guardado = localStorage.getItem(CLAVE);
      if (guardado) {
        const bruto = JSON.parse(guardado) as Record<string, unknown>;
        const lista = Array.isArray(bruto.lista)
          ? (bruto.lista.map((s) => sanear(s)).filter(Boolean) as Simulacion[])
          : [];
        inicial = { activa: typeof bruto.activa === "string" ? bruto.activa : lista[0]?.id ?? null, lista };
      } else {
        // Migracion desde el formato viejo (una sola configuracion
        // global): se conserva el trabajo en vez de descartarlo en
        // silencio, que es justo lo que mas molesta al actualizar.
        const viejo = localStorage.getItem(CLAVE_VIEJA);
        if (viejo) {
          const cfg = JSON.parse(viejo) as { componentes?: Componente[]; modelo?: string };
          const s = sanear({ ...cfg, nombre: "Simulación recuperada" });
          if (s) inicial = { activa: s.id, lista: [s] };
        }
      }
    } catch {
      // almacenamiento no disponible o JSON corrupto: se arranca vacio
    }
    setAlmacen(inicial);
    setListo(true);
  }, []);

  useEffect(() => {
    if (!listo) return;
    try {
      localStorage.setItem(CLAVE, JSON.stringify(almacen));
    } catch {
      // sin persistencia; la sesion sigue funcionando igual
    }
  }, [almacen, listo]);

  const simulacion = almacen.lista.find((s) => s.id === almacen.activa) ?? null;

  const parchear = useCallback((id: string, cambio: Partial<Omit<Simulacion, "id">>) => {
    setAlmacen((a) => ({
      ...a,
      lista: a.lista.map((s) => (s.id === id ? { ...s, ...cambio, modificada: ahora() } : s)),
    }));
  }, []);

  const actualizar = useCallback(
    (cambio: Partial<Omit<Simulacion, "id">>) => {
      if (!almacen.activa) return;
      parchear(almacen.activa, cambio);
    },
    [almacen.activa, parchear]
  );

  /**
   * El lienzo se guarda solo, pero NO en cada tecla: se agrupa con un
   * retardo corto. Sin esto, arrastrar un nodo dispara decenas de
   * escrituras a localStorage por segundo.
   */
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const guardarFlowsheet = useCallback(
    (estado: EstadoFlowsheet) => {
      const id = almacen.activa;
      if (!id) return;
      if (temporizador.current) clearTimeout(temporizador.current);
      temporizador.current = setTimeout(() => parchear(id, { flowsheet: estado }), 400);
    },
    [almacen.activa, parchear]
  );

  const crear = useCallback((nombre: string, plantillaId = "vacia") => {
    const plantilla = PLANTILLAS.find((p) => p.id === plantillaId) ?? PLANTILLAS[0];
    const id = nuevoId();
    const s: Simulacion = {
      id,
      nombre: nombre.trim() || plantilla.nombre,
      creada: ahora(),
      modificada: ahora(),
      componentes: plantilla.componentes,
      modelo: plantilla.modelo,
      // Las plantillas se escriben en SI; arrancar sin preferencias hace
      // que se lean en SI, que es lo unico coherente con sus numeros.
      unidades: {},
      // copia profunda: si no, dos simulaciones creadas de la misma
      // plantilla compartirian los mismos nodos y editar una tocaria la otra
      flowsheet: structuredClone(plantilla.flowsheet),
    };
    setAlmacen((a) => ({ activa: id, lista: [s, ...a.lista] }));
    return id;
  }, []);

  const eliminar = useCallback((id: string) => {
    setAlmacen((a) => {
      const lista = a.lista.filter((s) => s.id !== id);
      return { lista, activa: a.activa === id ? lista[0]?.id ?? null : a.activa };
    });
  }, []);

  const duplicar = useCallback((id: string) => {
    setAlmacen((a) => {
      const origen = a.lista.find((s) => s.id === id);
      if (!origen) return a;
      const copia: Simulacion = {
        ...structuredClone(origen),
        id: nuevoId(),
        nombre: `${origen.nombre} (copia)`,
        creada: ahora(),
        modificada: ahora(),
      };
      return { activa: copia.id, lista: [copia, ...a.lista] };
    });
  }, []);

  const exportar = useCallback(
    (id: string) => {
      const s = almacen.lista.find((x) => x.id === id);
      if (!s) return;
      const archivo = { formato: FORMATO_ARCHIVO, exportada: ahora(), simulacion: s };
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(archivo, null, 2)], { type: "application/json" })
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `${s.nombre.replace(/[^\w\-. ]+/g, "_") || "simulacion"}.simproc.json`;
      a.click();
      URL.revokeObjectURL(url);
    },
    [almacen.lista]
  );

  const importar = useCallback((texto: string) => {
    let bruto: unknown;
    try {
      bruto = JSON.parse(texto);
    } catch {
      return { ok: false as const, error: "El archivo no es JSON válido." };
    }
    const envoltorio = bruto as Record<string, unknown>;
    // Se acepta tanto el archivo con envoltorio como una simulacion
    // suelta: quien edite el JSON a mano no tiene por que saber del
    // formato exterior.
    const cruda = envoltorio?.simulacion ?? bruto;
    const s = sanear(cruda);
    if (!s || (s.componentes.length === 0 && (s.flowsheet.nodes as unknown[]).length === 0 && !envoltorio?.simulacion)) {
      return { ok: false as const, error: "El archivo no parece una simulación de este programa." };
    }
    // Id nuevo siempre: importar dos veces el mismo archivo debe dar dos
    // simulaciones, no pisar la que ya estaba.
    const importada: Simulacion = { ...s, id: nuevoId(), modificada: ahora() };
    setAlmacen((a) => ({ activa: importada.id, lista: [importada, ...a.lista] }));
    return { ok: true as const, id: importada.id };
  }, []);

  // Relleno de masas molares que falten: sin MW no se pueden ofrecer
  // caudales en base masica (kg/h -> mol/s necesita la MW de la mezcla).
  const idActiva = almacen.activa;
  const componentes = simulacion?.componentes;
  useEffect(() => {
    if (!listo || !idActiva || !componentes) return;
    const sinMW = componentes.filter((c) => c.MW === undefined);
    if (sinMW.length === 0) return;

    let cancelado = false;
    Promise.all(
      sinMW.map((c) =>
        fetch(`${API_URL}/componentes/buscar?q=${encodeURIComponent(c.nombre)}`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null)
      )
    ).then((respuestas) => {
      if (cancelado) return;
      const masas = new Map<string, number>();
      respuestas.forEach((info, i) => {
        if (info?.MW) masas.set(sinMW[i].nombre, info.MW);
      });
      if (masas.size === 0) return;
      setAlmacen((a) => ({
        ...a,
        lista: a.lista.map((s) =>
          s.id !== idActiva
            ? s
            : {
                ...s,
                componentes: s.componentes.map((c) =>
                  c.MW === undefined && masas.has(c.nombre) ? { ...c, MW: masas.get(c.nombre) } : c
                ),
              }
        ),
      }));
    });
    return () => { cancelado = true; };
  }, [listo, idActiva, componentes]);

  const compartir = useCallback(
    async (id: string) => {
      const s = almacen.lista.find((x) => x.id === id);
      if (!s) {
        return { ok: false as const, largo: 0, error: "Esa simulación ya no existe." };
      }
      return construirEnlace(s);
    },
    [almacen.lista],
  );

  // UNA SIMULACION QUE LLEGA POR ENLACE.
  //
  // Se lee despues de cargar el localStorage (de ahi el guard de 'listo')
  // para no pisar lo que el usuario ya tenia. Y entra como simulacion
  // NUEVA, igual que importar un archivo: un enlace nunca sobrescribe
  // trabajo existente.
  //
  // El fragmento se limpia en cuanto se usa, por dos motivos: recargar
  // no debe duplicar la simulacion, y la URL deja de ser kilometrica.
  useEffect(() => {
    if (!listo) return;
    const fragmento = window.location.hash;
    if (!fragmento.startsWith("#s=")) return;
    let cancelado = false;
    (async () => {
      const crudo = await decodificar(fragmento.slice(3));
      // Se pasa por el MISMO saneador que los archivos: un enlace puede
      // venir manipulado y no merece mas confianza que un .json editado.
      const s = crudo ? sanear(crudo) : null;
      if (cancelado) return;
      history.replaceState(null, "", window.location.pathname + window.location.search);
      if (!s) return;
      const recibida: Simulacion = { ...s, id: nuevoId(), creada: ahora(), modificada: ahora() };
      setAlmacen((a) => ({ activa: recibida.id, lista: [recibida, ...a.lista] }));
      setReciboEnlace(recibida.nombre);
    })();
    return () => { cancelado = true; };
  }, [listo]);

  return (
    <Ctx.Provider
      value={{
        listo,
        simulaciones: almacen.lista,
        simulacion,
        crear,
        abrir: (id) => setAlmacen((a) => ({ ...a, activa: id })),
        eliminar,
        renombrar: (id, nombre) => parchear(id, { nombre: nombre.trim() || "Sin nombre" }),
        duplicar,
        actualizar,
        elegirUnidad: (clave, simbolo) =>
          actualizar({ unidades: { ...(simulacion?.unidades ?? {}), [clave]: simbolo } }),
        guardarFlowsheet,
        exportar,
        importar,
        compartir,
        reciboEnlace,
        componentes: simulacion?.componentes ?? [],
        modelo: simulacion?.modelo ?? "unifac_raoult",
        setComponentes: (c) => actualizar({ componentes: c }),
        setModelo: (m) => actualizar({ modelo: m }),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSimulacion() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSimulacion debe usarse dentro de SimulacionProvider.");
  return ctx;
}

/** Alias historico: antes los componentes eran una config global, ahora viven en la simulacion activa. */
export const useConfiguracion = useSimulacion;

/** Nombres en el orden definido -- el orden importa: el indice 0 es el "ligero" por convencion. */
export function nombresDe(componentes: Componente[]): string[] {
  return componentes.map((c) => c.nombre);
}

/**
 * Ajusta una composicion a la cantidad actual de componentes. Hace falta
 * porque la lista puede cambiar despues de que ya se escribieron
 * composiciones en el flowsheet.
 */
export function normalizarComposicion(composicion: number[] | undefined, n: number): number[] {
  const base = composicion ?? [];
  if (base.length === n) return base;
  const ajustada = base.slice(0, n);
  while (ajustada.length < n) ajustada.push(0);
  return ajustada;
}
