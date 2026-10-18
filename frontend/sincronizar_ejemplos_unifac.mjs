import fs from 'node:fs';
import assert from 'node:assert/strict';
const dir='../docs/ejemplos/motor-unifac/';
const fuentes=[
  ['original-2','UNIFAC original · Calentamiento de 2 componentes','calentamiento-2'],
  ['original-4','UNIFAC original · Calentamiento de 4 componentes','calentamiento-4'],
  ['red-5','UNIFAC original · Red de 5 componentes e inversión','red-5-especie-entrante'],
  ['monofasico','UNIFAC original · Detención por política de fase','monofasico-detenido'],
  ['dortmund-4','UNIFAC Dortmund · Calentamiento de 4 componentes','dortmund-calentamiento-4'],
  ['lle-mezcla','UNIFAC ELL · Mezcla adiabática y separación líquida','lle-mezcla-agua-butanol'],
];
const ejemplos=fuentes.map(([id,nombre,n])=>{const fuente=`motor-ensamblaje-v2-resolver-unifac-${n}-peticion.json`;return {id,nombre,fuente,solicitud:JSON.parse(fs.readFileSync(dir+fuente,'utf8'))};});
const destino='app/motor/ejemplosUNIFAC.json',texto=JSON.stringify(ejemplos,null,2)+'\n';
if(process.argv.includes('--check'))assert.equal(fs.readFileSync(destino,'utf8'),texto,'UNIFAC inputs must match original endpoint requests');
else fs.writeFileSync(destino,texto);
console.log(`${ejemplos.length} solicitudes originales UNIFAC; sin respuestas precargadas ni datos simulados.`);
