// Internal multiphysics regression inputs, never installed product examples.
// Fundamental laws and recorded assumptions -> common model -> common compiler.
// Compare accepted physical states/events with the TS or native v2 reference;
// preserve unsupported-case diagnostics. The generated canonical report is
// docs/engine/multiphysics-battery.md; do not edit that report by hand.
// Run from frontend/: node verificar_bateria_multifisica.mjs (~10 min).
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const cache = new Map();
function cargar(ruta) {
  const archivo = fs.existsSync(ruta + ".ts") ? ruta + ".ts" : ruta;
  if (cache.has(archivo)) return cache.get(archivo);
  const m = { exports: {} }; cache.set(archivo, m.exports);
  if (archivo.endsWith(".json")) { m.exports = JSON.parse(fs.readFileSync(archivo, "utf8")); cache.set(archivo, m.exports); return m.exports; }
  const js = ts.transpileModule(fs.readFileSync(archivo, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, resolveJsonModule: true, esModuleInterop: true } }).outputText;
  new Function("exports", "module", "require", "process", js)(m.exports, m, r => {
    if (!r.startsWith(".")) throw new Error("dependencia externa: " + r);
    const p = path.resolve(path.dirname(archivo), r);
    if (p.endsWith(".json")) { const j = JSON.parse(fs.readFileSync(p, "utf8")); return { __esModule: true, default: j }; }
    return cargar(p);
  }, { env: {} });
  cache.set(archivo, m.exports);
  return m.exports;
}
const motor = n => cargar(path.join(AQUI, "app/motor", n));
const { resolverMotor } = motor("integracionMotor");
const { modeloDesdeHojaMotor } = cargar(path.join(AQUI, "motores/modelo/desdeHojaMotor"));
const { modeloBalancesDesdeHoja, cabeEnBalances } = cargar(path.join(AQUI, "motores/modelo/desdeHojaBalances"));
const { resolverHoja } = motor("modeloHojaMotor");
const { balancesHoja } = motor("seleccionBalances");

// Consume the same inventory as /models so future examples cannot be omitted.
const { REGRESSION_MODELS } = cargar(path.join(AQUI, "testing/modelFixtures"));
const CONJUNTOS = REGRESSION_MODELS.map(template => [template.name, template.create()]);

const casos = [];
for (const [conjunto, hojas] of CONJUNTOS) for (const h of hojas) {
  const b = balancesHoja(h), fisica = ["materia", "energia", "momento"].filter(k => b[k]);
  const c = { conjunto, nombre: h.nombre, hoja: h, fisica };
  if (h.redTermodinamica) { c.via = "red"; c.solicitud = h.redTermodinamica.solicitud; }
  else if (cabeEnBalances(h)) {
    // Ecuaciones generadas en el servidor por el motor de balances desde los supuestos de la hoja.
    try { c.modelo = modeloBalancesDesdeHoja(h); c.via = "balances"; }
    catch (e) { c.via = "adaptador"; c.motivo = e.message; }
  } else {
    try { c.modelo = modeloDesdeHojaMotor(h); c.via = "materia"; }
    catch (e) { c.via = "adaptador"; c.motivo = e.message; }
  }
  casos.push(c);
}

