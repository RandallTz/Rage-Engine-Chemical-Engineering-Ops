import fs from 'node:fs';
import assert from 'node:assert/strict';
const dir='../docs/ejemplos/motor-n-componentes/';
const leer=n=>JSON.parse(fs.readFileSync(dir+n,'utf8'));
const fuentes=[
  ['ideal-5','Mezcla ideal · Calentamiento de 5 componentes','motor-ensamblaje-v2-resolver-calentamiento-ideal-5-peticion.json'],
  ['nrtl-4','NRTL · Calentamiento de 4 componentes','motor-ensamblaje-v2-resolver-calentamiento-nrtl-4-peticion.json'],
  ['red-5','Red · 5 componentes con especie entrante','motor-ensamblaje-v2-resolver-red-ideal-5-especie-entrante-peticion.json'],
  ['par-ausente','Diagnóstico · NRTL con parámetro ausente','motor-ensamblaje-v2-validar-nrtl-4-par-ausente-peticion.json'],
];
const ejemplos=fuentes.map(([id,nombre,fuente])=>({id,nombre,fuente,solicitud:leer(fuente)}));
// Additional acceptance input: retain the 5-component heat/frontier declarations,
// use the published 7-component catalog and equimolar inventory (one mol total).
// This is editable test data, never an engine branch, property or cached answer.
const siete=structuredClone(ejemplos[0].solicitud),puntual=leer('motor-termodinamica-ideal-7-lv-peticion.json');
siete.solicitudId='n7-cal-ui';siete.componentes=puntual.componentes;
const v=siete.volumenes[0];v.componenteIds=siete.componentes.map(c=>c.id);
for(const id of Object.values(v.inicial.cantidades.datoIds))delete siete.datos[id];
v.inicial.cantidades.datoIds=Object.fromEntries(v.componenteIds.map(id=>{
  const k=`volumen.${v.id}.n0.${id}`;
  siete.datos[k]={magnitud:'cantidad',funcion:'inicial',declaracion:{texto:String(1/v.componenteIds.length),unidad:'mol'},origen:{propietarioId:`volumen:${v.id}`,ruta:`/datos/${k}/declaracion`}};
  return [id,k];
}));
ejemplos.splice(2,0,{id:'ideal-7',nombre:'Mezcla ideal · Calentamiento de 7 componentes',fuente:'calentamiento-ideal-5 + catálogo ideal-7; inventario equimolar de 1 mol',solicitud:siete});
const destino='app/motor/ejemplosNComponentes.json',texto=JSON.stringify(ejemplos,null,2)+'\n';
if(process.argv.includes('--check'))assert.equal(fs.readFileSync(destino,'utf8'),texto,'Examples must match their documented source inputs');
else fs.writeFileSync(destino,texto);
console.log(`${ejemplos.length} solicitudes de prueba N, sin respuestas ni propiedades incrustadas.`);
