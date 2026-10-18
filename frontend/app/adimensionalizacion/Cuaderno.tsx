"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Documento } from "./contrato";
import { CLAVE_ALMACEN, crearDocumento, leerDocumento } from "./documento";
import { archivarHoja, CLAVE_HOJAS, crearCuaderno, duplicarHoja, leerCuaderno, nuevaHoja } from "./hojas";
import type { Cuaderno as DatosCuaderno, Hoja } from "./hojas";
import Editor from "./Editor";
import { crearColeccionHojasEjemplo, EJEMPLOS_COMPLEJOS } from "./ejemplos";
import { leerHojaMotor } from "./desdeMotor";
import { guardarImportacion, leerOrigen } from "./origenMotor";
import { useHojasMotor } from "../motor/useHojasMotor";
import tema from "../motor/balances.module.css";
import styles from "../motor/trabajoMotor.module.css";
import barra from "../motor/motor.module.css";

type Pestana = "hojas" | "motor" | "catalogo" | "archivadas";

function descargar(nombre: string, texto: string) {
  const url = URL.createObjectURL(new Blob([texto], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function crearCuadernoConEjemplos(): DatosCuaderno {
  const hojas = crearColeccionHojasEjemplo().map(d => nuevaHoja(d));
  return { formato: "adimensionalizacion.hojas", version: 1, hojas, activaId: hojas[0].id };
}
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

export default function Cuaderno() {
  const [datos, setDatos] = useState<DatosCuaderno | null>(null);
  const [vista, setVista] = useState<"gestor" | "hoja">("gestor");
  const [pestana, setPestana] = useState<Pestana>("hojas");
  const [error, setError] = useState(""), [aviso, setAviso] = useState("");
  const [apertura, setApertura] = useState(0);
  const [guardado, setGuardado] = useState("Abriendo hojas…");
  const hojasMotor = useHojasMotor();
  const lecturas = useMemo(() => hojasMotor.filter(h => !h.archivada).map(leerHojaMotor), [hojasMotor]);

  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const texto = localStorage.getItem(CLAVE_HOJAS), legado = localStorage.getItem(CLAVE_ALMACEN);
        let cuaderno: DatosCuaderno;
        if (texto) {
          const leido = leerCuaderno(texto);
          const vacio = leido.hojas.every(h => h.documento.modelo.ecuaciones.length === 0 && !h.borrador?.trim());
          cuaderno = vacio ? crearCuadernoConEjemplos() : leido;
        } else cuaderno = legado ? crearCuaderno(leerDocumento(legado)) : crearCuadernoConEjemplos();
        setDatos(cuaderno);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setDatos(crearCuadernoConEjemplos());
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
    if (!datos) return;
    setDatos({ ...datos, activaId: hojaId }); setVista("hoja"); setApertura(n => n + 1); setError("");
  }
  function agregar(doc?: Documento): Hoja | null {
    if (!datos) return null;
    if (datos.hojas.length >= 50) { setError("El cuaderno admite hasta 50 hojas. Archiva o exporta algunas antes de añadir otra."); return null; }
    const hoja = nuevaHoja(doc ?? { ...crearDocumento(), nombre: `Hoja ${datos.hojas.length + 1}` });
    setDatos({ ...datos, hojas: [...datos.hojas, hoja], activaId: hoja.id });
    setVista("hoja"); setApertura(n => n + 1); setError("");
    return hoja;
  }
  function archivar(id: string) {
    try { setDatos(archivarHoja(datos!, id)); setError(""); return true; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return false; }
  }
  function duplicar(h: Hoja) {
    if (!datos || datos.hojas.length >= 50) return;
    const copia = duplicarHoja(h);
    setDatos({ ...datos, hojas: [...datos.hojas, copia], activaId: copia.id });
  }

  const activas = datos?.hojas.filter(h => !h.archivada) ?? [];
  const archivadas = datos?.hojas.filter(h => h.archivada) ?? [];
  const activa = datos?.hojas.find(h => h.id === datos.activaId);
  const importadaDe = (hojaMotorId: string) => activas.find(h => leerOrigen(h.documento.id)?.hojaId === hojaMotorId);

  if (vista === "hoja" && activa && datos) {
    const origen = leerOrigen(activa.documento.id);
    return (
      <div className={tema.espacio} data-balance="materia">
        <div className={barra.page}>
          {error && <div role="alert" className={styles.error}>{error}<button aria-label="Cerrar aviso" onClick={() => setError("")}>×</button></div>}
          <Editor key={`${activa.id}:${apertura}`} inicial={activa.documento} guardar={doc => guardarHoja(activa.id, doc)}
            textoInicial={activa.borrador} guardarTexto={txt => guardarBorradorHoja(activa.id, txt)}
            volver={() => { setVista("gestor"); setError(""); }}
            barra={<div className={barra.documentBar}>
              <form onSubmit={e => e.preventDefault()}>
                <input aria-label="Nombre de la hoja" value={activa.documento.nombre} onBlur={() => setApertura(n => n + 1)}
                  onChange={e => { if (e.target.value.trim()) setDatos({ ...datos, hojas: datos.hojas.map(h => h.id === activa.id ? { ...h, documento: { ...h.documento, nombre: e.target.value } } : h) }); }} />
              </form>
              {origen && <Link href={`/motor/hojas/${origen.hojaId}`}>Hoja del motor ↗</Link>}
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
          <span>{ecs ? plural(ecs, "ecuación", "ecuaciones") : "Sin ecuaciones"} · {plural(h.documento.modelo.simbolos.length, "símbolo", "símbolos")}{origen ? " · del motor" : ""}</span>
          <small>{new Date(h.actualizada).toLocaleString("es-MX")}</small>
        </button>
        <div>
          {h.archivada
            ? <button onClick={() => setDatos({ ...datos!, hojas: datos!.hojas.map(x => x.id === h.id ? { ...x, archivada: false } : x) })}>Restaurar</button>
            : <><button className={styles.solveLink} onClick={() => abrirHoja(h.id)}>Abrir →</button><button onClick={() => duplicar(h)}>Duplicar</button><button onClick={() => archivar(h.id)}>Archivar</button></>}
        </div>
      </article>
    );
  };

  return (
    <div className={tema.espacio} data-balance="materia">
      <div className={styles.page}>
        <header className={styles.heading}>
          <div><span className={styles.eyebrow}>Adimensionalización / Hojas</span><h1>Mis hojas</h1></div>
          <button className={styles.primary} disabled={!datos} onClick={() => agregar()}>Nueva hoja</button>
        </header>
        {error && <div role="alert" className={styles.error}>{error}<button aria-label="Cerrar aviso" onClick={() => setError("")}>×</button></div>}
        {aviso && <div role="status" className={styles.notice}>{aviso}<button aria-label="Cerrar confirmación" onClick={() => setAviso("")}>×</button></div>}
        <nav className={styles.localNav}>
          {([["hojas", "Mis hojas"], ["motor", "Del motor"], ["catalogo", "Catálogo"], ["archivadas", "Archivadas"]] as const).map(([id, nombre]) =>
            <button key={id} aria-pressed={pestana === id} onClick={() => setPestana(id)}>{nombre}</button>)}
          <Link href="/motor/hojas">Ir al motor</Link>
        </nav>

        {pestana === "hojas" && (activas.length
          ? <div className={styles.sheetList}>{activas.map(tarjeta)}</div>
          : <div className={styles.empty}><h2>Tu primera hoja</h2><span>Una hoja por modelo: sus ecuaciones, su forma adimensional y su estudio.</span><button className={styles.primary} onClick={() => agregar()}>Crear hoja</button></div>)}

        {pestana === "motor" && (lecturas.length
          ? <div className={styles.sheetList}>{lecturas.map(({ hoja, importacion, motivo }) => {
              const previa = importadaDe(hoja.id);
              const importar = () => {
                const nueva = leerHojaMotor(hoja).importacion;
                if (!nueva) return;
                const h = agregar(nueva.documento);
                if (h) { guardarImportacion({ ...nueva, documento: h.documento }); setAviso(""); }
              };
              return (
                <article key={hoja.id}>
                  <Link href={`/motor/hojas/${hoja.id}`}>
                    <h2>{hoja.nombre}</h2>
                    <span>{importacion
                      ? `${importacion.origen.modo === "1d" ? "Campo en 1D" : "Evolución temporal"} · ${plural(importacion.origen.componentes.length, "componente", "componentes")}${hoja.resultadoRef ? " · resuelta en el motor" : ""}`
                      : motivo}</span>
                    <small>{new Date(hoja.actualizada).toLocaleString("es-MX")}</small>
                  </Link>
                  <div>
                    {previa
                      ? <><button className={styles.solveLink} onClick={() => abrirHoja(previa.id)}>Abrir hoja →</button><button onClick={importar}>Importar de nuevo</button></>
                      : importacion ? <button className={styles.solveLink} onClick={importar}>Importar →</button> : <span>No importable todavía</span>}
                  </div>
                </article>
              );
            })}</div>
          : <div className={styles.empty}><h2>Sin hojas del motor</h2><span>Las hojas de materia del motor guardadas en este navegador aparecen aquí para adimensionalizarlas. El motor no cambia.</span><Link className={styles.primary} href="/motor/hojas">Ir al motor</Link></div>)}

        {pestana === "catalogo" && <>
          <div className={styles.sampleTools}>
            <button disabled={!datos} onClick={() => {
              if (!datos) return;
              const nuevas = crearCuadernoConEjemplos().hojas;
              if (datos.hojas.length + nuevas.length > 50) { setError("El cuaderno admite hasta 50 hojas; archiva o exporta algunas antes de añadir los modelos."); return; }
              setDatos({ ...datos, hojas: [...datos.hojas, ...nuevas] }); setAviso(`${nuevas.length} modelos de partida añadidos a Mis hojas.`); setError("");
            }}>Añadir modelos de partida</button>
          </div>
          <div className={styles.sheetList}>{EJEMPLOS_COMPLEJOS.map(ej => (
            <article key={ej.id}>
              <div><h2>{ej.nombre}</h2><span>{ej.categoria}</span><small>{ej.descripcion}</small></div>
              <div><button className={styles.solveLink} onClick={() => agregar(ej.crear())}>Cargar como hoja →</button></div>
            </article>))}
          </div>
        </>}

        {pestana === "archivadas" && (archivadas.length
          ? <div className={styles.sheetList}>{archivadas.map(tarjeta)}</div>
          : <div className={styles.empty}><h2>Sin hojas archivadas</h2><span>Las hojas archivadas se pueden recuperar.</span></div>)}

        <small className={styles.muted}>
          {guardado}{" "}
          <button className="adim-enlace" disabled={!datos} onClick={() => datos && descargar("cuaderno-adimensionalizacion.json", JSON.stringify(datos, null, 2))}>Exportar cuaderno</button>{" · "}
          <label className="adim-enlace">Importar cuaderno<input type="file" className="sr-only" accept="application/json,.json" onChange={async e => {
            const f = e.target.files?.[0]; e.target.value = "";
            if (!f) return;
            try { if (f.size > 8_000_000) throw new Error("El cuaderno supera 8 MB."); setDatos(leerCuaderno(await f.text())); setApertura(n => n + 1); setError(""); }
            catch (err) { setError(err instanceof Error ? err.message : String(err)); }
          }} /></label>
        </small>
      </div>
    </div>
  );
}
