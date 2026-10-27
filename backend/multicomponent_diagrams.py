"""
Multicomponent equilibrium diagrams (own protocol, revision 1): the ternary liquid-liquid diagram at fixed T and P
and the composition-line slice of any number of species. Types: docs/contratos/contratoDiagramasEquilibrio.ts
(section "Multicomponent diagrams"). Document: docs/engine/equilibrium-diagrams.md section 6c.

The service validates the request (every known rejection is a structured response with a path), builds the SAME
package the states use (core/mezclas.Sistema), runs core/ternary_liquid_liquid.py or core/composition_slices.py
and translates their results to component IDs. It never changes the package, drops a species or completes data.
"""

import hashlib
import json
import math

import numpy as np

from backend import motor_diagramas as md
from backend import motor_mezclas
from backend import motor_termodinamica as mt
from core import coexistencia_ll as ll
from core import composition_slices as cs
from core import diagramas_equilibrio as dg
from core import mezclas as mz
from core import ternary_liquid_liquid as tl

REVISION = 1
OPERATIONS = {"ternary_liquid_liquid": {"tracer": tl.TRAZADOR, "components": (3, 3)},
              "composition_line": {"tracer": cs.TRAZADOR, "components": (2, None)}}
FIELDS = {"revision", "requestId", "components", "model", "expectedModelFingerprint", "condition", "resolution",
          "pureData"}
REQUIRED = ("revision", "requestId", "components", "model", "condition", "resolution")
PLAIT_TOLERANCE = 1e-6            # the residual core/ternary_liquid_liquid.plait_point accepts

RESIDUAL_IDS = {"igualdad_mu": "mu_equality", "normalizacion": "normalization", "condicion_fija": "fixed_condition",
                "distincion_fases": "distinct_phases"}
RESIDUAL_SCALES = {"mu_equality": "max |mu_i^a - mu_i^b| / RT over species and phase pairs",
                   "normalization": "max |sum_i x_i - 1| over phases",
                   "fixed_condition": "relative to the slice's fixed condition",
                   "distinct_phases": "min over phase pairs of max_i |x_i^a - x_i^b|"}
CHECK_IDS = {"equilibrio": "equilibrium", "estabilidad": "stability", "reconstruccion_material": "material_reconstruction"}
KINDS = {"liquido": "liquid", "vapor": "vapor"}
STABILITY_METHOD = ("tangent-plane distance with the common mu: vapor by its analytic minimum, liquid trials on a "
                    "composition lattice with refinement of the lowest minima (not a proof of the global minimum)")


def capabilities():
    profiles = [{"id": k, "limitEvaluations": dg.PERFILES[k]["limiteEvaluaciones"],
                 "limitSeconds": dg.PERFILES[k]["limiteSegundos"], "ternaryLattice": tl.PROFILES[k]["lattice"],
                 "ternaryMaxStep": tl.PROFILES[k]["dsMax"], "lineBasePoints": cs.PROFILES[k]["puntosBase"],
                 "lineBisections": cs.PROFILES[k]["biseccion"], "muTolerance": tl.TOL_MU,
                 "stabilityTolerance": tl.TOL_TM} for k in ("exploratoria", "refinada")]
    packages = [{"model": {"id": c["id"], "version": c["version"]}, "componentsCAS": list(c["componentesCAS"]),
                 "domain": dict(c["dominio"])} for c in motor_mezclas.capacidades_mezcla()]
    return {"revision": REVISION, "operations": [
        {"id": "ternary_liquid_liquid", "route": "/motor/termodinamica/diagramas/ternary-liquid-liquid",
         "components": {"min": 3, "max": 3}, "tracer": dict(tl.TRAZADOR),
         "publishes": ["tie lines with certificates", "binodal branches (liquid-a and liquid-b sides)",
                       "plait point", "binary-edge pair", "liquid-liquid-vapor triangle"]},
        {"id": "composition_line", "route": "/motor/termodinamica/diagramas/composition-line",
         "components": {"min": 2, "max": None}, "tracer": dict(cs.TRAZADOR),
         "publishes": ["certified equilibrium rows along the line", "phase-set boundaries located by bisection"]}],
        "profiles": profiles, "packages": packages,
        "unsupported": [
            {"element": "three-liquid regions of a ternary diagram", "reason": "not traced; a composition-line slice "
             "does detect them"},
            {"element": "solid phases and SLE regions", "reason": "the mixture packages have no solid phase"},
            {"element": "agua-iapws95 and agua-iapws95-hielo-ih", "reason": "single component: their diagram is P-T"},
            {"element": "critical region and vapor above 5 bar", "reason": "excluded by the packages' domain"}]}


