"""Demo 0.3 C9 review, reproducer of C9-R1 (run: python tests/c9_review_preview_units.py; not collected by pytest).

The live preview's unit labels. The heated region with the duty declared in kW (a Model choice).
What unit does the workbench report for heaterDuty (the label `unit(id)` in DerivedSolve.tsx), and what numbers do
the session rows carry for it (the plotted values)? `LiveRun` in frontend/app/models/DerivedSolve.tsx labels the
rows, the action event text and the time-input field with `unit(id)`, the workbench unit, while the rows are SI.
"""
import copy, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import test_time_inputs as ti
from backend.api_modelo import _modelo
from core.compilador.run_session import SessionStore
from core.modelo.equation_workbench import describe

original = ti.Author.append
def append(self, kind, **kw):
    if kw.get('name') in ('heaterDuty', 'heaterPower'):
        kw['unit'] = 'kW'
    return original(self, kind, **kw)
ti.Author.append = append
author, energy = ti.heated_region()
ti.Author.append = original
model = ti.selection_model(author, energy, inputs=['heaterDuty'])
data_id = model['motores']['derivedExecution']['timeInputs']['heaterDuty']
model['datos'][data_id]['declaracion'] = {'texto': '1', 'unidad': 'kW'}     # 1 kW = 1000 W
parsed = _modelo({'modelo': model})
report = describe(copy.deepcopy(parsed))
units = {q['id']: q['unit'] for q in report['quantities']}
print('workbench unit of heaterDuty (the preview label):', units.get('heaterDuty'), flush=True)
store = SessionStore()
s = store.start(copy.deepcopy(parsed), None, background=False)
print('session state', s.state, s.error, flush=True)
ids = list(s.system.state_ids)
a = store.advance(s.id, 0, 50.0)
print('row values for heaterDuty (plotted and offered as the field placeholder under that label):', a['rows']['values']['heaterDuty'][:3], flush=True)
print('every state: workbench unit and last row value', {i: (units.get(i), a['rows']['values'][i][-1]) for i in ids}, flush=True)
store.stop(s.id)
