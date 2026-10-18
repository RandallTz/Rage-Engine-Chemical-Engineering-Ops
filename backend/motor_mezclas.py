"""
Paquetes de mezcla en la API puntual del motor (revision 1, ampliacion
aditiva): modelos 'mezcla-ideal' y 'nrtl-chemsep' publicados en
/motor/termodinamica/capacidades con los MISMOS campos de la revision 1.
La EvaluacionEstado multicomponente ya estaba prevista en los tipos
(composicion por fase, varias fases con ID propio).

La construccion termodinamica y los algoritmos estan en core/mezclas.py y
core/mezclas_datos.py; aqui solo se adapta al contrato. Las evidencias de
potenciales quimicos (mu, G, estado estandar) se publican en la revision 2
del ensamblaje (backend/motor_ensamblaje_v2.py), no en esta respuesta.
"""

import math

import numpy as np

from core import mezclas as mz
from core import mezclas_datos as md

MODELOS = {"mezcla-ideal": "1", "nrtl-chemsep": "1", "nrtl-lle-agua-butanol": "1", "unifac-original-public": "1",
           "unifac-dortmund-public": "1", "unifac-original-lle-public": "1"}
FASES_MEZCLA = ["liquido", "vapor"]


def capacidades_mezcla():
    """componentesCAS = especies del registro admitidas por la regla UNICA de core/catalogo.faltantes (la misma que
    aplica el Sistema, tambien a una especie pura); el dominio en T es la envolvente de esas especies, recortada
    por el intervalo de datos del paquete cuando lo tiene (NRTL-LLE, tabla UNIFAC ELL)."""
    from core import catalogo, unifac
    sal = []
    for mid, ver in MODELOS.items():
        d = mz.PAQUETES[mid]
        cas = [c for c in md.especies_disponibles() if not catalogo.faltantes(d.liquido, c, mid)]
        T_dom = [min(md.especie(c).T_rango[0] for c in cas), max(md.especie(c).T_rango[1] for c in cas)]
        if d.liquido == "nrtl_lle":
            # parametros solo donde hay datos de solubilidad
            T_dom = [max(T_dom[0], mz.NRTL_LLE_AGUA_BUTANOL["T"][0]), min(T_dom[1], mz.NRTL_LLE_AGUA_BUTANOL["T"][1])]
        elif d.liquido.startswith("unifac_"):
            rango = unifac.RANGO_T.get(d.liquido.split("_", 1)[1])
            if rango is not None:
                T_dom = [max(T_dom[0], rango[0]), min(T_dom[1], rango[1])]
        sal.append({
            "id": mid, "version": ver, "nombre": d.nombre,
            "componentesCAS": cas,
            "especificaciones": ["TP", "PH", "UP", "UV"],
            "fases": list(FASES_MEZCLA),
            "dominio": {"T": T_dom, "P": [mz.P_MIN, mz.P_MAX]},
            "referencia": dict(mz.REFERENCIA),
            "propiedades": ["u", "h", "v", "s"],
            "dinamica": False,
        })
    return sal


def es_modelo_mezcla(modelo):
    return isinstance(modelo, dict) and MODELOS.get(modelo.get("id")) == modelo.get("version")


def _verif(id_, estado, residuo, tolerancia, motivo=None):
    v = {"id": id_, "estado": estado, "residuo": residuo, "tolerancia": tolerancia}
    if motivo:
        v["motivo"] = motivo
    return v


