"""Rutas del modelo común (docs/contracts/common-model.md, docs/engine/vertical-slice.md).

  POST /modelo/validar   {modelo} -> lectura estricta, relaciones siempre presentes y variables de la capa
  POST /modelo/resolver  {modelo} -> conjunto de resultados en el formato común (compilador + solvers propios)
  POST /modelo/termodinamica {modelo} | {solicitudV2} -> por volumen: cierre, fases candidatas, modelo de estado y
                         relaciones siempre presentes (panel Termodinámica del Engine; no calcula estados)
"""
from typing import Any

from fastapi import APIRouter, Body, HTTPException

from core.compilador import NoSoportado, resolver
from core.compilador.report import compilation_report
from core.modelo import ErrorModelo, leer_modelo_comun, relaciones
from core.modelo import desde_ensamblaje_v2
from core.termodinamica import NoSoportado as CapaNoSoportada, variables
from core.termodinamica.descripcion import describir

router = APIRouter(prefix="/modelo", tags=["modelo"])


@router.post('/indexed-execution')
def prepare_indexed_execution(body: Any = Body(...)):
    """Prepare the exact network; steady means zeroing its original rates."""
    from core.compilador.indexed_contract import prepare
    try:
        if (not isinstance(body, dict) or set(body) != {'format', 'version', 'model', 'mode'}
                or body['format'] != 'rage.indexed-execution.request'
                or type(body['version']) is not int or body['version'] != 1):
            raise ValueError('Expected indexed execution request version 1.')
        model = leer_modelo_comun(body['model'])
        if 'indexSet' not in model:
            raise ValueError('An index set is required.')
        return prepare(model, body['mode'])[1]
    except (ErrorModelo, ValueError, KeyError, TypeError, NoSoportado) as error:
        raise HTTPException(422, {'message': str(error), 'diagnostics': _located_diagnostics(error)}) from error


def _indexed_request(body, *, solve):
    from core.compilador.indexed_contract import prepare, resolve, validate_selection
    try:
        if set(body) != {'modelo', 'indexedExecution'}:
            raise ValueError('Expected modelo and indexedExecution only.')
        model = leer_modelo_comun(body['modelo'])
        if 'indexSet' not in model:
            raise ValueError('An index set is required.')
        selected = validate_selection(model, body['indexedExecution'])
        return resolve(model, selected) if solve else prepare(model, selected['mode'])[1]
    except (ErrorModelo, ValueError, KeyError, TypeError, NoSoportado) as error:
        raise HTTPException(422, {'message': str(error), 'diagnostics': _located_diagnostics(error)}) from error


@router.post('/chart-data')
def result_chart_data(body: Any = Body(...)):
    from core.modelo.result_charts import chart_data
    from core.resultados import ErrorResultados
    from core.unidades import ErrorUnidad
    try:
        return chart_data(body)
    except (ValueError, TypeError, KeyError, ErrorResultados, ErrorUnidad) as error:
        raise HTTPException(422, {'message': str(error)}) from error


@router.post('/index-set-assessment')
def index_set_assessment(body: Any = Body(...)):
    if not isinstance(body, dict) or body.get('format') != 'rage.index-set-expansion' or type(body.get('version')) is not int or body['version'] != 1:
        raise HTTPException(422, {'message': 'Expected rage.index-set-expansion version 1.'})
    raise HTTPException(422, {'message': 'Indexed stage networks require network lowering.', 'diagnostics': [{'code': 'index_set_not_lowered', 'path': 'indexSet', 'message': 'Numerical execution of the expanded network is not implemented.'}]})


@router.post('/index-set-expansion')
def index_set_expansion(body: Any = Body(...)):
    from core.modelo.index_sets import expand_index_set
    from core.modelo.template_instance import TemplateInstanceError
    try:
        if not isinstance(body, dict) or set(body) != {'format', 'version', 'model'} or body['format'] != 'rage.index-set-expansion.request' or type(body['version']) is not int or body['version'] != 1:
            raise ValueError('Expected rage.index-set-expansion.request version 1.')
        return expand_index_set(body['model'])
    except (ErrorModelo, TemplateInstanceError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, {'message': str(error), 'diagnostics': getattr(error, 'diagnostics', [])}) from error


