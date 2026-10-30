/** Versioned steady contracts. Validation and fingerprints only; no browser solver. */
import type {TemporalDerivedExecution} from './derivedExecution';
import type {ConjuntoResultados} from '../resultados/contrato';

export type SteadySelection = Omit<TemporalDerivedExecution,'version'|'initialValues'|'initialEquations'|'scaling'|'dae'|'algebraic'|'nonlinear'> & {
  version:5; initialValues?:never;initialEquations?:never;scaling?:never;dae?:never;
  algebraic:{quantityId:string;equationId:string}[];unknowns:string[];invariants:Record<string,string>;
  nonlinear:NonNullable<TemporalDerivedExecution['nonlinear']>;
};
export type SteadyReport={
  format:'rage.compilation';version:2;study:'steady';sourceModelId:string;signature:string;
  sourceSignature:string;formulationSignature:string;dataSignature:string;settingsSignature:string;method:'damped_newton';
  selection:SteadySelection;variables:{id:string;name:string;unit:string;scaleSI:number;seedSI:number;boundsSI:number[]}[];
  rows:{id:string;family:string;before:string;after:string;identity:boolean}[];residualRows:{id:string;unit:string;scaleSI:number}[];
  invariants:{quantityId:string;equationId:string;dataId:string;value:number;unit:string}[];
  parameters:{id:string;dataId:string;value:number;unit:string}[];
  proofConditions:{equationId:string;kind:string;latex:string}[];runtimeConditions:SteadyReport['proofConditions'];scope:string;
  derivedExecution?:never;
};
export type SteadyDiagnostics={version:1;verdict:'local_regular_root';globalUniqueness:'not_proved';method:'damped_newton';
  sourceSignature:string;formulationSignature:string;dataSignature:string;settingsSignature:string;compilationSignature:string;
  quantityIds:string[];equationIds:string[];variableScales:number[];residualScales:number[];smallestSingularValue:number;
  conditionThreshold:number;inverseThreshold:number;relativeAmplification:number;inverseAmplification:number;initialResidualNorm:number;
  solver:{iterations:number;evaluations:number;backtracks:number;residualNorm:number;stepNorm:number;conditionInfinity:number;terminationReason:string;completedProbes:number;uniqueness:string};scope:string;resultSignature:string;
};
const fail=(message:string):never=>{throw new Error(message);};
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const identity=(v:unknown):v is string=>typeof v==='string'&&v.trim().length>0&&v.length<=160;
const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
function object(v:unknown,fields?:string[]):Record<string,unknown>{
  if(!v||typeof v!=='object'||Array.isArray(v))fail('Invalid steady object.');
  const r=v as Record<string,unknown>;
  if(fields&&(fields.length!==Object.keys(r).length||fields.some(k=>!Object.hasOwn(r,k))))fail('Unknown or missing steady fields.');return r;
}
function array(v:unknown):unknown[]{if(!Array.isArray(v))fail('Expected steady array.');return v as unknown[];}
function exactKeys(v:object,expected:string[]){if(!same(Object.keys(v).sort(),[...expected].sort()))fail('Steady identities do not match.');}
export function readSteadySelection(value:unknown,data?:Record<string,unknown>):SteadySelection{
  const r=object(value,['format','version','sourceSignature','timeId','states','algebraic','unknowns','parameters','invariants','reconstructions','checks','nonlinear']);
  if(r.format!=='rage.derived-execution'||r.version!==5||typeof r.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(r.sourceSignature)||!identity(r.timeId))fail('Invalid steady selection identity.');
  const datum=(v:unknown)=>{if(!identity(v)||data&&!Object.hasOwn(data,v))fail('Missing steady datum.');};
  for(const name of ['parameters','invariants']){const mapping=object(r[name]);if(Object.keys(mapping).length>200)fail('Too many steady bindings.');for(const [k,v] of Object.entries(mapping)){if(!identity(k))fail('Invalid quantity ID.');datum(v);}}
  for(const name of ['states','algebraic','reconstructions','checks']){
    const rows=array(r[name]),fields=name==='checks'?['equationId','scaleDataId']:['quantityId','equationId'];
    if(rows.length>200)fail('Too many steady rows.');
    const seen=new Set();for(const row of rows){const item=object(row,fields);if(fields.some(k=>!identity(item[k]))||seen.has(item[fields[0]]))fail('Invalid or duplicate steady row.');seen.add(item[fields[0]]);if(name==='checks')datum(item.scaleDataId);}
  }
  const s=r as unknown as SteadySelection,states=s.states.map(r=>r.quantityId),algebraic=s.algebraic.map(r=>r.quantityId);
  const owned=[s.timeId,...states,...algebraic,...s.reconstructions.map(r=>r.quantityId),...Object.keys(s.parameters)];
  if(new Set(owned).size!==owned.length||Object.keys(s.invariants).some(k=>!states.includes(k)))fail('Invalid steady quantity ownership.');
  const rowIds=[...s.states,...s.algebraic,...s.reconstructions].map(r=>r.equationId);if(new Set(rowIds).size!==rowIds.length)fail('Steady rows must be distinct.');
  const unknowns=array(s.unknowns);if(!unknowns.length||unknowns.length>200||unknowns.some(v=>!identity(v))||new Set(unknowns).size!==unknowns.length||!same([...unknowns].sort(),[...states.filter(k=>!Object.hasOwn(s.invariants,k)),...algebraic].sort()))fail('Steady unknowns must cover unbound states and algebraic variables.');
  const c=object(s.nonlinear,['variables','residualScales','residualTolerance','stepTolerance','maxIterations','maxBacktracks']);
  const variables=object(c.variables),scales=object(c.residualScales);exactKeys(variables,s.unknowns);exactKeys(scales,[...s.states.filter(r=>!Object.hasOwn(s.invariants,r.quantityId)),...s.algebraic].map(r=>r.equationId));
  Object.values(variables).forEach(v=>Object.values(object(v,['seedDataId','lowerDataId','upperDataId','scaleDataId'])).forEach(datum));Object.values(scales).forEach(datum);
  for(const k of ['residualTolerance','stepTolerance'])if(!finite(c[k])||Number(c[k])<=0)fail('Invalid steady tolerance.');
  for(const [k,limit] of [['maxIterations',30],['maxBacktracks',20]] as const)if(!Number.isSafeInteger(c[k])||Number(c[k])<1||Number(c[k])>limit)fail('Invalid steady iteration budget.');return s;
}

