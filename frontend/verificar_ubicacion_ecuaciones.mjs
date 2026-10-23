// Regla: cada ecuación va en su lugar (ARCHITECTURE.md §8; app/motor/ubicacionEcuaciones.ts).
// Para TODAS las ecuaciones que publica el Engine en los ejemplos de redes (respuestas de validación y
// resolución v2 en docs/ejemplos): cada una tiene exactamente un panel; el de materia no contiene
// ecuaciones de estado, equilibrio ni energía; el de energía no contiene de materia ni termodinámicas;
// el de termodinámica solo contiene el cierre de estado y el equilibrio entre fases.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const js = ts.transpileModule(fs.readFileSync(path.join(AQUI, "app/motor/ubicacionEcuaciones.ts"), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const m = { exports: {} }; new Function("exports", "module", "require", js)(m.exports, m, () => ({}));
const { panelDeEcuacion } = m.exports;

const archivos = [];
const recorrer = d => { for (const x of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, x.name); if (x.isDirectory()) recorrer(p); else if (/motor-ensamblaje-v2-.*respuesta\.json$/.test(x.name)) archivos.push(p); } };
recorrer(path.join(RAIZ, "docs/ejemplos"));
let n = 0, total = 0;
const ok = (v, msg) => { n++; assert.ok(v, msg); };
const PERMITIDAS = {
  materia: e => e.familia === "materia" || (e.familia === "transferencia" && /\.(caudal|composicion)$/.test(e.id)) || /^global\.materia\./.test(e.id),
  energia: e => e.familia === "energia" || e.familia === "mecanica" || (e.familia === "transferencia" && (/^transferencia\.calor\./.test(e.id) || /\.entalpia$/.test(e.id))) || e.id === "global.energia",
  termodinamica: e => e.familia === "estado" || e.familia === "equilibrio",
  momento: e => e.familia === "momento",
};
const porPanel = { materia: 0, energia: 0, termodinamica: 0, momento: 0 };
for (const f of archivos) {
  const r = JSON.parse(fs.readFileSync(f, "utf8")), ecs = (r.validacion ?? r).ecuaciones ?? [];
  for (const e of ecs) {
    total++;
    const p = panelDeEcuacion(e);
    ok(p !== null, `${path.basename(f)}: ${e.id} (${e.familia}) tiene un lugar`);
    ok(PERMITIDAS[p](e), `${path.basename(f)}: ${e.id} (${e.familia}) está en un panel que admite su familia (${p})`);
    ok(Object.entries(PERMITIDAS).filter(([, f]) => f(e)).length === 1, `${path.basename(f)}: ${e.id} cabe en un solo panel`);
    porPanel[p]++;
  }
}
ok(archivos.length >= 20 && total > 300, `ejemplos suficientes (${archivos.length} respuestas, ${total} ecuaciones)`);
ok(porPanel.termodinamica > 0 && porPanel.materia > 0 && porPanel.energia > 0, `las ecuaciones termodinámicas existen y van a su panel (${JSON.stringify(porPanel)})`);
console.log(`Ubicación de ecuaciones: ${n} comprobaciones correctas · ${total} ecuaciones de ${archivos.length} respuestas · ${JSON.stringify(porPanel)}.`);
