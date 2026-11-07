// Exercise the real endpoint and the production TypeScript reader without starting a server.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
const dir=path.dirname(fileURLToPath(import.meta.url));
const file=path.join(dir,'app/models/equationWorkbench.ts');
const module={exports:{}};
new Function('exports','module',ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(module.exports,module);
const {readEquationWorkbenchReport,readEquationWorkbench}=module.exports;
const python=String.raw`
import asyncio,copy,json
import httpx
from fastapi import FastAPI
from backend.api_modelo import router
app=FastAPI();app.include_router(router)
async def post(payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        return await client.post("/modelo/equation-workbench",json=payload)
draft={'format':'rage.fundamental-equations','version':3,'modelId':'custom-relation-verifier','materialJournal':{'origin':'recorded','operations':[]},'ports':[],'definition':{'format':'rage.equation-workbench','version':1,'operations':[],'cursor':0}}
def call(action=None, source=None):
    payload={'draft':copy.deepcopy(source or draft)}
    if action is not None:payload['action']=action
    return asyncio.run(post(payload))
def action(kind,op=None):
    response=call({'kind':kind,**({'operation':op} if op else {})})
    if response.status_code!=200:raise AssertionError(response.text)
    report=response.json();draft['definition']=report['definition'];return report
def add(**op):return action('append',{'family':'thermodynamics',**op})
for name,unit in [('p','Pa'),('pref','Pa'),('T','K'),('A','1'),('B','K'),('C','K')]:r=add(kind='declare_symbol',name=name,unit=unit)
alias={q['name']:q['input'] for q in r['quantities']}
r=add(kind='declare_relation',left=alias['T'],right=alias['T'],reason='Temperature identity',relationKind='definition')
t=next(q['id'] for q in r['quantities'] if q['name']=='T')
domain={'kind':'declare_domain','family':'thermodynamics','sources':['operation.7'],'symbol':t,'domain':'interval','lower':'273','upper':'303','lowerOpen':False,'upperOpen':False,'endpointUnit':'K','reason':'NIST range'}
bad=copy.deepcopy(domain);bad['endpointUnit']='Pa';bad_response=call({'kind':'append','operation':bad})
assert bad_response.status_code==422,bad_response.text
assert 'incompatible dimensions' in bad_response.text,bad_response.text
action('append',domain)
source={'kind':'literature','citation':'Bridgeman and Aldrich (1964), NIST Chemistry WebBook','url':'https://webbook.nist.gov/cgi/cbook.cgi?ID=C7732185&Type=ANTOINE','table':'Antoine Equation Parameters','validRange':'273 to 303 K'}
alias={q['name']:q['input'] for q in action('undo')['quantities']}
action('redo')
bad_url=copy.deepcopy(source);bad_url['url']='javascript:alert(1)'
invalid_url=call({'kind':'append','operation':{'kind':'declare_relation','family':'thermodynamics','left':alias['p'],'right':alias['pref'],'reason':'Invalid URL','relationKind':'constitutive','source':bad_url}})
assert invalid_url.status_code==422 and 'Invalid relation source field: url.' in invalid_url.text,invalid_url.text
relation=add(kind='declare_relation',left=alias['p'],right=f"{alias['pref']}*exp(log(10)*({alias['A']}-{alias['B']}/({alias['T']}+{alias['C']})))",reason='Empirical vapour pressure',relationKind='constitutive',source=source,domains=['operation.8'])
assert relation['definition']['operations'][8]['source']==source
consumer=add(kind='expand',sources=['operation.9'])
stale=copy.deepcopy(draft);stale['definition']['operations'][8]['source']['citation']='Changed source'
recovered=call(source=stale);assert recovered.status_code==200,recovered.text
recovery=recovered.json();assert recovery['replay']['failedOperation']==10,recovery
undo=action('undo');undo_relation=action('undo');redo=action('redo');redo_consumer=action('redo')
assert redo_consumer['definition']==consumer['definition']
print(json.dumps({'relation':relation,'consumer':consumer,'recovery':recovery,'undo':undo,'undoRelation':undo_relation,'redo':redo,'redoConsumer':redo_consumer,'rejection':bad_response.json()}))
`;
const result=spawnSync('python',['-c',python],{cwd:path.resolve(dir,'..'),encoding:'utf8',maxBuffer:8*1024*1024});
if(result.status!==0)throw new Error(result.stderr||result.stdout);
const reports=JSON.parse(result.stdout);
for(const report of ['relation','consumer','recovery','undo','undoRelation','redo','redoConsumer'])readEquationWorkbenchReport(reports[report]);
const op=reports.relation.definition.operations[8];
assert.equal(op.source.kind,'literature');assert.equal(op.source.validRange,'273 to 303 K');assert.deepEqual(op.domains,['operation.8']);
assert.match(reports.rejection.detail.message,/incompatible dimensions/);
assert.equal(reports.recovery.replay.failedOperation,10);assert.equal(reports.recovery.execution.supported,false);
assert.deepEqual(reports.redoConsumer.definition,reports.consumer.definition);
const invalid=structuredClone(reports.relation.definition);delete invalid.operations[8].source.citation;assert.throws(()=>readEquationWorkbench(invalid),/Invalid relation source field: citation\./);
const invalidUrl=structuredClone(reports.relation.definition);invalidUrl.operations[8].source.url='javascript:alert(1)';assert.throws(()=>readEquationWorkbench(invalidUrl),/Invalid relation source field: url\./);
console.log('Custom relation endpoint and TypeScript reader: source, domain, rejection, invalidation and undo/redo passed.');