/** SHA-256 over sorted JSON with numbers encoded as IEEE-754 binary64 bytes.
 * Python and JavaScript therefore agree on 1 versus 1.0 and exponent formatting. */
export function steadySignature(value:unknown):string{
  function canonical(v:unknown):unknown{
    if(typeof v==='number'){if(!Number.isFinite(v))fail('Nonfinite fingerprint input.');const b=new ArrayBuffer(8);new DataView(b).setFloat64(0,v);return {$binary64:Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('')};}
    if(Array.isArray(v))return v.map(canonical);
    if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical((v as Record<string,unknown>)[k])]));return v;
  }
  const bytes=new TextEncoder().encode(JSON.stringify(canonical(value))),length=Math.ceil((bytes.length+9)/64)*64,data=new Uint8Array(length);data.set(bytes);data[bytes.length]=128;
  const view=new DataView(data.buffer);view.setUint32(length-8,Math.floor(bytes.length/0x20000000));view.setUint32(length-4,bytes.length*8);
  const k=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],w=new Uint32Array(64),rotate=(x:number,n:number)=>(x>>>n)|(x<<(32-n));
  for(let offset=0;offset<length;offset+=64){for(let i=0;i<16;i++)w[i]=view.getUint32(offset+i*4);for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(rotate(x,7)^rotate(x,18)^(x>>>3))+w[i-16]+(rotate(y,17)^rotate(y,19)^(y>>>10))+w[i-7];}
    let [a,b,c,d,e,f,g,z]=h;for(let i=0;i<64;i++){const t1=(z+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+k[i]+w[i])|0,t2=((rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c)))|0;z=g;g=f;f=e;e=(d+t1)|0;d=c;c=b;b=a;a=(t1+t2)|0;}[a,b,c,d,e,f,g,z].forEach((v,i)=>h[i]=(h[i]+v)|0);
  }return h.map(v=>(v>>>0).toString(16).padStart(8,'0')).join('');
}

