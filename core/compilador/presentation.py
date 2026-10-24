"""Read-only mathematical handoffs. No integration or equilibrium initialization."""
from core.balances import material_derivation as material
from core.balances import energy_derivation as energy
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun


def symbolic_formulation_summary(draft):
    """Carry an unbound Model graph into Transform without inventing species."""
    from core.modelo.equation_workbench import fundamental_report
    from core.modelo.operation_journal import JournalError
    report=fundamental_report(draft)
    if report.get('replay'):
        raise JournalError('The saved equation operations no longer match their source. Review Model before selecting a Transform formulation.')
    families=[]
    keys={'matter':'materialJournal','energy':'energyJournal','momentum':'momentumJournal','thermodynamics':'thermodynamicJournal'}
    for family in ('matter','energy','momentum','thermodynamics'):
        rows=[row for row in report['equations'] if row['family']==family and (row['current'] or row['id'].startswith('operation.'))]
        families.append({'id':family,'volumes':[{'volumeId':'dominio','status':'recorded' if keys[family] in draft else 'unrecorded',
                                               'steps':rows,'note':'Symbolic formulation with unbound component index i; numerical execution remains blocked until components and supported lowering are declared.'}]})
    return {'format':'rage.formulation-summary','version':1,'modelId':report['modelId'],'families':families}


def compiled_balance_equations(model):
    """Symbolic display of the admitted assembly's actual oriented RHS terms."""
    def label(value):
        escapes = {"\\": r"\backslash ", "_": r"\_", "{": r"\{", "}": r"\}", "%": r"\%", "#": r"\#", "&": r"\&", "$": r"\$", "^": r"\^{}", "~": r"\~{}"}
        return r"\mathrm{" + "".join(escapes.get(char, char) for char in str(value)) + "}"

    def oriented(items, owner, term):
        pieces = []
        for item in items:
            sign = int(item['hasta'] == owner) - int(item['desde'] == owner)
            if sign:
                pieces.append(('+' if sign > 0 else '-') + term(item))
        return ''.join(pieces).lstrip('+') or '0'

    rows = []
    for volume in model['volumenes']:
        owner = volume['id']
        v = label(owner)
        for component in volume['componenteIds']:
            rhs = oriented([s for s in model['corrientes'] if component in s['componenteIds']], owner,
                           lambda s: rf"\dot n_{{{label(s['id'])}}}x_{{{label(s['id'])},{component}}}")
            rows.append({'id': f'materia.{owner}.{component}', 'family': 'Matter',
                         'latex': rf"\frac{{dn_{{{v},{component}}}}}{{dt}}={rhs}"})
        energy = 'U' if volume['frontera']['tipo'] == 'rigida' else 'H'
        stream = oriented(model['corrientes'], owner, lambda s: rf"\dot n_{{{label(s['id'])}}}h_{{{label(s['id'])}}}")
        heat = oriented(model['intercambios'], owner, lambda q: rf"\dot Q_{{{label(q['id'])}}}")
        terms = [term for term in (stream, heat) if term != '0']
        if energy == 'H':
            terms.append(rf"V_{{{v}}}\frac{{dP_{{{v}}}}}{{dt}}")
        rhs = '+'.join(terms).replace('+-', '-') or '0'
        rows.append({'id': f'energia.{owner}', 'family': 'Energy', 'latex': rf"\frac{{d{energy}_{{{v}}}}}{{dt}}={rhs}"})
        if energy == 'H':
            rows.append({'id': f'enthalpy.{owner}', 'family': 'Thermodynamics', 'latex': rf"H_{{{v}}}=U_{{{v}}}+P_{{{v}}}V_{{{v}}}"})
        rows.append({'id': f'closure.{owner}', 'family': 'Thermodynamics', 'latex':
                     rf"(\mathbf n_{{{v}}},U_{{{v}}},V_{{{v}}})\longmapsto(T_{{{v}}},P_{{{v}}},\{{n_k,\mathbf x^k\}})" if energy == 'U' else
                     rf"(\mathbf n_{{{v}}},H_{{{v}}},P_{{{v}}})\longmapsto(T_{{{v}}},V_{{{v}}},\{{n_k,\mathbf x^k\}})"})
    return rows