class _Reader:
    def __init__(self):
        self.diagnostics = []

    def add(self, status, code, path, message, ids=()):
        self.diagnostics.append({"code": code, "status": status, "path": path, "message": message,
                                 "componentIds": list(ids)})

    def statuses(self):
        return {d["status"] for d in self.diagnostics}


STATUS_ORDER = ("invalid", "unsupported", "incomplete")


def _empty(operation, rid, status, diagnostics, model=None, fingerprint=None):
    return {"revision": REVISION, "requestId": rid, "operation": operation, "status": status,
            "identity": {"model": model or {"id": "", "version": ""}, "modelFingerprint": fingerprint,
                         "querySignature": None, "tracer": dict(OPERATIONS[operation]["tracer"])},
            "condition": None, "diagnostics": diagnostics}


def _quantity(rd, v, path, mag):
    units = mt.UNIDADES[mag]
    if not isinstance(v, dict) or set(v) != {"valor", "unidad"}:
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", path, "Expected {valor, unidad}.")
        return None
    val, unit = v["valor"], v["unidad"]
    if val is None:
        rd.add("incomplete", "MOTOR_DIAG_DATO_INVALIDO", path + ".valor", "Unspecified value (null is not zero).")
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", path + ".valor", "Non-numeric or non-finite value.")
        return None
    if unit not in units:
        rd.add("invalid", "MOTOR_DIAG_UNIDAD", path + ".unidad",
               f"Unit {unit!r} is not a {mag} unit; use {', '.join(units)}.")
        return None
    f, d = units[unit]
    si = val * f + d
    if not si > 0:
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", path + ".valor", f"{mag} must be positive (absolute).")
        return None
    return si


