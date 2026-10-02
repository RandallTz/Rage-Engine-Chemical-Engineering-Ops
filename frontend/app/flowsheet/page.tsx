"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  ConnectionLineType,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useSimulacion, nombresDe } from "../components/SimulacionProvider";
import { NodoCorriente, NodoOperacion, ValoresContext, type Modo } from "./nodos";
import PanelLateral, { type InformeBloque, type Inconsistencia, type Redundancia } from "./PanelLateral";
import Reporte from "./Reporte";
import Diseno from "./Diseno";
import { useUnidades, aSI } from "./unidades";
import type { DatosDiagramaColumna } from "../components/DiagramaColumna";
import {
  TipoOperacion,
  DatosNodo,
  DatosOperacion,
  puertosDe,
  corrientesDeOperacion,
  metodoPorDefecto,
  listaReacciones,
  type RespuestaResolver,
} from "./modelo";
import EsperaCalculo from "../components/EsperaCalculo";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const nodeTypes = { corriente: NodoCorriente, operacion: NodoOperacion };

/**
 * Tuberia ortogonal, no curva de Bezier. Un diagrama de proceso se lee
 * como un plano: los tramos van en horizontal y vertical con esquinas a
 * escuadra. 'smoothstep' con borderRadius=0 da exactamente eso (el tipo
 * 'step' tambien, pero smoothstep enruta mejor cuando los nodos estan
 * desalineados).
 */