export function readSteadyReport(value:unknown):SteadyReport{
  const r=object(value,['format','version','study','sourceModelId','signature','sourceSignature','formulationSignature','dataSignature','settingsSignature','method','selection','variables','rows','residualRows','invariants','parameters','proofConditions','runtimeConditions','scope']) as unknown as SteadyReport;
  const s=readSteadySelection(r.selection);if(r.format!=='rage.compilation'||r.version!==2||r.study!=='steady'||r.method!=='damped_newton'||!identity(r.sourceModelId)||typeof r.scope!=='string')fail('Invalid steady compilation.');
  for(const k of ['signature','sourceSignature','formulationSignature','dataSignature','settingsSignature'] as const)if(typeof r[k]!=='string'||!/^[a-f0-9]{64}$/.test(r[k]))fail('Invalid steady fingerprint.');
  if(r.sourceSignature!==s.sourceSignature||r.formulationSignature!==steadySignature(s)||r.settingsSignature!==steadySignature(s.nonlinear))fail('Stale steady compilation.');
  array(r.variables);if(!same(r.variables.map(v=>v.id),s.unknowns))fail('Steady unknown order mismatch.');
  for(const v of r.variables){object(v,['id','name','unit','scaleSI','seedSI','boundsSI']);if(typeof v.name!=='string'||typeof v.unit!=='string'||!finite(v.scaleSI)||v.scaleSI<=0||!finite(v.seedSI)||array(v.boundsSI).length!==2||!v.boundsSI.every(finite)||!(v.boundsSI[0]<v.boundsSI[1])||v.seedSI<v.boundsSI[0]||v.seedSI>v.boundsSI[1])fail('Invalid steady variable.');}
  array(r.rows);if(!same(r.rows.map(v=>v.id),[...s.states,...s.algebraic].map(v=>v.equationId)))fail('Steady row order mismatch.');
  for(const v of r.rows){object(v,['id','family','before','after','identity']);if(typeof v.identity!=='boolean'||[v.family,v.before,v.after].some(x=>typeof x!=='string'))fail('Invalid steady row.');}
  array(r.residualRows);if(r.residualRows.length!==r.variables.length||!same(r.residualRows.map(v=>v.id),r.rows.filter(v=>!v.identity).map(v=>v.id)))fail('Invalid steady square block.');
  for(const v of r.residualRows){object(v,['id','unit','scaleSI']);if(typeof v.unit!=='string'||!finite(v.scaleSI)||v.scaleSI<=0)fail('Invalid residual scale.');}
  array(r.invariants);if(steadySignature(Object.fromEntries(r.invariants.map(v=>[v.quantityId,v.dataId])))!==steadySignature(s.invariants)||r.invariants.length!==Object.keys(s.invariants).length)fail('Invariant bindings mismatch.');
  for(const v of r.invariants){object(v,['quantityId','equationId','dataId','value','unit']);if(!finite(v.value)||typeof v.unit!=='string'||!r.rows.some(row=>row.id===v.equationId&&row.identity))fail('Invalid invariant evidence.');}
  array(r.parameters);if(steadySignature(Object.fromEntries(r.parameters.map(v=>[v.id,v.dataId])))!==steadySignature(s.parameters)||r.parameters.length!==Object.keys(s.parameters).length)fail('Parameter bindings mismatch.');
  for(const v of r.parameters){object(v,['id','dataId','value','unit']);if(!finite(v.value)||typeof v.unit!=='string')fail('Invalid steady parameter.');}
  for(const rows of [r.proofConditions,r.runtimeConditions])for(const v of array(rows)){if(Object.values(object(v,['equationId','kind','latex'])).some(x=>typeof x!=='string'))fail('Invalid steady condition.');}return r;
}

