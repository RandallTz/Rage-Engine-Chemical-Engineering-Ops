"""
Descripción termodinámica de un modelo común, para mostrarla (panel Termodinámica
del Engine). No calcula estados: dice, por volumen, qué cierre declara, qué fases
candidatas usa la capa, qué familia de modelo de estado tiene su paquete y qué
relaciones siempre presentes le corresponden (evaluadas o supuestas).

  describir(modelo) -> {"volumenes": [...]}
"""

from core import mezclas as mz
from core.modelo import leer_modelo_comun, relaciones

from . import capa

_FAMILIA = {"ideal": ("ideal", None), "nrtl": ("actividad", "nrtl"), "nrtl_lle": ("actividad", "nrtl"),
            "unifac_original": ("actividad", "unifac_original"), "unifac_dortmund": ("actividad", "unifac_dortmund"),
            "unifac_lle": ("actividad", "unifac_lle")}


def _modelo_estado(pid):
    if pid == capa.AGUA:
        return {"familia": "iapws95", "modeloLiquido": None, "nombre": "Agua pura, IAPWS-95 (energía de Helmholtz)"}
    p = mz.PAQUETES.get(pid)
    if p is None:
        return {"familia": "no_envuelto", "modeloLiquido": None, "nombre": pid}
    fam, liq = _FAMILIA.get(p.liquido, ("actividad", p.liquido))
    return {"familia": fam, "modeloLiquido": liq, "nombre": p.nombre}


def describir(modelo):
    m = leer_modelo_comun(modelo)
    rel = relaciones(m)
    paquetes = {p["id"]: p for p in m["termodinamica"]["paquetes"]}
    salida = []
    for v in m["volumenes"]:
        t = v["termodinamica"]
        propias = [r for r in rel if r["propietarioId"] == f"volumen:{v['id']}" and r["familia"] in ("estado", "equilibrio", "mecanica")]
        d = {"id": v["id"], "componenteIds": v["componenteIds"], "frontera": v["frontera"]["tipo"], "relaciones": propias}
        if t["tipo"] == "equilibrio":
            pid = paquetes[t["paqueteId"]]["modelo"]["id"]
            d["cierre"] = {"tipo": "equilibrio", "paquete": paquetes[t["paqueteId"]]["modelo"], "politica": t["politica"]}
            d["modeloEstado"] = _modelo_estado(pid)
            try:
                d["candidatas"] = capa.candidatas(m, v["id"])
            except capa.NoSoportado as e:
                d["candidatas"], d["motivoCandidatas"] = None, str(e)
        else:
            d["cierre"] = {"tipo": "supuesto", "supuesto": t["supuesto"], "motivo": t["motivo"]}
            d["modeloEstado"], d["candidatas"] = None, None
        salida.append(d)
    return {"formato": "rage.modelo.termodinamica", "version": 0, "volumenes": salida}