def _read_common(operation, body, rd, extra_fields=()):
    """Validated (rid, ids, cas, model id, version, T, P, profile, expected fingerprint) or None."""
    rid = body.get("requestId") if isinstance(body, dict) and isinstance(body.get("requestId"), str) else ""
    if not isinstance(body, dict):
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "", "The body must be an object.")
        return rid, None
    for k in body:
        if k not in FIELDS | set(extra_fields):
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", k, f"Field not accepted: {k}.")
    for k in REQUIRED + tuple(extra_fields):
        if k not in body:
            rd.add("incomplete", "MOTOR_DIAG_DATO_INVALIDO", k, f"Missing {k}.")
    rev = body.get("revision")
    if "revision" in body and (isinstance(rev, bool) or rev != REVISION):
        rd.add("invalid", "MOTOR_DIAG_REVISION", "revision", f"Revision {rev!r} is not accepted; this is {REVISION}.")
    if "requestId" in body and (not isinstance(body["requestId"], str) or not body["requestId"]):
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "requestId", "Empty request identifier.")
    lo, hi = OPERATIONS[operation]["components"]
    comps, ids, cas = body.get("components"), [], []
    if "components" in body:
        if not isinstance(comps, list):
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "components", "Expected a list.")
            comps = []
        elif len(comps) < lo or (hi is not None and len(comps) > hi):
            want = f"exactly {lo}" if lo == hi else f"at least {lo}"
            rd.add("unsupported", "MOTOR_DIAG_COMPONENTES_NO_SOPORTADO", "components",
                   f"This operation needs {want} components; {len(comps)} were declared. No component is removed or "
                   "renormalized; another set of species is another explicit request.")
        for k, c in enumerate(comps):
            cid = c.get("id") if isinstance(c, dict) else None
            ca = (c.get("identidadQuimica") or {}).get("cas") if isinstance(c, dict) else None
            if isinstance(cid, bool) or not isinstance(cid, int) or cid < 1:
                rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", f"components.{k}.id", "A positive integer ID is required.")
                continue
            if not isinstance(ca, str) or not mt._cas_valido(ca):
                rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", f"components.{k}.identidadQuimica.cas",
                       "Chemical identity without a valid CAS: a name does not identify a model.", [cid])
                continue
            ids.append(cid)
            cas.append(ca)
        if len(set(ids)) != len(ids):
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "components", "Repeated component IDs.")
        if len(set(cas)) != len(cas):
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "components", "Two components with the same substance.")
    mod, mid, ver = body.get("model"), None, None
    if "model" in body:
        if not isinstance(mod, dict) or set(mod) != {"id", "version"}:
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "model", "Expected {id, version}.")
        else:
            mid, ver = mod["id"], mod["version"]
            if not isinstance(mid, str) or motor_mezclas.MODELOS.get(mid) != ver:
                rd.add("unsupported", "MOTOR_DIAG_PAQUETE_NO_DISPONIBLE", "model",
                       f"Package {mid!r} version {ver!r} does not publish multicomponent diagrams; see "
                       "/motor/termodinamica/diagramas/multicomponent/capabilities. It is not replaced by another.")
    cond, T, P = body.get("condition"), None, None
    if "condition" in body:
        if not isinstance(cond, dict) or set(cond) != {"T", "P"}:
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "condition", "Expected exactly {T, P}.")
        else:
            T = _quantity(rd, cond["T"], "condition.T", "T")
            P = _quantity(rd, cond["P"], "condition.P", "P")
    profile = body.get("resolution")
    if "resolution" in body and profile not in dg.PERFILES:
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "resolution", "Profile 'exploratoria' or 'refinada'.")
    expected = body.get("expectedModelFingerprint")
    if expected is not None and not isinstance(expected, str):
        rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "expectedModelFingerprint", "Expected text.")
    return rid, {"ids": ids, "cas": cas, "mid": mid, "ver": ver, "T": T, "P": P, "profile": profile,
                 "expected": expected}


def _system(operation, body, rid, q, rd):
    """The package's Sistema after the species, data, fingerprint and domain checks; or a rejection response."""
    model = {"id": q["mid"], "version": q["ver"]}
    cap = next(c for c in motor_mezclas.capacidades_mezcla() if c["id"] == q["mid"])
    groups = mz.PAQUETES[q["mid"]].liquido.startswith("unifac_")
    for cid, ca in zip(q["ids"], q["cas"]):
        # As in the binary service: a catalog species missing from a group-contribution package's list has no group
        # assignment, and the Sistema rejects it with its precise code.
        if ca not in cap["componentesCAS"] and not (groups and ca in motor_mezclas.md.especies_disponibles()):
            rd.add("unsupported", "MOTOR_DIAG_COMPONENTE_NO_SOPORTADO", "components",
                   f"Package {q['mid']} has no pure-component data for {ca}.", [cid])
    if rd.diagnostics:
        return None, _empty(operation, rid, "unsupported", rd.diagnostics, model)
    from core import catalogo
    try:
        subs = catalogo.leer_sustituciones(body.get("pureData"), "pureData", q["cas"])
    except catalogo.SustitucionRechazada as x:
        st = "invalid" if x.codigo == "SUSTITUCION_INVALIDA" else "unsupported"
        rd.add(st, f"MOTOR_DIAG_{x.codigo}", x.ruta, x.mensaje, q["ids"])
        return None, _empty(operation, rid, st, rd.diagnostics, model)
    try:
        sis = mz.Sistema(q["mid"], q["cas"], subs)
    except mz.FaltaParametro as x:
        rd.add("unsupported", f"MOTOR_DIAG_{x.codigo}", "components", str(x), q["ids"])
        return None, _empty(operation, rid, "unsupported", rd.diagnostics, model)
    fp = sis.huella()
    if q["expected"] is not None and q["expected"] != fp:
        rd.add("invalid", "MOTOR_DIAG_HUELLA_DISTINTA", "expectedModelFingerprint",
               f"The expected fingerprint does not match the current package ({fp}): its data or parameters changed; "
               "solve again before comparing.")
        return None, _empty(operation, rid, "invalid", rd.diagnostics, model, fp)
    try:
        sis.dominio(q["T"], q["P"])
    except mz.FueraDeAlcance as x:
        path = "condition.T" if x.datos.get("T_fuera") else "condition.P"
        rd.add("unsupported", "MOTOR_DIAG_FUERA_DE_DOMINIO", path,
               f"Outside the package's domain: T in [{sis.T_rango[0]:.6g}, {sis.T_rango[1]:.6g}] K and P in "
               f"[{mz.P_MIN:g}, {mz.P_MAX:g}] Pa (ideal vapor); nothing is extrapolated.", q["ids"])
        return None, _empty(operation, rid, "unsupported", rd.diagnostics, model, fp)
    return sis, None


