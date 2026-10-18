"""
Modelo estatico 'agua-iapws95-hielo-ih' (M5): agua pura con hielo Ih,
liquido y vapor (core/agua_slv.py). Ampliacion aditiva de la revision 1 de
/motor/termodinamica: el modelo 'agua-iapws95' no cambia.
"""

from functools import lru_cache

from core import agua_iapws95 as agua
from core import agua_slv as slv
from core import hielo_ih

MODELO = {"id": "agua-iapws95-hielo-ih", "version": "1"}
REFERENCIA = {
    "id": "iapws95-u0-s0-liquido-saturado-punto-triple",
    "descripcion": "IAPWS-95: u = 0 y s = 0 del líquido saturado en el punto triple; el hielo Ih de IAPWS "
                   "R10-06(2009) usa la constante s0 de la versión IAPWS-95, de modo que comparte esa referencia. "
                   "Propiedades específicas por kg.",
}
FUENTE_MASA_MOLAR = "IAPWS-95 (R6-95(2018)): M = 18.015268 g/mol"
FASES = ["solido", "liquido", "vapor"]


@lru_cache(maxsize=1)
def verificacion():
    """(publicable, motivo): Tabla 6 de R10-06 reproducida y triple del cierre junto al definido."""
    peor, _ = hielo_ih.verificar()
    if peor > 1e-8:
        return False, f"hielo Ih: error {peor:.3g} frente a la Tabla 6 de R10-06"
    Ttr, Ptr = slv.triple()
    if abs(Ttr - hielo_ih.TT) > 1e-6 or abs(Ptr / hielo_ih.PT - 1) > 1e-5:
        return False, f"punto triple del cierre ({Ttr:.9g} K, {Ptr:.9g} Pa) lejos del definido"
    return True, ""


def capacidad():
    return {
        "id": MODELO["id"], "version": MODELO["version"],
        "nombre": "Agua pura con hielo Ih: IAPWS-95 (fluido) + IAPWS R10-06 (hielo Ih)",
        "componentesCAS": [agua.CAS],
        "especificaciones": ["TP", "PH", "UP", "UV"],
        "fases": list(FASES),
        "dominio": {"T": [slv.T_MIN, slv.T_MAX], "P": [slv.P_MIN, slv.P_MAX]},
        "referencia": dict(REFERENCIA),
        "propiedades": ["u", "h", "v", "s", "cp"],
        "dinamica": False,
    }


def es_modelo(m):
    return m == MODELO


def _verif(id_, estado, residuo, tolerancia, motivo=None):
    v = {"id": id_, "estado": estado, "residuo": residuo, "tolerancia": tolerancia}
    if motivo:
        v["motivo"] = motivo
    return v


_DOMINIO = (f"T en [{slv.T_MIN}, {slv.T_MAX}] K, P en [{slv.P_MIN:g}, {slv.P_MAX:g}] Pa. P ≤ 100 MPa deja fuera "
            "los hielos II, III, V… (IAPWS R14-08); no se declaran por extrapolación. Líquido sobreenfriado "
            f"candidato solo con T ≥ {slv.T_LIQUIDO_MIN} K. Comprobación de pertenencia, sin residuo.")

_CRITERIO = {
    "TP": "Criterio TP: fase de menor g entre las candidatas evaluables a (T, P).",
    "PH": "Criterio PH: secuencia de fases estables al subir T a P fija (h crece con T); mesetas por palanca "
          "sobre las curvas de coexistencia de la propia formulación.",
    "UP": "Criterio UP: como PH con u = U/m.",
    "UV": "Criterio UV: máximo de S a (U, V, m) entre todas las candidatas que cumplen U y V (una fase, dos "
          "fases sobre cada curva, tres en el triple).",
}