@router.post('/template-instance')
def template_instance(body: Any = Body(...)):
    """Replay a recipe into a fresh, unconnected instance; never copy a result."""
    from core.modelo.template_instance import instantiate_template, TemplateInstanceError
    try:
        if not isinstance(body, dict) or set(body) != {'format','version','model'} or body['format'] != 'rage.template-instance.request' or type(body['version']) is not int or body['version'] != 1:
            raise TemplateInstanceError('request','Expected rage.template-instance.request version 1.')
        return instantiate_template(body['model'])
    except TemplateInstanceError as error:
        raise HTTPException(422, {'message': str(error), 'diagnostics': error.diagnostics}) from error


@router.post('/steady-transform')
def steady_transform(body: Any = Body(...)):
    """One zero-rate Transform of the current dynamic selection, without solving."""
    from core.modelo.steady_transform import prepare_steady_transform
    try:
        if not isinstance(body, dict) or set(body) != {'format', 'version', 'model'} or body['format'] != 'rage.steady-transform.request' or type(body['version']) is not int or body['version'] != 1:
            raise ValueError('Expected rage.steady-transform.request version 1.')
        if isinstance(body['model'], dict) and 'indexSet' in body['model']:
            raise ValueError('Indexed stage networks require network lowering before a steady Transform.')
        return prepare_steady_transform(body['model'])
    except (ErrorModelo, ValueError, KeyError, TypeError, NoSoportado) as error:
        diagnostics = _located_diagnostics(error)
        if not diagnostics and isinstance(error, ErrorModelo):
            diagnostics = [{'code': 'invalid_model', 'path': error.ruta, 'message': error.mensaje}]
        raise HTTPException(422, {'message': str(error), 'diagnostics': diagnostics}) from error


