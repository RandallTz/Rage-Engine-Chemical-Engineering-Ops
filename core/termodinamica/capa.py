"""
La termodinámica siempre presente, como capa del modelo común.

Cada volumen con cierre de equilibrio tiene un conjunto FIJO de fases
candidatas, decidido por su paquete y no por su estado:

  solución ideal (g^E = 0):         vapor-1, liquido-1
  modelos de actividad (NRTL, UNIFAC): vapor-1, liquido-1, liquido-2

Para cada candidata k, en cualquier estado, se publican las mismas
magnitudes: cantidad n_k >= 0 (fracción beta_k), composición (la de la fase
o, si no está, la de la fase incipiente) y la distancia al plano tangente
mínima tm_k >= 0 (adimensional, por RT y mol de fase de prueba). El cierre
cumple, fase por fase, la complementariedad

    beta_k >= 0,   tm_k >= 0,   beta_k * tm_k = 0

Un líquido subenfriado tiene beta_vapor = 0 y tm_vapor > 0: las ecuaciones
del vapor están y no arrojan nada. En el punto de burbuja tm_vapor llega a
0 y beta_vapor empieza a crecer. Las ecuaciones no cambian.

No duplica la física:
  - paquetes de mezcla: core/mezclas (equilibrio por minimización de G y
    prueba de estabilidad del propio paquete);
  - agua pura (agua-iapws95): core/agua_iapws95 (evaluaciones PH, UV y TP
    con su prueba de estabilidad). Para una sustancia pura, tm de la fase
    ausente es la distancia al plano tangente de Helmholtz a T fija sobre la
    otra rama de la EOS, en su mínimo rho_m, por RT y por unidad de masa de
    la fase de prueba: tm = TPD(rho_m) / (rho_m R T). Es la misma escala que
    la de las mezclas y se reduce a (g_k(T, P) - g*) / RT cuando la rama tiene
    raíz a la P del estado.
"""

import math

import numpy as np

from core import agua_iapws95 as agua
from core import mezclas as mz

TOL_PRESENTE = mz.N_AUSENTE         # fase con n_k / n por debajo: ausente (la misma regla del paquete)
TOL_IGUAL = 1e-5                     # composición de prueba igual a una fase presente


class NoSoportado(Exception):
    pass


def _volumen(modelo, vid):
    v = next((x for x in modelo["volumenes"] if x["id"] == vid), None)
    if v is None:
        raise KeyError(f"volumen {vid!r} inexistente")
    t = v["termodinamica"]
    if t["tipo"] != "equilibrio":
        raise NoSoportado(f"el volumen {vid} declara su estado como supuesto ({t['supuesto']}): no hay cierre que evaluar")
    paq = next(p for p in modelo["termodinamica"]["paquetes"] if p["id"] == t["paqueteId"])
    return v, paq


AGUA = "agua-iapws95"
CUBICO = "peng-robinson-vdw1f"      # F8b mixture EOS: core/termodinamica/cubic_eos.py (k_ij = 0 through the layer)
PSRK = "psrk-unifac"                 # F8b PSRK: SRK with the UNIFAC (PSRK table) g^E mixing rule, core/termodinamica/psrk.py
EOS_PAQUETES = (CUBICO, PSRK)        # one residual Helmholtz function for both phases: the same closure serves both


def _cas(modelo, v):
    comps = {c["id"]: c for c in modelo["componentes"]}
    return [comps[i]["identidadQuimica"]["cas"] for i in v["componenteIds"]]


def _sistema(modelo, v, paq):
    pid = paq["modelo"]["id"]
    if pid not in mz.PAQUETES:
        raise NoSoportado(f"el paquete {pid} todavía no está envuelto por la capa (solo paquetes de mezcla)")
    comps = {c["id"]: c for c in modelo["componentes"]}
    cas = [comps[i]["identidadQuimica"]["cas"] for i in v["componenteIds"]]
    from core import catalogo, unifac
    try:
        sust = catalogo.leer_sustituciones(paq["datosPuros"], "datosPuros", set(cas)) if paq.get("datosPuros") else None
        return mz.Sistema(pid, cas, sustituciones=sust)
    except (mz.FaltaParametro, mz.FueraDeAlcance, unifac.FaltaDatoUNIFAC, catalogo.SustitucionRechazada) as e:
        # Un dato que el paquete no tiene es un rechazo con su motivo, nunca un valor por omisión.
        raise NoSoportado(f"paquete {pid} en el volumen {v['id']}: {e}") from e