def evaluar(lector, sid, comps, componentes_crudos, espec, politica, rechazo, respuesta):
    """Respuesta para una solicitud ya leida (un componente, agua)."""
    from backend import motor_termodinamica as mt
    cid, cas = comps[0]
    tipo, valores, z, n = espec
    try:
        if tipo == "TP":
            e = slv.evaluar_TP(valores["T"], valores["P"])
        elif tipo == "PH":
            e = slv.evaluar_PH(valores["P"], valores["h"])
        else:
            base, cantidades = n
            m = sum(cantidades.values()) * (agua.M if base == "molar" else 1.0)
            e = slv.evaluar_UP(valores["P"], valores["U"] / m) if tipo == "UP" else \
                slv.evaluar_UV(valores["U"] / m, valores["V"] / m)
    except slv.FueraDeAlcance as x:
        if x.motivo == "invalido":
            lector.diag("invalido", "MOTOR_ESTADO_DATO_INVALIDO", "declaracion.especificacion", x.mensaje, [cid])
            return rechazo()
        if x.motivo == "saturacion" and x.datos.get("triple"):
            # en el triple ni PH ni UP determinan el reparto (tres fases, dos ecuaciones): solo UV
            lector.diag("incompleto", "MOTOR_ESTADO_SATURACION_INDETERMINADA", "declaracion.especificacion",
                        x.mensaje + " Hace falta U y V (masa, energía y volumen fijan las tres fracciones); "
                        "no se elige un reparto por omisión.", [cid], alternativas=[["U", "V", "cantidades"]])
            return rechazo()
        return mt._rechazo_fisico(lector, x, cid, rechazo, tipo)

    tipos = [f.tipo for f, _ in e.fases]
    permitidos = politica.get("tiposPermitidos")
    if permitidos is not None and any(t not in permitidos for t in tipos):
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos",
                    f"El estado estable calculado tiene {' y '.join(tipos)}; no todas están entre los tipos "
                    f"permitidos ({', '.join(permitidos)}). No se fuerza una rama metastable para cumplirlo.", [cid])
        return rechazo()
    if politica["cantidad"] == "monofasico" and len(e.fases) > 1:
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.cantidad",
                    f"La política es monofásica, pero el estado estable tiene {len(e.fases)} fases "
                    f"({', '.join(tipos)}).", [cid])
        return rechazo()

    vs = []
    r, tol = e.residuos["estabilidad"]
    no_ev = e.estabilidad["no_evaluables"]
    excl = e.estabilidad["excluidas_por_curvas"]
    vs.append(_verif("estabilidad", "cumple" if r <= tol else "no_cumple", r, tol,
                     "Residuo = max(0, -min (g_candidata - g_estado)/(R T)) sobre las candidatas evaluables a la T y P "
                     f"del estado: {', '.join(e.estabilidad['candidatas'])}."
                     + (f" No evaluables a esta T, P: {', '.join(no_ev)} (fuera de la validez de su formulación o "
                        "sin raíz de densidad en su rama)" + (
                            f"; {', '.join(excl)} queda(n) fuera de la región estable según las curvas de fusión, "
                            "sublimación y vaporización de este mismo cierre (contrastadas con IAPWS R14-08)."
                            if excl else "; no se excluyen por las curvas: el alcance no las incluye.")
                        if no_ev else "")))
    vs.append(_verif("dominio", "cumple", None, None, _DOMINIO))
    if "equilibrio" in e.residuos:
        r, tol = e.residuos["equilibrio"]
        vs.append(_verif("equilibrio", "cumple" if r <= tol else "no_cumple", r, tol,
                         "Residuo = (max g - min g)/(R T) entre las fases presentes, a T y P comunes por construcción "
                         "(curva de coexistencia o punto triple de la propia formulación)."))
    if "especificacion" in e.residuos:
        r, tol = e.residuos["especificacion"]
        vs.append(_verif("energia", "cumple" if r <= tol else "no_cumple", r, tol,
                         "Residuo relativo de la especificación (h, u y, en UV, v) reconstruida como Σ w_α "
                         "(propiedad de fase) frente a la pedida."))
    for k in ("identidad_h_u_Pv", "identidad_g_h_Ts"):
        r, tol = e.residuos[k]
        vs.append(_verif(k, "cumple" if r <= tol else "no_cumple", r, tol,
                         "Residuo relativo por fase (escala max(|h|, R T)), con la P publicada."))
    w = [b for _, b in e.fases]
    eps = [b * f.v / e.v for f, b in e.fases]
    res_b = max(abs(sum(w) - 1.0), abs(sum(eps) - 1.0))
    vs.append(_verif("reconstruccion_material", "cumple", abs(sum(w) - 1.0), 1e-12,
                     "Un componente: Σ β_α = 1 y x_α = z = 1."))
    vs.append(_verif("bases_fase", "cumple" if res_b <= 1e-12 else "no_cumple", res_b, 1e-12,
                     "max(|Σ w_α - 1|, |Σ ε_α - 1|), ε_α = w_α v_α / v; fracción molar = másica (un componente)."))
    if tipo == "UV":
        vs.append(_verif("unicidad", "cumple", None, None,
                         f"{len(e.estabilidad_candidatas_UV)} candidata(s) con U y V dadas; se publica la de mayor S."))
    for c in componentes_crudos:
        if isinstance(c, dict) and c.get("id") == cid and isinstance(c.get("masaMolar"), dict):
            q = c["masaMolar"].get("cantidad") or {}
            if q.get("valor") is not None:
                factor = {"kg/mol": 1.0, "g/mol": 1e-3}[q["unidad"]]
                vs.append(_verif("masa_molar", "cumple", abs(q["valor"] * factor - agua.M) / agua.M,
                                 mt.TOL_MASA_MOLAR, "Masa molar declarada frente a la del modelo."))
    if permitidos is not None or politica["cantidad"] == "monofasico":
        vs.append(_verif("politica_fases", "cumple", None, None,
                         f"Fases del estado estable ({', '.join(tipos)}) compatibles con la política declarada."))
    if politica["cambioInterno"] == "prohibido":
        vs.append(_verif("cambio_interno", "no_evaluable", None, None,
                         "Consulta puntual sin trayectoria: no hay cambio interno que comparar."))
    if any(v["estado"] == "no_cumple" for v in vs):
        lector.diag("no_convergente", "MOTOR_ESTADO_VERIFICACION_FALLIDA", "declaracion.especificacion",
                    "Una verificación del estado no se cumple; no se publica.", [cid])
        return rechazo()

    fases = []
    for (f, b), ep in zip(e.fases, eps):
        props = {"u": f.u, "h": f.h, "v": f.v, "s": f.s}
        if f.cp is not None:
            props["cp"] = f.cp
        fases.append({"id": f"{f.tipo}-1", "tipo": f.tipo, "regimen": "ordinario",
                      "fraccionMolar": b, "fraccionMasica": b, "fraccionVolumen": ep,
                      "composicionMolar": {str(cid): 1.0}, "propiedades": props})
    mezcla = {"u": e.u, "h": e.h, "v": e.v, "s": e.s}
    if len(e.fases) == 1 and e.fases[0][0].cp is not None:
        mezcla["cp"] = e.fases[0][0].cp
    evaluacion = {
        "T": e.T, "P": e.P,
        "composicionMolar": {str(cid): 1.0},
        "componentes": [{"id": cid, "cas": cas, "masaMolarKgMol": agua.M, "fuente": FUENTE_MASA_MOLAR}],
        "fases": fases,
        "mezcla": mezcla,
        "referencia": dict(REFERENCIA),
        "estabilidad": {"estado": "estable",
                        "alcance": [t for t in FASES if t in e.estabilidad["candidatas"] or t in excl],
                        "metodo": f"{_CRITERIO[tipo]} Estabilidad: g mínima entre hielo Ih (R10-06), líquido y "
                                  "vapor (IAPWS-95, raíz de densidad de cada rama) a la T y P del estado; tolerancia "
                                  f"{slv.TOL_G:g} en Δg/(R T). Una fase no evaluable a esa T, P (hielo por encima "
                                  "de 273.16 K, vapor sin raíz sobre su curva, líquido bajo 235 K) solo entra en el "
                                  "alcance si las curvas de coexistencia del mismo cierre la dejan fuera de la región "
                                  "estable."},
        "verificaciones": vs,
    }
    return respuesta(evaluacion)