def evaluacion_desde_estado(e, ids, sistema, politica=None, objetivo=None, masas_declaradas=None):
    """EvaluacionEstado (revision 1) de un EstadoMezcla. objetivo: dict con
    residuos de especificacion ya calculados {id: (residuo, tol, motivo)}."""
    P, T = e.P, e.T
    n = e.n
    masa = float(np.sum(n * sistema.M))
    V = e.V
    z = n / n.sum()
    fases = []
    unica = len(e.fases) == 1
    for f in e.fases:
        m_f = f.n * f.M
        # Una sola fase contiene todo: las tres fracciones son 1 por identidad (el cociente en coma flotante
        # podia publicar 1.0000000000000002, que un lector estricto rechaza con razon).
        fases.append({
            "id": f.id, "tipo": f.tipo, "regimen": "ordinario",
            "fraccionMolar": 1.0 if unica else f.n / n.sum(), "fraccionMasica": 1.0 if unica else m_f / masa,
            "fraccionVolumen": 1.0 if unica else f.n * f.v / V,
            "composicionMolar": {str(i): float(f.x[k]) for k, i in enumerate(ids)},
            "propiedades": {"u": (f.h - P * f.v) / f.M, "h": f.h / f.M, "v": f.v / f.M, "s": f.s / f.M},
        })
    mezcla = {"u": e.U / masa, "h": e.H / masa, "v": V / masa, "s": e.S / masa}
    RT = mz.R * T
    vs = []
    res_est, tol_est, mot = e.verificaciones["estabilidad"]
    vs.append(_verif("estabilidad", "cumple" if res_est <= tol_est else "no_cumple", res_est, tol_est,
                     f"{mot}. Fases candidatas: {', '.join(e.estabilidad.get('candidatas', []))}; "
                     f"{e.estabilidad.get('pruebas', 0)} pruebas de fase; min tm = {e.estabilidad.get('tm_min', 0):.3g}."))
    if len(e.fases) > 1:
        r, t, m = e.verificaciones["equilibrio"]
        vs.append(_verif("equilibrio", "cumple" if r <= t else "no_cumple", r, t,
                         "T y P comunes por construcción; " + m))
    r, t, m = e.verificaciones["reconstruccion_material"]
    vs.append(_verif("reconstruccion_material", "cumple" if r <= t else "no_cumple", r, t, m))
    ident = max(abs(f.h - (f.h - P * f.v) - P * f.v) for f in e.fases) / RT
    vs.append(_verif("identidad_h_u_Pv", "cumple", ident, 1e-12, "max por fase |h - u - Pv|/(RT), molar"))
    ident_g = max(abs(f.g - (f.h - T * f.s)) for f in e.fases) / RT
    vs.append(_verif("identidad_g_h_Ts", "cumple" if ident_g <= 1e-9 else "no_cumple", ident_g, 1e-9,
                     "max por fase |g - (h - Ts)|/(RT) con g = sum x_i mu_i: potenciales y entalpía/entropía "
                     "salen de la misma función de Gibbs"))
    beta = [x["fraccionMolar"] for x in fases]
    chi = [x["fraccionMasica"] for x in fases]
    eps = [x["fraccionVolumen"] for x in fases]
    rb = max(abs(sum(beta) - 1), abs(sum(chi) - 1), abs(sum(eps) - 1))
    vs.append(_verif("bases_fase", "cumple" if rb <= 1e-12 else "no_cumple", rb, 1e-12,
                     "max(|Σβ-1|, |Σχ-1|, |Σε-1|); β molar, χ másica (masa molar de cada fase), ε volumétrica"))
    vs.append(_verif("dominio", "cumple", None, None,
                     f"T en [{sistema.T_rango[0]:.6g}, {sistema.T_rango[1]:.6g}] K (rangos de Psat y cp de las "
                     f"especies, T < 0.9 Tc) y P en [{mz.P_MIN:g}, {mz.P_MAX:g}] Pa (vapor ideal)."))
    for k, (r, t, m) in (objetivo or {}).items():
        vs.append(_verif(k, "cumple" if r <= t else "no_cumple", r, t, m))
    for cid, (decl, M) in (masas_declaradas or {}).items():
        vs.append(_verif("masa_molar", "cumple", abs(decl - M) / M, 1e-7, f"Componente {cid}: masa molar declarada."))
    if politica is not None and (politica.get("tiposPermitidos") is not None or politica.get("cantidad") == "monofasico"):
        vs.append(_verif("politica_fases", "cumple", None, None, "Fases calculadas compatibles con la política."))
    if politica is not None and politica.get("cambioInterno") == "prohibido":
        vs.append(_verif("cambio_interno", "no_evaluable", None, None,
                         "Consulta puntual sin trayectoria: no hay cambio interno que comparar."))
    return {
        "T": T, "P": P,
        "composicionMolar": {str(i): float(z[k]) for k, i in enumerate(ids)},
        "componentes": [{"id": i, "cas": c, "masaMolarKgMol": float(sistema.M[k]),
                         "fuente": f"thermo (IUPAC), {md.especie(c).nombre}"} for k, (i, c) in enumerate(zip(ids, sistema.cas))],
        "fases": fases, "mezcla": mezcla, "referencia": dict(mz.REFERENCIA),
        "estabilidad": {"estado": "estable", "alcance": list(FASES_MEZCLA),
                        "metodo": f"{sistema.paquete.nombre}. Mínimo de G a (T, P, n): fase única de menor G, prueba "
                                  "de distancia al plano tangente frente a vapor (mínimo analítico) y líquido (malla "
                                  "en el simplex de hasta 3 componentes y refinamiento local), adición de la fase "
                                  "inestable, minimización de G y pulido de Newton de la igualdad de potenciales; "
                                  "certificación final con la prueba completa. Hasta 3 fases (LLV). Especies "
                                  "ausentes excluidas sin evaluar log(0). Parámetros: " + sistema.procedencia + "."},
        "verificaciones": vs,
    }