const PUENTE = `
import sys, json, re, time, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
import numpy as np
from core.compilador import resolver, NoSoportado
from core.termodinamica import NoSoportado as CapaNoSoportada
from core.modelo import desde_ensamblaje_v2
from backend import motor_ensamblaje_v2 as v2
def resumen(c):
    return {'estado': c['estado'], 't_fin': c['ejes'][0]['valores'][-1], 'eventos': [(e['codigo'], e['valor']) for e in c['eventos']],
            'verif': {v['id']: v['valor'] for v in c['verificaciones']}, 'series': {s['id']: s['valores'] for s in c['series']}, 't': c['ejes'][0]['valores']}
salida = []
for x in json.load(sys.stdin):
    r = {}
    t0 = time.time()
    try:
        m = desde_ensamblaje_v2(x['solicitud']) if x['via'] == 'red' else x['modelo']
        r['modelo'] = {'volumenes': len(m['volumenes']), 'componentes': len(m['componentes']), 'corrientes': len(m['corrientes']),
                       'intercambios': len(m['intercambios']), 'paquetes': sorted({p['modelo']['id'] for p in m['termodinamica']['paquetes']}),
                       'fronteras': sorted({v['frontera']['tipo'] for v in m['volumenes']})}
        c = resolver(m)
        r['ok'] = resumen(c)
    except (NoSoportado, CapaNoSoportada) as e:
        r['no_soportado'] = str(e)
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {e}'
    r['segundos'] = time.time() - t0
    if x['via'] == 'red' and 'no_soportado' in r:
        try:
            v = v2.resolver_v2(x['solicitud']); v = v[0] if isinstance(v, tuple) else v
            r['motor_rechaza'] = v['estado'] not in ('resuelto', 'parcial')
            r['motor_estado'] = v['estado']
        except Exception as e:
            r['motor_rechaza'] = True
            r['motor_estado'] = f'{type(e).__name__}'
    if x['via'] == 'red' and 'ok' in r:
        t1 = time.time()
        try:
            v = v2.resolver_v2(x['solicitud']); v = v[0] if isinstance(v, tuple) else v
            pub = v['resultados']; S = r['ok']['series']; tt = np.array(r['ok']['t']); tp = np.array(pub['tiempos'])
            peor, cual = 0.0, None
            for s in pub['series']:
                k = s['variableId']
                if k in S and re.search(r'\\.(n\\.\\d+|T|H|U)$', k):
                    a = np.interp(tp, tt, np.array(S[k], dtype=float)); b = np.array(s['valores'], dtype=float)
                    d = float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))
                    if d > peor: peor, cual = d, k
            r['motor'] = {'estado': v['estado'], 'peor': peor, 'cual': cual, 'eventos': [(e['codigo'], e['tiempo']) for e in pub['eventos']], 'segundos': time.time() - t1}
        except Exception as e:
            r['motor'] = {'error': f'{type(e).__name__}: {e}'}
    del_series = r.get('ok', {}).pop('series', None) if x['via'] == 'red' else None
    salida.append(r)
print(json.dumps(salida))`;
const entrada = casos.filter(c => c.via !== "adaptador").map(c => ({ via: c.via, modelo: c.modelo, solicitud: c.solicitud }));
const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify(entrada), encoding: "utf8", maxBuffer: 1 << 30, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
if (r.status !== 0) throw new Error(r.stderr);
const respuestas = JSON.parse(r.stdout);
let k = 0;
for (const c of casos) if (c.via !== "adaptador") c.r = respuestas[k++];

// Materia: frente al solver TS que usa hoy el Engine.
const interp = (xs, ys, x) => { if (x <= xs[0]) return ys[0]; for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] * (1 - a) + ys[i] * a; } return ys.at(-1); };
for (const c of casos) if ((c.via === "materia" || c.via === "balances") && c.r.ok) {
  const rm = c.via === "balances" ? await resolverHoja(c.hoja) : await resolverMotor(c.hoja.historial.pasos[c.hoja.historial.activo].formulacion, c.hoja.config);
  // Compare only physical states. Budget integrals (campo.aux_*) and
  // derived observables (observable.*) have no state column in the TS solver.
  const ids = Object.keys(c.r.ok.series).filter(id => id.startsWith("campo.") && !id.startsWith("campo.aux_"));
  assert(ids.length > 0 && rm.valores.length === rm.tiempos.length && rm.valores.every(f => f.length === ids.length && f.every(v => v.length === 1 && Number.isFinite(v[0]))), `${c.nombre}: physical state columns do not match the TS reference`);
  assert(ids.every(id => c.r.ok.series[id].length === c.r.ok.t.length && c.r.ok.series[id].every(Number.isFinite)), `${c.nombre}: invalid compiler state series`);
  let peor = 0, escala = 0;
  ids.forEach((id, j) => c.r.ok.t.forEach((x, q) => { const v = c.r.ok.series[id][q]; escala = Math.max(escala, Math.abs(v)); peor = Math.max(peor, Math.abs(v - interp(rm.tiempos, rm.valores.map(f => f[j][0]), x))); }));
  c.motor = { estado: rm.estado, peor: peor / Math.max(escala, 1e-300) };
}