def _signature(operation, q, fp, extra):
    data = {"operation": operation, "model": [q["mid"], q["ver"]], "fingerprint": fp, "cas": sorted(q["cas"]),
            "T": float(f"{q['T']:.12g}"), "P": float(f"{q['P']:.12g}"), "profile": q["profile"],
            "tracer": OPERATIONS[operation]["tracer"], **extra}
    return "sha256:" + hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _head(operation, rid, body, q, fp, signature, rd):
    return {"revision": REVISION, "requestId": rid, "operation": operation,
            "identity": {"model": {"id": q["mid"], "version": q["ver"]}, "modelFingerprint": fp,
                         "querySignature": signature, "tracer": dict(OPERATIONS[operation]["tracer"])},
            "condition": {"input": body["condition"], "T": float(q["T"]), "P": float(q["P"]),
                          "components": [{"id": i, "cas": c} for i, c in zip(q["ids"], q["cas"])],
                          "resolution": q["profile"]},
            "diagnostics": rd.diagnostics}


def _composition(ids, x):
    return {str(i): float(v) for i, v in zip(ids, x)}


def _certificate(c, ids, ids_of=None):
    """Core certificate -> contract certificate. ids_of maps the certificate's composition vector to component
    IDs (the binary-edge certificate is on two species)."""
    ids_of = ids_of or ids
    res = []
    for r in c["residuos"]:
        rid = RESIDUAL_IDS[r["id"]]
        res.append({"id": rid, "value": float(r["valor"]), "tolerance": float(r["tolerancia"]),
                    "scale": RESIDUAL_SCALES[rid], "status": "pass" if r["estado"] == "cumple" else "fail"})
    e = c["estabilidad"]
    st = {"status": "stable" if e["estado"] == "estable" else "unstable", "tmMinimum": float(e["tmMinimo"]),
          "tolerance": float(e["tolerancia"]), "candidates": [KINDS[k] for k in e["candidatas"]],
          "trials": int(e["pruebas"]), "method": STABILITY_METHOD}
    if "competidora" in e:
        k = e["competidora"]
        st["competitor"] = {"kind": KINDS[k["tipo"]], "composition": _composition(ids_of, k["composicion"]),
                            "tm": float(k["tm"])}
    return {"status": "pass" if c["estado"] == "cumple" else "fail", "residuals": res, "stability": st}


def _liquids(ids, xa, xb):
    return [{"id": "liquid-a", "kind": "liquid", "composition": _composition(ids, xa)},
            {"id": "liquid-b", "kind": "liquid", "composition": _composition(ids, xb)}]


