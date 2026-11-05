"""Cold independent lowering versus one generic plan plus identity binding."""
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.compilador.derived import DerivedSystem
from core.compilador.template_lowering import bind_stage
from core.mathematics.preparation import preparation_policy
from core.modelo.template_instance import instantiate_template
from demo02_drum import frozen_model


def main():
    source=frozen_model();rows=[]
    for count in (5,10,20,40):
        start=time.perf_counter()
        instances=[instantiate_template(source,identity_namespace=f'benchmark-generic:{j}') for j in range(count)]
        replay=time.perf_counter()-start
        start=time.perf_counter();generic=DerivedSystem(source)
        bound=[bind_stage(generic,row) for row in instances]
        reused=time.perf_counter()-start
        cold=0.;validation=0.
        for stage,row in zip(bound,instances):
            # Disable all preparation caches for the independent cold reference.
            start=time.perf_counter()
            with preparation_policy(cached=False):reference=DerivedSystem(row['model'])
            cold+=time.perf_counter()-start
            start=time.perf_counter()
            assert stage.rates==reference.rates and stage.checks==reference.checks
            np.testing.assert_allclose(stage.rhs(0.,stage.initial()),reference.rhs(0.,reference.initial()),rtol=1e-13,atol=1e-13)
            validation+=time.perf_counter()-start
        result={'count':count,'replaySeconds':replay,'genericBindSeconds':reused,'coldLoweringSeconds':cold,'validationSeconds':validation}
        rows.append(result);print(json.dumps(result),flush=True)
        Path('.tmp/template-lowering-benchmark.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    for key in ('genericBindSeconds','coldLoweringSeconds'):
        print(key+' exponent: '+str(np.polyfit(np.log([r['count'] for r in rows]),np.log([r[key] for r in rows]),1)[0]),flush=True)


if __name__=='__main__':main()