export function steadyResultSignature(result:ConjuntoResultados):string{
  const provenance:Record<string,unknown>=Object.fromEntries(Object.entries(result.procedencia).filter(([k])=>k!=='assessment'));
  provenance.steadyDiagnostics=Object.fromEntries(Object.entries(result.procedencia.steadyDiagnostics!).filter(([k])=>k!=='resultSignature'));
  return steadySignature({...result,procedencia:provenance});
}
export function readSteadyResult(result:ConjuntoResultados):void{
  const e=object(result.procedencia.steadyDiagnostics,['version','verdict','globalUniqueness','method','sourceSignature','formulationSignature','dataSignature','settingsSignature','compilationSignature','quantityIds','equationIds','variableScales','residualScales','smallestSingularValue','conditionThreshold','inverseThreshold','relativeAmplification','inverseAmplification','initialResidualNorm','solver','scope','resultSignature']) as unknown as SteadyDiagnostics;
  const r=readSteadyReport(result.procedencia.compilation),s=r.selection,c=s.nonlinear;
  if(result.estado!=='resuelto'||result.ejes.length||result.eventos.length||result.modeloId!==r.sourceModelId||result.procedencia.motor!=='rage.compilador.steady'||result.procedencia.metodo!==e.method||e.version!==1||e.verdict!=='local_regular_root'||e.globalUniqueness!=='not_proved'||e.method!=='damped_newton'||typeof e.scope!=='string')fail('Invalid scalar steady verdict.');
  for(const k of ['sourceSignature','formulationSignature','dataSignature','settingsSignature'] as const)if(e[k]!==r[k])fail('Stale steady evidence.');
  if(e.compilationSignature!==r.signature||e.resultSignature!==steadyResultSignature(result)||!same(e.quantityIds,r.variables.map(v=>v.id))||!same(e.equationIds,r.residualRows.map(v=>v.id))||!same(e.variableScales,r.variables.map(v=>v.scaleSI))||!same(e.residualScales,r.residualRows.map(v=>v.scaleSI)))fail('Steady result fingerprint/order mismatch.');
  const n=e.solver;object(n,['iterations','evaluations','backtracks','residualNorm','stepNorm','conditionInfinity','terminationReason','completedProbes','uniqueness']);
  for(const k of ['iterations','evaluations','backtracks','completedProbes'] as const)if(!Number.isSafeInteger(n[k])||n[k]<0)fail('Invalid Newton counter.');
  if([n.residualNorm,n.stepNorm,n.conditionInfinity,e.smallestSingularValue,e.relativeAmplification,e.inverseAmplification,e.initialResidualNorm].some(x=>!finite(x)||x<0)||n.conditionInfinity<1||e.smallestSingularValue<=0||n.terminationReason!=='converged'||n.residualNorm>c.residualTolerance||n.stepNorm>c.stepTolerance||n.iterations>c.maxIterations||e.conditionThreshold!==1e-8||e.inverseThreshold!==1e-8||e.relativeAmplification!==n.conditionInfinity*Number.EPSILON||e.inverseAmplification!==Number.EPSILON/e.smallestSingularValue||Math.max(e.relativeAmplification,e.inverseAmplification)>1e-8||n.uniqueness!=='local_root_only; finite probes do not prove global uniqueness')fail('Steady convergence/regularity gate failed.');
  const expected=[...s.unknowns,...Object.keys(s.invariants),...s.reconstructions.map(v=>v.quantityId)].map(k=>'steady.'+k).concat(e.equationIds.map(k=>'steady.residual.'+k));
  if(!same(result.series.map(v=>v.id).sort(),expected.sort())||result.series.some(v=>v.ejes.length||!finite(v.valores)))fail('Invalid scalar steady series.');
  const series=new Map(result.series.map(v=>[v.id,v]));
  for(const v of r.variables){const row=series.get('steady.'+v.id)!;if(row.unidadSI!==v.unit||Number(row.valores)<v.boundsSI[0]||Number(row.valores)>v.boundsSI[1])fail('Steady domain/unit mismatch.');}
  for(const v of r.invariants){const row=series.get('steady.'+v.quantityId)!;if(row.valores!==v.value||row.unidadSI!==v.unit)fail('Changed steady invariant.');}
  let maximum=0;for(const v of r.residualRows){const row=series.get('steady.residual.'+v.id)!;if(row.unidadSI!==v.unit)fail('Residual unit mismatch.');maximum=Math.max(maximum,Math.abs(Number(row.valores))/v.scaleSI);}
  const ids=['steady.scaled_residual',...s.checks.map(v=>'conservation.'+v.equationId),...Object.keys(s.invariants).map(k=>'invariant.'+k)];
  if(!same(result.verificaciones.map(v=>v.id).sort(),ids.sort())||maximum>c.residualTolerance||result.verificaciones.find(v=>v.id==='steady.scaled_residual')?.valor!==maximum)fail('Steady verification mismatch.');
  for(const v of result.verificaciones){const tol=v.id==='steady.scaled_residual'?c.residualTolerance:1e-6;if(!finite(v.valor)||v.valor<0||v.valor>tol||v.tolerancia!==tol)fail('Steady verification failed.');}
}

export function steadyCSV(result:ConjuntoResultados):string{
  readSteadyResult(result);const quote=(v:string)=>'"'+v.replaceAll('"','""')+'"';
  return 'quantity,unit,value\n'+result.series.map(row=>[quote(row.nombre),quote(row.unidadSI),String(row.valores)].join(',')).join('\n');
}
