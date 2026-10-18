import type { Expresion } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import { nombreLatex } from "./exportar";

export type CoeficienteElasticidad = {
  parametroId: string;
  parametroLatex: string;
  elasticidad: number; // d(ln Pi) / d(ln p)
  impacto: "directo" | "inverso" | "nulo" | "cuadratico_directo" | "cuadratico_inverso";
  interpretacion: string;
};

export type SensibilidadGrupo = {
  grupoId: string;
  grupoLatex: string;
  definicionTexto: string;
  coeficientes: CoeficienteElasticidad[];
};

export type MatrizSensibilidad = {
  parametrosUnicos: string[];
  grupos: SensibilidadGrupo[];
  parametroMasSensibleGlobal: string;
  resumenFisico: string;
};

function evaluarNumero(e: Expresion): number {
  if (e.tipo === "numero") return e.valor;
  if (e.tipo === "producto") {
    return e.argumentos.reduce((acc, a) => acc * evaluarNumero(a), 1);
  }
  if (e.tipo === "cociente") {
    const n = evaluarNumero(e.numerador);
    const d = evaluarNumero(e.denominador);
    return d !== 0 ? n / d : 1;
  }
  return 1;
}

function extraerExponentes(expr: Expresion, signoGlobal = 1): Record<string, number> {
  const exp: Record<string, number> = {};

  function recorrer(e: Expresion, signo: number) {
    if (e.tipo === "simbolo") {
      exp[e.id] = (exp[e.id] ?? 0) + signo;
      return;
    }
    if (e.tipo === "potencia") {
      const expVal = evaluarNumero(e.exponente);
      if (e.base.tipo === "simbolo") {
        exp[e.base.id] = (exp[e.base.id] ?? 0) + signo * expVal;
      } else {
        recorrer(e.base, signo * expVal);
      }
      return;
    }
    if (e.tipo === "producto") {
      for (const arg of e.argumentos) {
        recorrer(arg, signo);
      }
      return;
    }
    if (e.tipo === "cociente") {
      recorrer(e.numerador, signo);
      recorrer(e.denominador, -signo);
      return;
    }
  }

  recorrer(expr, signoGlobal);
  return exp;
}

/**
 * Calcula la Matriz de Elasticidad y Sensibilidad Paramétrica Logarítmica:
 * S_ij = (p_j / Pi_i) * (d Pi_i / d p_j) = d(ln Pi_i) / d(ln p_j)
 * Representa el porcentaje de variación en el grupo Pi_i ante una variación del 1% en p_j.
 */
export function calcularSensibilidadParametrica(f: FormulacionNucleo): MatrizSensibilidad {
  const gruposRaw = f.grupos ?? [];
  const parametrosSet = new Set<string>();
  const gruposResultado: SensibilidadGrupo[] = [];

  for (const g of gruposRaw) {
    const exponentes = extraerExponentes(g.definicion);
    for (const p of Object.keys(exponentes)) {
      parametrosSet.add(p);
    }
  }

  const parametrosUnicos = Array.from(parametrosSet).sort();
  const conteoImpactoGlobal: Record<string, number> = {};

  for (const g of gruposRaw) {
    const exponentes = extraerExponentes(g.definicion);
    const coefs: CoeficienteElasticidad[] = [];

    for (const p of parametrosUnicos) {
      const e = exponentes[p] ?? 0;
      let impacto: CoeficienteElasticidad["impacto"] = "nulo";
      if (e === 1) impacto = "directo";
      else if (e === -1) impacto = "inverso";
      else if (e > 1) impacto = "cuadratico_directo";
      else if (e < -1) impacto = "cuadratico_inverso";

      conteoImpactoGlobal[p] = (conteoImpactoGlobal[p] ?? 0) + Math.abs(e);

      let interpretacion = "Sin influencia directa.";
      if (e !== 0) {
        const sentido = e > 0 ? "incrementa" : "reduce";
        interpretacion = `Una variación del +1% en ${p} ${sentido} este número adimensional en un ${Math.abs(e).toFixed(1)}%.`;
      }

      coefs.push({
        parametroId: p,
        parametroLatex: nombreLatex(p),
        elasticidad: e,
        impacto,
        interpretacion,
      });
    }

    gruposResultado.push({
      grupoId: g.id,
      grupoLatex: nombreLatex(g.id),
      definicionTexto: g.definicion.tipo === "simbolo" ? g.definicion.id : "f(p)",
      coeficientes: coefs,
    });
  }

  let parametroMasSensibleGlobal = parametrosUnicos[0] ?? "Ninguno";
  let maxImpacto = -1;
  for (const [p, imp] of Object.entries(conteoImpactoGlobal)) {
    if (imp > maxImpacto) {
      maxImpacto = imp;
      parametroMasSensibleGlobal = p;
    }
  }

  const resumenFisico = `El parámetro físico con mayor apalancamiento global en el espacio adimensional es «${parametroMasSensibleGlobal}» (índice acumulado de elasticidad: ${maxImpacto}). Su control experimental o calibración analítica gobierna prioritariamente las bifurcaciones y transiciones de escala del sistema continuo.`;

  return {
    parametrosUnicos,
    grupos: gruposResultado,
    parametroMasSensibleGlobal,
    resumenFisico,
  };
}
