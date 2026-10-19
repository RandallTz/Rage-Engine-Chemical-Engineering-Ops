"use client";

/** Cuaderno de la adimensionalización. Regla (ARQUITECTURA_MOTOR.md §2, principio 10): la adimensionalización
 * trabaja SOLO sobre ecuaciones derivadas de las fundamentales en una hoja del Engine. No se escriben modelos
 * aquí: se importan de una hoja del Engine. Un documento escrito directamente (de versiones anteriores o de un
 * cuaderno importado) queda retirado: se conserva para exportarlo, pero no se abre para trabajar. */
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Documento } from "./contrato";
import { CLAVE_ALMACEN, leerDocumento } from "./documento";
import { archivarHoja, CLAVE_HOJAS, crearCuaderno, cuadernoVacio, duplicarHoja, leerCuaderno, nuevaHoja, retirarEscritas } from "./hojas";
import type { Cuaderno as DatosCuaderno, Hoja } from "./hojas";
import Editor from "./Editor";
import { leerHojaMotor } from "./desdeMotor";
import { copiarOrigen, guardarImportacion, leerOrigen } from "./origenMotor";
import { useHojasMotor } from "../motor/useHojasMotor";
import tema from "../motor/balances.module.css";
import styles from "../motor/trabajoMotor.module.css";
import barra from "../motor/motor.module.css";

type Pestana = "motor" | "hojas" | "archivadas" | "retiradas";