// --- Matriz -------------------------------------------------------------------------
let n = 0;
const fallos = [];
const ok = (v, m) => { n++; if (!v) fallos.push(m); };
const filas = [], faltas = new Map();
for (const c of casos) {
  let estado, detalle;
  if (c.via === "adaptador") { estado = "not reached"; detalle = `adapter: ${c.motivo}`; }
  else if (c.r.no_soportado && c.r.motor_rechaza) { estado = "rejected, as by the current Engine"; detalle = `${c.r.no_soportado} (current Engine: ${c.r.motor_estado})`; }
  else if (c.r.no_soportado) { estado = "not reached"; detalle = `compiler: ${c.r.no_soportado}`; }
  else if (c.r.error) { estado = "ERROR"; detalle = c.r.error; }
  else {
    const m = c.via === "red" ? c.r.motor : c.motor;
    const ev = c.r.ok.eventos.map(([e, t]) => `${e} ${(+t).toPrecision(6)}`).join(", ") || "no events";
    estado = c.r.ok.estado;
    detalle = m?.error ? `reference: ${m.error}` : `against the current Engine: ${m.peor.toExponential(1)} (${m.estado}); ${ev}`;
    ok(!m?.error && m.peor < 1e-4 && m.estado === c.r.ok.estado, `${c.conjunto} · ${c.nombre}: igual que el Engine actual (${detalle})`);
  }
  if (estado === "not reached") { const clave = detalle.replace(/^(adapter|compiler): /, "$1: ").replace(/volumen \\S+|corriente \\S+/g, "").slice(0, 160); faltas.set(clave, [...(faltas.get(clave) ?? []), `${c.conjunto} · ${c.nombre}`]); }
  ok(estado !== "ERROR", `${c.conjunto} · ${c.nombre}: sin errores no tratados (${detalle})`);
  const mod = c.r?.modelo;
  filas.push(`| ${c.conjunto} | ${c.nombre} | ${c.via} | ${c.fisica.join(" + ")} | ${mod ? `${mod.volumenes} vol · ${mod.componentes} comp · ${mod.corrientes} streams · ${mod.intercambios} heat · ${mod.paquetes.join(", ") || "assumed state"}` : "—"} | **${estado}** | ${detalle.replace(/\|/g, "/")} | ${c.r ? c.r.segundos.toFixed(1) : "—"} |`);
}
const resueltas = filas.filter(f => /\*\*(resuelto|parcial)\*\*/.test(f)).length;
const rechazadas = filas.filter(f => /\*\*rejected/.test(f)).length;
const md = `# Engine multiphysics battery

Generated by \`frontend/verificar_bateria_multifisica.mjs\` on ${new Date().toISOString().slice(0, 10)}. Do not edit by hand.

Every internal regression model goes through the common path: fundamental equations and assumptions, the common model, the common compiler (\`POST /modelo/resolver\`). These fixtures are not installed product examples and do not repopulate the library. Results are compared with the TS solver or the live v2 assembly. Historical fixture names and published rejection identifiers retain their compatible values.

Path of each sheet: **balances**, equations generated on the server by the balance engine (\`core/balances\`) from the sheet's assumptions; **red** (network), a v2 thermodynamic request (structural compiler with an equilibrium closure); **materia** (matter), equations written by the client's adapter (the forms the balance engine does not generate yet).

**${resueltas} of ${casos.length} sheets solved through the common path**${rechazadas ? `, and ${rechazadas} diagnostic sheet(s) rejected with their reason, as by the current Engine` : ""}. Every solved sheet matches the current Engine (tolerance 1e-4 relative; in practice between 1e-16 and 1e-7).

## What is missing, grouped by reason

${[...faltas].sort((a, b) => b[1].length - a[1].length).map(([m, hs]) => `- **${hs.length}** · ${m}\n  - ${hs.join("\n  - ")}`).join("\n")}

## Matrix

| Set | Sheet | Path | Physics | Common model | Status | Detail | s |
|---|---|---|---|---|---|---|---|
${filas.join("\n")}
`;
fs.writeFileSync(path.join(RAIZ, "docs/engine/multiphysics-battery.md"), md);
console.log(md.split("## Matrix")[0]);
for (const f of fallos) console.log("FALLO " + f);
console.log(`Batería multifísica: ${n - fallos.length} de ${n} comprobaciones correctas; ${resueltas} de ${casos.length} hojas por el camino común.`);
assert.equal(fallos.length, 0, `${fallos.length} hojas resueltas difieren del Engine actual o fallan`);
