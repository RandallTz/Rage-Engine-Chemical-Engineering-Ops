"""Direct Python entry points must never run an indexed model's generic stage."""
import pytest

from core.compilador.compilador import compilar, resolver
from core.compilador.derived import DerivedSystem
from core.compilador.derived_graph import LoweringError
from core.compilador.report import compilation_report
from core.compilador.steady import SteadySystem
from test_index_sets import source_model


@pytest.mark.parametrize('entry', [compilar, resolver, compilation_report, DerivedSystem])
def test_indexed_dynamic_cannot_fall_back_to_generic_stage(entry):
    with pytest.raises(LoweringError) as caught:
        entry(source_model())
    assert caught.value.diagnostics[0]['code'] == 'index_set_not_lowered'
    assert caught.value.diagnostics[0]['path'] == 'indexSet'


@pytest.mark.parametrize('entry', [compilar, resolver, compilation_report, SteadySystem])
def test_indexed_steady_cannot_fall_back_to_generic_stage(entry):
    model = source_model()
    model['motores']['derivedExecution']['version'] = 5
    with pytest.raises(LoweringError) as caught:
        entry(model)
    assert caught.value.diagnostics[0]['code'] == 'index_set_not_lowered'
    assert caught.value.diagnostics[0]['path'] == 'indexSet'