# --- ternary liquid-liquid -----------------------------------------------------------------------------------
def ternary_liquid_liquid(body):
    op = "ternary_liquid_liquid"
    rd = _Reader()
    rid, q = _read_common(op, body, rd)
    if q is None or rd.statuses() & set(STATUS_ORDER):
        st = next(s for s in STATUS_ORDER if s in rd.statuses())
        return _empty(op, rid, st, rd.diagnostics, {"id": q["mid"], "version": q["ver"]} if q and q["mid"] else None)
    sis, rejected = _system(op, body, rid, q, rd)
    if rejected:
        return rejected
    fp = sis.huella()
    budget = dg._Presupuesto(dg.PERFILES[q["profile"]])
    branches_c = tl.trace(sis, q["T"], q["P"], tl.PROFILES[q["profile"]], spend=budget.gastar,
                          exhausted=lambda: budget.agotado)
    out = _head(op, rid, body, q, fp, _signature(op, q, fp, {}), rd)
    out.update(_publish_ternary(sis, q["ids"], q["T"], q["P"], branches_c, budget, q["mid"]))
    out["status"] = out.pop("_status")
    return out


def _publish_ternary(sis, ids, T, P, branches_c, budget, mid):
    branches, ties, special, incid = [], [], [], []
    for k, b in enumerate(branches_c, 1):
        bid = f"tl-{k}"
        tids = []
        for p in b.points:
            tid = f"{bid}-t{len(tids) + 1:04d}"
            tids.append(tid)
            ties.append({"id": tid, "branchId": bid, "phases": _liquids(ids, p["xa"], p["xb"]),
                         "certificate": _certificate(p["cert"], ids),
                         "origin": "flash_seed" if p["origen"] == "semilla_por_flash" else "continuation"})
        ends = []
        for side, e in zip(("start", "end"), b.ends):
            kind = e["tipo"]
            sid = f"tl-s{len(special) + 1:03d}"
            if kind == "pliegue":
                ok = e["residuo"] <= PLAIT_TOLERANCE and e["estable"]
                special.append({
                    "id": sid, "branchId": bid, "side": side, "kind": "plait_point",
                    "composition": _composition(ids, e["x"]),
                    "certificate": {"status": "pass" if ok else "fail", "residuals": [
                        {"id": "criticality", "value": float(e["residuo"]), "tolerance": PLAIT_TOLERANCE,
                         "scale": "max(|det H| x0 x1 x2, |u^T (dH/du) u| (x0 x1 x2)^1.5), H the Hessian of g/RT in "
                                  "(x0, x1) from central differences of (mu_i - mu_2)/RT, u its null vector",
                         "status": "pass" if e["residuo"] <= PLAIT_TOLERANCE else "fail"}],
                        "stability": {"status": "stable" if e["estable"] else "unstable",
                                      "tmOtherPhase": float(e["tmOtraFase"]) if math.isfinite(e["tmOtraFase"]) else None,
                                      "tolerance": tl.TOL_TM, "method": STABILITY_METHOD}},
                    "description": "plait point: the two liquids merge; the spinodal det H = 0 and the critical "
                                   "cubic form along H's null vector, solved in logit coordinates"})
                ends.append({"side": side, "specialPointId": sid})
            elif kind == "borde_binario":
                keep = [i for i in range(3) if i != e["especieAusente"]]
                special.append({
                    "id": sid, "branchId": bid, "side": side, "kind": "binary_edge",
                    "absentComponentId": ids[e["especieAusente"]],
                    "phases": _liquids(ids, e["xa"], e["xb"]),
                    "certificate": _certificate(e["cert"], ids, [ids[i] for i in keep]),
                    "description": "binary edge: one species vanishes from both liquids; the end is the binary pair "
                                   "of the other two species solved directly at the same T and P and certified"})
                ends.append({"side": side, "specialPointId": sid})
            elif kind == "tres_fases":
                special.append({
                    "id": sid, "branchId": bid, "side": side, "kind": "three_phase",
                    "phases": _liquids(ids, e["xa"], e["xb"]) +
                              [{"id": "vapor", "kind": "vapor", "composition": _composition(ids, e["y"])}],
                    "certificate": _certificate(e["cert"], ids),
                    "description": "liquid-liquid-vapor triangle: a vapor trial lowered the tangent plane; the three "
                                   "phases solve the six mu equalities and are certified"})
                ends.append({"side": side, "specialPointId": sid})
            else:
                iid = f"tl-i{len(incid) + 1:03d}"
                competitor = e.get("competidora")
                incid.append({"id": iid, "branchId": bid, "side": side,
                              "kind": {"presupuesto": "budget", "inestable": "competing_phase"}.get(kind,
                                                                                                  "no_convergence"),
                              "cause": str(e.get("mensaje", kind))[:400] + (
                                  f" (competing {KINDS[competitor['tipo']]}, tm = {competitor['tm']:.3g})"
                                  if competitor else ""),
                              "action": "the branch is published up to its last certified tie line; no extrapolation"})
                ends.append({"side": side, "incidenceId": iid})
        branches.append({"id": bid, "tieLineIds": tids, "ends": ends})
    if budget.agotado and not any(i["kind"] == "budget" for i in incid):
        incid.append({"id": f"tl-i{len(incid) + 1:03d}", "branchId": None, "side": None, "kind": "budget",
                      "cause": "evaluation or time budget exhausted during the seed search",
                      "action": "what was computed is published"})
    pair = md._pares(mid)[2]
    status = "partial" if incid else ("complete" if branches else "no_coexistence")
    return {"_status": status, "branches": branches, "tieLines": ties, "specialPoints": special,
            "incidences": incid, "budget": _budget(budget),
            "evidence": ({"combination": "liquido_liquido", "level": pair["evidencia"], "reason": pair["motivo"]}
                         if pair else None),
            "method": ("Seeds from the package's certified TP flash on a ternary lattice pulled 2 % inside the "
                       "simplex, only where the tangent-plane test of a single liquid finds another liquid. Each tie "
                       "line (logit coordinates of both liquids) solves the package's mu equality between the two "
                       "liquids and is followed by pseudo-arclength continuation in both directions. Every tie line is "
                       "certified (mu equality <= 1e-10 RT, normalization, distinct liquids and the tangent plane with "
                       "the common mu against vapor and liquid trials). Branch ends: plait point, binary edge, "
                       "liquid-liquid-vapor triangle, budget or no convergence. Lines between consecutive tie-line "
                       "ends are visual interpolation of certified points.")}


