/** FIXTURES DE PRUEBA del núcleo y del formato de documento (verificar_capa_dimensional.mjs,
 * verificar_estudio_adimensionalizacion.mjs). No se ofrecen en la interfaz: son modelos escritos directamente y la
 * adimensionalización solo trabaja sobre ecuaciones derivadas en una hoja del Engine (ARCHITECTURE.md §2,
 * principio 10). No volver a mostrarlos como catálogo ni como «modelos de partida». */
import type { Documento, Modelo } from "./contrato";
import { crearDocumento, crearEntrada } from "./documento";
import { leerEcuaciones } from "./entradaEcuaciones";

/** Entrada editable: difusión en medio continuo y reacción con fuente lineal y no lineal. */
export function crearEjemploDifusionReaccion(): Documento {
  const doc = crearEntrada(true);
  doc.nombre = "Difusión y reacción";
  return doc;
}

/** Entrada editable: evolución temporal cinética con términos de orden 1 y orden 2. */
export function crearEjemploCinetica(): Documento {
  const doc = crearEntrada(false);
  doc.nombre = "Cinética no lineal";
  return doc;
}

/** Entrada editable; todas las relaciones y formulaciones las calcula el núcleo. */
export function crearSistemaDifusion(): Documento {
  const doc = crearDocumento(); doc.nombre = "Sistema de dos campos";
  doc.modelo = leerEcuaciones("d(u,t) = D1*lap(u,x) + k*v\nd(v,t) = D2*lap(v,x) + k*u", doc.modelo);
  const unidades: Record<string, string> = { u: "mol/L", v: "mol/L", t: "s", x: "m" };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({ ...s, unidad: unidades[s.id] ?? null,
    rol: s.id === "t" ? "tiempo" : s.rol, signo: s.rol === "parametro" ? "positivo" : s.signo }));
  return doc;
}