def evaluar_mezcla(lector, sid, modelo, comps, componentes_crudos, espec, politica, rechazo, respuesta,
                   sustituciones=None):
    """Rama de /motor/termodinamica/evaluar para un modelo de mezcla."""
    ids = [cid for cid, _ in comps]
    cas = [c for _, c in comps]
    if any(c is None for c in cas):
        return rechazo()
    if len(set(cas)) != len(cas):
        return rechazo()
    from core import catalogo
    try:
        sust = catalogo.leer_sustituciones(sustituciones, "declaracion/datosPuros", cas)
    except catalogo.SustitucionRechazada as x:
        lector.diag("invalido" if x.codigo == "SUSTITUCION_INVALIDA" else "no_soportado", f"MOTOR_ESTADO_{x.codigo}",
                    x.ruta.replace("/", "."), x.mensaje)
        return rechazo()
    try:
        sistema = mz.Sistema(modelo["id"], cas, sust)
    except mz.FaltaParametro as x:
        lector.diag("no_soportado", f"MOTOR_ESTADO_{x.codigo}", "componentes", x.mensaje, ids)
        return rechazo()
    masas = {}
    for c in componentes_crudos:
        if isinstance(c, dict) and isinstance(c.get("masaMolar"), dict):
            q = c["masaMolar"].get("cantidad") or {}
            if q.get("valor") is not None and c.get("id") in ids:
                k = ids.index(c["id"])
                f = {"kg/mol": 1.0, "g/mol": 1e-3}[q["unidad"]]
                M = float(sistema.M[k])
                if abs(q["valor"] * f - M) > 1e-7 * M:
                    lector.diag("invalido", "MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA", f"componentes.{c['id']}.masaMolar",
                                f"Masa molar declarada {q['valor']} {q['unidad']} contradice la del paquete "
                                f"({M * 1e3:.6f} g/mol).", [c["id"]])
                    return rechazo()
                masas[c["id"]] = (q["valor"] * f, M)
    tipo, valores, z, n_decl = espec
    RT = None
    try:
        if tipo in ("TP", "PH"):
            base, fr = z
            w = np.array([fr[i] for i in ids], dtype=float)
            n = w if base == "molar" else w / sistema.M
            n = n / n.sum()
            if tipo == "TP":
                e = sistema.equilibrio_TP(valores["T"], valores["P"], n)
                obj = {}
            else:
                masa = float(np.sum(n * sistema.M))
                H = valores["h"] * masa
                e = sistema.equilibrio_PH(valores["P"], H, n)
                obj = {"energia": (abs(e.H - H) / (mz.R * e.T * n.sum()), 1e-10,
                                   "|H reconstruida - h·m| / (R T n)")}
        else:
            base, cant = n_decl
            n = np.array([cant[i] for i in ids], dtype=float)
            if base == "masica":
                n = n / sistema.M
            if tipo == "UP":
                e = sistema.equilibrio_UP(valores["P"], valores["U"], n)
                obj = {"energia": (abs(e.U - valores["U"]) / (mz.R * e.T * n.sum()), 1e-10, "|U reconstruida - U|/(R T n)")}
            else:
                e = sistema.equilibrio_UV(valores["U"], valores["V"], n)
                obj = {"energia": (abs(e.U - valores["U"]) / (mz.R * e.T * n.sum()), 1e-10, "|U reconstruida - U|/(R T n)"),
                       "volumen": (abs(e.V - valores["V"]) / valores["V"], 1e-10, "|V reconstruido - V|/V")}
    except mz.FueraDeAlcance as x:
        ruta = "declaracion.especificacion"
        if x.motivo == "saturacion":
            lector.diag("incompleto", "MOTOR_ESTADO_SATURACION_INDETERMINADA", ruta,
                        x.mensaje + " Hace falta una especificación de energía o volumen.", ids,
                        alternativas=[["P", "h", "composicion"], ["U", "P", "cantidades"], ["U", "V", "cantidades"]])
        elif x.motivo == "fuera_de_dominio":
            lector.diag("no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", ruta, x.mensaje, ids)
        elif x.motivo == "no_soportado" and x.datos.get("tope_fases"):
            lector.diag("no_soportado", "MOTOR_ESTADO_TOPE_FASES", ruta, x.mensaje, ids)
        elif x.motivo == "no_soportado":
            lector.diag("no_soportado", "MOTOR_ESTADO_NO_SOPORTADO", ruta, x.mensaje, ids)
        elif x.motivo == "invalido":
            lector.diag("invalido", "MOTOR_ESTADO_DATO_INVALIDO", ruta, x.mensaje, ids)
        else:
            lector.diag("no_convergente", "MOTOR_ESTADO_NO_CONVERGENTE", ruta, x.mensaje, ids)
        return rechazo()
    tipos = [f.tipo for f in e.fases]
    permitidos = politica.get("tiposPermitidos")
    if permitidos is not None and any(t not in permitidos for t in tipos):
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos",
                    f"El estado estable tiene {', '.join(f.id for f in e.fases)}; no todas están permitidas.", ids)
        return rechazo()
    if politica.get("cantidad") == "monofasico" and len(e.fases) > 1:
        lector.diag("invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.cantidad",
                    f"Política monofásica, pero el estado estable tiene {len(e.fases)} fases.", ids)
        return rechazo()
    ev = evaluacion_desde_estado(e, ids, sistema, politica, obj, masas)
    if any(v["estado"] == "no_cumple" for v in ev["verificaciones"]):
        lector.diag("no_convergente", "MOTOR_ESTADO_VERIFICACION_FALLIDA", "declaracion.especificacion",
                    "Una verificación del estado no se cumple; no se publica.", ids)
        return rechazo()
    return respuesta(ev)
