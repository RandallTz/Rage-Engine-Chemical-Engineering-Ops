"""
Always-present structural relations of a common model (contract §2).

These equations belong to the physical model whether or not they are active
at a given instant. Each volume's equilibrium closure remains present even
when the volume contains only liquid: an absent phase has zero amount under
the same equations. A volume whose engine does not evaluate its state adds
a `supuesta` relation to make that limitation visible.

The same structure produces the same list in the same order. For v2 assemblies,
the equation identities match those published by /motor/ensamblajes/validar
(tests/validar_modelo_comun.py checks this against its fixtures).
"""


def _r(id_, familia, propietario, descripcion, supuesta=False):
    r = {"id": id_, "familia": familia, "propietarioId": propietario, "descripcion": descripcion}
    if supuesta:
        r["supuesta"] = True
    return r


def relaciones(modelo):
    vols = modelo["volumenes"]
    out = []
    for v in vols:
        p = f"volumen:{v['id']}"
        t = v["termodinamica"]
        if t["tipo"] == "supuesto":
            out.append(_r(f"estado.{v['id']}.supuesto", "estado", p,
                          f"State not evaluated by a package ({t['supuesto']}): {t['motivo']}", supuesta=True))
            continue
        rigida = v["frontera"]["tipo"] == "rigida"
        cierre = "UV" if rigida else "PH"
        out.append(_r(f"estado.{v['id']}.energia", "estado", p, f"Package {cierre} closure: energy of every phase"))
        out.append(_r(f"estado.{v['id']}.volumen", "estado", p, f"Package {cierre} closure: volume of every phase"))
        out.append(_r(f"equilibrio.{v['id']}", "equilibrio", p,
                      "Equilibrium partition over all candidate phases, with stability search; "
                      "an absent phase has zero amount"))
        if not rigida:
            out.append(_r(f"estado.{v['id']}.U", "estado", p, "U = H - P V"))
            out.append(_r(f"mecanica.{v['id']}.trabajo", "mecanica", p, "Boundary work P dV/dt (verification)"))
    for s in modelo["corrientes"]:
        p = f"corriente:{s['id']}"
        pres = (s.get("estadoExterior") or {}).get("presion") or {}
        if pres.get("tipo") == "continuidad":
            out.append(_r(f"mecanica.continuidad.{s['id']}", "mecanica", p, "Declared pressure continuity"))
        out.append(_r(f"transferencia.{s['id']}.composicion", "transferencia", p, "Donor composition follows the flow direction"))
        out.append(_r(f"transferencia.{s['id']}.entalpia", "transferencia", p, "Donor enthalpy follows the flow direction"))
        out.append(_r(f"transferencia.{s['id']}.caudal", "transferencia", p, "Molar flow rate"))
    for q in modelo["intercambios"]:
        if q["ley"]["tipo"] == "conductancia":
            out.append(_r(f"transferencia.calor.{q['id']}", "transferencia", f"calor:{q['id']}",
                          "Q = G (T_desde - T_hasta)"))
    for v in vols:
        p = f"volumen:{v['id']}"
        if v["balances"]["materia"]:
            for c in v["componenteIds"]:
                out.append(_r(f"materia.{v['id']}.{c}", "materia", p, "Conservation of each component"))
        if v["balances"]["energia"]:
            out.append(_r(f"energia.{v['id']}", "energia", p, "First law"))
    if vols:
        for c in modelo["componentes"]:
            if any(c["id"] in v["componenteIds"] and v["balances"]["materia"] for v in vols):
                out.append(_r(f"global.materia.{c['id']}", "verificacion", "red", "Global component conservation"))
        if any(v["balances"]["energia"] for v in vols):
            out.append(_r("global.energia", "verificacion", "red", "Global energy conservation"))
    return out
