import type { Expresion, Modelo, Simbolo } from "./contrato";

export function normalizarSubindicesEntrada(texto: string): string {
  return texto
    .replace(/\b([cCuUvVwW])([A-Z])\b/g, "$1_$2")
    .replace(/\b([kK])([0-9]+)\b/g, "$1_$2");
}

/** Traducción de sintaxis a AST. No transforma ecuaciones ni infiere física. */
export function leerEcuaciones(texto: string, anterior: Modelo): Modelo {
  if (!texto.trim()) throw new Error("Escribe al menos una ecuación.");
  if (texto.length > 20000) throw new Error("La entrada supera 20 000 caracteres.");
  const textoLimpio = normalizarSubindicesEntrada(texto);
  const lineas = textoLimpio.split(/[;\n]/).map(s => s.trim()).filter(Boolean);
  if (lineas.length > 40) throw new Error("Introduce hasta 40 ecuaciones por documento.");
  const usados = new Set<string>(), campos = new Set<string>(), independientes = new Set<string>();
  const dependientesAlgebraicas = new Set<string>();
  const funciones = new Map<string, number>();
  let nodos = 0;
  const nodo = <T extends Expresion>(e: T): T => { if (++nodos > 3000) throw new Error("La entrada contiene demasiadas operaciones."); return e; };
  const simbolosEn = (e: Expresion): string[] => {
    switch (e.tipo) {
      case "simbolo": return [e.id];
      case "numero": return [];
      case "suma": case "producto": case "funcion": case "llamada": return e.argumentos.flatMap(simbolosEn);
      case "potencia": return [...simbolosEn(e.base), ...simbolosEn(e.exponente)];
      case "cociente": return [...simbolosEn(e.numerador), ...simbolosEn(e.denominador)];
      default: return simbolosEn(e.expresion);
    }
  };
  const ecuaciones = lineas.map((linea, indice) => {
    const tokens: { valor: string; nombre: boolean; numero: boolean }[] = [];
    let pos = 0;
    while (pos < linea.length) {
      const match = /^\s*(?:(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|([A-Za-z_][A-Za-z0-9_]*)|("(?:[^"\\]|\\.)*")|([+\-*/^(),=]))/.exec(linea.slice(pos));
      if (!match) { if (!linea.slice(pos).trim()) break; throw new Error(`Ecuación ${indice + 1}: símbolo no admitido cerca de «${linea.slice(pos, pos + 16)}». Usa * para multiplicar y d(c,t) para derivar.`); }
      tokens.push({ valor: match[3] ? JSON.parse(match[3]) : match[0].trim(), nombre: !!(match[2] || match[3]), numero: !!match[1] });
      pos += match[0].length;
    }
    let i = 0, profundidad = 0;
    const es = (t: string) => tokens[i]?.valor === t && !tokens[i]?.nombre;
    const exigir = (t: string) => { if (!es(t)) throw new Error(`Ecuación ${indice + 1}: falta «${t}».`); i++; };
    function atom(): Expresion {
      if (++profundidad > 40) throw new Error(`Ecuación ${indice + 1}: demasiados niveles de paréntesis.`);
      try {
        if (es("(")) { i++; const e = suma(); exigir(")"); return e; }
        const token = tokens[i++];
        if (!token) throw new Error(`Ecuación ${indice + 1}: expresión incompleta.`);
        if (token.numero) { const valor = Number(token.valor); if (!Number.isFinite(valor)) throw new Error("Se requiere un número finito."); return nodo({ tipo: "numero", valor }); }
        if (!token.nombre || !token.valor.trim()) throw new Error(`Ecuación ${indice + 1}: se esperaba una variable o un número.`);
        const nombre = token.valor;
        if (!es("(")) { usados.add(nombre); return nodo({ tipo: "simbolo", id: nombre }); }
        i++; const argumentos = [suma()]; while (es(",")) { i++; argumentos.push(suma()); } exigir(")");
        if (["d", "diff", "grad", "div", "lap"].includes(nombre)) {
          if (argumentos.length < 2) throw new Error(`${nombre}: indica el campo y la variable, por ejemplo ${nombre}(u,x).`);
          const expr = argumentos[0];
          if (nombre === "d" || nombre === "diff") {
            if (argumentos.length > 3 || argumentos[1].tipo !== "simbolo") throw new Error("Usa d(c,t) o d(c,t,2).");
            const orden = argumentos[2] ?? { tipo: "numero", valor: 1 };
            if (orden.tipo !== "numero" || !Number.isSafeInteger(orden.valor) || orden.valor < 1 || orden.valor > 12) throw new Error("El orden de derivada debe ser un entero entre 1 y 12.");
            independientes.add(argumentos[1].id); simbolosEn(expr).forEach(s => campos.add(s));
            return nodo({ tipo: "derivada", expresion: expr, respecto: argumentos[1].id, orden: orden.valor });
          }
          const coordenadas = argumentos.slice(1).map(a => { if (a.tipo !== "simbolo") throw new Error(`${nombre}: las coordenadas deben ser símbolos.`); independientes.add(a.id); return a.id; });
          if (new Set(coordenadas).size !== coordenadas.length) throw new Error(`${nombre}: coordenadas repetidas.`);
          simbolosEn(expr).forEach(s => campos.add(s));
          return nodo({ tipo: nombre === "lap" ? "laplaciano" : nombre === "grad" ? "gradiente" : "divergencia", expresion: expr, coordenadas });
        }
        if (["lap_cil", "lap_esf"].includes(nombre)) {
          if (argumentos.length < 2) throw new Error(`${nombre}: indica el campo y la coordenada radial, ej. ${nombre}(c, r).`);
          const expr = argumentos[0];
          const rArg = argumentos[1];
          if (rArg.tipo !== "simbolo") throw new Error(`${nombre}: la coordenada radial debe ser un símbolo, ej. r.`);
          const rId = rArg.id;
          independientes.add(rId);
          simbolosEn(expr).forEach(s => campos.add(s));
          const numFactor = nombre === "lap_esf" ? 2 : 1;
          const terminoCurvo = nodo({
            tipo: "producto",
            argumentos: [
              nodo({
                tipo: "cociente",
                numerador: nodo({ tipo: "numero", valor: numFactor }),
                denominador: nodo({ tipo: "simbolo", id: rId })
              }),
              nodo({ tipo: "derivada", expresion: expr, respecto: rId, orden: 1 })
            ]
          });
          const lapRadial = nodo({
            tipo: "suma",
            argumentos: [
              nodo({ tipo: "derivada", expresion: expr, respecto: rId, orden: 2 }),
              terminoCurvo
            ]
          });
          if (argumentos.length >= 3) {
            const zArg = argumentos[2];
            if (zArg.tipo !== "simbolo") throw new Error(`${nombre}: la coordenada axial debe ser un símbolo, ej. z.`);
            independientes.add(zArg.id);
            return nodo({
              tipo: "suma",
              argumentos: [
                lapRadial,
                nodo({ tipo: "derivada", expresion: expr, respecto: zArg.id, orden: 2 })
              ]
            });
          }
          return lapRadial;
        }
        if (["exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf", "abs", "min", "max"].includes(nombre)) {
          if (!["min", "max"].includes(nombre) && argumentos.length !== 1) throw new Error(`${nombre}: se requiere un argumento.`);
          return nodo({ tipo: "funcion", nombre: nombre as Extract<Expresion, { tipo: "funcion" }>["nombre"], argumentos });
        }
        if (nombre === "sqrt") { if (argumentos.length !== 1) throw new Error("sqrt: se requiere un argumento."); return nodo({ tipo: "potencia", base: argumentos[0], exponente: { tipo: "cociente", numerador: { tipo: "numero", valor: 1 }, denominador: { tipo: "numero", valor: 2 } } }); }
        if (funciones.has(nombre) && funciones.get(nombre) !== argumentos.length) throw new Error(`${nombre}: usa el mismo número de argumentos en todas las llamadas.`);
        funciones.set(nombre, argumentos.length);
        return nodo({ tipo: "llamada", funcionId: nombre, argumentos });
      } finally { profundidad--; }
    }
    function potencia(): Expresion { if (++profundidad > 40) throw new Error("Demasiados niveles de potencias."); try { const base = atom(); if (es("^")) { i++; return nodo({ tipo: "potencia", base, exponente: unario() }); } return base; } finally { profundidad--; } }
    function unario(): Expresion { if (es("-") || es("+")) { const negativo = es("-"); i++; if (++profundidad > 40) throw new Error("Demasiados operadores consecutivos."); const e = unario(); profundidad--; return negativo ? nodo({ tipo: "producto", argumentos: [{ tipo: "numero", valor: -1 }, e] }) : e; } return potencia(); }
    function producto(): Expresion { let e = unario(); while (es("*") || es("/")) { const division = es("/"); i++; const a = unario(); e = nodo(division ? { tipo: "cociente", numerador: e, denominador: a } : { tipo: "producto", argumentos: [e, a] }); } return e; }
    function suma(): Expresion { let e = producto(); while (es("+") || es("-")) { const negativo = es("-"); i++; const a = producto(); e = nodo({ tipo: "suma", argumentos: [e, negativo ? { tipo: "producto", argumentos: [{ tipo: "numero", valor: -1 }, a] } : a] }); } return e; }
    const izquierda = suma(); exigir("="); const derecha = suma();
    if (izquierda.tipo === "simbolo") dependientesAlgebraicas.add(izquierda.id);
    if (i !== tokens.length) throw new Error(`Ecuación ${indice + 1}: operación inesperada. Usa * para multiplicar.`);
    return { id: anterior.ecuaciones[indice]?.id ?? `ecuacion-${indice + 1}`, izquierda, derecha };
  });
  const pila = ecuaciones.flatMap(e => [{ e: e.izquierda, nivel: 0 }, { e: e.derecha, nivel: 0 }]);
  while (pila.length) {
    const { e, nivel } = pila.pop()!;
    if (nivel > 35) throw new Error("La expresión contiene demasiados niveles de operaciones.");
    const hijos = e.tipo === "suma" || e.tipo === "producto" || e.tipo === "funcion" || e.tipo === "llamada" ? e.argumentos : e.tipo === "potencia" ? [e.base, e.exponente] : e.tipo === "cociente" ? [e.numerador, e.denominador] : "expresion" in e ? [e.expresion] : [];
    hijos.forEach(e => pila.push({ e, nivel: nivel + 1 }));
  }
  if ([...funciones.keys()].some(f => usados.has(f))) throw new Error("Un mismo nombre no puede ser variable y función declarada.");
  // Símbolos que no aparecen en las ecuaciones pero sí en la geometría, las
  // condiciones o la escala declarada de una función: siguen siendo parte del
  // modelo y se conservan con su declaración anterior.
  const externos = new Set<string>();
  for (const d of anterior.dominios) [...simbolosEn(d.desde), ...simbolosEn(d.hasta)].forEach(s => externos.add(s));
  for (const c of anterior.condiciones) [...simbolosEn(c.ecuacion.izquierda), ...simbolosEn(c.ecuacion.derecha)].forEach(s => externos.add(s));
  for (const f of anterior.funciones) if (f.escala) externos.add(f.escala.simboloId);
  for (const id of externos) if (!usados.has(id) && anterior.simbolos.some(s => s.id === id)) usados.add(id);
  const simbolos: Simbolo[] = [...usados].map(id => {
    const previo = anterior.simbolos.find(s => s.id === id);
    if (previo) return { ...previo, dependeDe: previo.dependeDe.filter(d => usados.has(d) && independientes.has(d)) };
    // Coordenada independiente no significa tiempo, longitud ni dimensión conocida.
    const rol = independientes.has(id) ? "coordenada" : campos.has(id) || dependientesAlgebraicas.has(id) ? "campo" : "parametro";
    return { id, nombre: id, rol, dimension: null, unidad: null, constante: rol === "parametro", dependeDe: rol === "campo" ? [...independientes] : [], signo: "desconocido" };
  });
  for (const id of independientes) { const s = simbolos.find(s => s.id === id)!; if (s.rol !== "coordenada" && s.rol !== "tiempo") throw new Error(`«${id}» está declarado como ${s.rol}; revisa su rol en Avanzado antes de usarlo como variable independiente.`); }
  if (anterior.dominios.some(d => !independientes.has(d.variableId)) || anterior.condiciones.some(c => [...simbolosEn(c.ecuacion.izquierda), ...simbolosEn(c.ecuacion.derecha)].some(s => !usados.has(s)))) throw new Error("El cambio quita de las ecuaciones una variable que usa la geometría o las condiciones guardadas. Revísalas en Avanzado antes de reemplazar el modelo.");
  return { ...anterior, simbolos, ecuaciones, funciones: [...funciones].map(([id, cantidad]) => anterior.funciones.find(f => f.id === id && f.entradas.length === cantidad) ?? { id, nombre: id, entradas: Array(cantidad).fill(null), salida: null, dependeDe: [] }) };
}

const nombre = (id: string) => /^[A-Za-z_][A-Za-z0-9_]*$/.test(id) ? id : JSON.stringify(id);
export function textoExpresion(e: Expresion): string {
  function t(e: Expresion, contexto = 0): string {
    let resultado: string, prioridad = 4;
    switch (e.tipo) {
      case "numero": resultado = String(e.valor); if (e.valor < 0) prioridad = 2; break;
      case "simbolo": resultado = nombre(e.id); break;
      case "suma": {
        const terminos = (x: Expresion): Expresion[] => x.tipo === "suma" ? x.argumentos.flatMap(terminos) : [x];
        resultado = terminos(e).map((a, i) => {
          if (a.tipo === "producto" && a.argumentos[0]?.tipo === "numero" && a.argumentos[0].valor === -1 && a.argumentos.length > 1) {
            const resto = a.argumentos.slice(1); return `${i ? " - " : "-"}${t(resto.length === 1 ? resto[0] : { tipo: "producto", argumentos: resto }, 2)}`;
          }
          return `${i ? " + " : ""}${t(a)}`;
        }).join(""); prioridad = 1; break;
      }
      case "producto": {
        const negativo = e.argumentos.length > 1 && e.argumentos[0].tipo === "numero" && e.argumentos[0].valor === -1;
        const resto = negativo ? e.argumentos.slice(1) : e.argumentos;
        resultado = (negativo ? "-" : "") + resto.map(a => t(a, 2)).join("*"); prioridad = 2; break;
      }
      case "cociente": resultado = `${t(e.numerador, 2)}/${t(e.denominador, 3)}`; prioridad = 2; break;
      case "potencia": resultado = `${t(e.base, 4)}^${t(e.exponente, 3)}`; prioridad = 3; break;
      case "funcion": resultado = `${e.nombre}(${e.argumentos.map(a => t(a)).join(",")})`; break;
      case "llamada": resultado = `${nombre(e.funcionId)}(${e.argumentos.map(a => t(a)).join(",")})`; break;
      case "derivada": resultado = `d(${t(e.expresion)},${nombre(e.respecto)}${e.orden > 1 ? `,${e.orden}` : ""})`; break;
      default: resultado = `${{ laplaciano: "lap", gradiente: "grad", divergencia: "div" }[e.tipo]}(${t(e.expresion)},${e.coordenadas.map(nombre).join(",")})`;
    }
    return prioridad < contexto ? `(${resultado})` : resultado;
  }
  return t(e);
}
export function textoModelo(modelo: Modelo): string {
  return modelo.ecuaciones.map(e => `${textoExpresion(e.izquierda)} = ${textoExpresion(e.derecha)}`).join("\n");
}