def _budget(b):
    r = b.resumen()
    return {"evaluations": r["evaluaciones"], "limitEvaluations": r["limiteEvaluaciones"], "seconds": r["segundos"],
            "limitSeconds": r["limiteSegundos"]}


# --- composition line ----------------------------------------------------------------------------------------
def composition_line(body):
    op = "composition_line"
    rd = _Reader()
    rid, q = _read_common(op, body, rd, extra_fields=("line",))
    ends = None
    if q is not None and "line" in body:
        line = body["line"]
        if not isinstance(line, dict) or set(line) != {"start", "end"}:
            rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", "line", "Expected exactly {start, end}.")
        elif q["ids"]:
            keys = {str(i) for i in q["ids"]}
            ends = []
            for name in ("start", "end"):
                z = line[name]
                if not isinstance(z, dict) or set(z) != keys or not all(
                        not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in z.values()):
                    rd.add("invalid", "MOTOR_DIAG_DATO_INVALIDO", f"line.{name}",
                           "One finite mole fraction for every declared component ID (no species is dropped).")
                    ends = None
                elif ends is not None:
                    ends.append([float(z[str(i)]) for i in q["ids"]])
    if q is None or rd.statuses() & set(STATUS_ORDER):
        st = next(s for s in STATUS_ORDER if s in rd.statuses())
        return _empty(op, rid, st, rd.diagnostics, {"id": q["mid"], "version": q["ver"]} if q and q["mid"] else None)
    sis, rejected = _system(op, body, rid, q, rd)
    if rejected:
        return rejected
    fp = sis.huella()
    budget = dg._Presupuesto(dg.PERFILES[q["profile"]])
    try:
        tr = cs.trace(sis, q["T"], q["P"], ends[0], ends[1], cs.PROFILES[q["profile"]], spend=budget.gastar,
                      exhausted=lambda: budget.agotado)
    except cs.SliceRejected as x:
        st = "invalid" if x.motivo == "invalido" else "unsupported"
        rd.add(st, "MOTOR_DIAG_DATO_INVALIDO" if st == "invalid" else "MOTOR_DIAG_COMPONENTE_AUSENTE", "line",
               {"invalido": "Each end needs non-negative mole fractions of every declared component that sum to 1 "
                            "(within 1e-12).",
                "no_soportado": "A component is absent from both ends. It is not dropped silently: declare a line of "
                                "the other components instead."}[x.motivo], q["ids"])
        return _empty(op, rid, st, rd.diagnostics, {"id": q["mid"], "version": q["ver"]}, fp)
    by_cas = sorted(range(len(q["cas"])), key=lambda i: q["cas"][i])
    sig = _signature(op, q, fp, {"line": [[float(f"{e[i]:.12g}") for i in by_cas] for e in ends]})
    out = _head(op, rid, body, q, fp, sig, rd)
    out["condition"]["line"] = {"start": _composition(q["ids"], ends[0]), "end": _composition(q["ids"], ends[1])}
    out.update(_publish_line(q["ids"], tr, budget))
    out["status"] = out.pop("_status")
    return out


