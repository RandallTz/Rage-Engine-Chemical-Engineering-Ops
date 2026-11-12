// A full browser store must give a located message, keep the previous saved sheet, and leave other errors untouched.
import modulePath from 'node:path';
import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(modulePath.posix.join(modulePath.posix.dirname(n),r)));cache.set(n,m.exports);return m.exports;}
const store=new Map();let failWith=null;
globalThis.window={dispatchEvent(){}};
globalThis.localStorage={getItem:k=>store.get(k)??null,setItem(k,v){if(failWith)throw failWith;store.set(k,v);}};
const hojas=cargar('hojasMotor'),casos=cargar('hojasPruebaAcoplamiento').crearHojasPruebaAcoplamiento();
const sheet=casos[0];hojas.guardarHoja(sheet);const before=store.get(hojas.CLAVE_HOJAS);
const quota=new Error("Failed to execute 'setItem' on 'Storage': Setting the value exceeded the quota.");quota.name='QuotaExceededError';failWith=quota;
assert.throws(()=>hojas.guardarHoja({...sheet,nombre:'Renamed'}),e=>/Browser storage is full: model "Renamed"/.test(e.message)&&/Export the model/.test(e.message)&&e.cause===quota);
assert.throws(()=>hojas.guardarHojasNuevas([{...structuredClone(sheet),id:'other'}]),e=>/Browser storage is full: 1 imported model/.test(e.message));
assert.equal(store.get(hojas.CLAVE_HOJAS),before,'The previously saved sheet is unchanged');
failWith=new Error('disk on fire');assert.throws(()=>hojas.guardarHoja(sheet),/disk on fire/,'Other errors are not relabelled');
failWith=null;hojas.guardarHoja({...sheet,nombre:'Renamed'});assert.equal(hojas.leerHojas()[0].nombre,'Renamed');
console.log('storage quota: located message, unchanged store, other errors untouched: all checks passed');