const ARISTA_RECTA = {
  type: "smoothstep" as const,
  pathOptions: { borderRadius: 0 },
  style: { strokeWidth: 1.6 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
};

const CATALOGO: { tipo: TipoOperacion; etiqueta: string; grupo: string }[] = [
  { tipo: "columna", etiqueta: "Columna", grupo: "Separación" },
  { tipo: "mezclador", etiqueta: "Mezclador", grupo: "Mezcla" },
  { tipo: "divisor", etiqueta: "Divisor", grupo: "Mezcla" },
  { tipo: "bomba", etiqueta: "Bomba", grupo: "Transporte" },
  { tipo: "reactor_cstr", etiqueta: "Reactor CSTR", grupo: "Reacción" },
  { tipo: "flash", etiqueta: "Flash", grupo: "Separación" },
  { tipo: "intercambiador", etiqueta: "Intercambiador", grupo: "Térmicos" },
  { tipo: "valvula", etiqueta: "Válvula", grupo: "Térmicos" },
  { tipo: "separador", etiqueta: "Separador", grupo: "Separación" },
  { tipo: "compresor", etiqueta: "Compresor / turbina", grupo: "Transporte" },
  { tipo: "reactor_equilibrio", etiqueta: "Reactor de equilibrio", grupo: "Reacción" },
  { tipo: "intercambiador_doble", etiqueta: "Intercambiador 2 corrientes", grupo: "Térmicos" },
  { tipo: "reactor_pfr", etiqueta: "Reactor PFR", grupo: "Reacción" },
  { tipo: "absorbedor", etiqueta: "Absorbedor", grupo: "Separación" },
];

export default function FlowsheetPage() {
  const { componentes, simulacion, guardarFlowsheet, elegirUnidad, actualizar, listo: simListo } = useSimulacion();
  const nombresComponentes = nombresDe(componentes);
  const nComp = componentes.length;

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<DatosNodo>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [modo, setModo] = useState<Modo | "reporte" | "diseno">("editar");
  const [menu, setMenu] = useState<{ nodoId: string; x: number; y: number } | null>(null);

  const [dados, setDados] = useState<Record<string, string>>({});
  const [pool, setPool] = useState<Record<string, number>>({});
  const [diagnostico, setDiagnostico] = useState<InformeBloque[]>([]);
  const [incognitas, setIncognitas] = useState<string[]>([]);
  const [inconsistencias, setInconsistencias] = useState<Inconsistencia[]>([]);
  const [diagramas, setDiagramas] = useState<Record<string, DatosDiagramaColumna>>({});
  const [masasMolares, setMasasMolares] = useState<Record<string, number>>({});
  const [completo, setCompleto] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [gradosLibertad, setGradosLibertad] = useState<{
    grados_de_libertad: number; ecuaciones: number; incognitas: number; redundancias: Redundancia[];
  } | null>(null);
  const unidades = useUnidades(simulacion?.unidades ?? {}, elegirUnidad);
  const [instancia, setInstancia] = useState<{ fitView: (o?: object) => void } | null>(null);

  /**
   * El lienzo vive en la simulacion, no en este componente: por eso ya
   * no se pierde al cambiar de panel. La sincronizacion es en un solo
   * sentido por vez para no entrar en bucle -- 'cargadaDe' recuerda que
   * simulacion se volco ya en el estado local, de modo que el efecto de
   * carga solo corre al ABRIR otra simulacion, nunca como reaccion a los
   * guardados que el propio lienzo dispara.
   */
  const cargadaDe = useRef<string | null>(null);
  const idSimulacion = simulacion?.id ?? null;

  useEffect(() => {
    if (!simListo) return;
    if (cargadaDe.current === idSimulacion) return;
    cargadaDe.current = idSimulacion;
    const fs = simulacion?.flowsheet;
    setNodes((fs?.nodes ?? []) as Node<DatosNodo>[]);
    setEdges((fs?.edges ?? []) as Edge[]);
    setDados(fs?.dados ?? {});
    // Los resultados NO se guardan: son derivados de los datos y del
    // codigo de calculo, asi que revivirlos de disco solo serviria para
    // mostrar numeros viejos como si fueran de la version actual.
    setPool({}); setDiagramas({}); setCompleto(null);
    setIncognitas([]); setInconsistencias([]); setDiagnostico([]);
    setSeleccionado(null); setError(null);
    setTimeout(() => instancia?.fitView({ padding: 0.25, duration: 200 }), 80);
  }, [simListo, idSimulacion, simulacion, setNodes, setEdges, instancia]);

  useEffect(() => {
    if (!simListo || cargadaDe.current !== idSimulacion || idSimulacion === null) return;
    guardarFlowsheet({ nodes, edges, dados });
  }, [simListo, idSimulacion, nodes, edges, dados, guardarFlowsheet]);

  const onConnect = useCallback((c: Connection) => setEdges((eds) => addEdge(c, eds)), [setEdges]);

  function idLibre(prefijo: string, actuales: Node<DatosNodo>[]) {
    const usados = actuales.map((n) => n.id);
    let i = 1;
    while (usados.includes(`${prefijo}${i}`)) i += 1;
    return `${prefijo}${i}`;
  }

  /**
   * Coloca el nodo nuevo en una rejilla holgada y reencuadra la vista.
   * Antes se apilaban (30 px de separacion para nodos de 150-250 px de
   * alto) y ademas podian caer fuera del encuadre, con lo que sus
   * puertos quedaban inalcanzables para conectar.
   */
  function posicionLibre(indice: number) {
    return { x: 80 + (indice % 4) * 270, y: 80 + Math.floor(indice / 4) * 240 };
  }

  function reencuadrar() {
    setTimeout(() => instancia?.fitView({ padding: 0.25, duration: 300 }), 60);
  }

  function agregarCorrienteSuelta() {
    const sid = idLibre("s", nodes);
    setNodes((nds) => [
      ...nds,
      { id: sid, type: "corriente", position: posicionLibre(nds.length), data: { clase: "corriente" } },
    ]);
    setSeleccionado(sid);
    reencuadrar();
  }

  /**
   * La operacion se agrega SOLA: las corrientes se crean aparte y se
   * conectan arrastrando. Antes venian creadas y conectadas
   * automaticamente, pero el usuario lo encontro tedioso -- te obligaba
   * a borrar las que no querias.
   */
  function agregarOperacion(tipo: TipoOperacion) {
    const PREFIJO: Partial<Record<TipoOperacion, string>> = {
      columna: "col", reactor_cstr: "r", flash: "fl",
      intercambiador: "e", valvula: "v", separador: "sep",
      compresor: "k", reactor_equilibrio: "req", intercambiador_doble: "ic",
      reactor_pfr: "pfr", absorbedor: "ab",
    };
    const opId = idLibre(PREFIJO[tipo] ?? tipo.slice(0, 3), nodes);
    const datos: DatosOperacion = {
      clase: "operacion",
      tipo,
      P_sistema: 101325,
      ...(tipo === "columna"
        ? {
            // Con mas de 2 componentes McCabe-Thiele no es aplicable, asi
            // que arrancar ahi solo llevaria a un error: se elige FUG.
            metodo: metodoPorDefecto(nComp),
            con_balance_energia: true,
            ...(nComp > 2 ? { indice_LK: 0, indice_HK: 1 } : {}),
          }
        : {}),
      ...(tipo === "divisor" ? { fracciones: "0.5,0.5" } : {}),
      ...(tipo === "reactor_cstr"
        ? { nu: "", A: 1e4, Ea: 45000, con_cinetica: true, n_entradas: 1, modo_energia: "isotermo" }
        : {}),
      // Adiabatico por defecto: es el separador tipico detras de una
      // valvula, y es la unica spec que no obliga a inventarse un numero.
      ...(tipo === "flash" ? { spec_flash: "adiabatico", Q_por_mol: 0 } : {}),
      // Igual aqui: Q=0 no hace nada raro, y el usuario pone lo suyo.
      ...(tipo === "intercambiador" ? { spec_intercambiador: "Q_por_mol", Q_por_mol: 0 } : {}),
      // Una valvula sin caida de presion no es una valvula: se arranca
      // con la mitad de la presion de operacion para que haga algo.
      ...(tipo === "valvula" ? { P_salida: 101325 / 2 } : {}),
      // Valores tipicos de libro, visibles y editables: el equipo resuelve
      // de inmediato y se ve que se supuso.
      ...(tipo === "separador"
        ? { recuperaciones: Array.from({ length: Math.max(nComp, 1) },
              (_, i) => (i === 0 ? "0.95" : "0.05")).join(",") }
        : {}),
      ...(tipo === "compresor" ? { P_salida: 3 * 101325, eficiencia: 0.75 } : {}),
      ...(tipo === "reactor_equilibrio"
        ? { nu: "", A: 1e4, Ea: 45000, n_entradas: 1, con_balance_energia: false }
        : {}),
      ...(tipo === "reactor_pfr"
        ? { nu: "", A: 1e4, Ea: 45000, n_entradas: 1 }
        : {}),
      ...(tipo === "absorbedor" ? { N_etapas: 6 } : {}),
      ...(tipo === "intercambiador_doble"
        ? { spec_ic: "T_salida_caliente", T_salida_caliente: 350,
            aproximacion_minima: 5, contracorriente: true }
        : {}),
    };
    setNodes((nds) => [
      ...nds,
      { id: opId, type: "operacion", position: posicionLibre(nds.length), data: datos },
    ]);
    setSeleccionado(opId);
    reencuadrar();
  }

  /**
   * Renombra un elemento. No basta con cambiar el id del nodo: las
   * aristas lo referencian por nombre, y TODAS las claves del pool
   * ("s1.F", "s1.x0"...) y de las unidades llevan el nombre delante.
   * Si alguna se quedara con el nombre viejo, el dato existiria pero
   * apuntaria a una corriente que ya no existe -- desapareceria sin
   * decir nada.
   */
  function renombrarNodo(viejo: string, bruto: string): string | null {
    const nuevo = bruto.trim();
    if (!nuevo || nuevo === viejo) return null;
    if (!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(nuevo)) {
      return "Usa solo letras, números, guion y guion bajo, empezando por letra.";
    }
    if (nuevo.includes(".")) return "El nombre no puede llevar puntos.";
    if (nodes.some((n) => n.id === nuevo)) return `Ya hay un elemento llamado "${nuevo}".`;

    const reclave = (clave: string) =>
      clave.startsWith(`${viejo}.`) ? `${nuevo}.${clave.slice(viejo.length + 1)}` : clave;

    setNodes((nds) => nds.map((n) => (n.id === viejo ? { ...n, id: nuevo } : n)));
    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        source: e.source === viejo ? nuevo : e.source,
        target: e.target === viejo ? nuevo : e.target,
      }))
    );
    setDados((d) => Object.fromEntries(Object.entries(d).map(([k, v]) => [reclave(k), v])));
    if (simulacion?.unidades) {
      actualizar({
        unidades: Object.fromEntries(
          Object.entries(simulacion.unidades).map(([k, v]) => [reclave(k), v])
        ),
      });
    }
    // Los resultados dejan de valer: sus claves son las viejas.
    setPool({}); setDiagramas({}); setCompleto(null);
    setIncognitas([]); setInconsistencias([]); setDiagnostico([]);
    setSeleccionado(nuevo);
    return null;
  }

  function eliminarNodo(id: string) {
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    setSeleccionado(null);
    setMenu(null);
  }

  function actualizarDatosNodo(id: string, cambio: Partial<DatosOperacion>) {
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== id || n.data.clase !== "operacion") return n;
        const datos: DatosOperacion = { ...(n.data as DatosOperacion), ...cambio };
        return { ...n, data: datos };
      })
    );
  }

  const nodoSeleccionado = nodes.find((n) => n.id === seleccionado);

  /**
   * Arma la peticion que comparten /diagrama/resolver y
   * /diagrama/grados-libertad. Aqui es donde se cruza la frontera de
   * unidades: lo que el usuario escribio esta en SU unidad y se
   * convierte a SI, porque el nucleo trabaja siempre en SI.
   */
  function construirPeticion() {
    const corrientes = nodes.filter((n) => n.data.clase === "corriente").map((n) => n.id);
    const operaciones = [];
    for (const n of nodes.filter((x) => x.data.clase === "operacion")) {
      const datos = n.data as DatosOperacion;
      const mapa = corrientesDeOperacion(n, edges);
      if (!mapa) throw new Error(`${n.id}: le faltan corrientes conectadas en algún puerto.`);
      operaciones.push({
        nombre: n.id,
        tipo: datos.tipo,
        corrientes: mapa,
        metodo: datos.metodo ?? null,
        P_sistema: datos.P_sistema,
        q: datos.metodo === "ponchon_savarit" || datos.metodo === "fug" ? datos.q_fijo ?? 1.0 : null,
        indice_LK: datos.metodo === "fug" ? datos.indice_LK ?? 0 : null,
        indice_HK: datos.metodo === "fug" ? datos.indice_HK ?? 1 : null,
        fracciones: datos.tipo === "divisor" ? (datos.fracciones ?? "0.5,0.5").split(",").map(Number) : null,
        con_balance_energia: datos.con_balance_energia !== false,
        // La estequiometria, una reaccion o varias.
        //
        // Con UNA se manda en 'reaccion', exactamente como antes: asi la
        // peticion de un diagrama que ya existia no cambia ni un byte, y
        // el pool sigue diciendo 'r1.xi'. Con varias se manda en
        // 'reacciones' y el servidor rechaza que lleguen los dos campos.
        ...(() => {
          const esReactor =
            datos.tipo === "reactor_cstr" || datos.tipo === "reactor_equilibrio" ||
            datos.tipo === "reactor_pfr";
          if (!esReactor) return { reaccion: null, reacciones: null };
          const lista = listaReacciones(datos)
            .filter((r) => (r.nu ?? "").trim())
            .map((r) => ({
              nu: (r.nu ?? "").split(",").map((v) => Number(v.trim())),
              A: r.A ?? 1e4,
              Ea: r.Ea ?? 45000,
              componente_referencia: 0,
            }));
          if (lista.length === 0) return { reaccion: null, reacciones: null };
          if (lista.length === 1) return { reaccion: lista[0], reacciones: null };
          return { reaccion: null, reacciones: lista };
        })(),
        con_cinetica: datos.con_cinetica !== false,
        modo_energia: datos.tipo === "reactor_cstr" ? (datos.modo_energia ?? "isotermo") : "isotermo",

        // --- equipos termicos. Se manda SOLO la especificacion elegida:
        // el nucleo rechaza (con su propio mensaje) que lleguen dos, y
        // mandar las dos "por si acaso" convertiria un diagrama valido
        // en un error de sobre-especificacion.
        Q:
          (datos.tipo === "reactor_cstr" && datos.modo_energia === "calor_dado") ||
          (datos.tipo === "intercambiador_doble" && datos.spec_ic === "Q")
            ? Number(datos.Q ?? 0)
            : null,
        T_operacion:
          (datos.tipo === "flash" && datos.spec_flash === "isotermo")
            ? Number(datos.T_operacion ?? 0)
            : datos.tipo === "absorbedor" && datos.T_operacion
              ? Number(datos.T_operacion)
              : null,
        fraccion_vapor:
          datos.tipo === "flash" && datos.spec_flash === "fraccion"
            ? Number(datos.fraccion_vapor ?? 0.5)
            : null,
        Q_por_mol:
          (datos.tipo === "flash" && datos.spec_flash === "adiabatico") ||
          (datos.tipo === "intercambiador" && datos.spec_intercambiador !== "T_salida")
            ? Number(datos.Q_por_mol ?? 0)
            : null,
        T_salida:
          datos.tipo === "intercambiador" && datos.spec_intercambiador === "T_salida"
            ? Number(datos.T_salida ?? 0)
            : null,
        P_salida:
          datos.tipo === "valvula" || datos.tipo === "compresor"
            ? Number(datos.P_salida ?? 0)
            : null,

        // --- equipos nuevos
        recuperaciones:
          datos.tipo === "separador"
            ? String(datos.recuperaciones ?? "").split(",").map((v) => Number(v.trim()))
            : null,
        eficiencia: datos.tipo === "compresor" ? Number(datos.eficiencia ?? 0.75) : null,
        T_salida_caliente:
          datos.tipo === "intercambiador_doble" && datos.spec_ic === "T_salida_caliente"
            ? Number(datos.T_salida_caliente ?? 350)
            : null,
        T_salida_frio:
          datos.tipo === "intercambiador_doble" && datos.spec_ic === "T_salida_frio"
            ? Number(datos.T_salida_frio ?? 340)
            : null,
        aproximacion_minima:
          datos.tipo === "intercambiador_doble" ? Number(datos.aproximacion_minima ?? 5) : 5,

        // --- caidas de presion. Se mandan SIEMPRE (0 por omision) y no
        // solo cuando el equipo las admite: el esquema del servidor las
        // ignora donde no aplican, y un condicional por tipo aqui seria un
        // sitio mas donde olvidarse de un equipo al anadirlo.
        caida_P: Number(datos.caida_P ?? 0),
        caida_P_caliente:
          datos.tipo === "intercambiador_doble" ? Number(datos.caida_P_caliente ?? 0) : 0,
        caida_P_frio:
          datos.tipo === "intercambiador_doble" ? Number(datos.caida_P_frio ?? 0) : 0,
        caida_P_gas: datos.tipo === "absorbedor" ? Number(datos.caida_P_gas ?? 0) : 0,
        N_etapas: datos.tipo === "absorbedor" ? Number(datos.N_etapas ?? 6) : null,
        contracorriente:
          datos.tipo === "intercambiador_doble" ? datos.contracorriente !== false : true,
      });
    }

    const valores: Record<string, number> = {};
    const caudales_masicos: Record<string, number> = {};
    for (const [clave, texto] of Object.entries(dados)) {
      if (texto === "" || !Number.isFinite(Number(texto))) continue;
      const [nodoId, ...resto] = clave.split(".");
      const variable = resto.join(".");
      const unidad = unidades.unidadDe(clave);
      // Un caudal dado en masa fija la MISMA variable F, pero como su
      // conversion depende de la composicion, viaja aparte y el backend
      // lo mete como restriccion en vez de como valor fijo.
      if (variable === "F" && unidad?.magnitud === "flujo_masico") {
        caudales_masicos[nodoId] = Number(texto) * unidad.factor; // -> kg/s
      } else {
        valores[clave] = aSI(Number(texto), unidad);
      }
    }

    return { componentes: nombresComponentes, corrientes, operaciones, valores, caudales_masicos };
  }

  /**
   * Volcado de una respuesta de /diagrama/resolver al estado comun.
   *
   * Vive aparte porque hay DOS caminos que la producen: el boton
   * "Resolver" y el panel de diseno con sus especificaciones. Que los dos
   * dejen el mismo estado es lo que permite resolver persiguiendo un
   * objetivo y pasar a "Resultados" a verlo con sus graficas, como
   * cualquier otra resolucion.
   */
  function aplicarRespuesta(datos: RespuestaResolver) {
    setPool(datos.pool);
    setDiagnostico(datos.diagnostico);
    setIncognitas(datos.incognitas_restantes);
    setCompleto(datos.completo);
    setInconsistencias(datos.inconsistencias ?? []);
    setDiagramas(datos.diagramas ?? {});
    setMasasMolares(datos.masas_molares_mezcla ?? {});
    setModo((m) => (m === "editar" ? "resultados" : m));
  }

  async function resolver() {
    setCargando(true);
    setError(null);
    try {
      const peticion = construirPeticion();

      const resp = await fetch(`${API_URL}/diagrama/resolver`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(peticion),
      });
      if (!resp.ok) {
        const detalle = await resp.json().catch(() => null);
        throw new Error(detalle?.detail ?? `Error HTTP ${resp.status}`);
      }
      aplicarRespuesta(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setCompleto(null);
    } finally {
      setCargando(false);
    }
  }

  // Conteo en vivo, con retardo: construir el diagrama en el backend
  // implica precalcular la curva de equilibrio de cada columna, asi que
  // no se puede llamar en cada tecla.
  useEffect(() => {
    if (nodes.length === 0 || nComp === 0) { setGradosLibertad(null); return; }
    const temporizador = setTimeout(async () => {
      try {
        const resp = await fetch(`${API_URL}/diagrama/grados-libertad`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(construirPeticion()),
        });
        setGradosLibertad(resp.ok ? await resp.json() : null);
      } catch {
        setGradosLibertad(null); // p.ej. faltan corrientes conectadas; no es un error que mostrar
      }
    }, 600);
    return () => clearTimeout(temporizador);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, dados, nComp, unidades.preferidas]);

  const grupos = useMemo(() => [...new Set(CATALOGO.map((c) => c.grupo))], []);
  const clavesIncoherentes = useMemo(
    () => new Set(inconsistencias.map((i) => i.variable).filter(Boolean) as string[]),
    [inconsistencias]
  );
  const modoCanvas: Modo = modo === "resultados" ? "resultados" : "editar";

  return (
    <ValoresContext.Provider value={{ componentes: nombresComponentes, dados, pool, modo: modoCanvas, clavesIncoherentes, unidades, masasMolares }}>
      <div className="flex min-h-0 flex-1 flex-col" onClick={() => setMenu(null)}>
        {/* Barra de modos: editar y leer resultados son tareas distintas,
            y mezclarlas en una sola vista fue lo que resulto confuso. */}
        <div className="flex items-center gap-3 border-b border-zinc-800 bg-zinc-900 px-3 py-1.5">
          <div className="flex rounded border border-zinc-700 p-0.5">
            {([["editar", "Editar"], ["resultados", "Resultados"], ["diseno", "Diseño"], ["reporte", "Reporte"]] as const).map(
              ([valor, etiqueta]) => (
                <button
                  key={valor}
                  onClick={() => setModo(valor)}
                  className={`rounded px-3 py-1 text-xs ${
                    modo === valor ? "bg-emerald-600 text-white" : "text-zinc-400 hover:text-zinc-100"
                  }`}
                >
                  {etiqueta}
                </button>
              )
            )}
          </div>

          <button
            onClick={resolver}
            disabled={cargando || nodes.length === 0 || nComp === 0}
            className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {cargando ? "Resolviendo..." : "Resolver"}
          </button>

          <EsperaCalculo activa={cargando} titulo="resolviendo el diagrama" segundosEsperados={12} compacto />

          {error && <span className="text-xs text-red-400">{error}</span>}
          {!unidades.listo && (
            <span
              className="rounded border border-amber-700 bg-amber-950/60 px-2 py-0.5 text-xs text-amber-200"
              title="GET /unidades no respondió. Sin esa tabla no hay selectores de unidad ni conversiones."
            >
              ⚠ sin conexión con el servidor: no se cargaron las unidades
            </span>
          )}
          {/* Sin componentes, una corriente se dibuja SIN composiciones y
              el diagrama no puede resolver nada. Antes eso no se decia:
              la corriente salia muda, con F y poco mas, y no habia forma
              de adivinar que faltaba elegir la mezcla. */}
          {simListo && !simulacion && (
            <Link href="/simulaciones"
              className="rounded border border-amber-700 bg-amber-950/60 px-2 py-0.5 text-xs text-amber-200 hover:bg-amber-900/60">
              ⚠ no hay simulación abierta — crear una
            </Link>
          )}
          {simListo && simulacion && nComp === 0 && (
            <Link href="/configuracion"
              className="rounded border border-amber-700 bg-amber-950/60 px-2 py-0.5 text-xs text-amber-200 hover:bg-amber-900/60">
              ⚠ esta simulación no tiene componentes — elígelos
            </Link>
          )}
          <Estado
            gradosLibertad={gradosLibertad}
            inconsistencias={inconsistencias.length}
            completo={completo}
            sinDeterminar={incognitas.length}
          />

          <span className="ml-auto text-[11px] text-zinc-500">
            {modo === "editar"
              ? "En ámbar: lo que falta por introducir"
              : modo === "resultados"
              ? "En azul: lo que calculó el simulador"
              : modo === "diseno"
              ? "La pregunta inversa: pedir el resultado y obtener el dato"
              : "Tabla completa de corrientes y equipos"}
          </span>
        </div>

        {modo === "reporte" ? (
          <Reporte nodos={nodes} componentes={nombresComponentes} dados={dados} pool={pool}
            inconsistencias={inconsistencias} diagramas={diagramas} unidades={unidades}
            masasMolares={masasMolares} />
        ) : modo === "diseno" ? (
          <Diseno nodos={nodes} componentes={nombresComponentes} dados={dados}
            unidades={unidades} apiUrl={API_URL}
            construirPeticion={construirPeticion} onResuelto={aplicarRespuesta} />
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-[1fr_340px]">
            <div className="relative min-h-0 min-w-0">
              {modo === "editar" && (
                <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-2">
                  {grupos.map((grupo) => (
                    <div key={grupo} className="flex items-center gap-1.5 rounded border border-zinc-800 bg-zinc-900/95 px-2 py-1">
                      <span className="text-[9px] uppercase tracking-wide text-zinc-500">{grupo}</span>
                      {CATALOGO.filter((c) => c.grupo === grupo).map((c) => (
                        <button
                          key={c.tipo}
                          onClick={() => agregarOperacion(c.tipo)}
                          className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-200 hover:border-emerald-500 hover:text-white"
                        >
                          + {c.etiqueta}
                        </button>
                      ))}
                    </div>
                  ))}
                  <button
                    onClick={agregarCorrienteSuelta}
                    className="rounded border border-emerald-700 bg-emerald-950/60 px-2 py-1 text-xs text-emerald-200 hover:border-emerald-400"
                  >
                    + Corriente
                  </button>
                  <span
                    className="rounded border border-dashed border-zinc-800 bg-zinc-900/95 px-2 py-1 text-[10px] text-zinc-600"
                    title="Una columna con extracciones laterales o varias alimentaciones no se puede resolver con métodos de atajo (McCabe-Thiele, FUG): necesita el sistema MESH plato a plato, que todavía no está. Lo que falta no es una entrada en este catálogo, es la física."
                  >
                    Extracción lateral — necesita MESH
                  </span>
                </div>
              )}

              {nComp === 0 && (
                <div className="absolute left-1/2 top-16 z-10 -translate-x-1/2 rounded border border-amber-600/60 bg-amber-950/90 px-3 py-2 text-xs text-amber-100">
                  No hay componentes. <Link href="/configuracion" className="underline">Defínelos primero</Link>.
                </div>
              )}

              <ReactFlow
          defaultEdgeOptions={ARISTA_RECTA}
          connectionLineType={ConnectionLineType.SmoothStep}
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                onNodeClick={(_, n) => { setSeleccionado(n.id); setMenu(null); }}
                onNodeContextMenu={(evento, n) => {
                  evento.preventDefault();
                  setSeleccionado(n.id);
                  setMenu({ nodoId: n.id, x: evento.clientX, y: evento.clientY });
                }}
                onPaneClick={() => { setSeleccionado(null); setMenu(null); }}
                deleteKeyCode={["Delete"]}
                colorMode="dark"
                onInit={(i) => setInstancia(i)}
                fitView
              >
                <Background color="#3f3f46" gap={18} />
                <Controls position="top-right" className="!border-zinc-700 !bg-zinc-900" />
                <MiniMap pannable zoomable className="!bg-zinc-900" maskColor="rgba(9,9,11,0.7)" />
              </ReactFlow>

              {menu && (
                <div
                  className="fixed z-50 min-w-40 rounded border border-zinc-700 bg-zinc-900 py-1 text-xs shadow-xl"
                  style={{ left: menu.x, top: menu.y }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="px-3 py-1 font-mono text-[10px] text-zinc-500">{menu.nodoId}</div>
                  <button
                    className="block w-full px-3 py-1.5 text-left hover:bg-zinc-800"
                    onClick={() => { setSeleccionado(menu.nodoId); setMenu(null); }}
                  >
                    Editar propiedades
                  </button>
                  <button
                    className="block w-full px-3 py-1.5 text-left text-red-400 hover:bg-zinc-800"
                    onClick={() => eliminarNodo(menu.nodoId)}
                  >
                    Eliminar
                  </button>
                </div>
              )}
            </div>

            <PanelLateral
              nodo={nodoSeleccionado}
              componentes={nombresComponentes}
              dados={dados}
              pool={pool}
              diagnostico={diagnostico}
              inconsistencias={inconsistencias}
              incognitas={incognitas}
              completo={completo}
              onValor={(clave, valor) => setDados((d) => ({ ...d, [clave]: valor }))}
              onDatos={(cambio) => nodoSeleccionado && actualizarDatosNodo(nodoSeleccionado.id, cambio)}
              onEliminar={() => nodoSeleccionado && eliminarNodo(nodoSeleccionado.id)}
              onRenombrar={renombrarNodo}
              onIrA={(nodoId) => setSeleccionado(nodoId)}
              unidades={unidades}
              redundancias={gradosLibertad?.redundancias ?? []}
              masasMolares={masasMolares}
            />
          </div>
        )}
      </div>
    </ValoresContext.Provider>
  );
}

