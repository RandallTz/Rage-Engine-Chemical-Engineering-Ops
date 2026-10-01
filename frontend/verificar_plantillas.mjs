/**
 * Cada plantilla marcada como "lista" debe resolver SOLA: se abre y se
 * pulsa Resolver, sin escribir nada. Este test manda cada una al backend
 * exactamente como lo haria la interfaz y exige completo=true, sin
 * incognitas y sin datos sobrantes (GL=0).
 *
 * No usa navegador: replica construirPeticion() de page.tsx, que es la
 * unica traduccion entre el lienzo y el contrato del backend.
 */
import { PLANTILLAS } from "./app/components/plantillas.ts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const fallos = [];
const comprobar = (c, m) => { console.log(c ? `    OK   ${m}` : `    FALLA ${m}`); if (!c) fallos.push(m); };

/** Misma logica que corrientesDeOperacion() en app/flowsheet/modelo.ts. */
function corrientesDe(nodo, edges) {
  const d = nodo.data;
  const entradaDe = (p) => edges.find((e) => e.target === nodo.id && e.targetHandle === p)?.source;
  const salidaDe = (p) => edges.find((e) => e.source === nodo.id && e.sourceHandle === p)?.target;
  if (d.tipo === "columna") {
    return {
      alimentacion: entradaDe("alimentacion"),
      destilado: salidaDe("destilado"),
      fondos: salidaDe("fondos"),
    };
  }
  if (d.tipo === "mezclador") {
    return {
      entradas: ["entrada_1", "entrada_2"].map(entradaDe).filter(Boolean),
      salida: salidaDe("salida"),
    };
  }
  if (d.tipo === "divisor") {
    return {
      entrada: entradaDe("entrada"),
      salidas: ["salida_1", "salida_2"].map(salidaDe).filter(Boolean),
    };
  }
  if (d.tipo === "reactor_cstr") {
    const n = Math.max(1, d.n_entradas ?? 1);
    const puertos = Array.from({ length: n }, (_, i) => (i === 0 ? "entrada" : `entrada_${i + 1}`));
    return { entradas: puertos.map(entradaDe).filter(Boolean), salida: salidaDe("salida") };
  }
  if (d.tipo === "flash") {
    // Dos salidas con nombre propio: no son intercambiables.
    return { entrada: entradaDe("entrada"), vapor: salidaDe("vapor"), liquido: salidaDe("liquido") };
  }
  return { entrada: entradaDe("entrada"), salida: salidaDe("salida") };
}

function construirPeticion(p) {
  const nodos = p.flowsheet.nodes;
  const edges = p.flowsheet.edges;
  const corrientes = nodos.filter((n) => n.type === "corriente").map((n) => n.id);
  const operaciones = [];
  for (const n of nodos.filter((x) => x.type === "operacion")) {
    const d = n.data;
    const mapa = corrientesDe(n, edges);
    for (const [puerto, valor] of Object.entries(mapa)) {
      const vacio = Array.isArray(valor) ? valor.length === 0 : !valor;
      if (vacio) throw new Error(`${n.id}: el puerto '${puerto}' no está conectado`);
    }
    operaciones.push({
      nombre: n.id,
      tipo: d.tipo,
      corrientes: mapa,
      metodo: d.metodo ?? null,
      P_sistema: d.P_sistema,
      q: d.metodo === "ponchon_savarit" || d.metodo === "fug" ? d.q_fijo ?? 1.0 : null,
      indice_LK: d.metodo === "fug" ? d.indice_LK ?? 0 : null,
      indice_HK: d.metodo === "fug" ? d.indice_HK ?? 1 : null,
      fracciones: d.tipo === "divisor" ? (d.fracciones ?? "0.5,0.5").split(",").map(Number) : null,
      con_balance_energia: d.con_balance_energia !== false,
      // Equipos termicos: se manda SOLO la especificacion elegida. Mandar
      // dos convertiria un diagrama valido en un error de
      // sobre-especificacion (el nucleo las rechaza a proposito).
      modo_energia: d.tipo === "reactor_cstr" ? (d.modo_energia ?? "isotermo") : "isotermo",
      Q: d.tipo === "reactor_cstr" && d.modo_energia === "calor_dado" ? Number(d.Q ?? 0) : null,
      T_operacion: d.tipo === "flash" && d.spec_flash === "isotermo" ? Number(d.T_operacion ?? 0) : null,
      fraccion_vapor: d.tipo === "flash" && d.spec_flash === "fraccion" ? Number(d.fraccion_vapor ?? 0.5) : null,
      Q_por_mol:
        (d.tipo === "flash" && (d.spec_flash ?? "adiabatico") === "adiabatico") ||
        (d.tipo === "intercambiador" && (d.spec_intercambiador ?? "Q_por_mol") !== "T_salida")
          ? Number(d.Q_por_mol ?? 0)
          : null,
      T_salida: d.tipo === "intercambiador" && d.spec_intercambiador === "T_salida" ? Number(d.T_salida ?? 0) : null,
      P_salida: d.tipo === "valvula" ? Number(d.P_salida ?? 0) : null,
      reaccion:
        d.tipo === "reactor_cstr" && (d.nu ?? "").trim()
          ? { nu: d.nu.split(",").map(Number), A: d.A ?? 1e4, Ea: d.Ea ?? 45000, componente_referencia: 0 }
          : null,
      con_cinetica: d.con_cinetica !== false,
    });
  }
  const valores = {};
  for (const [clave, texto] of Object.entries(p.flowsheet.dados)) {
    if (texto === "" || !Number.isFinite(Number(texto))) continue;
    valores[clave] = Number(texto);   // las plantillas se escriben en SI
  }
  return {
    componentes: p.componentes.map((c) => c.nombre),
    corrientes, operaciones, valores, caudales_masicos: {},
  };
}

