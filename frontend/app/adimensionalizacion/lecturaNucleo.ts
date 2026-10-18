import type { Documento, Forma } from "./contrato";
import type { SolicitudExploracion } from "./exploracion";
import type { FormulacionNucleo, RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";

type Obj = Record<string, unknown>;
const fallo = (ruta: string, mensaje: string): never => { throw new Error(`${ruta}: ${mensaje}`); };
const obj = (v: unknown, p: string): Obj => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Obj : fallo(p, "objeto requerido");
const arr = (v: unknown, p: string): unknown[] => Array.isArray(v) && v.length <= 100000 ? v : fallo(p, "lista inválida");
const txt = (v: unknown, p: string): string => typeof v === "string" && v.length > 0 && v.length < 20000 ? v : fallo(p, "texto requerido");
const opcion = (v: unknown, p: string, valores: unknown[]) => { if (!valores.includes(v)) fallo(p, "valor no admitido"); };
const entero = (v: unknown, p: string, min = 0) => { if (!Number.isSafeInteger(v) || (v as number) < min) fallo(p, "entero inválido"); };
const booleano = (v: unknown, p: string) => opcion(v, p, [true, false]);
const claves = (o: Obj, p: string, requeridas: string[], opcionales: string[] = []) => { if (requeridas.some(k => !Object.hasOwn(o, k)) || Object.keys(o).some(k => !requeridas.includes(k) && !opcionales.includes(k))) fallo(p, "campos desconocidos o ausentes"); };
const strings = (v: unknown, p: string) => arr(v, p).map(x => txt(x, p));
const unicos = (v: unknown[], p: string): Set<string> => { const ids = v.map(x => txt(obj(x, p).id, p)); if (new Set(ids).size !== ids.length) fallo(p, "identidades repetidas"); return new Set(ids); };
export function igualdadProfunda(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => igualdadProfunda(x, b[i]));
  if (a && b && typeof a === "object" && typeof b === "object" && !Array.isArray(a) && !Array.isArray(b)) {
    const x = a as Obj, y = b as Obj; return Object.keys(x).length === Object.keys(y).length && Object.keys(x).every(k => Object.hasOwn(y, k) && igualdadProfunda(x[k], y[k]));
  }
  return false;
}
const eleccion = (f: Forma, mapas: SolicitudNucleo["transformaciones"]) => ({
  escalas: f.escalas, objetivos: f.objetivos, presentacion: f.presentacion,
  ...(mapas?.length ? { transformaciones: mapas } : {}),
  ...(f.referencias?.length ? { referencias: f.referencias } : {}),
  ...(f.prioridadEscalas?.length ? { prioridadEscalas: f.prioridadEscalas } : {}),
});
function tieneCamposV2Exclusivos(doc: Documento): boolean {
  if (doc.modelo.funciones.some(f => f.escala)) return true;
  if (doc.modelo.condiciones.some(c => c.ubicacion)) return true;
  if (doc.formas.some(f => (f.referencias && f.referencias.length > 0) || (f.prioridadEscalas && f.prioridadEscalas.length > 0) || f.objetivos.some(o => Boolean(o.terminoId)))) return true;
  return false;
}
export function prepararSolicitud(doc: Documento, opciones: SolicitudNucleo["opciones"] = {}, usarForma = false): SolicitudNucleo {
  const forma = doc.formas.find(f => f.id === doc.activaId)!;
  const mapas = forma.transformaciones ?? [];
  if (doc.version === 2 && tieneCamposV2Exclusivos(doc)) {
    const docV2: Documento = structuredClone(doc);
    const opcionesV2: SolicitudNucleo["opciones"] = { ...opciones };
    const sids = new Set(docV2.modelo.simbolos.map(s => s.id));
    const eqids = new Set(docV2.modelo.ecuaciones.map(e => e.id));
    const cids = new Set(docV2.modelo.condiciones.map(c => c.id));
    const todasEqs = new Set([...eqids, ...cids]);
    if (!usarForma) {
      if (forma.referencias?.length && !opcionesV2.referencias) {
        const validRefs = forma.referencias.filter(r => todasEqs.has(r.ecuacionId));
        if (validRefs.length) opcionesV2.referencias = structuredClone(validRefs);
      }
      if (forma.prioridadEscalas?.length && !opcionesV2.prioridadEscalas) {
        const validPrios = forma.prioridadEscalas.filter(p => sids.has(p));
        if (validPrios.length) opcionesV2.prioridadEscalas = structuredClone(validPrios);
      }
    }
    return {
      formato: "adimensionalizacion.solicitud", version: 1, operacion: "adimensionalizar", documento: docV2, opciones: opcionesV2,
      ...(usarForma ? { formaId: doc.activaId } : {}),
      ...(!usarForma && mapas.length ? { transformaciones: structuredClone(mapas) } : {}),
    };
  }
  const documento: Documento = { ...structuredClone(doc), version: 1, formas: doc.formas.map(f => { const { transformaciones: _mapas, ...v1 } = f; void _mapas; return v1; }) };
  return { formato: "adimensionalizacion.solicitud", version: 1, operacion: "adimensionalizar", documento, opciones,
    ...(usarForma ? { formaId: doc.activaId } : {}), ...(mapas.length ? { transformaciones: structuredClone(mapas) } : {}) };
}
const camposFormulacion = ["simbolos", "escalas", "transformaciones", "libres", "rangoObjetivos", "normalizacion", "ecuaciones", "dominios", "condiciones", "directa", "inversa", "grupos", "objetivos", "restricciones", "pasos", "equivalencia", "desarrollo", "desarrolloEstado"];
const operacionesPaso = ["analisis_dimensional", "cambio_variables", "regla_cadena", "sustitucion", "factorizacion", "normalizacion", "agrupacion", "simplificacion", "geometria_condiciones", "verificacion_inversa", "hipotesis_fisica"];

