"""
Relaciones estructurales siempre presentes de un modelo común (contrato §2).

Son las ecuaciones que el modelo contiene por ser físico, se usen o no en
un instante concreto. El cierre de equilibrio de cada volumen figura aunque
ese volumen sea hoy un líquido sin vapor: la fase ausente tiene cantidad
cero con las mismas ecuaciones. Un volumen cuyo motor no evalúa el estado
aporta una relación `supuesta`, para que la carencia sea visible.

Misma estructura, misma lista y mismo orden. Para los ensamblajes v2
coincide con las ecuaciones que publica /motor/ensamblajes/validar
(tests/validar_modelo_comun.py lo comprueba con sus ejemplos).
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
                          f"estado no evaluado por un paquete ({t['supuesto']}): {t['motivo']}", supuesta=True))
            continue
        rigida = v["frontera"]["tipo"] == "rigida"
        cierre = "UV" if rigida else "PH"
        out.append(_r(f"estado.{v['id']}.energia", "estado", p, f"cierre {cierre} del paquete: energía de todas las fases"))
        out.append(_r(f"estado.{v['id']}.volumen", "estado", p, f"cierre {cierre} del paquete: volumen de todas las fases"))
        out.append(_r(f"equilibrio.{v['id']}", "equilibrio", p,
                      "reparto de equilibrio entre todas las fases candidatas, con prueba de estabilidad; "
                      "una fase ausente tiene cantidad cero"))
        if not rigida:
            out.append(_r(f"estado.{v['id']}.U", "estado", p, "U = H - P V"))
            out.append(_r(f"mecanica.{v['id']}.trabajo", "mecanica", p, "trabajo de frontera P dV/dt (comprobación)"))
    for s in modelo["corrientes"]:
        p = f"corriente:{s['id']}"
        pres = (s.get("estadoExterior") or {}).get("presion") or {}
        if pres.get("tipo") == "continuidad":
            out.append(_r(f"mecanica.continuidad.{s['id']}", "mecanica", p, "continuidad de presión declarada"))
        out.append(_r(f"transferencia.{s['id']}.composicion", "transferencia", p, "composición del donante según el signo del caudal"))
        out.append(_r(f"transferencia.{s['id']}.entalpia", "transferencia", p, "entalpía del donante según el signo del caudal"))
        out.append(_r(f"transferencia.{s['id']}.caudal", "transferencia", p, "caudal en base molar"))
    for q in modelo["intercambios"]:
        if q["ley"]["tipo"] == "conductancia":
            out.append(_r(f"transferencia.calor.{q['id']}", "transferencia", f"calor:{q['id']}",
                          "Q = G (T_desde - T_hasta)"))
    for v in vols:
        p = f"volumen:{v['id']}"
        if v["balances"]["materia"]:
            for c in v["componenteIds"]:
                out.append(_r(f"materia.{v['id']}.{c}", "materia", p, "conservación por componente"))
        if v["balances"]["energia"]:
            out.append(_r(f"energia.{v['id']}", "energia", p, "primera ley"))
    if vols:
        for c in modelo["componentes"]:
            if any(c["id"] in v["componenteIds"] and v["balances"]["materia"] for v in vols):
                out.append(_r(f"global.materia.{c['id']}", "verificacion", "red", "conservación global del componente"))
        if any(v["balances"]["energia"] for v in vols):
            out.append(_r("global.energia", "verificacion", "red", "conservación global de energía"))
    return out