def _row(ids, row, rid):
    tm = row["tmMinimo"]
    return {"id": rid, "l": row["l"], "feed": _composition(ids, row["z"]),
            "phases": [{"kind": KINDS[f["tipo"]], "fraction": f["fraccion"], "composition": _composition(ids, f["x"])}
                       for f in row["fases"]],
            "phaseSet": [KINDS[k] for k in row["firma"]], "certified": bool(row["certificado"]),
            "checks": [{"id": CHECK_IDS.get(k, k), "residual": v[0], "tolerance": v[1]}
                       for k, v in row["verificaciones"].items()],
            "tmMinimum": float(tm) if math.isfinite(tm) else None}


def _publish_line(ids, tr, budget):
    rows = [_row(ids, r, f"r{k + 1:04d}") for k, r in enumerate(tr["filas"])]
    bounds = [{"id": f"b{k + 1:03d}", "lInterval": b["l"], "before": _row(ids, b["antes"], f"b{k + 1:03d}-before"),
               "after": _row(ids, b["despues"], f"b{k + 1:03d}-after")} for k, b in enumerate(tr["fronteras"])]
    fails = [{"l": f["l"], "reason": f["motivo"], "message": f["mensaje"]} for f in tr["fallos"]]
    complete = (tr["finalizacion"] == "recorrido_completo" and not fails and all(r["certified"] for r in rows)
                and all(b["before"]["certified"] and b["after"]["certified"] for b in bounds))
    return {"_status": "complete" if complete else "partial", "rows": rows, "boundaries": bounds, "failures": fails,
            "completion": "complete_walk" if tr["finalizacion"] == "recorrido_completo" else "budget",
            "budget": _budget(budget),
            "method": ("Feeds z(l) = (1 - l) z_start + l z_end on a Chebyshev grid of l, each closed by the package's "
                       "certified TP equilibrium seeded with the previous state (a fast Newton on the previous phase "
                       "set followed by the full stability test, or the full TP operation when the phase set "
                       "changes). Where the phase set changes between neighbours, the boundary is bisected; it lies "
                       "inside lInterval, and the incipient phase of the side with more phases is the other end of a "
                       "tie line through the boundary feed. Every species is kept. Points are not joined across a "
                       "boundary.")}