export function leerRespuestaNucleo(dato: unknown, entrada: SolicitudNucleo | SolicitudExploracion): RespuestaNucleo {
  const exploracion = entrada.formato === "solicitud_exploracion_adimensional" ? entrada : null;
  const solicitud: SolicitudNucleo = exploracion ? { formato: "adimensionalizacion.solicitud", version: 1, operacion: "transformar", documento: { formato: "adimensionalizacion", version: 1, id: exploracion.documentoId, nombre: "Exploración", modelo: exploracion.modelo, formas: [exploracion.formaBase], activaId: exploracion.formaBase.id }, formaId: exploracion.formaBase.id } : entrada as SolicitudNucleo;
  const r = obj(dato, "respuesta");
  claves(r, "respuesta", ["formato", "version", "operacion", "estado", "nucleo", "vinculo", "diagnosticos"], ["dimensional", "terminos", "formaBase", "formulaciones", "evaluaciones", "cobertura", "gruposPi", "funcionesAdimensionales", ...camposFormulacion]);
  opcion(r.formato, "formato", ["adimensionalizacion.resultado"]); opcion(r.version, "version", [1]);
  opcion(r.operacion, "operacion", [exploracion ? "explorar" : solicitud.operacion]); opcion(r.estado, "estado", ["correcto", "rechazado", "no_soportado", "requiere_datos"]); txt(r.nucleo, "nucleo");
  arr(r.diagnosticos, "diagnosticos").forEach((d, i) => { const x = obj(d, `diagnosticos[${i}]`); txt(x.ruta, "ruta"); txt(x.codigo, "codigo"); txt(x.mensaje, "mensaje"); opcion(x.severidad, "severidad", ["error", "aviso"]); if (x.simbolos) strings(x.simbolos, "simbolos"); });
  const modelo = solicitud.documento.modelo, originales = new Set(modelo.simbolos.map(s => s.id)), fidsOriginales = new Set(modelo.funciones.map(f => f.id)), funciones = new Map(modelo.funciones.map(f => [f.id, f.entradas.length]));
  const independientes = new Set(modelo.simbolos.filter(s => s.rol === "tiempo" || s.rol === "coordenada").map(s => s.id));
  const referencia = (id: unknown, ids: Set<string>, p: string) => { if (!ids.has(txt(id, p))) fallo(p, "referencia inexistente"); };
  function dimension(v: unknown, p: string) { if (v === null) return; const d = obj(v, p); for (const [k, x] of Object.entries(d)) { if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(k)) fallo(p, "base inválida"); const q = obj(x, p); claves(q, p, ["n", "d"]); if (!Number.isSafeInteger(q.n)) fallo(p, "exponente inválido"); entero(q.d, p, 1); } }
  let nodos = 0;
  function expr(v: unknown, ids: Set<string>, indep: Set<string>, p: string, nivel = 0, fnMap = funciones): void {
    if (++nodos > 2000000 || nivel > 80) fallo(p, "respuesta demasiado compleja");
    const e = obj(v, p), sub = (x: unknown, k: string) => expr(x, ids, indep, `${p}.${k}`, nivel + 1, fnMap);
    switch (e.tipo) {
      case "numero": claves(e, p, ["tipo", "valor"]); if (typeof e.valor !== "number" || !Number.isFinite(e.valor)) fallo(p, "número no finito"); break;
      case "simbolo": claves(e, p, ["tipo", "id"]); referencia(e.id, ids, p); break;
      case "suma": case "producto": case "funcion": case "llamada": {
        claves(e, p, e.tipo === "funcion" ? ["tipo", "nombre", "argumentos"] : e.tipo === "llamada" ? ["tipo", "funcionId", "argumentos"] : ["tipo", "argumentos"]);
        const a = arr(e.argumentos, p); if (!a.length) fallo(p, "argumentos vacíos");
        if (e.tipo === "funcion") { opcion(e.nombre, p, ["exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf", "abs", "min", "max"]); if (!["min", "max"].includes(e.nombre as string) && a.length !== 1) fallo(p, "aridad inválida"); }
        if (e.tipo === "llamada" && fnMap.get(e.funcionId as string) !== a.length) fallo(p, "función desconocida o aridad inválida");
        a.forEach((x, i) => sub(x, `argumentos[${i}]`)); break;
      }
      case "cociente": claves(e, p, ["tipo", "numerador", "denominador"]); sub(e.numerador, "numerador"); sub(e.denominador, "denominador"); break;
      case "potencia": claves(e, p, ["tipo", "base", "exponente"]); sub(e.base, "base"); sub(e.exponente, "exponente"); break;
      case "derivada": claves(e, p, ["tipo", "expresion", "respecto", "orden"]); referencia(e.respecto, indep, p); entero(e.orden, p, 1); sub(e.expresion, "expresion"); break;
      case "gradiente": case "divergencia": case "laplaciano": claves(e, p, ["tipo", "expresion", "coordenadas"]); if (!arr(e.coordenadas, p).length) fallo(p, "coordenadas vacías"); strings(e.coordenadas, p).forEach(c => referencia(c, indep, p)); sub(e.expresion, "expresion"); break;
      default: fallo(p, "operador desconocido");
    }
  }
  function revisarArboles(v: unknown, ids: Set<string>, indep: Set<string>, p: string, nivel = 0, fnMap = funciones): void {
    if (nivel > 100) fallo(p, "respuesta demasiado anidada");
    if (Array.isArray(v)) { v.forEach((x, i) => revisarArboles(x, ids, indep, `${p}[${i}]`, nivel + 1, fnMap)); return; }
    if (!v || typeof v !== "object") return;
    const o = v as Obj;
    if (["numero", "simbolo", "suma", "producto", "cociente", "potencia", "funcion", "llamada", "derivada", "gradiente", "divergencia", "laplaciano"].includes(o.tipo as string)) { expr(o, ids, indep, p, 0, fnMap); return; }
    for (const [k, x] of Object.entries(o)) {
      if (["expresion", "izquierda", "derecha", "coeficiente", "coeficienteFinal", "definicion", "factorGlobal", "nucleo", "numerador", "denominador", "base", "exponente"].includes(k) && x && typeof x === "object" && !Array.isArray(x)) expr(x, ids, indep, `${p}.${k}`, 0, fnMap);
      else revisarArboles(x, ids, indep, `${p}.${k}`, nivel + 1, fnMap);
    }
  }
  if (r.vinculo === null) { if (r.estado === "correcto" || r.estado === "requiere_datos") fallo("vinculo", "ausente"); }
  else {
    const v = obj(r.vinculo, "vinculo");
    if (v.documentoId !== solicitud.documento.id || v.modeloId !== modelo.id || v.modeloRevision !== modelo.revision) fallo("vinculo", "resultado de otro modelo o revisión");
    if (!/^sha256:[a-f0-9]{64}$/.test(txt(v.firma, "firma"))) fallo("firma", "firma de servidor inválida");
    if (solicitud.operacion !== "analizar") {
      opcion(v.formaId, "vinculo.formaId", [solicitud.formaId ?? null]);
      if (solicitud.formaId) { const f = solicitud.documento.formas.find(f => f.id === solicitud.formaId); if (!f || !igualdadProfunda(v.eleccion, eleccion(f, solicitud.transformaciones))) fallo("vinculo.eleccion", "elecciones distintas"); }
      else {
        const e = obj(v.eleccion, "vinculo.eleccion");
        if (!igualdadProfunda(e.transformaciones ?? [], solicitud.transformaciones ?? []) || arr(e.objetivos, "objetivos").length) fallo("vinculo.eleccion", "mapas u objetivos distintos");
        const vistas = new Set();
        arr(e.escalas, "escalas").forEach(x => { const s = obj(x, "escala"); referencia(s.simboloId, originales, "escala"); if (s.transformar !== true || obj(s.valor, "escala.valor").tipo !== "libre" || vistas.has(s.simboloId)) fallo("vinculo.eleccion", "selección automática inesperada"); vistas.add(s.simboloId); });
        if (r.estado === "correcto") { const base = obj(r.formaBase, "formaBase"); if (!igualdadProfunda(e, eleccion(base as unknown as Forma, solicitud.transformaciones))) fallo("formaBase", "no corresponde al vínculo"); }
      }
      if (solicitud.operacion === "adimensionalizar") {
        const opciones = { presupuesto: 200, maxObjetivos: null, desde: 0, gruposPi: true, maxExponentePi: 4, maxDenominadorPi: 4, presentacion: "factorizada", ...solicitud.opciones };
        if (!igualdadProfunda(v.opciones, opciones)) fallo("vinculo.opciones", "opciones distintas");
      }
    }
  }
  if (r.dimensional) {
    const d = obj(r.dimensional, "dimensional"); opcion(d.estado, "dimensional.estado", ["compatible", "incompatible", "indeterminado"]);
    strings(d.faltantes, "faltantes").forEach(s => referencia(s, originales, "faltantes"));
    const ds = arr(d.simbolos, "dimensional.simbolos"); unicos(ds, "dimensional.simbolos"); ds.forEach(v => { const s = obj(v, "simbolo"); referencia(s.id, originales, "simbolo.id"); dimension(s.dimension, "simbolo.dimension"); opcion(s.origen, "origen", ["declarada", "unidad", "inferida", "indeterminada", "sin_uso"]); });
  }
  if (r.estado !== "correcto") {
    if ([...camposFormulacion, "formulaciones", "gruposPi", "formaBase", "cobertura", "evaluaciones", "terminos", "funcionesAdimensionales"].some(k => Object.hasOwn(r, k))) fallo("respuesta", "un rechazo contiene resultados");
    if (r.estado === "requiere_datos" && (!r.dimensional || obj(r.dimensional, "dimensional").estado !== "indeterminado")) fallo("dimensional", "datos pendientes inconsistentes");
    return dato as RespuestaNucleo;
  }
  if (r.terminos) revisarArboles(r.terminos, originales, independientes, "terminos");
  function formulacion(v: unknown, p: string): void {
    const f = obj(v, p); claves(f, p, camposFormulacion, ["id", "objetivosAplicados", "subconjuntos", "propuestas", "funcionesAdimensionales"]);
    const simbolos = arr(f.simbolos, p + ".simbolos"), nuevos = unicos(simbolos, p);
    if ([...nuevos].some(i => originales.has(i) || funciones.has(i))) fallo(p, "símbolo nuevo colisiona con el original");
    const ids = new Set([...originales, ...nuevos]), indep = new Set(independientes);
    const funcionesLocales = new Map(funciones);
    if (f.funcionesAdimensionales) {
      const fads = arr(f.funcionesAdimensionales, p + ".funcionesAdimensionales"); unicos(fads, p + ".funcionesAdimensionales");
      fads.forEach((fadRaw, fi) => {
        const fad = obj(fadRaw, `${p}.funcionesAdimensionales[${fi}]`);
        claves(fad, `${p}.funcionesAdimensionales[${fi}]`, ["id", "nombre", "funcionId", "escalaId", "entradas", "salida", "dependeDe", "argumentos", "definicion"]);
        txt(fad.id, `${p}.funcionesAdimensionales[${fi}]`); txt(fad.nombre, `${p}.funcionesAdimensionales[${fi}]`);
        referencia(fad.funcionId, fidsOriginales, `${p}.funcionesAdimensionales[${fi}]`);
        referencia(fad.escalaId, originales, `${p}.funcionesAdimensionales[${fi}]`);
        txt(fad.definicion, `${p}.funcionesAdimensionales[${fi}]`);
        const args = arr(fad.argumentos, `${p}.funcionesAdimensionales[${fi}]`);
        args.forEach((aRaw, ai) => {
          const a = obj(aRaw, `${p}.funcionesAdimensionales[${fi}].argumentos[${ai}]`);
          booleano(a.extraida, `${p}.funcionesAdimensionales[${fi}].argumentos[${ai}]`);
          expr(a.escala, ids, indep, `${p}.funcionesAdimensionales[${fi}].argumentos[${ai}].escala`, 0, funcionesLocales);
        });
        funcionesLocales.set(fad.id as string, args.length);
      });
    }
    simbolos.forEach(v => { const s = obj(v, p); opcion(s.rol, p, ["escala", "variable_adimensional"]); referencia(s.variableId, originales, p); dimension(s.dimension, p); if (["tiempo", "coordenada"].includes(s.rolOrigen as string)) indep.add(s.id as string); });
    simbolos.forEach(v => { const s = obj(v, p); if (s.valor !== null && s.valor !== undefined) expr(s.valor, ids, indep, p, 0, funcionesLocales); if (s.dependeDe) strings(s.dependeDe, p).forEach(d => referencia(d, indep, p)); });
    const leerExpr = (e: unknown, ruta = p) => expr(e, ids, indep, ruta, 0, funcionesLocales);
    const igualdad = (v: unknown, ruta: string, conId = true) => { const e = obj(v, ruta); claves(e, ruta, conId ? ["id", "izquierda", "derecha"] : ["izquierda", "derecha"]); if (conId) txt(e.id, ruta); leerExpr(e.izquierda, ruta + ".izquierda"); leerExpr(e.derecha, ruta + ".derecha"); };
    const norm = obj(f.normalizacion, p); opcion(norm.estado, p, ["completa", "parcial"]); arr(norm.motivos, p).forEach(m => txt(obj(m, p).codigo, p));
    strings(f.libres, p).forEach(s => referencia(s, nuevos, p)); entero(f.rangoObjetivos, p);
    const grupos = arr(f.grupos, p), gids = unicos(grupos, p);
    grupos.forEach(v => { const g = obj(v, p); leerExpr(g.definicion); dimension(g.dimension, p); booleano(g.adimensional, p); booleano(g.contieneEscalasLibres, p); strings(g.usos, p); });
    const eqs = arr(f.ecuaciones, p); unicos(eqs.map(e => obj(e, p).igualdad), p);
    if (!eqs.length || eqs.length !== modelo.ecuaciones.length) fallo(p, "ecuaciones faltantes");
    eqs.forEach(v => { const e = obj(v, p); igualdad(e.igualdad, p); leerExpr(e.factorGlobal); arr(e.terminos, p).forEach(v => { const t = obj(v, p); txt(t.id, p); for (const k of ["original", "coeficiente", "nucleo"]) leerExpr(t[k]); dimension(t.dimensionNucleo, p); if (t.grupoId !== null) referencia(t.grupoId, gids, p); }); });
    const doms = arr(f.dominios, p), dids = unicos(doms, p);
    if (doms.length !== modelo.dominios.length || modelo.dominios.some(d => !dids.has(d.id))) fallo(p, "se perdieron dominios originales");
    doms.forEach(v => { const d = obj(v, p); referencia(d.variableId, indep, p); leerExpr(d.desde); leerExpr(d.hasta); });
    const condiciones = arr(f.condiciones, p), cids = unicos(condiciones, p);
    if (condiciones.length !== modelo.condiciones.length || modelo.condiciones.some(c => !cids.has(c.id))) fallo(p, "se perdieron condiciones originales");
    condiciones.forEach(v => {
      const c = obj(v, p), original = modelo.condiciones.find(x => x.id === c.id)!;
      referencia(c.dominioId, dids, p);
      if (c.tipo !== original.tipo || c.dominioId !== original.dominioId) fallo(p, "cambió el tipo o dominio de una condición");
      txt(c.ubicacion, p); igualdad(c.ecuacion, p);
      if (c.factorGlobal) leerExpr(c.factorGlobal);
      if (c.lugar) {
        const l = obj(c.lugar, p + ".lugar");
        claves(l, p + ".lugar", ["variableId", "variableOriginal", "extremo", "valor", "original"]);
        referencia(l.variableId, indep, p);
        referencia(l.variableOriginal, originales, p);
        opcion(l.extremo, p + ".lugar.extremo", ["desde", "hasta"]);
        leerExpr(l.valor);
        leerExpr(l.original);
      }
    });
    for (const k of ["directa", "inversa"]) arr(f[k], p).forEach(v => { const m = obj(v, p); referencia(m.simboloId, ids, p); leerExpr(m.expresion); });
    arr(f.transformaciones, p).forEach(v => { const t = obj(v, p); referencia(t.variableId, originales, p); referencia(t.nuevoId, nuevos, p); opcion(t.familia, p, ["multiplicativa", "afin", "no_lineal"]); leerExpr(t.directa); leerExpr(t.inversa); strings(t.constantes, p).forEach(c => referencia(c, nuevos, p)); });
    arr(f.escalas, p).forEach(v => { const s = obj(v, p); referencia(s.simboloId, originales, p); referencia(s.escalaId, nuevos, p); opcion(s.estado, p, ["libre", "dada", "dada_por_expresion", "determinada", "relacionada"]); leerExpr(s.valor); });
    arr(f.objetivos, p).forEach(v => {
      const o = obj(v, p); txt(o.id, p); opcion(o.estado, p, ["satisfecho", "dependiente", "incompatible", "pendiente", "conservado"]); txt(o.motivo, p);
      if (o.terminoId) txt(o.terminoId, p + ".terminoId");
      if (o.valorObjetivo !== undefined) opcion(o.valorObjetivo, p + ".valorObjetivo", [1, -1]);
      if (o.comprobado !== undefined) booleano(o.comprobado, p + ".comprobado");
      for (const k of ["coeficienteFinal", "valorObjetivo"]) if (o[k] && typeof o[k] === "object") leerExpr(o[k]);
      if (o.relacion) igualdad(o.relacion, p, false);
    });
    const restricciones = arr(f.restricciones, p), rids = unicos(restricciones, p); restricciones.forEach(v => { const q = obj(v, p); opcion(q.tipo, p, ["positivo", "negativo", "no_nulo", "signo", "igualdad"]); txt(q.motivo, p); leerExpr(q.expresion); if (q.valor && typeof q.valor === "object") leerExpr(q.valor); });
    arr(f.pasos, p).forEach(v => { const x = obj(v, p); txt(x.regla, p); igualdad(x.antes, p, false); igualdad(x.despues, p, false); strings(x.supuestos, p); });
    const desarrollo = arr(f.desarrollo, p); unicos(desarrollo, p); if (!desarrollo.length) fallo(p, "falta el desarrollo");
    desarrollo.forEach((v, i) => { const ruta = `${p}.desarrollo[${i}]`, x = obj(v, ruta); claves(x, ruta, ["id", "operacion", "regla", "justificacion", "antes", "despues", "supuestos", "objetosAfectados"]); opcion(x.operacion, ruta, operacionesPaso); txt(x.regla, ruta); txt(x.justificacion, ruta); strings(x.supuestos, ruta); strings(x.objetosAfectados, ruta); for (const k of ["antes", "despues"]) { const a = obj(x[k], ruta); opcion(a.tipo, ruta, ["expresion", "igualdad"]); claves(a, ruta, a.tipo === "expresion" ? ["tipo", "expresion"] : ["tipo", "igualdad"]); if (a.tipo === "expresion") leerExpr(a.expresion, ruta + "." + k); else igualdad(a.igualdad, ruta + "." + k); } });
    opcion(obj(f.desarrolloEstado, p).estado, p, ["completo"]);
    const e = obj(f.equivalencia, p); opcion(e.estado, p, ["demostrada", "no_demostrada"]); txt(e.alcance, p); strings(e.restricciones, p).forEach(s => referencia(s, rids, p)); arr(e.comprobaciones, p).forEach(v => { const c = obj(v, p); txt(c.ambito, p); txt(c.tipo, p); txt(c.estado, p); });
    revisarArboles(f, ids, indep, p, 0, funcionesLocales);
  }
  if (solicitud.operacion === "adimensionalizar") {
    const fs = arr(r.formulaciones, "formulaciones"); unicos(fs, "formulaciones"); fs.forEach((f, i) => formulacion(f, `formulaciones[${i}]`));
    const c = obj(r.cobertura, "cobertura"); booleano(c.completa, "cobertura.completa"); entero(c.desde, "cobertura.desde"); entero(c.evaluados, "cobertura.evaluados"); entero(c.formulacionesDistintas, "cobertura.formulacionesDistintas");
    if (c.formulacionesDistintas !== fs.length || c.desde !== (solicitud.opciones?.desde ?? 0)) fallo("cobertura", "recuento o continuación inconsistentes");
    if (c.siguiente !== null) { entero(c.siguiente, "cobertura.siguiente"); if ((c.siguiente as number) <= (c.desde as number) || c.completa) fallo("cobertura.siguiente", "continuación inválida"); }
    if (Object.hasOwn(r, "ecuaciones")) fallo("respuesta", "formulaciones mezcladas con resultado individual");
  } else if (!exploracion && solicitud.operacion === "transformar") {
    const cuerpo = Object.fromEntries([...camposFormulacion, "funcionesAdimensionales"].filter(k => Object.hasOwn(r, k)).map(k => [k, r[k]])); formulacion(cuerpo, "resultado");
  }
  if (exploracion) {
    const fs = arr(r.formulaciones, "formulaciones"); unicos(fs, "formulaciones"); fs.forEach((f, i) => formulacion(f, `formulaciones[${i}]`));
    const c = obj(r.cobertura, "cobertura"); entero(c.propuestasRecibidas, "cobertura"); entero(c.propuestasEvaluadas, "cobertura");
    if (c.propuestasRecibidas !== exploracion.propuestas.length || c.formulacionesDistintas !== fs.length) fallo("cobertura", "recuento inconsistente");
  }
  if (r.gruposPi) {
    const g = obj(r.gruposPi, "gruposPi"); entero(g.rango, "gruposPi.rango"); entero(g.numeroGrupos, "gruposPi.numeroGrupos"); const ids = new Set(strings(g.cantidades, "gruposPi.cantidades")); ids.forEach(i => referencia(i, originales, "gruposPi.cantidades"));
    const bases = arr(g.bases, "gruposPi.bases"); unicos(bases, "gruposPi.bases"); bases.forEach(v => arr(obj(v, "base").grupos, "grupos").forEach(v => { const x = obj(v, "grupo"); txt(x.id, "grupo.id"); expr(x.definicion, ids, independientes, "grupo.definicion"); }));
  }
  return dato as RespuestaNucleo;
}

export function formulacionesDe(r: RespuestaNucleo): FormulacionNucleo[] {
  return r.estado !== "correcto" ? [] : r.formulaciones ?? (r.operacion === "transformar" ? [r as unknown as FormulacionNucleo] : []);
}
