"""
Round trips between the common model and existing formats (contract §3).
Each pair is exact: format -> model -> format returns the original.

  nondimensionalization document (v1/v2) <-> model (matematico + motores.adimensionalizacion)
  engine assembly v2 request             <-> model (volumes, streams, thermodynamics)

The TS engine's material sheet is adapted in TypeScript
(frontend/motores/modelo/desdeHojaMotor.ts), where its compiler lives.
"""

import copy

from .lector import VERSION


def _vacio(id_, nombre, procedencia):
    return {"formato": "rage.modelo", "version": VERSION, "id": id_, "nombre": nombre, "componentes": [],
            "termodinamica": {"paquetes": []}, "volumenes": [], "corrientes": [], "intercambios": [],
            "datos": {}, "matematico": None, "estudio": None, "motores": {}, "procedencia": procedencia}


# --- nondimensionalization document -------------------------------------------
def desde_documento_adimensional(doc):
    d = copy.deepcopy(doc)
    m = _vacio(d["id"], d["nombre"], {"tipo": "documento_adimensional", "documentoId": d["id"]})
    m["matematico"] = d["modelo"]
    cfg = {"version": d["version"], "formas": d["formas"], "activaId": d["activaId"]}
    if "exploracion" in d:
        cfg["exploracion"] = d["exploracion"]
    m["motores"]["adimensionalizacion"] = cfg
    return m


def a_documento_adimensional(modelo):
    m = copy.deepcopy(modelo)
    cfg = m["motores"]["adimensionalizacion"]
    doc = {"formato": "adimensionalizacion", "version": cfg["version"], "id": m["id"], "nombre": m["nombre"],
           "modelo": m["matematico"], "formas": cfg["formas"], "activaId": cfg["activaId"]}
    if "exploracion" in cfg:
        doc["exploracion"] = cfg["exploracion"]
    return doc


# --- assembly v2 request --------------------------------------------------
def desde_ensamblaje_v2(sol):
    s = copy.deepcopy(sol)
    proc = {"tipo": "ensamblaje_v2", "solicitudId": s["solicitudId"], "revision": s["revision"]}
    if "derivacion" in s:
        proc["derivacion"] = s["derivacion"]
    m = _vacio(s["solicitudId"], s["solicitudId"], proc)
    for namespace in ("materialDerivation", "energyDerivation", "thermodynamicDerivation", "dynamicDefinition", "momentumDerivation", "hydraulicNetwork", "equationWorkbench"):
        if isinstance(s.get("derivacion"), dict) and namespace in s["derivacion"]:
            m["motores"][namespace] = copy.deepcopy(s["derivacion"][namespace])
    m["componentes"] = s["componentes"]
    m["termodinamica"]["paquetes"] = s["paquetes"]
    m["volumenes"] = [{
        "id": v["id"], "componenteIds": v["componenteIds"], "balances": v["balances"],
        "supuestos": {"materia": v["formulacionMateria"], "energia": v["formulacionEnergia"]},
        "frontera": v["frontera"], "inicial": v["inicial"],
        "termodinamica": {"tipo": "equilibrio", "paqueteId": v["paqueteId"], "politica": v["politica"]},
    } for v in s["volumenes"]]
    m["corrientes"] = s["corrientes"]
    m["intercambios"] = s["intercambiosTermicos"]
    m["datos"] = s["datos"]
    m["estudio"] = s["estudio"]
    return m


def a_ensamblaje_v2(modelo):
    m = copy.deepcopy(modelo)
    proc = m["procedencia"]
    vols = []
    for v in m["volumenes"]:
        t = v["termodinamica"]
        if t["tipo"] != "equilibrio":
            raise ValueError(f"Assembly v2 requires an equilibrium closure in volume {v['id']}")
        vols.append({"id": v["id"], "componenteIds": v["componenteIds"], "balances": v["balances"],
                     "formulacionMateria": v["supuestos"]["materia"], "formulacionEnergia": v["supuestos"]["energia"],
                     "paqueteId": t["paqueteId"], "politica": t["politica"], "frontera": v["frontera"],
                     "inicial": v["inicial"]})
    sol = {"revision": proc.get("revision", 2), "solicitudId": proc.get("solicitudId", m["id"]),
           "componentes": m["componentes"], "paquetes": m["termodinamica"]["paquetes"], "volumenes": vols,
           "corrientes": m["corrientes"], "intercambiosTermicos": m["intercambios"], "datos": m["datos"],
           "estudio": m["estudio"]}
    if "derivacion" in proc:
        sol["derivacion"] = proc["derivacion"]
    for namespace in ("materialDerivation", "energyDerivation", "thermodynamicDerivation", "dynamicDefinition", "momentumDerivation", "hydraulicNetwork", "equationWorkbench"):
        if namespace in m["motores"]:
            sol.setdefault("derivacion", {})[namespace] = copy.deepcopy(m["motores"][namespace])
    return sol