def candidatas(modelo, vid):
    v, paq = _volumen(modelo, vid)
    if paq["modelo"]["id"] == AGUA:
        if _cas(modelo, v) != [agua.CAS]:
            raise NoSoportado("el paquete agua-iapws95 describe agua pura: el volumen debe tener solo agua (7732-18-5)")
        return ["vapor-1", "liquido-1"]
    if paq["modelo"]["id"] in EOS_PAQUETES:
        return ["vapor-1", "liquido-1"]     # two-phase package; a third phase is rejected, never published
    liquido = mz.PAQUETES[paq["modelo"]["id"]].liquido if paq["modelo"]["id"] in mz.PAQUETES else None
    if liquido is None:
        raise NoSoportado(f"el paquete {paq['modelo']['id']} todavía no está envuelto por la capa")
    ids = ["vapor-1", "liquido-1"]
    if liquido != "ideal" and len(v["componenteIds"]) > 1:
        ids.append("liquido-2")     # una solución ideal es siempre estable frente a separarse en dos líquidos
    return ids


def variables(modelo):
    """Variables de estado de cada volumen con cierre de equilibrio: las mismas en cualquier estado."""
    out = []
    for v in modelo["volumenes"]:
        if v["termodinamica"]["tipo"] != "equilibrio":
            continue
        p = f"volumen.{v['id']}"
        out += [f"{p}.T", f"{p}.P", f"{p}.V"]
        for k in candidatas(modelo, v["id"]):
            out += [f"{p}.fase.{k}.n"] + [f"{p}.fase.{k}.x.{c}" for c in v["componenteIds"]] + [f"{p}.fase.{k}.tm"]
    return out


def cierre(modelo, vid, n, especificacion):
    """Estado del volumen con todas sus fases candidatas.

    n: {componenteId: mol}. especificacion: ("PH", P [Pa], H [J]) | ("UV", U [J], V [m3]) | ("TP", T [K], P [Pa]).
    """
    v, paq = _volumen(modelo, vid)
    if paq["modelo"]["id"] == AGUA:
        return _cierre_agua(modelo, v, n, especificacion)
    if paq["modelo"]["id"] in EOS_PAQUETES:
        return _cierre_cubico(modelo, v, n, especificacion)
    sis = _sistema(modelo, v, paq)
    nv = np.array([float(n[c] if c in n else n[str(c)]) for c in v["componenteIds"]])
    tipo = especificacion[0]
    if tipo == "PH":
        e = sis.equilibrio_PH(especificacion[1], especificacion[2], nv)
    elif tipo == "UV":
        e = sis.equilibrio_UV(especificacion[1], especificacion[2], nv)
    elif tipo == "TP":
        e = sis.equilibrio_TP(especificacion[1], especificacion[2], nv)
    else:
        raise ValueError(f"especificación no admitida: {tipo}")
    ntot = float(nv.sum())
    idx = [i for i in range(len(nv)) if nv[i] > 0]
    presentes = {f.id: f for f in e.fases if f.n > TOL_PRESENTE * ntot}
    ref = next(iter(presentes.values()))
    mu_ref = ref.mu[idx]
    pruebas = sis.prueba_estabilidad(e.T, e.P, mu_ref, idx, incluir_vapor=True)
    ya = [(f.tipo, f.x[idx]) for f in presentes.values()]
    nuevas = mz._candidatas_nuevas(pruebas, ya, tol=TOL_IGUAL)
    ids_c = [c for c in v["componenteIds"]]
    fases = []
    for k in candidatas(modelo, vid):
        tipo_k = "vapor" if k.startswith("vapor") else "liquido"
        f = presentes.get(k)
        if f is not None:
            # Presente: tm = 0 por la igualdad de potenciales (residuo del propio paquete en verificaciones).
            comp = {c: float(f.x[i]) for i, c in enumerate(ids_c)}
            fases.append({"id": k, "tipo": tipo_k, "presente": True, "n": float(f.n), "beta": float(f.n) / ntot,
                          "composicion": comp, "tm": 0.0})
            continue
        cand = [p for p in nuevas if p[0] == tipo_k]
        if cand:
            w, tm = min(((p[1], p[2]) for p in cand), key=lambda z: z[1])
            comp = {c: 0.0 for c in ids_c}
            for j, i in enumerate(idx):
                comp[ids_c[i]] = float(w[j])
            fases.append({"id": k, "tipo": tipo_k, "presente": False, "n": 0.0, "beta": 0.0,
                          "composicionIncipiente": comp, "tm": float(tm)})
        else:
            # Ningún mínimo de esta clase distinto de las fases presentes: la candidata no puede aparecer aquí.
            fases.append({"id": k, "tipo": tipo_k, "presente": False, "n": 0.0, "beta": 0.0,
                          "composicionIncipiente": None, "tm": None})
    resid = 0.0
    for f in fases:
        if f["tm"] is not None:
            resid = max(resid, abs(f["beta"] * f["tm"]), max(0.0, -f["tm"]), max(0.0, -f["beta"]))
    return {"volumenId": vid, "especificacion": tipo, "T": float(e.T), "P": float(e.P), "V": float(e.V),
            "H": float(e.H), "U": float(e.U), "fases": fases, "complementariedad": resid,
            "presentes": [f["id"] for f in fases if f["presente"]],
            "verificaciones": {k: list(x) for k, x in e.verificaciones.items()}}