function descargar(nombre: string, texto: string) {
  const url = URL.createObjectURL(new Blob([texto], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;
/** Un documento es de trabajo solo si viene de una hoja del Engine. */
const derivada = (h: Hoja) => !!leerOrigen(h.documento.id);

export default function Cuaderno() {
  const [datos, setDatos] = useState<DatosCuaderno | null>(null);
  const [vista, setVista] = useState<"gestor" | "hoja">("gestor");
  const [pestana, setPestana] = useState<Pestana>("motor");
  const [error, setError] = useState(""), [aviso, setAviso] = useState("");
  const [apertura, setApertura] = useState(0);
  const [guardado, setGuardado] = useState("Abriendo hojas…");
  const hojasMotor = useHojasMotor();
  const lecturas = useMemo(() => hojasMotor.filter(h => !h.archivada).map(leerHojaMotor), [hojasMotor]);

  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const texto = localStorage.getItem(CLAVE_HOJAS), legado = localStorage.getItem(CLAVE_ALMACEN);
        const cuaderno = texto ? leerCuaderno(texto) : legado ? crearCuaderno(leerDocumento(legado)) : cuadernoVacio();
        const revisado = retirarEscritas(cuaderno, derivada);
        const retiradas = revisado.hojas.filter(h => h.retirada).length - cuaderno.hojas.filter(h => h.retirada).length;
        if (retiradas > 0) setAviso(`${plural(retiradas, "documento escrito directamente quedó retirado", "documentos escritos directamente quedaron retirados")}: la adimensionalización trabaja sobre ecuaciones derivadas en una hoja del Engine. Siguen en «Retiradas» para exportarlos.`);
        setDatos(revisado);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setDatos(cuadernoVacio());
      }
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!datos) return;
    const timer = setTimeout(() => {
      try { localStorage.setItem(CLAVE_HOJAS, JSON.stringify(datos)); setGuardado("Guardado en este navegador."); }
      catch { setGuardado("No se pudo guardar. Exporta el cuaderno para conservar las hojas."); }
    }, 200);
    return () => clearTimeout(timer);
  }, [datos]);

  const guardarHoja = useCallback((hojaId: string, documento: Documento) => {
    setDatos(prev => {
      const hoja = prev?.hojas.find(h => h.id === hojaId);
      if (!prev || !hoja || JSON.stringify(hoja.documento) === JSON.stringify(documento)) return prev;
      return { ...prev, hojas: prev.hojas.map(h => h.id === hojaId ? { ...h, documento, borrador: null, actualizada: new Date().toISOString() } : h) };
    });
  }, []);
  const guardarBorradorHoja = useCallback((hojaId: string, borrador: string) => {
    setDatos(prev => prev ? { ...prev, hojas: prev.hojas.map(h => h.id === hojaId ? { ...h, borrador, actualizada: new Date().toISOString() } : h) } : prev);
  }, []);

  function abrirHoja(hojaId: string) {
    const h = datos?.hojas.find(x => x.id === hojaId);
    if (!datos || !h || h.retirada) return;
    setDatos({ ...datos, activaId: hojaId }); setVista("hoja"); setApertura(n => n + 1); setError("");
  }
  /** Única entrada de documentos: una hoja del Engine importada. */
  function agregarImportado(doc: Documento): Hoja | null {
    if (!datos) return null;
    if (datos.hojas.length >= 50) { setError("El cuaderno admite hasta 50 hojas. Archiva o exporta algunas antes de importar otra."); return null; }
    const hoja = nuevaHoja(doc);
    setDatos({ ...datos, hojas: [...datos.hojas, hoja], activaId: hoja.id });
    setVista("hoja"); setApertura(n => n + 1); setError("");
    return hoja;
  }
  function archivar(id: string) {
    try { setDatos(archivarHoja(datos!, id)); setError(""); return true; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return false; }
  }
  function duplicar(h: Hoja) {
    if (!datos || datos.hojas.length >= 50 || h.retirada) return;
    const copia = duplicarHoja(h);
    copiarOrigen(h.documento.id, copia.documento.id);
    setDatos({ ...datos, hojas: [...datos.hojas, copia], activaId: copia.id });
  }

  const activas = datos?.hojas.filter(h => !h.archivada && !h.retirada) ?? [];
  const archivadas = datos?.hojas.filter(h => h.archivada && !h.retirada) ?? [];
  const retiradas = datos?.hojas.filter(h => h.retirada) ?? [];
  const activa = datos?.hojas.find(h => h.id === datos.activaId && !h.retirada);
  const importadaDe = (hojaMotorId: string) => activas.find(h => leerOrigen(h.documento.id)?.hojaId === hojaMotorId);

  if (vista === "hoja" && activa && datos) {
    const origen = leerOrigen(activa.documento.id);
    return (
      <div className={tema.espacio} data-balance="materia">
        <div className={barra.page}>
          {error && <div role="alert" className={styles.error}>{error}<button aria-label="Cerrar aviso" onClick={() => setError("")}>×</button></div>}
          <Editor key={`${activa.id}:${apertura}`} inicial={activa.documento} guardar={doc => guardarHoja(activa.id, doc)}
            textoInicial={activa.borrador} guardarTexto={txt => guardarBorradorHoja(activa.id, txt)}
            derivadaDe={origen ? { hojaId: origen.hojaId, nombre: origen.hojaNombre } : undefined}
            volver={() => { setVista("gestor"); setError(""); }}
            barra={<div className={barra.documentBar}>
              <form onSubmit={e => e.preventDefault()}>
                <input aria-label="Nombre de la hoja" value={activa.documento.nombre} onBlur={() => setApertura(n => n + 1)}
                  onChange={e => { if (e.target.value.trim()) setDatos({ ...datos, hojas: datos.hojas.map(h => h.id === activa.id ? { ...h, documento: { ...h.documento, nombre: e.target.value } } : h) }); }} />
              </form>
              {origen && <Link href={`/motor/hojas/${origen.hojaId}`}>Hoja del Engine ↗</Link>}
              <button type="button" onClick={() => { duplicar(activa); setApertura(n => n + 1); }}>Duplicar</button>
              <button type="button" onClick={() => { if (archivar(activa.id)) setVista("gestor"); }}>Archivar</button>
            </div>} />
          <small className={styles.muted}>{guardado}</small>
        </div>
      </div>
    );
  }

  const tarjeta = (h: Hoja) => {
    const ecs = h.documento.modelo.ecuaciones.length, origen = leerOrigen(h.documento.id);
    return (
      <article key={h.id}>
        <button type="button" className="adim-tarjeta-abrir" onClick={() => abrirHoja(h.id)}>
          <h2>{h.documento.nombre}</h2>
          <span>{ecs ? plural(ecs, "ecuación", "ecuaciones") : "Sin ecuaciones"} · {plural(h.documento.modelo.simbolos.length, "símbolo", "símbolos")}{origen ? ` · de «${origen.hojaNombre}»` : ""}</span>
          <small>{new Date(h.actualizada).toLocaleString("es-MX")}</small>
        </button>
        <div>
          {h.archivada
            ? <button onClick={() => setDatos({ ...datos!, hojas: datos!.hojas.map(x => x.id === h.id ? { ...x, archivada: false } : x), activaId: datos!.activaId || h.id })}>Restaurar</button>
            : <><button className={styles.solveLink} onClick={() => abrirHoja(h.id)}>Abrir →</button><button onClick={() => duplicar(h)}>Duplicar</button><button onClick={() => archivar(h.id)}>Archivar</button></>}
        </div>
      </article>
    );
  };

  return (
    <div className={tema.espacio} data-balance="materia">
      <div className={styles.page}>
        <header className={styles.heading}>
          <div><span className={styles.eyebrow}>Adimensionalización / Hojas</span><h1>Adimensionalizar una hoja del Engine</h1></div>
          <Link className={styles.primary} href="/motor/hojas">Derivar un modelo en el Engine</Link>
        </header>
        <p className={styles.muted}>Todo modelo parte de las ecuaciones fundamentales y llega, con supuestos, al modelo que necesitas. Eso se hace en el Engine; aquí se escala y se estudia el resultado de esa derivación.</p>
        {error && <div role="alert" className={styles.error}>{error}<button aria-label="Cerrar aviso" onClick={() => setError("")}>×</button></div>}
        {aviso && <div role="status" className={styles.notice}>{aviso}<button aria-label="Cerrar confirmación" onClick={() => setAviso("")}>×</button></div>}
        <nav className={styles.localNav}>
          {([["motor", "Desde el Engine"], ["hojas", `Adimensionalizadas (${activas.length})`], ["archivadas", "Archivadas"], ["retiradas", `Retiradas (${retiradas.length})`]] as const).map(([id, nombre]) =>
            <button key={id} aria-pressed={pestana === id} onClick={() => setPestana(id)}>{nombre}</button>)}
          <Link href="/motor/hojas">Ir al Engine</Link>
        </nav>

        {pestana === "motor" && (lecturas.length
          ? <div className={styles.sheetList}>{lecturas.map(({ hoja, importacion, motivo }) => {
              const previa = importadaDe(hoja.id);
              const importar = () => {
                const nueva = leerHojaMotor(hoja).importacion;
                if (!nueva) return;
                const h = agregarImportado(nueva.documento);
                if (h) { guardarImportacion({ ...nueva, documento: h.documento }); setAviso(""); }
              };
              return (
                <article key={hoja.id}>
                  <Link href={`/motor/hojas/${hoja.id}`}>
                    <h2>{hoja.nombre}</h2>
                    <span>{importacion
                      ? `${importacion.origen.modo === "1d" ? "Campo en 1D" : "Evolución temporal"} · ${plural(importacion.origen.componentes.length, "componente", "componentes")}${hoja.resultadoRef ? " · resuelta en el Engine" : ""}`
                      : motivo}</span>
                    <small>{new Date(hoja.actualizada).toLocaleString("es-MX")}</small>
                  </Link>
                  <div>
                    {previa
                      ? <><button className={styles.solveLink} onClick={() => abrirHoja(previa.id)}>Abrir →</button><button onClick={importar}>Importar de nuevo</button></>
                      : importacion ? <button className={styles.solveLink} onClick={importar}>Adimensionalizar →</button> : <span>Todavía no se puede adimensionalizar</span>}
                  </div>
                </article>
              );
            })}</div>
          : <div className={styles.empty}><h2>Sin hojas en el Engine</h2><span>Deriva primero el modelo en una hoja del Engine, desde sus ecuaciones fundamentales. Después aparece aquí para adimensionalizarlo.</span><Link className={styles.primary} href="/motor/hojas">Ir al Engine</Link></div>)}

        {pestana === "hojas" && (activas.length
          ? <div className={styles.sheetList}>{activas.map(tarjeta)}</div>
          : <div className={styles.empty}><h2>Sin hojas adimensionalizadas</h2><span>Elige una hoja en «Desde el Engine» para adimensionalizar sus ecuaciones.</span><button className={styles.primary} onClick={() => setPestana("motor")}>Ver hojas del Engine</button></div>)}

        {pestana === "archivadas" && (archivadas.length
          ? <div className={styles.sheetList}>{archivadas.map(tarjeta)}</div>
          : <div className={styles.empty}><h2>Sin hojas archivadas</h2><span>Las hojas archivadas se pueden recuperar.</span></div>)}

        {pestana === "retiradas" && (retiradas.length
          ? <div className={styles.sheetList}>{retiradas.map(h => (
              <article key={h.id}>
                <div><h2>{h.documento.nombre}</h2><span>{plural(h.documento.modelo.ecuaciones.length, "ecuación escrita", "ecuaciones escritas")} · retirada el {new Date(h.retirada!.fecha).toLocaleDateString("es-MX")}</span><small>{h.retirada!.motivo}</small></div>
                <div><button onClick={() => descargar(`${h.documento.nombre.replace(/[^\w.-]+/g, "_")}.json`, JSON.stringify(h.documento, null, 2))}>Exportar</button></div>
              </article>))}</div>
          : <div className={styles.empty}><h2>Sin documentos retirados</h2><span>Aquí quedarían los documentos escritos directamente, sin derivarse en el Engine.</span></div>)}

        <small className={styles.muted}>
          {guardado}{" "}
          <button className="adim-enlace" disabled={!datos} onClick={() => datos && descargar("cuaderno-adimensionalizacion.json", JSON.stringify(datos, null, 2))}>Exportar cuaderno</button>{" · "}
          <label className="adim-enlace">Importar cuaderno<input type="file" className="sr-only" accept="application/json,.json" onChange={async e => {
            const f = e.target.files?.[0]; e.target.value = "";
            if (!f) return;
            try { if (f.size > 8_000_000) throw new Error("El cuaderno supera 8 MB."); setDatos(retirarEscritas(leerCuaderno(await f.text()), derivada)); setApertura(n => n + 1); setError(""); }
            catch (err) { setError(err instanceof Error ? err.message : String(err)); }
          }} /></label>
        </small>
      </div>
    </div>
  );
}