async function pedir(ruta, cuerpo) {
  const r = await fetch(API + ruta, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const datos = await r.json();
  if (!r.ok) throw new Error(datos?.detail ?? `HTTP ${r.status}`);
  return datos;
}

for (const p of PLANTILLAS) {
  console.log(`\n=== ${p.nombre}  [${p.lista ? "LISTA" : "vacía"}] ===`);
  if (!p.lista) {
    comprobar(p.flowsheet.nodes.length === 0 || p.componentes.length > 0,
      "una plantilla no-lista es coherente (o vacía, o con componentes)");
    continue;
  }
  let peticion;
  try {
    peticion = construirPeticion(p);
  } catch (e) {
    comprobar(false, `no se puede construir la petición: ${e.message}`);
    continue;
  }

  try {
    const gl = await pedir("/diagrama/grados-libertad", peticion);
    console.log(`    GL=${gl.grados_de_libertad}  (incógnitas ${gl.incognitas}, ecuaciones ${gl.ecuaciones})`);
    comprobar(gl.grados_de_libertad === 0,
      `queda exactamente determinada (GL=0, obtenido ${gl.grados_de_libertad})`);
    if (gl.redundancias?.length) {
      console.log("    redundancias:", gl.redundancias.map((r) => `${r.bloque} sobran ${r.sobran}`).join(" | "));
    }
  } catch (e) {
    comprobar(false, `grados de libertad falló: ${e.message}`);
  }

  try {
    const r = await pedir("/diagrama/resolver", peticion);
    comprobar(r.completo === true, `resuelve por completo (completo=${r.completo})`);
    if (r.reciclo) {
      console.log(`    reciclo: cortó ${r.reciclo.cortes.join(", ")} · ` +
        `convergió=${r.reciclo.convergio} en ${r.reciclo.ciclos} vueltas`);
      comprobar(r.reciclo.convergio === true, "el reciclo converge");
    }
    if (!r.completo) console.log("    sin determinar:", r.incognitas_restantes.slice(0, 8));
    comprobar((r.inconsistencias ?? []).length === 0,
      `sin ecuaciones violadas (${(r.inconsistencias ?? []).length})`);
    const destacados = Object.entries(r.pool)
      .filter(([k]) => /\.(N|F|Q_c|Q_R|V|X)$/.test(k))
      .slice(0, 6)
      .map(([k, v]) => `${k}=${typeof v === "number" ? v.toFixed(3) : v}`);
    console.log("    ", destacados.join("  "));
  } catch (e) {
    comprobar(false, `resolver falló: ${e.message}`);
  }
}

console.log(fallos.length === 0 ? "\nTODAS LAS PLANTILLAS OK\n" : `\n${fallos.length} FALLOS\n`);
process.exit(fallos.length === 0 ? 0 : 1);