def _cierre_agua(modelo, v, n, especificacion):
    ids = candidatas(modelo, v["id"])
    c = v["componenteIds"][0]
    nmol = float(n[c] if c in n else n[str(c)])
    m = nmol * agua.M
    tipo = especificacion[0]
    if tipo == "PH":
        e = agua.evaluar_PH(especificacion[1], especificacion[2] / m)
    elif tipo == "UV":
        e = agua.evaluar_UV(especificacion[1] / m, especificacion[2] / m)
    elif tipo == "TP":
        x = agua.evaluar_TP(especificacion[1], especificacion[2])
        e = agua.EstadoEquilibrio(especificacion="TP", T=especificacion[1], P=especificacion[2],
                                  fases=(agua.FaseCalculada(x.tipo, x.regimen, 1.0, x.propiedades),),
                                  u=x.propiedades.u, h=x.propiedades.h, v=x.propiedades.v, s=x.propiedades.s,
                                  cp=x.propiedades.cp, cv=x.propiedades.cv, coexistencia=None, frontera=False,
                                  estabilidad=(x.estabilidad,), saturacion_rama=x.saturacion, residuos={},
                                  residuo_derivadas=x.residuo_derivadas, unicidad="TP")
    else:
        raise ValueError(f"especificación no admitida: {tipo}")
    # 'fluido' por debajo de P_c ya llega como 'vapor'; por encima de P_c es la candidata gaseosa (supercrítico).
    presentes = {}
    for f in e.fases:
        if f.fraccion > TOL_PRESENTE:
            presentes["liquido-1" if f.tipo == "liquido" else "vapor-1"] = f
    tm_ausente = None
    if len(presentes) == 1 and getattr(e, "frontera", False):
        # En la curva de saturación con una sola fase (q = 0 o 1): la otra es incipiente, tm = 0 con beta = 0.
        tm_ausente = 0.0
    elif len(presentes) == 1 and e.estabilidad:
        est = e.estabilidad[0]
        if est.margen is not None and est.rho_margen:
            # margen = TPD(rho_m) / P*: se pasa a TPD / (rho_m R T), por RT y masa de la fase de prueba
            tm_ausente = float(est.margen * e.P / (est.rho_margen * agua.R * e.T))
    fases = []
    for k in ids:
        tipo_k = "vapor" if k.startswith("vapor") else "liquido"
        f = presentes.get(k)
        if f is not None:
            fase = {"id": k, "tipo": tipo_k, "presente": True, "n": nmol * f.fraccion, "beta": float(f.fraccion),
                    "composicion": {c: 1.0}, "tm": 0.0}
            if f.regimen == "supercritico":
                fase["denominacion"] = "fluido_supercritico"
            fases.append(fase)
        else:
            fases.append({"id": k, "tipo": tipo_k, "presente": False, "n": 0.0, "beta": 0.0,
                          "composicionIncipiente": {c: 1.0} if tm_ausente is not None else None, "tm": tm_ausente})
    resid = 0.0
    for f in fases:
        if f["tm"] is not None:
            resid = max(resid, abs(f["beta"] * f["tm"]), max(0.0, -f["tm"]), max(0.0, -f["beta"]))
    return {"volumenId": v["id"], "especificacion": tipo, "T": float(e.T), "P": float(e.P), "V": float(e.v * m),
            "H": float(e.h * m), "U": float(e.u * m), "fases": fases, "complementariedad": resid,
            "presentes": [f["id"] for f in fases if f["presente"]],
            "verificaciones": {k: [float(x)] for k, x in e.residuos.items()}}


def _ecuacion_estado(pid, cas):
    """The package's residual Helmholtz model over the present species (`EOS_PAQUETES`)."""
    from core.termodinamica import cubic_eos
    if pid == PSRK:
        from core.termodinamica import psrk
        return psrk.PSRKMixture(cas)
    return cubic_eos.PengRobinsonMixture(cas)