/**
 * Un solo mensaje coherente. Antes se mostraban dos indicadores por
 * separado y podian leerse como una contradiccion ("faltan 14 variables"
 * junto a "GL = -1 sobran datos"): ambos eran ciertos, porque el conteo
 * global no ve la DISTRIBUCION -- se puede tener datos de mas en una
 * ecuacion y de menos en otra.
 */
function Estado({
  gradosLibertad, inconsistencias, completo, sinDeterminar,
}: {
  gradosLibertad: { grados_de_libertad: number; ecuaciones: number; incognitas: number; redundancias: Redundancia[] } | null;
  inconsistencias: number;
  completo: boolean | null;
  sinDeterminar: number;
}) {
  if (inconsistencias > 0) {
    return (
      <span className="rounded border border-red-700 bg-red-950/60 px-2 py-0.5 text-xs text-red-200">
        {inconsistencias} dato(s) incompatibles con las ecuaciones
      </span>
    );
  }

  const gl = gradosLibertad?.grados_de_libertad;
  const sobran = (gradosLibertad?.redundancias ?? []).reduce((a, r) => a + r.sobran, 0);
  const pendiente = completo === false ? sinDeterminar : 0;

  if (sobran > 0 && pendiente > 0) {
    return (
      <span className="rounded border border-amber-700 bg-amber-950/50 px-2 py-0.5 text-xs text-amber-300"
        title="No es una contradicción: los datos están mal repartidos entre las ecuaciones. Mira el panel para ver dónde sobran.">
        Datos mal repartidos: sobran {sobran} donde no hacen falta y quedan {pendiente} variables sin determinar
      </span>
    );
  }

  if (completo === true) return <span className="text-xs text-emerald-400">Resuelto por completo</span>;
  if (pendiente > 0) return <span className="text-xs text-amber-400">Quedan {pendiente} variables sin determinar</span>;

  if (gl === undefined || gl === null) return null;
  const clase = gl === 0
    ? "border-emerald-700 bg-emerald-950/50 text-emerald-300"
    : gl > 0
    ? "border-amber-700 bg-amber-950/50 text-amber-300"
    : "border-sky-700 bg-sky-950/50 text-sky-300";
  const texto = gl === 0
    ? "Exactamente especificado (GL = 0)"
    : gl > 0
    ? `Faltan ${gl} dato(s) por dar (GL = +${gl})`
    : `Sobran ${-gl} dato(s); se comprobarán por consistencia (GL = ${gl})`;
  return (
    <span className={`rounded border px-2 py-0.5 text-xs ${clase}`}
      title={`${gradosLibertad?.incognitas} incógnitas y ${gradosLibertad?.ecuaciones} ecuaciones. Estimación: supone ecuaciones independientes.`}>
      {texto}
    </span>
  );
}