def _located_diagnostics(error):
    """Preserve physical ownership through compiler exception wrappers."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if hasattr(error, 'diagnostics'):
            return error.diagnostics
        error = error.__cause__
    return []


@router.post('/equation-workbench')
def equation_workbench(body: Any = Body(...)):
    """Author typed equation operations in the canonical Model worksheet."""
    from core.modelo.equation_workbench import describe_for_authoring,edit,fundamental_report
    try:
        if isinstance(body,dict) and 'draft' in body and set(body)<= {'draft','action'}:return fundamental_report(body['draft'],body.get('action'))
        if not isinstance(body,dict) or set(body)-{'modelo','solicitudV2','action'} or ('modelo' in body)==('solicitudV2' in body):raise ValueError('Expected one physical model and an optional equation operation.')
        model=leer_modelo_comun(desde_ensamblaje_v2(body['solicitudV2']) if 'solicitudV2' in body else body['modelo'])
        return edit(model,body['action']) if 'action' in body else describe_for_authoring(model)
    except (ErrorModelo,ValueError,KeyError,TypeError,NotImplementedError) as error:
        raise HTTPException(422,{'message':str(error)}) from error


@router.post('/derived-execution-source')
def derived_execution_source(body: Any = Body(...)):
    """Read-only pin for selecting the exact Transform graph in Solve."""
    from core.compilador.derived import source_signature
    try:
        model = leer_modelo_comun(desde_ensamblaje_v2(body['solicitudV2'])) if isinstance(body, dict) and set(body) == {'solicitudV2'} else _modelo(body)
        return {'format': 'rage.derived-execution-source', 'version': 1,
                'modelId': model['id'], 'sourceSignature': source_signature(model)}
    except (ErrorModelo, ValueError, KeyError, TypeError, NotImplementedError) as error:
        raise HTTPException(422, {'message': str(error)}) from error


@router.post('/hydraulics')
def hydraulic_inspection(body: Any = Body(...)):
    """Inspect generic hydraulic bindings, data roles and the admitted compiler."""
    from core.compilador.hydraulics import HydraulicSystem
    try:
        if not isinstance(body,dict) or set(body)!={'modelo'}:raise ValueError('Expected one common model envelope.')
        model=leer_modelo_comun(body['modelo']);system=HydraulicSystem(model)
        return {'format':'rage.hydraulic-inspection','version':1,'modelId':model['id'],'dataFields':list(system.data_fields.values()),'report':system.report()}
    except (ErrorModelo, ValueError, KeyError, TypeError, NoSoportado) as error:
        raise HTTPException(422,{'message':str(error), 'diagnostics':getattr(error,'diagnostics',[])}) from error


@router.post('/hydraulics/admission')
def hydraulic_admission(body: Any = Body(...)):
    """Check the physical reduction without evaluating numerical data in Model."""
    from core.compilador.hydraulics import validate_admission
    try:
        if not isinstance(body, dict) or set(body) != {'modelo'}:
            raise ValueError('Expected one common model envelope.')
        model = leer_modelo_comun(body['modelo'])
        validate_admission(model)
        return {'format': 'rage.model-admission', 'version': 1, 'modelId': model['id'],
                'scope': 'reduced-hydraulics', 'diagnostics': []}
    except (ErrorModelo, ValueError, KeyError, TypeError, NoSoportado) as error:
        raise HTTPException(422, {'message': str(error),
                                 'diagnostics': getattr(error, 'diagnostics', [])}) from error


@router.post("/momentum-derivation")
def momentum_derivation(body: Any = Body(...)):
    """Replay fundamental-law operations; no pump solver or property invention."""
    import copy
    from core.balances.momentum_derivation import FORMAT, describe_volume, edit_journal
    try:
        if not isinstance(body, dict) or set(body) - {"modelo", "solicitudV2", "volumeId", "action"} or ("modelo" in body) == ("solicitudV2" in body):
            raise ValueError("Expected one model envelope, volumeId and an optional action.")
        model = copy.deepcopy(desde_ensamblaje_v2(body["solicitudV2"]) if "solicitudV2" in body else body["modelo"])
        owner = body.get("volumeId")
        physical = copy.deepcopy(model)
        if isinstance(physical, dict) and isinstance(physical.get("motores"), dict):
            physical["motores"].pop("momentumDerivation", None)
        leer_modelo_comun(physical)
        if not isinstance(owner, str) or not any(v["id"] == owner for v in model["volumenes"]):
            raise ValueError("An existing momentum control volume is required.")
        journal = model["motores"].get("momentumDerivation", {"format": FORMAT, "version": 1, "volumes": {}})
        if "action" in body:
            journal = edit_journal(journal, owner, body["action"])
            model["motores"]["momentumDerivation"] = journal
        leer_modelo_comun(model)
        preview = owner not in journal["volumes"]
        if preview:
            journal = copy.deepcopy(journal)
            journal["volumes"][owner] = {"origin": "recorded", "operations": []}
        return {"journal": model["motores"].get("momentumDerivation"), "preview": preview,
                "development": describe_volume(journal, owner, model)}
    except (ErrorModelo, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, {"message": str(error)}) from error


@router.post("/thermodynamic-derivation")
def thermodynamic_derivation(body: Any = Body(...)):
    """Develop state relations and explicit package choices, independently of balances."""
    from core.termodinamica.derivation import describe_volume, edit_journal
    from core.modelo.operation_journal import JournalError, keys
    try:
        keys(body, ["journal", "volumeId", "fixed"], ["action", "configured"])
        journal = edit_journal(body["journal"], body["volumeId"], body["action"], body.get("configured")) if "action" in body else body["journal"]
        return {"journal": journal, "development": describe_volume(journal, body["volumeId"], body["fixed"])}
    except JournalError as error:
        raise HTTPException(422, {"code": "invalid_thermodynamic_derivation", "message": str(error)}) from error


@router.post("/energy-derivation")
def energy_derivation(body: Any = Body(...)):
    """Develop the first law from recorded operations; never solve a state."""
    from core.balances.energy_derivation import describe_volume, edit_journal
    from core.modelo.operation_journal import JournalError, keys
    try:
        keys(body, ["journal", "volumeId", "context"], ["action"])
        journal = edit_journal(body["journal"], body["volumeId"], body["action"]) if "action" in body else body["journal"]
        return {"journal": journal, "development": describe_volume(journal, body["volumeId"], body["context"])}
    except JournalError as error:
        raise HTTPException(422, {"code": "invalid_energy_derivation", "message": str(error)}) from error


@router.post("/material-derivation")
def material_derivation(body: Any = Body(...)):
    """Replay or author material assumptions; no integration or thermodynamic solve."""
    from core.balances.material_derivation import MaterialDerivationError, describe_volume, edit_journal
    try:
        if not isinstance(body, dict) or set(body) - {"journal", "volumeId", "action"} or not {"journal", "volumeId"} <= set(body):
            raise MaterialDerivationError("Expected journal, volumeId and an optional action.")
        journal = body["journal"]
        if "action" in body:
            journal = edit_journal(journal, body["volumeId"], body["action"])
        return {"journal": journal, "development": describe_volume(journal, body["volumeId"])}
    except MaterialDerivationError as error:
        raise HTTPException(422, {"code": "invalid_material_derivation", "message": str(error)}) from error


def _modelo(cuerpo):
    if not isinstance(cuerpo, dict) or "modelo" not in cuerpo:
        raise HTTPException(422, "se espera {'modelo': <modelo común v0>}")
    try:
        from core.compilador.derived import validate_selected_data, LoweringError
        validate_selected_data(cuerpo["modelo"])
        return leer_modelo_comun(cuerpo["modelo"])
    except LoweringError as error:
        raise HTTPException(422, {"codigo": "no_soportado", "mensaje": str(error), "diagnostics": error.diagnostics}) from error
    except ErrorModelo as e:
        raise HTTPException(422, {"ruta": e.ruta, "mensaje": e.mensaje}) from e


@router.post("/validar")
def validar(cuerpo: Any = Body(...)):
    m = _modelo(cuerpo)
    try:
        var = variables(m)
    except CapaNoSoportada as e:
        var, aviso = [], str(e)
    else:
        aviso = None
    return {"formato": "rage.modelo.validacion", "version": 0, "relaciones": relaciones(m), "variables": var,
            **({"aviso": aviso} if aviso else {})}


def _inverse_steady(body, model):
    """Solve evidence augments the pinned forward selection without changing it."""
    from core.solvers.inverse_steady import InverseSteadySystem
    from core.compilador.steady import read_report
    if not isinstance(body, dict) or set(body) - {'modelo', 'inverseSpecification'}:
        raise HTTPException(422, {'message': 'Expected modelo and inverseSpecification.'})
    system = InverseSteadySystem(model, body['inverseSpecification'])
    read_report(system.report)
    return system


@router.post("/resolver")
def resolver_modelo(cuerpo: Any = Body(...)):
    if isinstance(cuerpo, dict) and 'indexedExecution' in cuerpo:
        return _indexed_request(cuerpo, solve=True)
    if isinstance(cuerpo, dict) and isinstance(cuerpo.get('modelo'), dict) and 'indexSet' in cuerpo['modelo']:
        raise HTTPException(422, {'message': 'Indexed stage networks require network lowering; no generic stage is solved in their place.', 'diagnostics': [{'code': 'index_set_not_lowered', 'path': 'indexSet'}]})
    assessment = None
    if isinstance(cuerpo, dict) and 'assessmentVersion' in cuerpo and 'inverseSpecification' not in cuerpo:
        if type(cuerpo['assessmentVersion']) is not int or cuerpo['assessmentVersion'] != 1:
            raise HTTPException(422, {'message': 'Unsupported assessment version.'})
        assessment = model_assessment({'format': 'rage.model-assessment.request', 'version': 1, 'model': cuerpo.get('modelo')})
    try:
        m = _modelo(cuerpo)
        if isinstance(cuerpo, dict) and 'inverseSpecification' in cuerpo:
            from core.compilador.steady import read_result
            result = read_result(_inverse_steady(cuerpo, m).solve())
        else:
            result = resolver(m)
        if assessment is not None:
            from core.compilador.assessment import attach_result
            return attach_result(assessment, result)
        return result
    except HTTPException as error:
        if assessment is not None:
            detail = error.detail if isinstance(error.detail, dict) else {'mensaje': error.detail}
            raise HTTPException(error.status_code, {**detail, 'assessment': assessment}) from error
        raise
    except (NoSoportado, CapaNoSoportada) as e:
        raise HTTPException(422, {"codigo": "no_soportado", "mensaje": str(e), "diagnostics": _located_diagnostics(e),
                                 **({'assessment': assessment} if assessment is not None else {})}) from e


@router.post('/assessment')
def model_assessment(body: Any = Body(...)):
    """A versioned draft assessment; it does not weaken the executable reader."""
    from core.compilador.assessment import assess_model, read_assessment
    try:
        if (not isinstance(body, dict) or not {'format', 'version', 'model'} <= body.keys() or
                body.keys() - {'format', 'version', 'model', 'initialize'} or body['format'] != 'rage.model-assessment.request' or
                type(body['version']) is not int or body['version'] != 1 or not isinstance(body['model'], dict)):
            raise ValueError('Expected rage.model-assessment.request v1 with one model.')
        if 'indexSet' in body['model']:
            raise HTTPException(422, {'message': 'Indexed stage networks require network lowering.', 'diagnostics': [{'code': 'index_set_not_lowered', 'path': 'indexSet'}]})
        return read_assessment(assess_model(body['model'], initialize=body.get('initialize', True)))
    except (ValueError, TypeError) as error:
        raise HTTPException(422, {'message': str(error)}) from error


@router.post("/compilation")
def describe_compilation(cuerpo: Any = Body(...)):
    if isinstance(cuerpo, dict) and 'indexedExecution' in cuerpo:
        return _indexed_request(cuerpo, solve=False)
    if isinstance(cuerpo, dict) and set(cuerpo) == {"solicitudV2"}:
        try:
            model = leer_modelo_comun(desde_ensamblaje_v2(cuerpo["solicitudV2"]))
        except (ErrorModelo, KeyError, TypeError, ValueError) as error:
            raise HTTPException(422, {"codigo": "solicitud_invalida", "mensaje": str(error)}) from error
    else:
        model = _modelo(cuerpo)
    if 'indexSet' in model:
        raise HTTPException(422, {'message': 'Indexed stage networks require network lowering.', 'diagnostics': [{'code': 'index_set_not_lowered', 'path': 'indexSet'}]})
    try:
        if isinstance(cuerpo, dict) and 'inverseSpecification' in cuerpo:
            return _inverse_steady(cuerpo, model).report
        return compilation_report(model)
    except (NoSoportado, CapaNoSoportada) as error:
        raise HTTPException(422, {"codigo": "no_soportado", "mensaje": str(error), "diagnostics": _located_diagnostics(error)}) from error


@router.post("/formulation-summary")
def describe_formulation(body: Any = Body(...)):
    """Model -> Transform handoff; independent of study data or state initialization."""
    from core.compilador.presentation import formulation_summary, symbolic_formulation_summary
    try:
        if isinstance(body,dict) and set(body)=={'draft'}:
            return symbolic_formulation_summary(body['draft'])
        model = leer_modelo_comun(desde_ensamblaje_v2(body["solicitudV2"])) if isinstance(body, dict) and set(body) == {"solicitudV2"} else _modelo(body)
        return formulation_summary(model)
    except (ErrorModelo, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, {"message": str(error)}) from error


@router.post("/dynamic-definition")
def dynamic_definition(body: Any = Body(...)):
    """Physical Model policy authoring; no equilibrium initialization or integration."""
    from core.modelo.dynamic_definition import describe_definition, edit_definition
    import copy
    try:
        if not isinstance(body, dict) or set(body) - {"modelo", "solicitudV2", "action"} or ("modelo" in body) == ("solicitudV2" in body):
            raise ValueError("Expected one model envelope and an optional action.")
        model = copy.deepcopy(desde_ensamblaje_v2(body["solicitudV2"]) if "solicitudV2" in body else body["modelo"])
        if "action" in body:
            # Validate the whole physical definition before authoring. Isolate
            # only this extension so Undo can repair its stale binding.
            physical = copy.deepcopy(model)
            if isinstance(physical, dict) and isinstance(physical.get("motores"), dict):
                physical["motores"].pop("dynamicDefinition", None)
            leer_modelo_comun(physical)
            model["motores"]["dynamicDefinition"] = edit_definition(model, body["action"])
        model = leer_modelo_comun(model)
        return {"definition": model["motores"].get("dynamicDefinition"), "formulation": describe_definition(model)}
    except (ErrorModelo, ValueError, KeyError, TypeError) as error:
        raise HTTPException(422, {"message": str(error)}) from error


@router.post("/termodinamica")
def termodinamica(cuerpo: Any = Body(...)):
    if isinstance(cuerpo, dict) and "solicitudV2" in cuerpo:
        try:
            m = leer_modelo_comun(desde_ensamblaje_v2(cuerpo["solicitudV2"]))
        except (ErrorModelo, KeyError, TypeError, ValueError) as e:
            raise HTTPException(422, {"codigo": "solicitud_invalida", "mensaje": str(e)}) from e
    else:
        m = _modelo(cuerpo)
    return describir(m)