def _cierre_cubico(modelo, v, n, especificacion):
    """Closure of the cubic mixture packages (Peng-Robinson, PSRK): same candidates, tm scale and
    complementarity as the mixture packages. tm of an absent candidate is the least non-trivial tangent-plane
    minimum of the present phase (core/termodinamica/cubic_flash.stability); without one it is None, as for the
    other packages. PSRK rejects a TP state below a species' alpha regression range (located, as in psrk.py) and,
    since H and U are always published, a state outside a light gas's ideal-gas cp record (CO2: Poling appendix A,
    50-1000 K, core/termodinamica/psrk_data.py) as `outside_ideal_gas_range`."""
    from core.termodinamica import cubic_eos, cubic_flash
    from core.unifac import FaltaDatoUNIFAC
    pid = _volumen(modelo, v["id"])[1]["modelo"]["id"]
    cas = _cas(modelo, v)
    ids_c = list(v["componenteIds"])
    nv = np.array([float(n[c] if c in n else n[str(c)]) for c in ids_c])
    idx = [i for i in range(len(nv)) if nv[i] > 0]
    try:
        eos = _ecuacion_estado(pid, tuple(cas[i] for i in idx))
        tipo = especificacion[0]
        if tipo == "TP":
            if hasattr(eos, "check_temperature"):
                eos.check_temperature(especificacion[1])
            st = cubic_flash.flash_TP(eos, especificacion[1], especificacion[2], nv[idx])
            st["T"], st["P"] = especificacion[1], especificacion[2]
        elif tipo == "PH":
            st = cubic_flash.flash_PH(eos, especificacion[1], especificacion[2], nv[idx])
        elif tipo == "UV":
            st = cubic_flash.flash_UV(eos, especificacion[1], especificacion[2], nv[idx])
        else:
            raise ValueError(f"especificación no admitida: {tipo}")
    except FaltaDatoUNIFAC as e:
        ns = NoSoportado(f"paquete {pid} en el volumen {v['id']}: {e}")
        ns.datos = {"cause": "unifac_data_missing", "detalle": e.detalle, "volumenId": v["id"]}
        raise ns from e
    except cubic_eos.CubicOutOfScope as e:
        ns = NoSoportado(f"paquete {pid} en el volumen {v['id']}: {e}")
        ns.datos = {**getattr(e, "datos", {}), "volumenId": v["id"]}     # located cause (e.g. liquid_liquid_split)
        raise ns from e
    ntot = float(nv.sum())
    presentes = {("vapor-1" if p["kind"] == "vapor" else "liquido-1"): p for p in st["phases"]
                 if p["n"] > TOL_PRESENTE * ntot}
    # Absent candidate of one kind: the least tangent-plane minimum whose trial phase is of that kind, by the
    # same phase-identification parameter that labels present phases (A1 review PR-4). Without a trial of that
    # kind its tm is None, as for the other packages; a liquid-like trial never stands for the vapour candidate.
    por_tipo = {}
    if len(st["phases"]) == 1:
        for w, tm in st["trials"]:
            ph = eos.phase(st["T"], st["P"], w)
            lab = cubic_flash._label_single(eos, st["T"], st["P"], w, ph["Z"])
            if lab not in por_tipo or tm < por_tipo[lab][1]:
                por_tipo[lab] = (w, tm)
    fases = []
    for k in candidatas(modelo, v["id"]):
        tipo_k = "vapor" if k.startswith("vapor") else "liquido"
        f = presentes.get(k)
        if f is not None:
            comp = {c: 0.0 for c in ids_c}
            for j, i in enumerate(idx):
                comp[ids_c[i]] = float(f["x"][j])
            fases.append({"id": k, "tipo": tipo_k, "presente": True, "n": float(f["n"]), "beta": float(f["n"]) / ntot,
                          "composicion": comp, "tm": 0.0})
        elif tipo_k in por_tipo:
            w_abs, tm_abs = por_tipo[tipo_k]
            comp = {c: 0.0 for c in ids_c}
            for j, i in enumerate(idx):
                comp[ids_c[i]] = float(w_abs[j])
            fases.append({"id": k, "tipo": tipo_k, "presente": False, "n": 0.0, "beta": 0.0,
                          "composicionIncipiente": comp, "tm": float(tm_abs)})
        else:
            fases.append({"id": k, "tipo": tipo_k, "presente": False, "n": 0.0, "beta": 0.0,
                          "composicionIncipiente": None, "tm": None})
    resid = 0.0
    for f in fases:
        if f["tm"] is not None:
            resid = max(resid, abs(f["beta"] * f["tm"]), max(0.0, -f["tm"]), max(0.0, -f["beta"]))
    H = sum(p["n"] * p["h"] for p in st["phases"])
    V = sum(p["n"] * p["v"] for p in st["phases"])
    U = sum(p["n"] * p["u"] for p in st["phases"])
    return {"volumenId": v["id"], "especificacion": especificacion[0], "T": float(st["T"]), "P": float(st["P"]),
            "V": float(V), "H": float(H), "U": float(U), "fases": fases, "complementariedad": resid,
            "presentes": [f["id"] for f in fases if f["presente"]],
            "verificaciones": {"equilibrio": [st["mu_residual"], cubic_flash.TOL_MU,
                                              "max |ln f_i^V - ln f_i^L| between present phases"],
                               "estabilidad": [max(0.0, -st["tm_min"]), cubic_flash.TOL_TM,
                                               "-min tm over the non-trivial tangent-plane minima"]}}
