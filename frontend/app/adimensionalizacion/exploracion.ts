import type { ConfigExploracion, Documento, Expresion, Forma, Modelo } from "./contrato";

export const CONFIG_EXPLORACION: ConfigExploracion = {
  presupuesto: 200, maxObjetivos: 8, respetarEscalasFijadas: true,
  incluirGruposPi: true, maxExponentePi: 4, maxDenominadorPi: 4,
};
export type TerminoExplorable = {
  id: string; ecuacionId: string; lado: "izquierda" | "derecha";
  ruta: string; expresion: Expresion;
};
export type PropuestaExploracion = {
  id: string; estado: "sin_evaluar";
  objetivos: { terminoId: string; operacion: "normalizar_magnitud_coeficiente"; conservarSigno: true }[];
};
export type SolicitudExploracion = {
  formato: "solicitud_exploracion_adimensional"; version: 1;
  documentoId: string; modelo: Modelo; formaBase: Forma; config: ConfigExploracion;
  terminos: TerminoExplorable[]; propuestas: PropuestaExploracion[];
  cobertura: {
    combinacionesEnAlcance: string; propuestasPreparadas: number; limitadoPorPresupuesto: boolean;
    orden: "numero_de_objetivos_y_orden_del_modelo";
    alcance: "terminos_aditivos_explicitos_sin_desarrollar_productos";
  };
  politica: {
    incluirFamiliasLibres: true; resolverPorRango: true; deduplicarTrasResolver: true;
    evitarPreferenciaPorEspecie: true; conservarGeometriaYCondiciones: true;
    normalizacionGlobalSeparada: true; noEliminarTerminos: true;
    noElegirRaicesSilenciosamente: true;
    gruposPi: { estado: "solicitados" | "no_solicitados"; incluirInversosYCambiosDeBase: true };
  };
};
/** Inventario sintáctico. No extrae coeficientes, desarrolla fuentes ni decide
 * qué objetivos son compatibles: esas operaciones pertenecen al núcleo único. */
export function terminosExplorables(modelo: Modelo): TerminoExplorable[] {
  const terminos: TerminoExplorable[] = [];
  modelo.ecuaciones.forEach((eq, i) => {
    for (const lado of ["izquierda", "derecha"] as const) {
      function visitar(e: Expresion, ruta: string) {
        if (e.tipo === "suma") e.argumentos.forEach((a, j) => visitar(a, `${ruta}.argumentos[${j}]`));
        else terminos.push({ id: `${eq.id}:${ruta}`, ecuacionId: eq.id, lado, ruta, expresion: e });
      }
      visitar(eq[lado], `ecuaciones[${i}].${lado}`);
    }
  });
  return terminos;
}
export function validarConfigExploracion(config: ConfigExploracion): void {
  for (const [campo, min, max] of [["presupuesto", 1, 200], ["maxObjetivos", 1, 8], ["maxExponentePi", 1, 12], ["maxDenominadorPi", 1, 12]] as const) {
    if (!Number.isSafeInteger(config[campo]) || config[campo] < min || config[campo] > max) throw new Error(`${campo}: se requiere un entero entre ${min} y ${max}.`);
  }
  if (typeof config.respetarEscalasFijadas !== "boolean" || typeof config.incluirGruposPi !== "boolean") throw new Error("Preferencias de exploración inválidas.");
}
function numeroCombinaciones(n: number, maximo: number): bigint {
  let total = BigInt(1), coef = BigInt(1);
  for (let k = 1; k <= Math.min(n, maximo); k++) { coef = coef * BigInt(n - k + 1) / BigInt(k); total += coef; }
  return total;
}
export function prepararExploracion(doc: Documento, config: ConfigExploracion): SolicitudExploracion {
  validarConfigExploracion(config);
  const forma = doc.formas.find(f => f.id === doc.activaId);
  if (!forma) throw new Error("No existe una forma activa.");
  if (forma.modeloRevision !== doc.modelo.revision) throw new Error("Revisa la forma desactualizada antes de preparar la exploración.");
  const terminos = terminosExplorables(doc.modelo);
  if (!terminos.length) throw new Error("Agrega al menos una ecuación para explorar sus términos.");
  const propuestas: PropuestaExploracion[] = [{ id: "propuesta-0", estado: "sin_evaluar", objetivos: [] }];
  function combinar(inicio: number, restantes: number, seleccion: number[]) {
    if (propuestas.length >= config.presupuesto) return;
    if (!restantes) {
      propuestas.push({ id: `propuesta-${propuestas.length}`, estado: "sin_evaluar", objetivos: seleccion.map(i => ({ terminoId: terminos[i].id, operacion: "normalizar_magnitud_coeficiente", conservarSigno: true })) });
      return;
    }
    for (let i = inicio; i <= terminos.length - restantes && propuestas.length < config.presupuesto; i++) combinar(i + 1, restantes - 1, [...seleccion, i]);
  }
  for (let k = 1; k <= Math.min(config.maxObjetivos, terminos.length) && propuestas.length < config.presupuesto; k++) combinar(0, k, []);
  const total = numeroCombinaciones(terminos.length, config.maxObjetivos);
  const formaBase = structuredClone(forma);
  // Relajar una escala solo cambia la solicitud exportada, nunca el documento original.
  if (!config.respetarEscalasFijadas) formaBase.escalas = formaBase.escalas.map(e => e.transformar ? { ...e, valor: { tipo: "libre" } } : e);
  return {
    formato: "solicitud_exploracion_adimensional", version: 1,
    documentoId: doc.id, modelo: structuredClone(doc.modelo), formaBase, config: { ...config },
    terminos: structuredClone(terminos), propuestas,
    cobertura: { combinacionesEnAlcance: total.toString(), propuestasPreparadas: propuestas.length, limitadoPorPresupuesto: total > BigInt(propuestas.length), orden: "numero_de_objetivos_y_orden_del_modelo", alcance: "terminos_aditivos_explicitos_sin_desarrollar_productos" },
    politica: { incluirFamiliasLibres: true, resolverPorRango: true, deduplicarTrasResolver: true,
      evitarPreferenciaPorEspecie: true, conservarGeometriaYCondiciones: true, noElegirRaicesSilenciosamente: true,
      normalizacionGlobalSeparada: true, noEliminarTerminos: true,
      gruposPi: { estado: config.incluirGruposPi ? "solicitados" : "no_solicitados", incluirInversosYCambiosDeBase: true } },
  };
}
