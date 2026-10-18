/** Comparación de presentación entre la simulación del núcleo (devuelta a SI)
 * y el resultado guardado del motor para la misma hoja. Solo interpola para
 * evaluar ambas en los instantes y celdas del motor; no corrige ninguna. */
import type { EstudioSimulacion } from "./contratoEstudio";
import type { OrigenMotor } from "./desdeMotor";
import type { ResultadoMotor } from "../motor/modeloNumerico";

export type Comparacion = { diferenciaMaxima: number; escala: number; relativa: number; instantes: number; hasta: number };

function lineal(xs: number[], ys: number[], x: number) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] * (1 - a) + ys[i] * a; }
  return ys[ys.length - 1];
}
/** Nodos uniformes en [a, a + P) con el extremo b identificado con a. */
function periodica(xs: number[], ys: number[], x: number) {
  const h = xs[1] - xs[0], P = h * xs.length, u = (((x - xs[0]) % P) + P) % P / h, i = Math.floor(u), f = u - i;
  return ys[i % ys.length] * (1 - f) + ys[(i + 1) % ys.length] * f;
}

export function compararConMotor(origen: OrigenMotor, fisico: NonNullable<EstudioSimulacion["fisico"]>, motor: ResultadoMotor): Comparacion {
  const ts = fisico.tiempo.valoresSI;
  if (!ts) throw new Error("La simulación no tiene el tiempo en segundos.");
  const series = origen.componentes.map(c => fisico.campos[c.campoId]);
  if (series.some(s => !s)) throw new Error("La simulación no tiene todos los campos en unidades físicas.");
  const xs = fisico.coordenada?.valoresSI ?? null;
  if (origen.modo === "1d" && !xs) throw new Error("La simulación no tiene la coordenada en metros.");
  let dif = 0, escala = 0, instantes = 0;
  for (const [k, t] of motor.tiempos.entries()) {
    if (t > ts[ts.length - 1] * (1 + 1e-12)) break;
    instantes++;
    const j = Math.max(1, ts.findIndex(x => x >= t - 1e-12 * Math.max(1, Math.abs(t)))), w = ts[j] === ts[j - 1] ? 1 : (t - ts[j - 1]) / (ts[j] - ts[j - 1]);
    series.forEach((s, c) => {
      const celdas = origen.modo === "1d" ? motor.x : [0];
      celdas.forEach((x, m) => {
        const en = (fila: number[]) => origen.modo === "1d" ? (origen.simulacion.periodica ? periodica(xs!, fila, x) : lineal(xs!, fila, x)) : fila[0];
        const v = en(s![j - 1]) * (1 - w) + en(s![j]) * w, ref = motor.valores[k][c][m];
        dif = Math.max(dif, Math.abs(v - ref)); escala = Math.max(escala, Math.abs(ref));
      });
    });
  }
  return { diferenciaMaxima: dif, escala, relativa: escala ? dif / escala : dif, instantes, hasta: motor.tiempos[Math.max(0, instantes - 1)] ?? 0 };
}
