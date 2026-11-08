"""Whole-domain admission and independent point/reference checks are distinct."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from core.reactions import chemical_equilibrium as ce
from core.compilador.reaction_extent import certify_extent,nonsingular,add,multiply,pair
from core.compilador.derived_graph import LoweringError,source_signature
from core.compilador.derived import DerivedSystem,resolve_system
from core.modelo import leer_modelo_comun
from equilibrium_reaction_inputs import author,SPECIES,NU


@pytest.fixture(scope='module')
def model():
    result=author()
    Path('.tmp').mkdir(exist_ok=True)
    Path('.tmp/f5-equilibrium-model.json').write_text(json.dumps(result),encoding='utf-8')
    return result


def test_outward_composition_contains_exact_rational_arithmetic():
    from fractions import Fraction
    for function,operation in [(add,lambda a,b:a+b),(multiply,lambda a,b:a*b)]:
        a=(.1,.3);b=(-.7,.9);result=function(a,b)
        for x in a:
            for y in b:
                value=operation(Fraction(x),Fraction(y))
                assert Fraction(result[0])<=value<=Fraction(result[1])
    with pytest.raises(LoweringError) as caught:nonsingular([[[0.,1.]]])
    assert caught.value.diagnostics[0]['code']=='reaction_index_not_certified'
    exact=Fraction(1,10);lo,hi=pair([exact,exact])
    assert Fraction(lo)<=exact<=Fraction(hi) and lo<hi


def test_certified_extent_box_and_dependent_rows():
    gas=ce.IdealGasPhase(SPECIES)
    result=certify_extent(gas,[NU,[2*n for n in NU]],[[1.99,2.01],[1.99,2.01],[-.01,.01],[0,0]],[[.5,1.5]],[790,810],[9e4,11e4],phase_id='vapor',standard_state='ideal_gas_P0')
    assert result['certified'] and result['independent']==[0]
    assert result['determinantBounds'][0]>0
    # Independently analytic ideal-gas directional derivative; point checks
    # supplement, and never replace, the certified domain proof.
    for xi in np.linspace(.5,1.5,17):
        n=np.array([2,2,0,0])+np.array(NU)*xi
        derivative=sum(1/n)
        assert result['jacobianBounds'][0][0][0]<=derivative<=result['jacobianBounds'][0][0][1]


def test_two_reaction_block_encloses_independent_ideal_gas_jacobian():
    species=['7727-37-9','1333-74-0','7664-41-7','7782-44-7','7732-18-5']
    nu=np.array([[-1,-3,2,0,0],[0,-2,0,-1,2]])
    proof=certify_extent(ce.IdealGasPhase(species),nu,[[10,10]]*5,[[0,.1],[0,.1]],[700,700],[1e5,1e5],phase_id='vapor',standard_state='ideal_gas_P0')
    assert proof['determinantBounds'][0]>0
    for x in np.linspace(0,.1,4):
        for y in np.linspace(0,.1,4):
            n=np.ones(5)*10+nu.T@np.array([x,y])
            reference=nu@(np.diag(1/n)-np.ones((5,5))/sum(n))@nu.T
            for i in range(2):
                for j in range(2):assert proof['jacobianBounds'][i][j][0]<=reference[i,j]<=proof['jacobianBounds'][i][j][1]


def test_nonbinary_exact_stoichiometry_is_not_silently_rounded():
    with pytest.raises(LoweringError) as caught:
        certify_extent(ce.IdealGasPhase(SPECIES),[['-1/3','-1/3','1/3','1/3']],[[1,1]]*4,[[0,.1]],[800,800],[1e5,1e5],phase_id='vapor',standard_state='ideal_gas_P0')
    assert caught.value.diagnostics[0]['code']=='reaction_coefficient_not_representable'


@pytest.mark.parametrize('failure',['nonpositive','domain','phase','uncertified','unsupported','unsupported_vapour'])
def test_provider_rejections_are_located(failure,monkeypatch):
    gas=ce.IdealGasPhase(SPECIES);kw={'phase_id':'vapor','standard_state':'ideal_gas_P0'}
    ext=[[.5,1.5]];temperature=[800,800]
    if failure=='nonpositive':ext=[[-1,3]]
    elif failure=='domain':temperature=[1,2]
    elif failure=='phase':kw['phase_id']='liquido'
    elif failure=='uncertified':
        monkeypatch.setattr(ce,'reaction_jacobian_bounds',lambda *a,**k:{'certified':False,'diagnostics':[{'code':'NONFINITE_BOUND','path':'bounds.dg_dn','message':'Uncertified test provider'}]})
    elif failure=='unsupported_vapour':
        from core.mezclas import Sistema
        # Package vapour regions are not admitted by the extent gate (B3 review R1).
        gas=ce.PackagePhase(Sistema('unifac-dortmund-public',['64-17-5','7732-18-5']),'vapor',anchor='gas')
        ext=[[-.1,.1]];temperature=[350,350]
    else:
        from core.mezclas import Sistema
        # B3 admits UNIFAC liquids; a liquid model without certified bounds (NRTL) is still rejected, never replaced.
        gas=ce.PackagePhase(Sistema('nrtl-chemsep',['64-17-5','7732-18-5']),'liquido',anchor='liquid')
        kw={'phase_id':'liquido','standard_state':'pure_liquid_TP'}
        ext=[[-.1,.1]]
    with pytest.raises(LoweringError) as caught:
        certify_extent(gas,[NU] if not failure.startswith('unsupported') else [[-1,1]],[[2,2],[2,2],[0,0],[0,0]] if not failure.startswith('unsupported') else [[1,1],[1,1]],ext,temperature,[1e5,1e5],**kw)
    assert caught.value.diagnostics[0]['path'].startswith('equilibriumReactions.')
    expected={'nonpositive':'BOX_NONPOSITIVE','domain':'OUT_OF_DOMAIN','phase':'PHASE_MISMATCH','uncertified':'NONFINITE_BOUND','unsupported':'PROVIDER_UNSUPPORTED','unsupported_vapour':'PROVIDER_UNSUPPORTED'}
    assert caught.value.diagnostics[0]['code']==expected[failure]


def test_common_bdf_equilibrium_matches_both_independent_solvers(model):
    system=DerivedSystem(model);result=resolve_system(system)
    assert result['estado']=='resuelto'
    block=system.algebraic_block
    assert block.extent_proof['certified'] and block.last_certificate['certified']
    gas=ce.IdealGasPhase(SPECIES);A,_=ce.element_matrix(SPECIES)
    references=[solver(gas,[NU],[1,1,1,1],800,1e5,A)['moles'] for solver in (ce.solve_extents,ce.minimise_gibbs)]
    rows={r['id']:r['valores'] for r in result['series']}
    actual=np.array([rows['observable.'+qid][-1] for qid in model['motores']['equilibriumReactions']['volumes']['gas']['amountIds']])
    for expected in references:np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-9)
    assert max(abs(A@(actual-np.ones(4))))<1e-9
    Path('.tmp/f5-equilibrium-result.json').write_text(json.dumps(result),encoding='utf-8')


@pytest.mark.parametrize('failure',['stale','posed','liquid','thermal','box','partition','undo','units','fixed_species'])
def test_model_admission_rejects_incomplete_or_uncertified_constraints(model,failure):
    changed=copy.deepcopy(model);entry=changed['motores']['equilibriumReactions']['volumes']['gas'];selection=changed['motores']['derivedExecution']
    if failure=='stale':entry['anchor']='liquid'
    elif failure=='posed':
        entry['reactions'][0]['equationId']='thermodynamics.gas.G-euler';selection['algebraic'][0]['equationId']=entry['reactions'][0]['equationId']
    elif failure=='liquid':entry.update(provider='package',phaseId='liquido',standardState='pure_liquid_TP',anchor='liquid')
    elif failure=='thermal':selection['parameters'].pop(entry['temperatureId'])
    elif failure=='box':changed['datos']['extentlowerDataId']['declaracion']['texto']='-1'
    elif failure=='undo':changed['motores']['equationWorkbench']['cursor']-=1
    elif failure=='units':entry['pressureId']=entry['temperatureId']
    elif failure=='fixed_species':selection['initialValues'][entry['amountIds'][0]]='initial0'
    else:entry['referenceIds'][0]=entry['extentIds'][0]
    if failure!='stale':selection['sourceSignature']=source_signature(changed)
    with pytest.raises((LoweringError,ValueError)):DerivedSystem(changed)


def test_strict_declaration_unknown_keys_and_old_models_unchanged(model):
    from core.modelo.lector import ErrorModelo
    changed=copy.deepcopy(model);changed['motores']['equilibriumReactions']['extra']=True
    with pytest.raises(ErrorModelo):leer_modelo_comun(changed)
    from m1_acceptance import thermal_source
    old=thermal_source();assert leer_modelo_comun(old)==old


# '1٣' (Arabic-Indic three): both readers accept ASCII digits only (RA-1).
@pytest.mark.parametrize('coefficient',['1/0','01','-01','1/01','-0','1٣','1/٣','１'])
def test_stoichiometry_rejections_have_common_model_location(model,coefficient):
    from core.modelo.lector import ErrorModelo
    changed=copy.deepcopy(model)
    changed['motores']['equilibriumReactions']['volumes']['gas']['reactions'][0]['stoichiometry'][0]=coefficient
    with pytest.raises(ErrorModelo) as caught:leer_modelo_comun(changed)
    assert caught.value.ruta=='motores.equilibriumReactions'


def test_ammonia_wide_extent_box_has_certified_cover():
    proof=certify_extent(ce.IdealGasPhase(['7727-37-9','1333-74-0','7664-41-7']),
        [[-1,-3,2]],[[1,1],[3,3],[0,0]],[[.05,.9]],[700,700],[1e7,1e7],phase_id='vapor',standard_state='ideal_gas_P0')
    def leaves(node):
        assert node['certified']
        if 'split' not in node:
            assert node['determinantBounds'][0]>0
            return [node]
        split=node['split'];left,right=split['children'];axis=split['axis']
        assert left['extentBox'][axis]==[node['extentBox'][axis][0],split['point']]
        assert right['extentBox'][axis]==[split['point'],node['extentBox'][axis][1]]
        for i,box in enumerate(node['extentBox']):
            if i!=axis:assert left['extentBox'][i]==right['extentBox'][i]==box
        return leaves(left)+leaves(right)
    certified=leaves(proof)
    assert len(certified)>1
    assert sum(row['extentBox'][0][1]-row['extentBox'][0][0] for row in certified)==pytest.approx(.85)
    for xi in np.linspace(.05,.9,100):
        derivative=1/(1-xi)+9/(3-3*xi)+4/(2*xi)-4/(4-2*xi)
        leaf=next(row for row in certified if row['extentBox'][0][0]<=xi<=row['extentBox'][0][1])
        assert leaf['jacobianBounds'][0][0][0]<=derivative<=leaf['jacobianBounds'][0][0][1]


def test_certification_failure_names_owner_and_R_mismatch_is_specific(model):
    changed=copy.deepcopy(model);changed['datos']['extentlowerDataId']['declaracion']['texto']='-1'
    with pytest.raises(LoweringError) as caught:DerivedSystem(changed)
    assert caught.value.diagnostics[0]['path'].startswith('motores.equilibriumReactions.volumes.gas.')
    changed=copy.deepcopy(model);changed['datos']['R']['declaracion']['texto']='8.314'
    with pytest.raises(LoweringError) as caught:DerivedSystem(changed)
    assert caught.value.diagnostics[0]['code']=='reaction_gas_constant_mismatch'


def test_virtual_extent_is_a_Model_premise_not_a_Solve_datum(model):
    assert 'virtualExtent' not in model['motores']['derivedExecution']['parameters']
    assert 'variation' not in model['datos']
    assert any(op['kind']=='declare_domain' and op.get('symbol')=='virtualExtent' and op['domain']=='nonzero'
               for op in model['motores']['equationWorkbench']['operations'])
    system=DerivedSystem(model)
    assert any(row['kind']=='eliminated_coordinate_premise' for row in system.proof_conditions)


def test_uncertified_subdivision_leaf_rejects_the_whole_box(monkeypatch):
    public=ce.reaction_jacobian_bounds
    calls=[]
    def provider(*args,**kwargs):
        calls.append(args[2])
        if len(calls)>1:
            return {'certified':False,'diagnostics':[{'code':'NONFINITE_BOUND','path':'bounds.dg_dn','message':'Uncertified leaf'}]}
        return public(*args,**kwargs)
    monkeypatch.setattr(ce,'reaction_jacobian_bounds',provider)
    with pytest.raises(LoweringError) as caught:
        certify_extent(ce.IdealGasPhase(['7727-37-9','1333-74-0','7664-41-7']),
            [[-1,-3,2]],[[1,1],[3,3],[0,0]],[[.05,.9]],[700,700],[1e7,1e7],phase_id='vapor',standard_state='ideal_gas_P0')
    assert len(calls)==2
    assert caught.value.diagnostics[0]['code']=='NONFINITE_BOUND'