def formulation_summary(model):
    model = leer_modelo_comun(model)
    from core.balances import momentum_derivation as momentum
    from core.modelo.equation_workbench import describe
    for module in (material, energy, thermodynamics, momentum):
        module.validate_model_journal(model)
    development=describe(model)
    families = []
    for family, key, module in (("matter", "materialDerivation", material),
                                ("energy", "energyDerivation", energy),
                                ("thermodynamics", "thermodynamicDerivation", thermodynamics)):
        rows = []
        journal = model["motores"].get(key)
        for volume in model["volumenes"]:
            owner = volume["id"]
            active = family == "thermodynamics" or volume["balances"]["materia" if family == "matter" else "energia"]
            if not active:
                continue
            if journal is None or owner not in journal["volumes"]:
                rows.append({"volumeId": owner, "status": "unrecorded", "steps": [],
                             "note": "No replayable deduction is recorded for this family. Review Model before treating it as a derived formulation."})
                continue
            selected=[row for row in development['equations'] if row['ownerId']==owner and row['family']==family and row['current'] and not row['id'].startswith('operation.')]
            entry=journal['volumes'][owner]
            count = entry.get('cursor',len(entry['operations']))
            note = f"{count} recorded {'operation' if count == 1 else 'operations'} replayed against the current physical definition."
            if family == 'matter':
                note += ' Mass-form deduction; molar execution uses the equivalent relation m_i = M_i n_i.'
            rows.append({"volumeId": owner, "status": "recorded", "steps": selected, "note": note})
        families.append({"id": family, "volumes": rows})
    momentum_rows = []
    for volume in model["volumenes"]:
        if not volume["balances"]["momento"]:
            continue
        owner = volume["id"]
        journal = model["motores"].get("momentumDerivation")
        if journal is None or owner not in journal["volumes"]:
            momentum_rows.append({"volumeId": owner, "status": "unrecorded", "steps": [], "note": "Start the momentum journal explicitly from Cauchy conservation in Model. Coupled dynamic execution is not connected."})
            continue
        selected=[row for row in development['equations'] if row['ownerId']==owner and row['family']=='momentum' and row['current'] and not row['id'].startswith('operation.')]
        momentum_rows.append({"volumeId": owner, "status": "recorded", "steps": selected, "note": "Cauchy/Navier–Stokes reductions; the constant-density hydraulic compiler checks the selected path, medium and boundary roles in Solve." if model['motores'].get('hydraulicNetwork') else "Cauchy/Navier–Stokes and recorded control-volume reductions. Model deduction only; its dynamic compiler is pending."})
    families.insert(2, {"id": "momentum", "volumes": momentum_rows})
    if model['motores'].get('equationWorkbench',{}).get('cursor'):
        for family in families:
            consequences=[row for row in development['equations'] if row['family']==family['id'] and row['id'].startswith('operation.')]
            if consequences:family['volumes'].append({'volumeId':'system','status':'recorded','steps':consequences,'note':'Replayed equation operations. Dependent consequences retain their physical premises; declared relations require an admitted compiler.'})
    from core.modelo.dynamic_definition import describe_definition
    return {"format": "rage.formulation-summary", "version": 1, "modelId": model["id"], "families": families, "dynamicFormulation": describe_definition(model)}


