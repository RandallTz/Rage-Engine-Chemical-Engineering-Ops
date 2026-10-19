"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { Documento, Modelo } from "./contrato";
import type { RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";
import { leerEcuaciones, normalizarSubindicesEntrada, textoModelo } from "./entradaEcuaciones";
import { latexExpresion } from "./exportar";
import { consultarNucleo } from "./clienteNucleo";
import { formulacionesDe, prepararSolicitud } from "./lecturaNucleo";
import { exportarDesarrollo } from "./exportarDesarrollo";
import FormulaLatex from "../flowsheet/FormulaLatex";
import ResultadosNucleo, { type VistaResultado } from "./ResultadosNucleo";
import DimensionesModelo from "./DimensionesModelo";
import { claveCalculo, guardarCalculo, leerCalculo } from "./resultadosAdim";
import styles from "../motor/trabajoMotor.module.css";

type Pagina = { solicitud: SolicitudNucleo; respuesta: RespuestaNucleo };
type Calculo = { claveDocumento: string; fuente: string; documento: Documento; paginas: Pagina[] };
type Vista = "ecuaciones" | VistaResultado;

const OPERADORES = [["d(c,t)", "∂/∂t", "Derivada temporal"], ["d(c,x,2)", "∂²/∂x²", "Segunda derivada espacial"], ["lap(c,x)", "∇²", "Laplaciano (añade y, z para 2D o 3D)"],
  ["lap_cil(c,r)", "∇² cil.", "Laplaciano cilíndrico radial"], ["lap_esf(c,r)", "∇² esf.", "Laplaciano esférico radial"], ["div(F,x)", "∇·", "Divergencia"], ["grad(c,x)", "∇", "Gradiente"],
  ["^2", "x²", "Potencia"], ["sqrt(c)", "√", "Raíz cuadrada"], ["exp(c)", "exp", "Exponencial"], ["tanh(c)", "tanh", "Tangente hiperbólica"]] as const;
const SUGERENCIAS_UNIDADES = ["mol/m^3", "m^2/s", "1/s", "m/s", "s", "m", "K", "1", "mol/(m^2*s)", "kg/m^3"];

function descargar(nombre: string, texto: string, tipo = "application/json") {
  const url = URL.createObjectURL(new Blob([texto], { type: tipo }));
  const a = document.createElement("a"); a.href = url; a.download = nombre; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function EntradaSimple({ documento, procesar, revisionVista, textoInicial, guardarTexto, volver, barra, avanzado, derivadaDe }: {
  /** Ecuaciones derivadas en una hoja del Engine: se leen, no se escriben (principio 10). */
  derivadaDe?: { hojaId: string; nombre: string };
  documento: Documento; revisionVista: number; procesar: (modelo: Modelo) => Documento | null; textoInicial?: string | null; guardarTexto?: (texto: string) => void;
  volver?: () => void; barra?: ReactNode; avanzado?: ReactNode;
}) {
  const fuente = textoModelo(documento.modelo), claveDocumento = claveCalculo(documento);
  const base = `${revisionVista}:${documento.id}:${fuente}`;
  const [borrador, setBorrador] = useState<{ base: string; texto: string } | null>(() => textoInicial === null || textoInicial === undefined ? null : { base, texto: textoInicial });
  const texto = borrador?.base === base ? borrador.texto : fuente;
  const [enviado, setEnviado] = useState(false), [ocupado, setOcupado] = useState(false), [mensaje, setMensaje] = useState("");
  const [calculo, setCalculo] = useState<Calculo | null>(null), [pagina, setPagina] = useState(0);
  const [vista, setVista] = useState<Vista>("ecuaciones");
  const [unidades, setUnidades] = useState<Record<string, string>>({});
  const control = useRef<AbortController | null>(null);
  useEffect(() => () => control.current?.abort(), []);
  // El último cálculo guardado de esta hoja, si sigue siendo el de este documento.
  useEffect(() => {
    let vigente = true;
    leerCalculo(documento, fuente).then(c => { if (vigente && c) setCalculo(actual => actual ?? c); }).catch(() => undefined);
    return () => { vigente = false; };
  }, [documento, fuente]);
  let modelo: Modelo | null = null, error = "";
  try { if (texto.trim()) modelo = leerEcuaciones(texto, documento.modelo); }
  catch (e) { error = e instanceof Error ? e.message : String(e); }
  const canonico = modelo ? textoModelo(modelo) : texto;
  const vigente = calculo?.claveDocumento === claveDocumento && calculo.fuente === canonico ? calculo : null;
  const actual = vigente?.paginas[Math.min(pagina, vigente.paginas.length - 1)];
  const formas = actual ? formulacionesDe(actual.respuesta) : [];
  const conResultado = actual?.respuesta.estado === "correcto" && formas.length > 0;
  const pantalla: Vista = conResultado && !ocupado ? vista : "ecuaciones";

  async function calcular(doc: Documento, desde?: number) {
    control.current?.abort(); const controlador = new AbortController(); control.current = controlador;
    const timeout = setTimeout(() => controlador.abort(), 95000);
    const config = doc.exploracion;
    const solicitud = prepararSolicitud(doc, {
      presupuesto: config?.presupuesto ?? 200, ...(desde !== undefined ? { desde } : {}),
      gruposPi: config?.incluirGruposPi ?? true, maxExponentePi: config?.maxExponentePi ?? 4, maxDenominadorPi: config?.maxDenominadorPi ?? 4,
    });
    setOcupado(true); setMensaje(""); if (desde === undefined) { setCalculo(null); setPagina(0); }
    try {
      const respuesta = await consultarNucleo(solicitud, controlador.signal);
      if (control.current !== controlador) return;
      const paginaNueva = { solicitud, respuesta };
      const paginas = desde === undefined ? [paginaNueva] : [...(vigente?.paginas ?? []), paginaNueva];
      const nuevo = { claveDocumento: claveCalculo(doc), fuente: textoModelo(doc.modelo), documento: doc, paginas };
      setCalculo(nuevo); setPagina(paginas.length - 1); setUnidades({});
      if (respuesta.estado === "correcto") { setVista("resultado"); void guardarCalculo(doc.id, nuevo).catch(() => undefined); }
    } catch (e) {
      if (control.current !== controlador) return;
      setMensaje(controlador.signal.aborted ? "Solicitud cancelada o tiempo de espera agotado. Puedes reintentar con un presupuesto menor (Opciones avanzadas)." : e instanceof Error ? e.message : String(e));
    } finally { clearTimeout(timeout); if (control.current === controlador) { setOcupado(false); control.current = null; } }
  }
  function enviar() {
    setEnviado(true);
    const textoNorm = normalizarSubindicesEntrada(texto);
    if (textoNorm !== texto) { setBorrador({ base, texto: textoNorm }); guardarTexto?.(textoNorm); }
    let m = modelo;
    try { if (textoNorm.trim()) m = leerEcuaciones(textoNorm, documento.modelo); }
    catch (e) { setMensaje(e instanceof Error ? e.message : String(e)); return; }
    if (!m) { setMensaje(error || "Escribe una ecuación para continuar."); return; }
    const doc = procesar(m); if (doc) void calcular(doc);
  }
  function insertar(snippet: string) {
    const area = document.getElementById("adim-ecuacion") as HTMLTextAreaElement | null;
    const inicio = area?.selectionStart ?? texto.length, fin = area?.selectionEnd ?? texto.length;
    const nuevo = texto.slice(0, inicio) + snippet + texto.slice(fin);
    setBorrador({ base, texto: nuevo }); guardarTexto?.(nuevo);
    requestAnimationFrame(() => { area?.focus(); area?.setSelectionRange(inicio + snippet.length, inicio + snippet.length); });
  }

  const simbolos = (modelo ?? documento.modelo).simbolos;
  const conUnidad = simbolos.filter(s => s.unidad || s.dimension !== null).length;
  const fallo = !ocupado && actual && actual.respuesta.estado !== "correcto" && actual.respuesta.estado !== "requiere_datos" ? actual.respuesta : null;
  const nav = (
    <nav className={`${styles.workNav} adim-worknav`} aria-label="Vistas de la hoja">
      {volver && <button type="button" onClick={volver}>← Hojas</button>}
      {([["ecuaciones", "Ecuaciones"], ["resultado", "Formulaciones"], ["estudio", "Estudio"], ["desarrollo", "Desarrollo"], ...(formas.length > 1 ? [["comparar", "Comparar"]] : [])] as [Vista, string][]).map(([id, nombre]) =>
        <button key={id} type="button" aria-current={pantalla === id ? "page" : undefined} disabled={id !== "ecuaciones" && !conResultado} onClick={() => setVista(id)}>{nombre}</button>)}
    </nav>
  );

  if (pantalla !== "ecuaciones" && actual && vigente) return <>
    {nav}
    {vigente.paginas.length > 1 && <nav className={styles.tabs} aria-label="Páginas de búsqueda">{vigente.paginas.map((_, i) => <button key={i} aria-pressed={i === pagina} onClick={() => setPagina(i)}>Búsqueda {i + 1}</button>)}</nav>}
    <ResultadosNucleo
      key={pagina}
      vista={pantalla} ir={setVista}
      respuesta={actual.respuesta}
      solicitud={actual.solicitud}
      modelo={vigente.documento.modelo}
      documentoId={vigente.documento.id}
      nombreModelo={documento.nombre}
      continuar={() => { const siguiente = actual.respuesta.cobertura?.siguiente; if (typeof siguiente === "number") void calcular(vigente.documento, siguiente); }}
      exportar={(i, tipo) => {
        if (tipo === "json") descargar("adimensionalizacion-resultado.json", JSON.stringify({ solicitud: actual.solicitud, respuesta: actual.respuesta }, null, 2));
        else descargar(`desarrollo-forma-${i + 1}.tex`, exportarDesarrollo(formas[i]), "text/plain");
      }}
    />
  </>;

  return <>
    {nav}
    {barra}
    <header className={styles.heading}><div><span className={styles.eyebrow}>Adimensionalización / Hoja</span><h1>Ecuaciones</h1></div></header>
    <div className={styles.solveLayout}>
      <section className="adim-pagina">
        <form id="adim-form-ecuaciones" className="adim-simple" onSubmit={e => { e.preventDefault(); enviar(); }}>
          <label htmlFor="adim-ecuacion" className="adim-input-label">{derivadaDe ? `Ecuaciones derivadas en la hoja del Engine «${derivadaDe.nombre}»` : "Ecuación o sistema"}</label>
          {derivadaDe && <p className="adim-input-hint">Vienen de las ecuaciones fundamentales y los supuestos de esa hoja; aquí no se escriben. Para cambiarlas, edita la hoja en el Engine y vuelve a importarla. <a href={`/motor/hojas/${derivadaDe.hojaId}`}>Abrir la hoja del Engine ↗</a></p>}
          {!derivadaDe && <details className="adim-insertar">
            <summary>Insertar operador</summary>
            <div className="adim-quick-toolbar" aria-label="Operadores">
              {OPERADORES.map(([snippet, etiqueta, ayuda]) => <button key={snippet} type="button" className="adim-chip-btn" onClick={() => insertar(snippet)} title={ayuda}>{etiqueta}</button>)}
            </div>
          </details>}
          <textarea id="adim-ecuacion" aria-describedby="adim-sintaxis" spellCheck={false} value={texto} readOnly={!!derivadaDe}
            placeholder="d(c_A,t) = D*lap(c_A,x) - k_1*c_A*c_B + k_2*c_C"
            onChange={e => { control.current?.abort(); setBorrador({ base, texto: e.target.value }); guardarTexto?.(e.target.value); setMensaje(""); setEnviado(false); }}
            onBlur={() => { const norm = normalizarSubindicesEntrada(texto); if (norm !== texto) { setBorrador({ base, texto: norm }); guardarTexto?.(norm); } }} />
          <p id="adim-sintaxis" className="adim-input-hint">Una ecuación por línea. Subíndices con guion bajo (<code>c_A</code>, <code>k_1</code>), producto con <code>*</code>, derivadas con <code>d(c,t)</code>, potencias <code>c^2</code>, operadores <code>lap(c,x)</code>, <code>div(F,x)</code>, <code>grad(c,x)</code>.</p>
          {modelo && <div className="adim-live-equations" aria-label="Vista previa de la ecuación">{modelo.ecuaciones.map(eq => <FormulaLatex key={eq.id} bloque latex={`${latexExpresion(eq.izquierda)} = ${latexExpresion(eq.derecha)}`} lectura="Vista previa de la ecuación introducida" />)}</div>}
          {error && <p className="adim-input-error" role={enviado ? "alert" : undefined}>{error}</p>}
        </form>

        {ocupado && <div className="adim-loading" role="status"><p>El núcleo analiza dimensiones, compara formulaciones y construye el desarrollo algebraico.</p><div /><div /><div /></div>}
        {fallo && <div className={styles.error} role="alert"><span>{fallo.diagnosticos.filter(d => d.severidad === "error").map(d => d.mensaje).join(" · ") || `El núcleo respondió «${fallo.estado}».`}</span></div>}
        {!ocupado && actual?.respuesta.estado === "requiere_datos" && <form className="adim-required-data" onSubmit={e => {
          e.preventDefault();
          const faltantes = actual.respuesta.dimensional?.faltantes ?? [];
          if (faltantes.some(id => !unidades[id]?.trim())) { setMensaje("Completa las unidades solicitadas. Para una cantidad adimensional, escribe 1."); return; }
          const m = { ...vigente!.documento.modelo, simbolos: vigente!.documento.modelo.simbolos.map(s => faltantes.includes(s.id) ? { ...s, dimension: null, unidad: unidades[s.id].trim() } : s) };
          const doc = procesar(m); if (doc) void calcular(doc);
        }}>
          <h2>Solo faltan estas unidades</h2>
          <p>Indica una unidad compatible con cada variable; el núcleo infiere el resto. Usa 1 si la cantidad no tiene dimensiones.</p>
          <div className="adim-data-fields">
            {actual.respuesta.dimensional?.faltantes.map(id => (
              <div key={id} className="grid gap-2">
                <label>Unidad de {id}<input required value={unidades[id] ?? ""} placeholder="s, m, mol/m^3 o 1" onChange={e => setUnidades({ ...unidades, [id]: e.target.value })} /></label>
                <div className="adim-unit-suggestions">{SUGERENCIAS_UNIDADES.map(u => <button type="button" key={u} className="adim-unit-chip" onClick={() => setUnidades({ ...unidades, [id]: u })}>{u}</button>)}</div>
              </div>
            ))}
          </div>
          <button className={styles.primary} type="submit">Continuar</button>
        </form>}

        {modelo && <details className={styles.settings}>
          <summary>Unidades y dimensiones ({conUnidad} de {simbolos.length} declaradas)</summary>
          <DimensionesModelo documento={{ ...documento, modelo }} cambiar={m => { control.current?.abort(); procesar(m); }} />
        </details>}
        {avanzado}
      </section>
      <aside className={styles.solveAside}>
        <div className={styles.counts}>
          <div><span>Ecuaciones</span><strong>{modelo?.ecuaciones.length ?? 0}</strong></div>
          <div><span>Símbolos</span><strong>{simbolos.length}</strong></div>
          <div><span>Con unidad</span><strong>{conUnidad} / {simbolos.length}</strong></div>
          <div><span>Formulaciones</span><strong>{conResultado ? formas.length : "—"}</strong></div>
        </div>
        <button className={styles.primary} type="submit" form="adim-form-ecuaciones" disabled={ocupado}>{ocupado ? "Calculando…" : "Adimensionalizar"}</button>
        {ocupado && <button type="button" className="adim-enlace adim-aside-enlace" onClick={() => control.current?.abort()}>Cancelar cálculo</button>}
        {mensaje && <p className="adim-input-error" role="alert">{mensaje}</p>}
        {conResultado && !ocupado && <button type="button" className="adim-enlace adim-aside-enlace" onClick={() => setVista("resultado")}>Ver formulaciones →</button>}
        <p className="adim-aside-nota">El núcleo comprueba dimensiones, busca todas las normalizaciones de la familia y certifica cada formulación por sustitución inversa.</p>
      </aside>
    </div>
  </>;
}