/** Modelo v2: difusión no lineal con coeficiente de difusión dependiente D(c) y escala D*. */
export function crearEjemploFuncionEscalada(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Difusión con D(c) escalada";
  doc.modelo = leerEcuaciones("d(c,t) = div(Dc(c)*grad(c,x),x)", doc.modelo);
  const unidades: Record<string, string> = { c: "mol/m^3", t: "s", x: "m" };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.id === "Dstar" ? "positivo" : s.signo
  }));
  if (!doc.modelo.simbolos.some(s => s.id === "Dstar")) {
    doc.modelo.simbolos.push({
      id: "Dstar", nombre: "Dstar", rol: "parametro", constante: true, dependeDe: [],
      signo: "positivo", dimension: { L: { n: 2, d: 1 }, T: { n: -1, d: 1 } }, unidad: "m^2/s"
    });
  }
  doc.modelo.funciones = [{
    id: "Dc",
    nombre: "D",
    entradas: [{ N: { n: 1, d: 1 }, L: { n: -3, d: 1 } }],
    salida: { L: { n: 2, d: 1 }, T: { n: -1, d: 1 } },
    dependeDe: [],
    escala: { simboloId: "Dstar", funcionAdimensional: "Dh" }
  }];
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Modelo v2: convección-difusión con condiciones iniciales y de frontera en extremos de dominios. */
export function crearEjemploReferenciasUbicacion(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Convección-difusión y contorno";
  doc.modelo = leerEcuaciones("d(c,t) = D*lap(c,x) + k*c - a*c^2", doc.modelo);
  if (doc.modelo.ecuaciones[0]) doc.modelo.ecuaciones[0].id = "balance";
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m", D: "m^2/s", k: "1/s", a: "m^3/(mol*s)",
    ell: "m", c0: "mol/m^3", q: "mol/(m^2*s)", tf: "s"
  };
  const extraSimbolos: Modelo["simbolos"] = [
    { id: "ell", nombre: "ell", rol: "parametro", constante: true, dependeDe: [], signo: "positivo", dimension: { L: { n: 1, d: 1 } }, unidad: "m" },
    { id: "c0", nombre: "c0", rol: "parametro", constante: true, dependeDe: [], signo: "positivo", dimension: { N: { n: 1, d: 1 }, L: { n: -3, d: 1 } }, unidad: "mol/m^3" },
    { id: "q", nombre: "q", rol: "parametro", constante: true, dependeDe: [], signo: "positivo", dimension: { N: { n: 1, d: 1 }, L: { n: -2, d: 1 }, T: { n: -1, d: 1 } }, unidad: "mol/(m^2*s)" },
    { id: "tf", nombre: "tf", rol: "parametro", constante: true, dependeDe: [], signo: "positivo", dimension: { T: { n: 1, d: 1 } }, unidad: "s" },
  ];
  doc.modelo.simbolos = [
    ...doc.modelo.simbolos.map(s => ({
      ...s,
      unidad: unidades[s.id] ?? null,
      rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
      signo: ["D", "k", "a"].includes(s.id) ? "positivo" : s.signo
    })),
    ...extraSimbolos
  ];
  doc.modelo.dominios = [
    { id: "intervalo-x", variableId: "x", desde: { tipo: "numero", valor: 0 }, hasta: { tipo: "simbolo", id: "ell" } },
    { id: "intervalo-t", variableId: "t", desde: { tipo: "numero", valor: 0 }, hasta: { tipo: "simbolo", id: "tf" } }
  ];
  doc.modelo.condiciones = [
    {
      id: "ci", tipo: "inicial", dominioId: "intervalo-t",
      ecuacion: { id: "ci-eq", izquierda: { tipo: "simbolo", id: "c" }, derecha: { tipo: "simbolo", id: "c0" } },
      ubicacion: { variableId: "t", extremo: "desde" }
    },
    {
      id: "flujo", tipo: "flujo", dominioId: "intervalo-x",
      ecuacion: {
        id: "flujo-eq",
        izquierda: {
          tipo: "producto",
          argumentos: [
            { tipo: "numero", valor: -1 },
            { tipo: "simbolo", id: "D" },
            { tipo: "derivada", expresion: { tipo: "simbolo", id: "c" }, respecto: "x", orden: 1 }
          ]
        },
        derecha: { tipo: "simbolo", id: "q" }
      },
      ubicacion: { variableId: "x", extremo: "hasta" }
    }
  ];
  doc.formas[0].referencias = [
    { ecuacionId: "balance", terminoId: "balance:ecuaciones[0].derecha.argumentos[1]" },
    { ecuacionId: "flujo", terminoId: "flujo:condiciones[1].ecuacion.derecha" }
  ];
  doc.formas[0].prioridadEscalas = ["x"];
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => ["t", "x", "c"].includes(s.id)).map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 1: Balances acoplados de destilación reactiva con reacción reversible A + B <=> C. */
export function crearEjemploDestilacionReactiva(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Destilación reactiva (A + B ⇌ C)";
  doc.modelo = leerEcuaciones(
    "d(c_A,t) = D*lap(c_A,x) - k_1*c_A*c_B + k_2*c_C\n" +
    "d(c_B,t) = D*lap(c_B,x) - k_1*c_A*c_B + k_2*c_C\n" +
    "d(c_C,t) = D*lap(c_C,x) + k_1*c_A*c_B - k_2*c_C",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c_A: "mol/m^3", c_B: "mol/m^3", c_C: "mol/m^3",
    t: "s", x: "m", D: "m^2/s", k_1: "m^3/(mol*s)", k_2: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["c_A", "c_B", "c_C"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 2: Convección natural y capa límite térmica acoplada (aproximación de Boussinesq). */
export function crearEjemploConveccionBoussinesq(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Convección natural (Boussinesq)";
  doc.modelo = leerEcuaciones(
    "d(u,t) = nu*lap(u,x) + gbeta*theta\n" +
    "d(theta,t) = alphaT*lap(theta,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    u: "m/s", theta: "K", t: "s", x: "m",
    nu: "m^2/s", gbeta: "m/(s^2*K)", alphaT: "m^2/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["u", "theta"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 3: Reactor catalítico heterogéneo con difusión intraparticular y saturación (Thiele). */
export function crearEjemploPelletCatalitico(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Pellet catalítico (Módulo de Thiele)";
  doc.modelo = leerEcuaciones(
    "d(c,t) = De*lap(c,x) - k*c/(1 + K*c)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m",
    De: "m^2/s", k: "1/s", K: "m^3/mol"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 4: Transferencia simultánea de calor y masa con convección (números de Lewis y Péclet). */
export function crearEjemploCalorYMasa(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Calor y masa acoplados (Lewis / Péclet)";
  doc.modelo = leerEcuaciones(
    "d(c,t) = DAB*lap(c,x) - v*d(c,x)\n" +
    "d(T,t) = aT*lap(T,x) - v*d(T,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c: "mol/m^3", T: "K", t: "s", x: "m",
    DAB: "m^2/s", aT: "m^2/s", v: "m/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["c", "T"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 5: Dinámica de fluidos compresible 1D (ecuaciones de Euler acústicas). */
export function crearEjemploEulerCompresible(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Flujo compresible 1D (Euler acústico)";
  doc.modelo = leerEcuaciones(
    "d(rho,t) = - v0*d(rho,x) - rho0*d(u,x)\n" +
    "d(u,t) = - v0*d(u,x) - a2rho*d(rho,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    rho: "kg/m^3", u: "m/s", t: "s", x: "m",
    v0: "m/s", rho0: "kg/m^3", a2rho: "m^5/(kg*s^2)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["rho", "u"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema bidimensional: Convección-difusión 2D acoplada en x e y con reacción de primer orden. */
export function crearEjemploConveccionDifusion2D(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Convección y difusión 2D (x, y)";
  doc.modelo = leerEcuaciones(
    "d(c_A,t) = D*lap(c_A,x,y) - u*d(c_A,x) - v*d(c_A,y) - k_1*c_A",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c_A: "mol/m^3", t: "s", x: "m", y: "m",
    D: "m^2/s", u: "m/s", v: "m/s", k_1: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : ["x", "y"].includes(s.id) ? "coordenada" : s.id === "c_A" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema tridimensional: Dispersión reactiva 3D con advección axial longitudinal. */
export function crearEjemploDispersion3D(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Dispersión reactiva 3D (x, y, z)";
  doc.modelo = leerEcuaciones(
    "d(c,t) = D*lap(c,x,y,z) - u*d(c,x) - k*c",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m", y: "m", z: "m",
    D: "m^2/s", u: "m/s", k: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : ["x", "y", "z"].includes(s.id) ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema esférico: Difusión y reacción en pellet catalítico esférico con simetría radial. */
export function crearEjemploPelletEsferico(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Pellet catalítico esférico (r)";
  doc.modelo = leerEcuaciones("d(c,t) = D*lap_esf(c,r) - k*c", doc.modelo);
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", r: "m", D: "m^2/s", k: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "r" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema cilíndrico: Reactor tubular cilíndrico con dispersión radial y convección axial. */
export function crearEjemploReactorTubularCilindrico(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Reactor tubular cilíndrico (r, z)";
  doc.modelo = leerEcuaciones("d(c,t) = D*lap_cil(c,r) - u*d(c,z) - k*c", doc.modelo);
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", r: "m", z: "m", D: "m^2/s", u: "m/s", k: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : ["r", "z"].includes(s.id) ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema con contorno de Robin: Transferencia reactiva con resistencia de película (Sherwood). */
export function crearEjemploRobinSherwood(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Película reactiva con contorno de Robin (Sherwood)";
  doc.modelo = leerEcuaciones("d(c,t) = D*lap(c,x) - k*c", doc.modelo);
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m", D: "m^2/s", k: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema continuo general: transporte con ley constitutiva empírica saturable y disipación cuadrática. */
export function crearEjemploCineticaEmpiricaSaturacion(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Cinética empírica con saturación y amortiguamiento";
  doc.modelo = leerEcuaciones(
    "d(c,t) = D*lap(c,x) - u*d(c,x) + r_0*c/(1 + K*c) - beta*c^2",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m",
    D: "m^2/s", u: "m/s", r_0: "1/s",
    K: "m^3/mol", beta: "m^3/(mol*s)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Física estadística: Ecuación de Allen-Cahn para separación de fase y dinámica de muros de dominio. */
export function crearEjemploAllenCahn(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Transición de fase de Allen-Cahn (Ginzburg-Landau)";
  doc.modelo = leerEcuaciones(
    "d(phi,t) = epsilon*lap(phi,x) + a*phi - b*phi^3",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    phi: "mol/m^3", t: "s", x: "m",
    epsilon: "m^2/s", a: "1/s", b: "m^6/(mol^2*s)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "phi" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Geofísica y mecánica de fluidos: Flujo no lineal en medios porosos (Ecuación de Darcy-Barenblatt). */
export function crearEjemploMediosPorosos(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Difusión no lineal en medios porosos (Porous Medium Equation)";
  doc.modelo = leerEcuaciones(
    "d(c,t) = M*lap(c^2,x) - k*c",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    c: "mol/m^3", t: "s", x: "m",
    M: "m^5/(mol*s)", k: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "c" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Biofísica y electrofisiología: Dinámica continua de medios excitables (FitzHugh-Nagumo). */
export function crearEjemploFitzHughNagumo(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Medios excitables continuos (FitzHugh-Nagumo)";
  doc.modelo = leerEcuaciones(
    "d(u,t) = Du*lap(u,x) + a*u - b*u^3 - c_coup*v\n" +
    "d(v,t) = Dv*lap(v,x) + eps*u - gamma*v",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    u: "mol/m^3", v: "mol/m^3", t: "s", x: "m",
    Du: "m^2/s", Dv: "m^2/s", a: "1/s", b: "m^6/(mol^2*s)",
    c_coup: "1/s", eps: "1/s", gamma: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["u", "v"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 6: Destilación reactiva no isotérmica con acoplamiento térmico exotérmico (Arrhenius / Prater). */
export function crearEjemploDestilacionNoIsotermica(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Destilación reactiva no isotérmica (Arrhenius / Prater)";
  doc.modelo = leerEcuaciones(
    "d(cA,t) = D*lap(cA,x) - u*d(cA,x) - k0*cA - kT*cA*T\n" +
    "d(T,t) = alphaT*lap(T,x) - u*d(T,x) + betaH*k0*cA - Ua*T",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    cA: "mol/m^3", T: "K", t: "s", x: "m",
    D: "m^2/s", alphaT: "m^2/s", u: "m/s",
    k0: "1/s", kT: "1/(s*K)", betaH: "K*m^3/mol", Ua: "1/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["cA", "T"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 7: Convección doble difusiva termo-solutal (dedos de sal y gradientes opuestos de densidad). */
export function crearEjemploDobleDifusion(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Convección doble difusiva (Dedos de sal / Boussinesq)";
  doc.modelo = leerEcuaciones(
    "d(u,t) = nu*lap(u,x) + gbetaT*T - gbetaS*S\n" +
    "d(T,t) = alphaT*lap(T,x)\n" +
    "d(S,t) = DS*lap(S,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    u: "m/s", T: "K", S: "mol/m^3", t: "s", x: "m",
    nu: "m^2/s", alphaT: "m^2/s", DS: "m^2/s",
    gbetaT: "m/(s^2*K)", gbetaS: "m^4/(s^2*mol)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["u", "T", "S"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 8: Cinética de polimerización en cadena de 3 especies (Iniciador, Monómero y Cadena de Polímero). */
export function crearEjemploPolimerizacion(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Polimerización en cadena (Iniciación, Monómero y Polímero)";
  doc.modelo = leerEcuaciones(
    "d(cI,t) = DI*lap(cI,x) - kd*cI\n" +
    "d(cM,t) = DM*lap(cM,x) - kp*cM*cI\n" +
    "d(cP,t) = DP*lap(cP,x) + kp*cM*cI",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    cI: "mol/m^3", cM: "mol/m^3", cP: "mol/m^3", t: "s", x: "m",
    DI: "m^2/s", DM: "m^2/s", DP: "m^2/s",
    kd: "1/s", kp: "m^3/(mol*s)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidadDe(unidades, s.id),
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["cI", "cM", "cP"].includes(sinGuion(s.id)) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 9: Morfogénesis química y auto-catálisis no lineal de Turing (Brusselator Continuo). */
export function crearEjemploBrusselatorTuring(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Morfogénesis y patrones de Turing (Brusselator Continuo)";
  doc.modelo = leerEcuaciones(
    "d(u,t) = Du*lap(u,x) + a - b*u + creac*u^2*v - kd*u\n" +
    "d(v,t) = Dv*lap(v,x) + b*u - creac*u^2*v",
    doc.modelo
  );
  // kd es la constante del paso X -> productos (el «1» de (B+1)X en la forma
  // adimensional clásica); sin ella el término tendría unidades de concentración.
  const unidades: Record<string, string> = {
    u: "mol/m^3", v: "mol/m^3", t: "s", x: "m",
    Du: "m^2/s", Dv: "m^2/s",
    a: "mol/(m^3*s)", b: "1/s", kd: "1/s", creac: "m^6/(mol^2*s)"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["u", "v"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 10: Absorción reactiva de película líquido-gas con segundo orden y Número de Hatta. */
export function crearEjemploAbsorcionPeliculaHatta(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Absorción reactiva gas-líquido con película (Número de Hatta)";
  doc.modelo = leerEcuaciones(
    "d(cA,t) = DA*lap(cA,x) - k2*cA*cB\n" +
    "d(cB,t) = DB*lap(cB,x) - rB*k2*cA*cB",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    cA: "mol/m^3", cB: "mol/m^3", t: "s", x: "m",
    DA: "m^2/s", DB: "m^2/s",
    k2: "m^3/(mol*s)", rB: "mol/mol"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidadDe(unidades, s.id),
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["cA", "cB"].includes(sinGuion(s.id)) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** El lector de ecuaciones escribe cP como c_P y k2 como k_2: las unidades se buscan sin el guion. */
function sinGuion(id: string): string {
  return id.replace(/_/g, "");
}

function unidadDe(unidades: Record<string, string>, id: string): string | null {
  return unidades[id] ?? unidades[sinGuion(id)] ?? null;
}

/** Sistema complejo 11: Transporte electrocinético de Nernst-Planck con migración iónica forzada. */
export function crearEjemploNernstPlanckElectrocinetico(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Transporte electrocinético de Nernst-Planck (Migración Iónica)";
  doc.modelo = leerEcuaciones(
    "d(cp,t) = Dp*lap(cp,x) - vE*d(cp,x)\n" +
    "d(cm,t) = Dm*lap(cm,x) + vE*d(cm,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    cp: "mol/m^3", cm: "mol/m^3", t: "s", x: "m",
    Dp: "m^2/s", Dm: "m^2/s", vE: "m/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : ["cp", "cm"].includes(s.id) ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

/** Sistema complejo 12: Conducción térmica con avance de frontera de cambio de fase (Problema de Stefan). */
export function crearEjemploStefanSolidificacion(): Documento {
  const doc = crearDocumento();
  doc.nombre = "Solidificación con interfase móvil (Problema de Stefan)";
  doc.modelo = leerEcuaciones(
    "d(T,t) = alphaT*lap(T,x) - us*d(T,x)",
    doc.modelo
  );
  const unidades: Record<string, string> = {
    T: "K", t: "s", x: "m",
    alphaT: "m^2/s", us: "m/s"
  };
  doc.modelo.simbolos = doc.modelo.simbolos.map(s => ({
    ...s,
    unidad: unidades[s.id] ?? null,
    rol: (s.id === "t" ? "tiempo" : s.id === "x" ? "coordenada" : s.id === "T" ? "campo" : "parametro") as Modelo["simbolos"][number]["rol"],
    signo: s.rol === "parametro" ? "positivo" : s.signo
  }));
  doc.formas[0].escalas = doc.modelo.simbolos.filter(s => s.rol !== "parametro").map(s => ({
    simboloId: s.id, transformar: true, nuevoNombre: `${s.nombre}_ad`, dimension: s.dimension, valor: { tipo: "libre" }
  }));
  return doc;
}

export type DefinicionEjemploComplejo = {
  id: string;
  nombre: string;
  categoria: string;
  descripcion: string;
  gruposEsperados: string;
  crear: () => Documento;
};

export const EJEMPLOS_COMPLEJOS: DefinicionEjemploComplejo[] = [
  {
    id: "cinetica-empirica-saturacion",
    nombre: "Cinética empírica con saturación y amortiguamiento",
    categoria: "Sistemas Continuos con Términos Empíricos Generales",
    descripcion: "Demuestra la universalidad del motor procesando un balance continuo con términos de advección, difusión y fuentes empíricas no lineales combinadas (saturación racional y disipación cuadrática).",
    gruposEsperados: "Péclet (Pe = u x_ref / D), Damköhler lineal y cuadrático (Da_lin, Da_cuad), módulo de saturación empírico (κ = K c_ref)",
    crear: crearEjemploCineticaEmpiricaSaturacion
  },
  {
    id: "destilacion-reactiva",
    nombre: "Destilación reactiva (A + B ⇌ C)",
    categoria: "Ingeniería de Procesos Químicos",
    descripcion: "Tres balances acoplados de materia con difusión molecular y cinética reversible de segundo orden.",
    gruposEsperados: "Damköhler I y II (Da1, Da2), relación difusiva",
    crear: crearEjemploDestilacionReactiva
  },
  {
    id: "conveccion-difusion-2d",
    nombre: "Convección y difusión 2D (x, y)",
    categoria: "Transporte Multidimensional Anisotrópico",
    descripcion: "Transporte advectivo-difusivo bidimensional con velocidades u y v, generando números de Péclet direccionales y factor de forma.",
    gruposEsperados: "Péclet longitudinal (Pe_x), Péclet transversal (Pe_y), relación de aspecto (A_y = x_ref/y_ref), Damköhler",
    crear: crearEjemploConveccionDifusion2D
  },
  {
    id: "dispersion-3d",
    nombre: "Dispersión reactiva 3D (x, y, z)",
    categoria: "Transporte Multidimensional Anisotrópico",
    descripcion: "Dispersión molecular y advección axial en dominio tridimensional continuo con reacción de primer orden.",
    gruposEsperados: "Fourier 3D (Fo_x, Fo_y, Fo_z), factores de esbeltez (A_y, A_z), Péclet axial (Pe_x), Damköhler (Da)",
    crear: crearEjemploDispersion3D
  },
  {
    id: "conveccion-boussinesq",
    nombre: "Convección natural (Boussinesq)",
    categoria: "Mecánica de Fluidos y Transferencia",
    descripcion: "Acoplamiento no lineal de momento y energía térmica inducido por flotación gravitacional.",
    gruposEsperados: "Número de Prandtl (Pr = ν / α_T) y Grashof (Gr)",
    crear: crearEjemploConveccionBoussinesq
  },
  {
    id: "pellet-catalitico",
    nombre: "Pellet catalítico (Módulo de Thiele)",
    categoria: "Reactores Químicos Heterogéneos",
    descripcion: "Difusión en poro poroso con ley cinética no lineal tipo saturación (Langmuir-Hinshelwood).",
    gruposEsperados: "Módulo de Thiele (Φ² = k L² / De), parámetro de saturación K",
    crear: crearEjemploPelletCatalitico
  },
  {
    id: "calor-masa",
    nombre: "Calor y masa acoplados (Lewis / Péclet)",
    categoria: "Fenómenos de Transporte Multicomponente",
    descripcion: "Transporte simultáneo de vapor y energía térmica bajo convección forzada con velocidad v.",
    gruposEsperados: "Número de Lewis (Le = α_T / DAB), Péclet térmico y másico (Pe)",
    crear: crearEjemploCalorYMasa
  },
  {
    id: "euler-compresible",
    nombre: "Flujo compresible 1D (Euler acústico)",
    categoria: "Dinámica de Gases y Acústica",
    descripcion: "Conservación de masa y cantidad de movimiento en ondas de presión con velocidad del sonido.",
    gruposEsperados: "Número de Mach (Ma = v₀ / c_s), impedancia acústica",
    crear: crearEjemploEulerCompresible
  },
  {
    id: "pellet-esferico",
    nombre: "Pellet catalítico esférico (r)",
    categoria: "Coordenadas Curvilíneas Ortogonales",
    descripcion: "Difusión molecular radial en esfera porosa con ley cinética lineal de primer orden.",
    gruposEsperados: "Módulo de Thiele esférico (Φ² = k r_ref² / D), Fourier radial",
    crear: crearEjemploPelletEsferico
  },
  {
    id: "reactor-tubular-cilindrico",
    nombre: "Reactor tubular cilíndrico (r, z)",
    categoria: "Coordenadas Curvilíneas Ortogonales",
    descripcion: "Dispersión radial en conducto cilíndrico con convección y advección axial.",
    gruposEsperados: "Péclet axial (Pe_z = u z_ref / D), relación de esbeltez (A_r = z_ref / r_ref), Damköhler",
    crear: crearEjemploReactorTubularCilindrico
  },
  {
    id: "robin-sherwood",
    nombre: "Película reactiva con contorno de Robin",
    categoria: "Transporte con Condiciones de Interfase",
    descripcion: "Transferencia difusivo-reactiva acoplada a condición de contorno de resistencia convectiva en la pared.",
    gruposEsperados: "Número de Sherwood / Biot másico (Sh = kc L / D), Damköhler",
    crear: crearEjemploRobinSherwood
  },
  {
    id: "allen-cahn",
    nombre: "Transición de fase de Allen-Cahn (Ginzburg-Landau)",
    categoria: "Física Estadística y Dinámica No Lineal",
    descripcion: "Ecuación continua de orden de parámetro con cinética biestable de doble pozo que gobierna la separación de fases y movimiento de muros de dominio.",
    gruposEsperados: "Parámetro de Ginzburg-Landau (ε² = ε / (a x_ref²)), tiempo característico de relajación",
    crear: crearEjemploAllenCahn
  },
  {
    id: "medios-porosos",
    nombre: "Difusión no lineal en medios porosos (Porous Medium Equation)",
    categoria: "Mecánica de Fluidos y Flujo en Medios Porosos",
    descripcion: "Difusión no lineal con ley de Darcy cuadrática y sumidero continuo, generando soluciones autosimilares de Barenblatt con frentes de propagación nítidos.",
    gruposEsperados: "Invariante de Barenblatt (M c_ref / (x_ref² k)), tiempo característico de Darcy",
    crear: crearEjemploMediosPorosos
  },
  {
    id: "fitzhugh-nagumo",
    nombre: "Medios excitables continuos (FitzHugh-Nagumo)",
    categoria: "Biofísica y Medios Excitables",
    descripcion: "Sistema de dos campos continuos acoplados con activación cúbica no lineal e inhibición lenta, representativo de frentes de propagación en electrofisiología y química no lineal.",
    gruposEsperados: "Razón de difusividades (δ = Dv / Du), escalas relativas de excitación/relajación (ε/a, γ/a)",
    crear: crearEjemploFitzHughNagumo
  },
  {
    id: "destilacion-no-isotermica",
    nombre: "Destilación reactiva no isotérmica (Arrhenius / Prater)",
    categoria: "Ingeniería de Procesos Químicos y Reactores",
    descripcion: "Balance acoplado de materia y energía en columna con transporte advectivo, dispersión axial, reacción exotérmica sensible a la temperatura y enfriamiento de pared.",
    gruposEsperados: "Péclet másico (Pe_m), Péclet térmico (Pe_h), Damköhler (Da), Número de Prater / termicidad (β), Stanton de pared (St)",
    crear: crearEjemploDestilacionNoIsotermica
  },
  {
    id: "doble-difusion-convectiva",
    nombre: "Convección doble difusiva (Dedos de sal / Boussinesq)",
    categoria: "Mecánica de Fluidos y Flotabilidad Multicomponente",
    descripcion: "Tres campos acoplados (velocidad, temperatura y salinidad) con gradientes de densidad contrapuestos que desatan inestabilidades de doble difusión.",
    gruposEsperados: "Número de Prandtl (Pr = ν / α_T), Schmidt (Sc = ν / D_S), Lewis (Le = α_T / D_S), Grashof térmico (Gr_T), Relación de estabilidad de densidad (R_ρ)",
    crear: crearEjemploDobleDifusion
  },
  {
    id: "polimerizacion-cadena",
    nombre: "Polimerización en cadena (Iniciación, Monómero y Polímero)",
    categoria: "Cinética Macromolecular e Ingeniería de Polímeros",
    descripcion: "Tres balances de materia acoplados que modelan descomposición de iniciador, consumo de monómero y crecimiento macromolecular con marcada disparidad difusiva.",
    gruposEsperados: "Damköhler de descomposición (Da_d), Damköhler de propagación (Da_p), relaciones de difusividad macromolecular (δ_IM, δ_PM << 1)",
    crear: crearEjemploPolimerizacion
  },
  {
    id: "brusselator-turing",
    nombre: "Morfogénesis y patrones de Turing (Brusselator Continuo)",
    categoria: "Morfogénesis y Dinámica No Lineal",
    descripcion: "Dinámica no lineal de reacción-difusión con auto-catálisis que genera bifurcaciones de Turing y patrones espaciales estacionarios auto-organizados.",
    gruposEsperados: "Razón de difusión cruzada (d = Dv / Du > d_c), parámetros adimensionales de bifurcación de Turing (A, B), número de onda crítico (k_c)",
    crear: crearEjemploBrusselatorTuring
  },
  {
    id: "absorcion-pelicula-hatta",
    nombre: "Absorción reactiva gas-líquido con película (Número de Hatta)",
    categoria: "Transferencia de Masa Interfacial y Absorción",
    descripcion: "Absorción de gas en película líquida con reacción irreversible de segundo orden entre soluto disuelto y reactivo en fase líquida.",
    gruposEsperados: "Número de Hatta (Ha² = k₂ c_B0 δ_L² / D_A), factor de aceleración química (β_E), relación de difusividades gas-líquido (D_B / D_A)",
    crear: crearEjemploAbsorcionPeliculaHatta
  },
  {
    id: "nernst-planck-electrocinetico",
    nombre: "Transporte electrocinético de Nernst-Planck (Migración Iónica)",
    categoria: "Electroquímica y Canales Nanofluídicos",
    descripcion: "Transporte electrocinético acoplado de iones positivos y negativos bajo gradientes combinados de concentración y potencial eléctrico impuesto.",
    gruposEsperados: "Número de Péclet electrocinético (Pe_E = v_E L / D_p), ratio de movilidades iónicas (δ_mp = D_m / D_p)",
    crear: crearEjemploNernstPlanckElectrocinetico
  },
  {
    id: "stefan-solidificacion",
    nombre: "Solidificación con interfase móvil (Problema de Stefan)",
    categoria: "Cambio de Fase y Fronteras Móviles",
    descripcion: "Conducción térmica con velocidad de interfase sólida/líquida acoplada a la liberación de calor latente de cambio de fase.",
    gruposEsperados: "Péclet de velocidad de interfase (Pe_s = u_s L / α_T), Fourier de conducción (Fo)",
    crear: crearEjemploStefanSolidificacion
  }
];

/** Devuelve la lista completa de documentos de ejemplo listos para usar (5 canónicos). */
export function crearColeccionHojasEjemplo(): Documento[] {
  return [
    crearEjemploDifusionReaccion(),
    crearEjemploCinetica(),
    crearSistemaDifusion(),
    crearEjemploFuncionEscalada(),
    crearEjemploReferenciasUbicacion(),
  ];
}