def solution_strategy(report, model=None):
    """Capabilities of the compiler branch that already accepted this problem."""
    nested = report["closureStrategy"] == "nested_equilibrium"
    methods = [{"id": "RK45", "available": True, "reason": "Adaptive Dormand–Prince 5(4) integration of the retained differential states."}]
    methods.append({"id": "BDF", "available": not nested,
                    "reason": "Not connected to this nested-equilibrium compiler." if nested else "Implicit variable-order integration; Newton iterations use a numerical Jacobian."})
    steps = [
        {"id": "initialization", "title": "Initialize the same formulation", "description": "Read declared units in SI, replay deductions and construct compatible initial states. Missing data or unsupported constraints block execution.",
         "latex": r"\mathbf y(t_0)=\mathbf y_0"},
    ]
    if nested:
        steps.extend([
            {"id": "partition", "title": "Separate integrated quantities from local state unknowns", "description": "Integrate component amounts and U (rigid volume) or H (prescribed pressure). Temperature, pressure or volume, and phase amounts are recovered by the local thermodynamic closure.",
             "latex": r"\mathbf y=(\{n_{v,i}\},\{E_v\}),\quad E_v=\begin{cases}U_v&UV\\H_v&PH\end{cases},\qquad\mathbf z_v=\begin{cases}(T_v,P_v,\{n_k,\mathbf x^k\})&UV\\(T_v,V_v,\{n_k,\mathbf x^k\})&PH\end{cases}"},
            {"id": "closure", "title": "Solve equilibrium inside every RHS evaluation", "description": "For a trial state, solve UV or PH with the selected property package, phase policy and candidate-phase stability search. Evaluate each stream from its actual donor; use its composition and enthalpy in the balances.",
             "latex": r"\mathbf R_{\mathrm{thermo}}(t,\mathbf y,\mathbf z)=\mathbf0,\qquad \dot{\mathbf y}=\mathbf f(t,\mathbf y,\mathbf z)"},
            {"id": "balances", "title": "Assemble the conserved-quantity RHS", "description": "The same oriented streams couple matter and energy. For prescribed pressure retain V dP/dt; rigid volumes use internal energy without boundary-volume work.",
             "latex": r"\dot n_{v,i}=\sum_s B_{vs}\dot n_s x_{s,i},\quad \dot E_v=\sum_s B_{vs}\dot n_s h_s+\sum_q B_{vq}\dot Q_q+\begin{cases}0&E_v=U_v\\V_v\dot P_v&E_v=H_v\end{cases}"},
        ])
        packages = {p['modelo']['id'] for p in (model or {}).get('termodinamica', {}).get('paquetes', [])}
        if packages and packages != {'agua-iapws95'}:
            steps[2]['description'] += ' Mixture closures use seeded Newton iteration, full-flash fallback and bracketed searches; the full mixture flash minimizes Gibbs energy with SLSQP and refines phase chemical-potential equality with Newton. Stability uses a finite candidate search, not a universal global-minimum proof.'
    else:
        steps.append({"id": "rhs", "title": "Evaluate the compiled differential equations", "description": "Use the generated or explicitly declared RHS and its constitutive assumptions. Selected scaling is compiled first; physical variables are reconstructed through the saved inverse map.",
                      "latex": r"\dot{\mathbf y}=\mathbf f(t,\mathbf y),\qquad \mathbf y(t_0)=\mathbf y_0"})
    steps.append({"id": "time-step", "title": f"Advance with {report['method']}",
                  "description": "Adaptive embedded stages estimate local error and accept or reject steps. No global linear solve matrix is assembled." if report["method"] == "RK45" else "Solve the implicit multistep residual with Newton iterations. The numerical Jacobian belongs to this time-step solve; it is not the list of physical equations.",
                  "latex": r"\mathbf k_j=\mathbf f(t_n+c_jh,\mathbf y_n+h\sum_{l<j}a_{jl}\mathbf k_l),\quad\mathbf y_{n+1}=\mathbf y_n+h\sum_j b_j\mathbf k_j" if report["method"] == "RK45" else r"\mathbf r(\mathbf y_{n+1})=\sum_{j=0}^q\alpha_j\mathbf y_{n+1-j}-h\mathbf f(t_{n+1},\mathbf y_{n+1})=\mathbf0,\quad J_r=\alpha_0 I-hJ_f"})
    if nested:
        steps.append({"id": "events", "title": "Locate phase events and restart consistently", "description": "A phase appearance or disappearance triggers event localization and consistent local closure. The conservation laws remain the same.", "latex": r"t_e:\ \mathcal P(t_e^-)\ne\mathcal P(t_e^+)"})
    steps.append({"id": "verification", "title": "Reconstruct and verify Results", "description": "Publish the trajectory with conservation residuals and available closure, stability and second-law checks. Numerical convergence and physical certification are separate outcomes.", "latex": r"\Delta\mathbf y-\int_{t_0}^{t_f}\mathbf f\,dt=\mathbf r_{\mathrm{balance}}"})
    return {"methods": methods, "steps": steps, "scope": "Executable plan, not a transcript of Newton iterations. General DAE, steady-state and spatial assembly require their own supported compiler paths."}