def diagrama(modelo_id, version, puntos=60):
    """Diagrama P-T del cierre publicado: las curvas salen de las mismas funciones que resuelven los
    estados (g del hielo = g del fluido), no de correlaciones. Distingue region estable de cada fase,
    region no soportada y que el metastable no se dibuja como estable."""
    if {"id": modelo_id, "version": version} != MODELO:
        return {"revision": 1, "modelo": {"id": modelo_id, "version": version}, "estado": "no_soportado",
                "diagrama": None,
                "diagnosticos": [{"codigo": "MOTOR_ESTADO_MODELO_NO_PUBLICADO", "ruta": "modelo",
                                  "mensaje": f"Solo hay diagrama P-T para {MODELO['id']} versión {MODELO['version']}.",
                                  "componenteIds": [], "propietarioId": ""}]}
    c = slv.curvas(puntos)
    Ttr, Ptr = c["triple"]
    lineas = [
        {"id": "sublimacion", "fases": ["solido", "vapor"], "puntos": [{"T": T, "P": P} for T, P in c["sublimacion"]]},
        {"id": "fusion", "fases": ["solido", "liquido"], "puntos": [{"T": T, "P": P} for T, P in c["fusion"]]},
        {"id": "vaporizacion", "fases": ["liquido", "vapor"], "puntos": [{"T": T, "P": P} for T, P in c["vaporizacion"]]},
    ]
    return {
        "revision": 1, "modelo": dict(MODELO), "estado": "evaluado",
        "diagrama": {
            "ejes": {"T": {"unidad": "K", "rango": [slv.T_MIN, slv.T_MAX]},
                     "P": {"unidad": "Pa", "rango": [slv.P_MIN, slv.P_MAX], "escala": "logaritmica"}},
            "puntoTriple": {"T": Ttr, "P": Ptr, "fases": ["solido", "liquido", "vapor"],
                            "nota": "Triple del cierre (g iguales en las tres fases); el definido por IAPWS es "
                                    "273.16 K, 611.657 Pa."},
            "lineas": lineas,
            "regiones": [
                {"id": "solido", "estado": "estable", "fases": ["solido"],
                 "descripcion": "Por debajo de la sublimación y a la izquierda de la fusión."},
                {"id": "liquido", "estado": "estable", "fases": ["liquido"],
                 "descripcion": "Entre la fusión y la vaporización, P > P triple."},
                {"id": "vapor", "estado": "estable", "fases": ["vapor"],
                 "descripcion": "Por debajo de la sublimación y de la vaporización."},
            ],
            "noSoportado": [
                {"id": "hielos_alta_presion", "descripcion": "P > 100 MPa: hielos II, III, V… sin modelo propio "
                 "(IAPWS R14-08); no se extrapola el hielo Ih."},
                {"id": "fuera_de_T", "descripcion": f"T fuera de [{slv.T_MIN}, {slv.T_MAX}] K en este modelo; el "
                 "fluido por encima lo cubre agua-iapws95."},
                {"id": "liquido_sobreenfriado_profundo", "descripcion": f"Líquido con T < {slv.T_LIQUIDO_MIN} K: "
                 "IAPWS-95 extrapola; no es fase candidata."},
            ],
            "metastable": "Las prolongaciones de las curvas más allá del triple (líquido sobreenfriado, hielo "
                          "sobrecalentado) no se publican: los estados se resuelven siempre en el estable.",
            "fuentes": [hielo_ih.FUENTE, "IAPWS-95 (R6-95(2018)) para el fluido",
                        "IAPWS R14-08(2011) solo como contraste de las curvas (no se usa para resolver)"],
        },
        "diagnosticos": [],
    }
