"""Reproducible cProfile phases for shared-authored thermal chains."""
import cProfile
import argparse
import json
from pathlib import Path
import pstats
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.compilador.derived import DerivedSystem, resolve_system
from core.compilador.steady import SteadySystem
from core.modelo.steady_transform import prepare_steady_transform
from core.modelo.preparation_cache import preparation_policy, evidence


def phase(directory, name, function):
    profile = cProfile.Profile()
    start = time.perf_counter()
    result = profile.runcall(function)
    elapsed = time.perf_counter()-start
    profile.dump_stats(str(directory/(name+'.prof')))
    stats = pstats.Stats(profile)
    top = sorted(stats.stats.items(),key=lambda item:item[1][3],reverse=True)[:30]
    rows = [{'file':key[0], 'line':key[1], 'function':key[2], 'calls':value[1],
             'selfSeconds':value[2], 'cumulativeSeconds':value[3]} for key,value in top]
    categories = {
        'replay': ['replay_operations'], 'graphBuild': ['build','_source_graph'],
        'substitution': ['_expand','subs','xreplace','specialize'],
        'loweringAST': ['_ast','_lower_model','_compilar'],
        'regularity': ['factor_step','audit_graph','require_consequence'],
        'jacobian': ['configure_jacobian','_closure_residual'],
        'solve': ['solve','integrar'],
    }
    costs = {category:[{'file':key[0],'function':key[2], 'calls':value[1],
                       'selfSeconds':value[2],'cumulativeSeconds':value[3]}
                      for key,value in stats.stats.items() if key[2] in names]
             for category,names in categories.items()}
    report = {'phase':name,'wallSeconds':elapsed,'topCumulative':rows,'categories':costs,
              'note':'Cumulative costs overlap; do not sum nested phases. cProfile wall time includes instrumentation.'}
    (directory/(name+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'phase':name,'wallSeconds':elapsed,'top':rows[:5]}),flush=True)
    return result


def run(count, output):
    directory=Path(output)/str(count)
    directory.mkdir(parents=True,exist_ok=True)
    source=Path('.tmp/sparse-chains/model-'+str(count)+'.json')
    if not source.exists():
        from sparse_chain_inputs import thermal_chain
        source.parent.mkdir(parents=True,exist_ok=True)
        source.write_text(json.dumps(thermal_chain(count)),encoding='utf8')
    model=json.loads(source.read_text(encoding='utf8'))
    system=phase(directory,'dynamic-preparation',lambda:DerivedSystem(model))
    phase(directory,'dynamic-solve',lambda:resolve_system(system))
    transformed=phase(directory,'steady-transform',lambda:prepare_steady_transform(model))
    Path(directory/'steady-model.json').write_text(json.dumps(transformed['model']),encoding='utf8')
    steady=phase(directory,'steady-preparation',lambda:SteadySystem(transformed['model']))
    phase(directory,'steady-solve',steady.solve)
    (directory/'cache.json').write_text(json.dumps(evidence(),indent=2),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('counts',nargs='*',type=int,default=[5,10,20,40])
    parser.add_argument('--output',default='.tmp/symbolic-profile-cached')
    parser.add_argument('--uncached',action='store_true')
    options=parser.parse_args()
    with preparation_policy(cached=not options.uncached):
        for count in options.counts: run(count,options.output)
