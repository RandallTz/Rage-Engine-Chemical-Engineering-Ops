"""
Resultados de motores que no se modifican, al formato común (sin pérdida de valores).

  desde_ensamblaje_v2(respuesta): /motor/ensamblajes/resolver, revisión 2.

La simulación del núcleo de adimensionalización ya publica el formato común
(estudio.simulacion.resultados); el solver TS del motor se adapta en
frontend/motores/resultados/desdeMotor.ts.
"""

from .formato import conjunto, eje, evento, serie


def desde_ensamblaje_v2(respuesta):
    val = respuesta["validacion"]
    r = respuesta.get("resultados")
    estado = {"resuelto": "resuelto", "parcial": "parcial"}.get(respuesta["estado"], "fallido")
    proc = {"motor": "motor.ensamblaje.v2", "metodo": (r or {}).get("metodo"), "firma": val.get("modeloId")}
    if not r:
        return conjunto(val.get("solicitudId") or "ensamblaje", "Ensamblaje", "fallido", proc, [], [])
    meta = {v["id"]: v for v in val.get("variables", [])}
    t = eje("t", "tiempo", "tiempo", "s", r["tiempos"])
    series = []
    for s in r["series"]:
        m = meta.get(s["variableId"], {})
        series.append(serie(s["variableId"], s["variableId"], s["unidadSI"], ["t"], s["valores"],
                            propietarioId=m.get("propietarioId"), componenteId=m.get("componenteId"), faseId=m.get("faseId")))
    eventos = [evento(e["codigo"], "t", e["tiempo"], e.get("descripcion", e["codigo"]),
                      f"volumen:{e['volumenId']}" if e.get("volumenId") else None) for e in r.get("eventos", [])]
    verif = [{"id": x["ecuacionId"], "valor": x["maximoEscalado"], "tolerancia": x["tolerancia"], "descripcion": x["definicion"]}
             for x in r.get("residuos", [])]
    return conjunto(val.get("solicitudId") or "ensamblaje", "Ensamblaje", estado, proc, [t], series, eventos, verif,
                    modeloId=val.get("modeloId"))
