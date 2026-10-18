import type { Documento, Expresion, Forma, Modelo } from "./contrato";

export const CLAVE_ALMACEN = "adimensionalizacion.documento.v1";
export const LIMITE_BYTES = 1_000_000;
const id = () => crypto.randomUUID();
const s = (id: string): Expresion => ({ tipo: "simbolo", id });
const n = (valor: number): Expresion => ({ tipo: "numero", valor });
export function crearDocumento(): Documento {
  return { formato: "adimensionalizacion", version: 2, id: id(), nombre: "Nuevo documento",
    modelo: { id: id(), revision: 1, simbolos: [], funciones: [], ecuaciones: [], dominios: [], condiciones: [] },
    formas: [{ id: "forma-1", nombre: "Forma 1", padreId: null, modeloRevision: 1, escalas: [], objetivos: [], presentacion: "factorizada" }], activaId: "forma-1" };
}
/** Entradas declaradas para editar; no son resultados del transformador. */
export function crearEntrada(espacial: boolean): Documento {
  const doc = crearDocumento();
  const base = (id: string, rol: Modelo["simbolos"][number]["rol"], dimension: Modelo["simbolos"][number]["dimension"], dependeDe: string[] = []): Modelo["simbolos"][number] =>
    ({ id, nombre: id, rol, dimension, unidad: null, constante: rol === "parametro", dependeDe, signo: "desconocido" });
  doc.nombre = espacial ? "Entrada: difusión y fuente" : "Entrada: evolución temporal";
  doc.modelo.simbolos = [base("t", "tiempo", { T: { n: 1, d: 1 } }),
    base("c", "campo", { N: { n: 1, d: 1 }, L: { n: -3, d: 1 } }, espacial ? ["t", "x"] : ["t"]),
    base("k", "parametro", { T: { n: -1, d: 1 } }),
    base("a", "parametro", { N: { n: -1, d: 1 }, L: { n: 3, d: 1 }, T: { n: -1, d: 1 } })];
  const fuente: Expresion = { tipo: "suma", argumentos: [
    { tipo: "producto", argumentos: [s("k"), s("c")] },
    { tipo: "producto", argumentos: [n(-1), s("a"), { tipo: "potencia", base: s("c"), exponente: n(2) }] }] };
  if (espacial) doc.modelo.simbolos.push(base("x", "coordenada", { L: { n: 1, d: 1 } }), base("D", "parametro", { L: { n: 2, d: 1 }, T: { n: -1, d: 1 } }));
  doc.modelo.ecuaciones = [{ id: "balance", izquierda: { tipo: "derivada", expresion: s("c"), respecto: "t", orden: 1 },
    derecha: espacial ? { tipo: "suma", argumentos: [{ tipo: "producto", argumentos: [s("D"), { tipo: "laplaciano", expresion: s("c"), coordenadas: ["x"] }] }, fuente] } : fuente }];
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({ simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" } }));
  return doc;
}

/** Lector estricto de estructura y referencias. No sustituye el análisis dimensional. */
export function leerDocumento(texto: string): Documento {
  if (new TextEncoder().encode(texto).length > LIMITE_BYTES) throw new Error("El documento supera 1 MB.");
  const dato: unknown = JSON.parse(texto);
  const fallo = (ruta: string, motivo: string): never => { throw new Error(`${ruta}: ${motivo}`); };
  const obj = (v: unknown, ruta: string): Record<string, unknown> => {
    if (!v || typeof v !== "object" || Array.isArray(v)) return fallo(ruta, "se esperaba un objeto");
    return v as Record<string, unknown>;
  };
  const exacto = (v: unknown, ruta: string, claves: string[]) => {
    const o = obj(v, ruta);
    if (Object.keys(o).some(k => !claves.includes(k)) || claves.some(k => !Object.hasOwn(o, k))) fallo(ruta, "campos desconocidos o ausentes");
    return o;
  };
  const textoVal = (v: unknown, ruta: string) => { if (typeof v !== "string" || !v.trim() || v.length > 500) fallo(ruta, "texto requerido (máximo 500 caracteres)"); };
  const entero = (v: unknown, ruta: string, positivo = false) => { if (!Number.isSafeInteger(v) || (positivo && (v as number) <= 0)) fallo(ruta, "entero válido requerido"); };
  const lista = (v: unknown, ruta: string): unknown[] => { if (!Array.isArray(v) || v.length > 500) return fallo(ruta, "lista requerida (máximo 500 elementos)"); return v; };
  const opcion = (v: unknown, ruta: string, opciones: unknown[]) => { if (!opciones.includes(v)) fallo(ruta, "valor no admitido"); };
  const dimension = (v: unknown, ruta: string) => {
    if (v === null) return;
    const o = obj(v, ruta);
    if (Object.keys(o).length > 20) fallo(ruta, "demasiadas dimensiones base");
    for (const [k, r] of Object.entries(o)) { if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(k)) fallo(ruta, "base dimensional inválida"); const q = exacto(r, ruta + "." + k, ["n", "d"]); entero(q.n, ruta); entero(q.d, ruta, true); }
  };
  const clavesDocumento = ["formato", "version", "id", "nombre", "modelo", "formas", "activaId"];
  if (Object.hasOwn(obj(dato, "documento"), "exploracion")) clavesDocumento.push("exploracion");
  const doc = exacto(dato, "documento", clavesDocumento);
  if (Object.hasOwn(doc, "exploracion")) {
    const c = exacto(doc.exploracion, "exploracion", ["presupuesto", "maxObjetivos", "respetarEscalasFijadas", "incluirGruposPi", "maxExponentePi", "maxDenominadorPi"]);
    for (const [campo, max] of [["presupuesto", 200], ["maxObjetivos", 8], ["maxExponentePi", 12], ["maxDenominadorPi", 12]] as const) {
      entero(c[campo], `exploracion.${campo}`, true);
      if ((c[campo] as number) > max) fallo(`exploracion.${campo}`, `máximo ${max}`);
    }
    opcion(c.respetarEscalasFijadas, "exploracion.respetarEscalasFijadas", [true, false]);
    opcion(c.incluirGruposPi, "exploracion.incluirGruposPi", [true, false]);
  }
  opcion(doc.formato, "formato", ["adimensionalizacion"]); opcion(doc.version, "version", [1, 2]);
  for (const k of ["id", "nombre", "activaId"]) textoVal(doc[k], k);
  const modelo = exacto(doc.modelo, "modelo", ["id", "revision", "simbolos", "funciones", "ecuaciones", "dominios", "condiciones"]);
  textoVal(modelo.id, "modelo.id"); entero(modelo.revision, "modelo.revision", true);
  const unicos = (items: unknown[], ruta: string) => {
    const ids = items.map((v, i) => { const o = obj(v, `${ruta}[${i}]`); textoVal(o.id, ruta + ".id"); return o.id as string; });
    if (new Set(ids).size !== ids.length) fallo(ruta, "identidades duplicadas"); return new Set(ids);
  };
  const simbolos = lista(modelo.simbolos, "simbolos"), funciones = lista(modelo.funciones, "funciones");
  const ids = unicos(simbolos, "simbolos"), fids = unicos(funciones, "funciones");
  if ([...fids].some(i => ids.has(i))) fallo("funciones", "identidad compartida con un símbolo");
  const ref = (v: unknown, ruta: string, conjunto = ids) => { if (typeof v !== "string" || !conjunto.has(v)) fallo(ruta, "referencia inexistente"); };
  const roles = new Map(simbolos.map(v => { const o = obj(v, "simbolo"); return [o.id, o.rol]; }));
  const variables = new Set([...roles].filter(([, r]) => r === "tiempo" || r === "coordenada").map(([i]) => i as string));
  const coordenadas = new Set([...roles].filter(([, r]) => r === "coordenada").map(([i]) => i as string));
  const refs = (v: unknown, ruta: string, conjunto = ids) => { const a = lista(v, ruta); a.forEach(x => ref(x, ruta, conjunto)); if (new Set(a).size !== a.length) fallo(ruta, "referencias duplicadas"); };
  let nodos = 0;
  const expresion = (v: unknown, ruta: string, nivel = 0): void => {
    if (++nodos > 20000 || nivel > 40) fallo(ruta, "expresión demasiado compleja");
    const e = obj(v, ruta), sub = (x: unknown, r: string) => expresion(x, r, nivel + 1);
    switch (e.tipo) {
      case "numero": exacto(e, ruta, ["tipo", "valor"]); if (typeof e.valor !== "number" || !Number.isFinite(e.valor)) fallo(ruta, "número finito requerido"); break;
      case "simbolo": exacto(e, ruta, ["tipo", "id"]); ref(e.id, ruta); break;
      case "suma": case "producto": case "funcion": case "llamada": {
        exacto(e, ruta, e.tipo === "funcion" ? ["tipo", "nombre", "argumentos"] : e.tipo === "llamada" ? ["tipo", "funcionId", "argumentos"] : ["tipo", "argumentos"]);
        const args = lista(e.argumentos, ruta + ".argumentos");
        if (!args.length) fallo(ruta, "faltan argumentos");
        if (e.tipo === "funcion") { opcion(e.nombre, ruta, ["exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf", "abs", "min", "max"]); if (!["min", "max"].includes(e.nombre as string) && args.length !== 1) fallo(ruta, "la función necesita un argumento"); }
        if (e.tipo === "llamada") { ref(e.funcionId, ruta, fids); const f = funciones.find(f => obj(f, ruta).id === e.funcionId); if (args.length !== lista(obj(f, ruta).entradas, ruta).length) fallo(ruta, "aridad de función incorrecta"); }
        args.forEach((a, i) => sub(a, `${ruta}.argumentos[${i}]`)); break;
      }
      case "cociente": exacto(e, ruta, ["tipo", "numerador", "denominador"]); sub(e.numerador, ruta + ".numerador"); sub(e.denominador, ruta + ".denominador"); break;
      case "potencia": exacto(e, ruta, ["tipo", "base", "exponente"]); sub(e.base, ruta + ".base"); sub(e.exponente, ruta + ".exponente"); break;
      case "derivada": exacto(e, ruta, ["tipo", "expresion", "respecto", "orden"]); ref(e.respecto, ruta, variables); entero(e.orden, ruta, true); sub(e.expresion, ruta + ".expresion"); break;
      case "gradiente": case "divergencia": case "laplaciano": exacto(e, ruta, ["tipo", "expresion", "coordenadas"]); refs(e.coordenadas, ruta, coordenadas); if (!(e.coordenadas as unknown[]).length) fallo(ruta, "faltan coordenadas"); sub(e.expresion, ruta + ".expresion"); break;
      default: fallo(ruta, "operador no admitido por el contrato v1");
    }
  };
  simbolos.forEach((v, i) => { const ruta = `simbolos[${i}]`, o = exacto(v, ruta, ["id", "nombre", "rol", "dimension", "unidad", "constante", "dependeDe", "signo"]);
    textoVal(o.nombre, ruta); opcion(o.rol, ruta, ["tiempo", "coordenada", "campo", "parametro", "constante"]); dimension(o.dimension, ruta); if (o.unidad !== null) textoVal(o.unidad, ruta);
    opcion(o.constante, ruta, [true, false]); refs(o.dependeDe, ruta, variables); if (o.constante === true && (o.dependeDe as unknown[]).length) fallo(ruta, "un símbolo constante no puede depender de variables"); opcion(o.signo, ruta, ["positivo", "negativo", "cero", "desconocido"]);
  });
  if (simbolos.filter(v => obj(v, "simbolo").rol === "tiempo").length > 1) fallo("simbolos", "el sistema comparte una sola variable de tiempo");
  funciones.forEach((v, i) => {
    const ruta = `funciones[${i}]`, clavesFn = ["id", "nombre", "entradas", "salida", "dependeDe"];
    if (doc.version === 2 && Object.hasOwn(obj(v, ruta), "escala")) clavesFn.push("escala");
    const o = exacto(v, ruta, clavesFn);
    textoVal(o.nombre, ruta); lista(o.entradas, ruta).forEach(d => dimension(d, ruta)); dimension(o.salida, ruta); refs(o.dependeDe, ruta, variables);
    if (Object.hasOwn(o, "escala")) {
      const re = `${ruta}.escala`, e = exacto(o.escala, re, ["simboloId", "funcionAdimensional"]);
      ref(e.simboloId, re, ids);
      const sim = simbolos.find(s => obj(s, "simbolo").id === e.simboloId);
      if (sim && (!["parametro", "constante"].includes(obj(sim, "simbolo").rol as string) || !obj(sim, "simbolo").constante)) fallo(re, "la escala de una función debe ser un parámetro constante");
      if (sim && obj(sim, "simbolo").signo === "cero") fallo(re, "la escala de una función no puede ser nula");
      textoVal(e.funcionAdimensional, re);
      if (ids.has(e.funcionAdimensional as string) || fids.has(e.funcionAdimensional as string)) fallo(re, "identidad ocupada");
    }
  });
  const igualdad = (v: unknown, ruta: string) => { const o = exacto(v, ruta, ["id", "izquierda", "derecha"]); textoVal(o.id, ruta); expresion(o.izquierda, ruta + ".izquierda"); expresion(o.derecha, ruta + ".derecha"); };
  const ecuaciones = lista(modelo.ecuaciones, "ecuaciones"), eqids = unicos(ecuaciones, "ecuaciones"); ecuaciones.forEach((e, i) => igualdad(e, `ecuaciones[${i}]`));
  const dominios = lista(modelo.dominios, "dominios"), dids = unicos(dominios, "dominios");
  dominios.forEach((d, i) => { const ruta = `dominios[${i}]`, o = exacto(d, ruta, ["id", "variableId", "desde", "hasta"]); ref(o.variableId, ruta, variables); expresion(o.desde, ruta); expresion(o.hasta, ruta); });
  const condiciones = lista(modelo.condiciones, "condiciones"); unicos(condiciones, "condiciones");
  condiciones.forEach((c, i) => {
    const ruta = `condiciones[${i}]`, clavesCond = ["id", "tipo", "dominioId", "ecuacion"];
    if (doc.version === 2 && Object.hasOwn(obj(c, ruta), "ubicacion")) clavesCond.push("ubicacion");
    const o = exacto(c, ruta, clavesCond);
    opcion(o.tipo, ruta, ["inicial", "dirichlet", "flujo", "mixta"]); ref(o.dominioId, ruta, dids); igualdad(o.ecuacion, ruta);
    if (Object.hasOwn(o, "ubicacion")) {
      const ru = `${ruta}.ubicacion`, u = exacto(o.ubicacion, ru, ["variableId", "extremo"]);
      ref(u.variableId, ru, variables);
      const dom = dominios.find(d => obj(d, "dominio").id === o.dominioId);
      if (dom && obj(dom, "dominio").variableId !== u.variableId) fallo(ru, "la ubicación debe usar la variable del dominio de la condición");
      opcion(u.extremo, ru, ["desde", "hasta"]);
      const rol = roles.get(u.variableId as string);
      if ((o.tipo === "inicial") !== (rol === "tiempo")) fallo(ru, "una condición inicial se ubica en el tiempo y una de frontera en una coordenada");
    }
  });
  const formas = lista(doc.formas, "formas"), formasIds = unicos(formas, "formas"); ref(doc.activaId, "activaId", formasIds);
  formas.forEach((f, i) => {
    const ruta = `formas[${i}]`, clavesForma = ["id", "nombre", "padreId", "modeloRevision", "escalas", "objetivos", "presentacion"];
    if (doc.version === 2) {
      if (Object.hasOwn(obj(f, ruta), "transformaciones")) clavesForma.push("transformaciones");
      if (Object.hasOwn(obj(f, ruta), "referencias")) clavesForma.push("referencias");
      if (Object.hasOwn(obj(f, ruta), "prioridadEscalas")) clavesForma.push("prioridadEscalas");
    }
    const o = exacto(f, ruta, clavesForma);
    textoVal(o.nombre, ruta); if (o.padreId !== null) ref(o.padreId, ruta, formasIds); entero(o.modeloRevision, ruta, true); if ((o.modeloRevision as number) > (modelo.revision as number)) fallo(ruta, "revisión futura"); opcion(o.presentacion, ruta, ["factorizada", "desarrollada"]);
    const escalas = lista(o.escalas, ruta + ".escalas"), vistas = new Set();
    escalas.forEach((v, j) => { const r = `${ruta}.escalas[${j}]`, e = exacto(v, r, ["simboloId", "transformar", "nuevoNombre", "dimension", "valor"]); ref(e.simboloId, r); if (!["campo", "tiempo", "coordenada"].includes(roles.get(e.simboloId) as string)) fallo(r, "solo se escalan variables"); if (vistas.has(e.simboloId)) fallo(r, "escala duplicada"); vistas.add(e.simboloId); opcion(e.transformar, r, [true, false]); textoVal(e.nuevoNombre, r); dimension(e.dimension, r);
      const valor = obj(e.valor, r + ".valor");
      if (valor.tipo === "libre") exacto(valor, r, ["tipo"]);
      else if (valor.tipo === "cantidad") { exacto(valor, r, ["tipo", "valor", "unidad"]); if (typeof valor.valor !== "number" || !Number.isFinite(valor.valor) || valor.valor <= 0) fallo(r, "escala finita y positiva requerida"); textoVal(valor.unidad, r); if (["°C", "degC", "°F", "degF"].includes(valor.unidad as string)) fallo(r, "una temperatura afín no es una escala multiplicativa"); }
      else if (valor.tipo === "expresion") { exacto(valor, r, ["tipo", "expresion"]); expresion(valor.expresion, r); }
      else fallo(r, "tipo de escala no admitido");
    });
    if (Object.hasOwn(o, "transformaciones")) {
      const mapas = lista(o.transformaciones, ruta + ".transformaciones"), vistas = new Set(), nuevos = new Set();
      mapas.forEach((v, j) => {
        const r = `${ruta}.transformaciones[${j}]`, m = exacto(v, r, ["variableId", "nuevoId", "directa", "inversa", "constantes", "dominio"]);
        ref(m.variableId, r); if (!["campo", "tiempo", "coordenada"].includes(roles.get(m.variableId) as string)) fallo(r, "solo se transforman variables");
        if (vistas.has(m.variableId)) fallo(r, "transformación duplicada"); vistas.add(m.variableId);
        textoVal(m.nuevoId, r); if (nuevos.has(m.nuevoId) || ids.has(m.nuevoId as string) || fids.has(m.nuevoId as string)) fallo(r, "identidad ocupada"); nuevos.add(m.nuevoId);
        const constantes = lista(m.constantes, r), cids = unicos(constantes, r);
        if (cids.has(m.nuevoId as string) || [...cids].some(c => ids.has(c) || fids.has(c))) fallo(r, "identidad de constante ocupada");
        constantes.forEach(c => {
          const q = exacto(c, r, ["id", "nombre", "papel", "dimension", "valor"]); textoVal(q.nombre, r); opcion(q.papel, r, ["escala", "referencia"]); dimension(q.dimension, r);
          const valor = obj(q.valor, r);
          if (valor.tipo === "libre") exacto(valor, r, ["tipo"]);
          else if (valor.tipo === "cantidad") { exacto(valor, r, ["tipo", "valor", "unidad"]); if (typeof valor.valor !== "number" || !Number.isFinite(valor.valor) || (q.papel === "escala" && valor.valor <= 0)) fallo(r, "cantidad de mapa inválida"); textoVal(valor.unidad, r); }
          else if (valor.tipo === "expresion") { exacto(valor, r, ["tipo", "expresion"]); expresion(valor.expresion, r); }
          else fallo(r, "valor de constante no admitido");
        });
        const dom = exacto(m.dominio, r, ["original", "nuevo"]); opcion(dom.original, r, [null, "positivo", "negativo"]); opcion(dom.nuevo, r, [null, "positivo", "negativo"]);
        function algebraica(e: unknown): void { const q = obj(e, r); if (["derivada", "gradiente", "divergencia", "laplaciano", "llamada"].includes(q.tipo as string)) fallo(r, "el mapa debe ser algebraico"); for (const k of ["base", "exponente", "numerador", "denominador"]) if (Object.hasOwn(q, k)) algebraica(q[k]); if (Array.isArray(q.argumentos)) q.argumentos.forEach(algebraica); }
        const locales = [m.nuevoId as string, ...cids]; locales.forEach(c => ids.add(c));
        try { expresion(m.directa, r); expresion(m.inversa, r); algebraica(m.directa); algebraica(m.inversa); }
        finally { locales.forEach(c => ids.delete(c)); }
      });
    }
    if (Object.hasOwn(o, "referencias")) {
      const refsList = lista(o.referencias, `${ruta}.referencias`), vistasRef = new Set();
      const cids = unicos(condiciones, "condiciones");
      refsList.forEach((item, rIdx) => {
        const rRuta = `${ruta}.referencias[${rIdx}]`, refObj = exacto(item, rRuta, ["ecuacionId", "terminoId"]);
        ref(refObj.ecuacionId, rRuta, new Set([...eqids, ...cids]));
        if (eqids.has(refObj.ecuacionId as string) && cids.has(refObj.ecuacionId as string)) fallo(rRuta, "identidad ambigua: es a la vez ecuación y condición");
        if (vistasRef.has(refObj.ecuacionId)) fallo(rRuta, "referencia duplicada");
        vistasRef.add(refObj.ecuacionId);
        textoVal(refObj.terminoId, rRuta);
        if (!(refObj.terminoId as string).startsWith(`${refObj.ecuacionId}:`)) fallo(rRuta, `el término debe pertenecer a '${refObj.ecuacionId}'`);
      });
    }
    if (Object.hasOwn(o, "prioridadEscalas")) {
      const prio = lista(o.prioridadEscalas, `${ruta}.prioridadEscalas`);
      if (new Set(prio).size !== prio.length) fallo(`${ruta}.prioridadEscalas`, "prioridadEscalas con duplicados");
      prio.forEach(id => textoVal(id, `${ruta}.prioridadEscalas`));
    }
    const objetivos = lista(o.objetivos, ruta + ".objetivos"); unicos(objetivos, ruta);
    objetivos.forEach(v => {
      const clavesObj = ["id", "ecuacionId", "valor", "accion"];
      const objItem = obj(v, ruta);
      if (doc.version === 2) {
        if (Object.hasOwn(objItem, "termino")) clavesObj.push("termino");
        if (Object.hasOwn(objItem, "terminoId")) clavesObj.push("terminoId");
        if (!Object.hasOwn(objItem, "termino") && !Object.hasOwn(objItem, "terminoId")) fallo(ruta, "se requiere terminoId o termino");
      } else {
        clavesObj.push("termino");
      }
      const t = exacto(v, ruta, clavesObj);
      ref(t.ecuacionId, ruta, eqids);
      if (Object.hasOwn(t, "termino")) expresion(t.termino, ruta);
      if (Object.hasOwn(t, "terminoId")) {
        textoVal(t.terminoId, ruta);
        if (!(t.terminoId as string).startsWith(`${t.ecuacionId}:`)) fallo(ruta, `el término debe pertenecer a '${t.ecuacionId}'`);
      }
      opcion(t.valor, ruta, [1, -1]);
      opcion(t.accion, ruta, ["normalizar", "conservar_grupo"]);
    });
  });
  for (const forma of formas) { const visitados = new Set(); let actual: unknown = forma; while (actual) { const o = obj(actual, "formas"); if (visitados.has(o.id)) fallo("formas", "ciclo de ascendencia"); visitados.add(o.id); actual = o.padreId === null ? null : formas.find(f => obj(f, "formas").id === o.padreId); } }
  return dato as Documento;
}

export function editarModelo(doc: Documento, modelo: Modelo): Documento {
  const eqids = new Set(modelo.ecuaciones.map(e => e.id));
  const cids = new Set(modelo.condiciones.map(c => c.id));
  const sids = new Set(modelo.simbolos.map(s => s.id));
  const todasEqs = new Set([...eqids, ...cids]);
  const variables = modelo.simbolos.filter(s => ["campo", "tiempo", "coordenada"].includes(s.rol));
  const siguiente = { ...doc, modelo: { ...modelo, id: doc.modelo.id, revision: doc.modelo.revision + 1 },
    formas: doc.formas.map(f => {
      const existentes = new Set(f.escalas.map(e => e.simboloId));
      const nuevasEscalas = variables
        .filter(v => !existentes.has(v.id))
        .map(v => ({
          simboloId: v.id,
          transformar: true,
          nuevoNombre: `${v.nombre}_ad`,
          dimension: v.dimension,
          valor: { tipo: "libre" as const }
        }));
      return {
        ...f,
        escalas: [...f.escalas.filter(e => sids.has(e.simboloId)), ...nuevasEscalas],
        ...(f.transformaciones ? { transformaciones: f.transformaciones.filter(t => sids.has(t.variableId)) } : {}),
        ...(f.referencias ? { referencias: f.referencias.filter(r => todasEqs.has(r.ecuacionId)) } : {}),
        ...(f.prioridadEscalas ? { prioridadEscalas: f.prioridadEscalas.filter(p => sids.has(p)) } : {}),
        objetivos: f.objetivos.filter(o => eqids.has(o.ecuacionId))
      };
    }) };
  return leerDocumento(JSON.stringify(siguiente));
}
export function duplicarForma(doc: Documento): Documento {
  const original = doc.formas.find(f => f.id === doc.activaId)!;
  const copia: Forma = { ...structuredClone(original), id: id(), padreId: original.id, nombre: `${original.nombre.slice(0, 470)} · copia` };
  return leerDocumento(JSON.stringify({ ...doc, activaId: copia.id, formas: [...doc.formas, copia] }));
}
export function expresar(e: Expresion): string {
  switch (e.tipo) {
    case "numero": return String(e.valor);
    case "simbolo": return e.id;
    case "suma": return `(${e.argumentos.map(expresar).join(" + ")})`;
    case "producto": return `(${e.argumentos.map(expresar).join(" · ")})`;
    case "cociente": return `(${expresar(e.numerador)} / ${expresar(e.denominador)})`;
    case "potencia": return `(${expresar(e.base)})^(${expresar(e.exponente)})`;
    case "funcion": return `${e.nombre}(${e.argumentos.map(expresar).join(", ")})`;
    case "llamada": return `${e.funcionId}(${e.argumentos.map(expresar).join(", ")})`;
    case "derivada": return `∂${e.orden > 1 ? `^${e.orden}` : ""}[${expresar(e.expresion)}]/∂${e.respecto}${e.orden > 1 ? `^${e.orden}` : ""}`;
    default: return `${{ laplaciano: "∇²", divergencia: "div", gradiente: "∇" }[e.tipo]}_{${e.coordenadas.join(",")}}[${expresar(e.expresion)}]`;
  }
}

/** Migración explícita: conserva identidades, elecciones y el original. */
export function migrarDocumentoV2(doc: Documento): Documento {
  return leerDocumento(JSON.stringify({ ...doc, version: 2, formas: doc.formas.map(f => ({ ...f, transformaciones: f.transformaciones ?? [] })) }));
}
