"""Demo 0.3 C7 review, reproducers of C7-R1 and C7-R2 (run: python tests/c7_review_session_findings.py; not collected by pytest).

Plant: the F3 index-one DAE with a held time input bounded to [0, 1000] W (tests/test_regime_events.py,
`test_out_of_box_action_is_rejected_and_the_run_is_unchanged`), which has a nonlinear algebraic block.

C7-R1: a run session of this model, with no action at all, cannot publish: `publish_trajectory` binds the timeline
into `report['signature']`, while `nonlinearDiagnostics.lastEvaluation.formulationSignature` keeps the formulation
signature, so `leer_resultados` rejects the result (`core/resultados/formato.py`, "location is stale"). `/resolver`
on the same model publishes.

C7-R2: a scheduled action outside the declared box escapes `RunSession.advance` as a `TimelineError` (HTTP 500,
not a located 422); `TimelineRun.advance` has already popped the action, so the next `advance` with the same
`seq` runs on without it.
"""
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import test_f3_index1_dae as dae
from test_f3_nonlinear_algebraic import thermal_case
from test_time_inputs import bound_input, with_held_input
from backend.api_modelo import _modelo
from core.compilador import resolver
from core.compilador.run_session import SessionStore


def held_model():
    store = {}
    def held_case(owners=('domain_one', 'domain_two')):
        model, author = thermal_case(owners)
        _, held, store['qid'] = with_held_input(model, author)
        return held, author
    original = dae.thermal_case
    dae.thermal_case = held_case
    try:
        held = dae.dae_case()
    finally:
        dae.thermal_case = original
    return _modelo({'modelo': bound_input(held, store['qid'], 0, 1000)}), store['qid']


parsed, qid = held_model()
print('/resolver:', resolver(copy.deepcopy(parsed))['estado'], flush=True)

sessions = SessionStore()
session = sessions.start(copy.deepcopy(parsed), None, background=False)
try:
    sessions.advance(session.id, 0, session.run.horizon)
    print('C7-R1 not reproduced: the session published', session.result['estado'])
except Exception as error:
    print('C7-R1: no action, advance to the horizon raised', type(error).__name__, '-', str(error)[:120], flush=True)
try:
    sessions.stop(session.id)
except Exception as error:
    print('C7-R1: the session is left', session.state, 'and stop raised', type(error).__name__, '-', str(error), flush=True)

session = sessions.start(copy.deepcopy(parsed), [{'t': 1.0, 'quantityId': qid, 'value': 2000.0, 'unit': 'W'}], background=False)
if session.state == 'failed':
    print('C7-R2 repaired: the out-of-box scheduled action fails the session at start with', session.error['diagnostics'], flush=True)
else:
    horizon = session.run.horizon
    try:
        sessions.advance(session.id, 0, horizon / 2)
        print('C7-R2 not reproduced: the out-of-box scheduled action was answered')
    except Exception as error:
        print('C7-R2: out-of-box scheduled action raised', type(error).__name__, getattr(error, 'code', None),
              '(not a SessionError, so HTTP 500); pending scheduled actions afterwards:', len(session.run._pending),
              '; edge', session.run.edge, '; next seq', session.next_seq, flush=True)
