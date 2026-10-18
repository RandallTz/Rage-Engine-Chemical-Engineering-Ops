"""
Servicio de diagramas de equilibrio (protocolo propio, revision 1). Tipos:
docs/contratos/contratoDiagramasEquilibrio.ts. Documento: docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md.

Valida la solicitud (todo rechazo conocido es una respuesta estructurada con ruta), construye el MISMO
paquete que usan los estados (backend/motor_mezclas -> core/mezclas.Sistema), traza con
core/diagramas_equilibrio y traduce al componente del eje. Nunca cambia de paquete ni completa parametros.
"""

import hashlib
import json
import math

from backend import motor_mezclas
from backend import motor_termodinamica as mt
from core import coexistencia_lv as co
from core import diagramas_equilibrio as dg
from core import mezclas as mz

REVISION = 1
CAMPOS = ("revision", "solicitudId", "componentes", "modelo", "huellaModeloEsperada", "componenteEjeId", "corte",
          "intervaloComposicion", "resolucion", "datosPuros")
OBLIGATORIOS = ("revision", "solicitudId", "componentes", "modelo", "componenteEjeId", "corte",
                "intervaloComposicion", "resolucion")


def _pares(mid):
    from backend import motor_ensamblaje_v2 as v2
    paq = next(p for p in v2.capacidades_v2()["paquetes"] if p["modelo"]["id"] == mid)
    comb = {c["id"]: c for c in paq["combinaciones"]}
    return paq.get("pares"), comb.get("liquido_vapor"), comb.get("liquido_liquido")


def capacidades():
    paquetes = []
    for c in motor_mezclas.capacidades_mezcla():
        pares, _, _ = _pares(c["id"])
        extra = {}
        if c["id"].startswith("unifac-"):
            from backend import motor_ensamblaje_v2 as v2
            extra["coberturaGrupos"] = v2.cobertura_unifac(c["id"])
        paquetes.append({**extra,
            "modelo": {"id": c["id"], "version": c["version"]}, "operaciones": ["Txy", "Pxy"],
            "fases": ["liquido", "vapor"], "componentesCAS": list(c["componentesCAS"]), "dominio": dict(c["dominio"]),
            "pares": [{"componentesCAS": list(p["componentesCAS"]), "evidencia": p["evidencia"],
                       "procedencia": p["procedencia"]} for p in pares] if pares is not None else None,
            "combinacionesDetectadas": ["liquido_vapor (ramas y segmentos certificados)",
                                        "azeotropo (x = y refinado)",
                                        "encuentro_otra_fase (liquido competidor identificado; LL/LLV no se traza)",
                                        "limite_dominio", "extremo_puro"],
            "limites": [f"vapor ideal: P <= {mz.P_MAX:g} Pa", "T dentro del dominio del par (rangos de Psat y cp, "
                        "T <= 0.9 Tc)", "variable de continuacion: x del liquido (no hay continuacion por longitud de "
                        "arco: un pliegue en x se declararia, no se sigue)"]})
    return {"revision": REVISION, "trazador": dict(dg.TRAZADOR), "operaciones": ["Txy", "Pxy"], "componentes": 2,
            "perfiles": [dict(p) for p in dg.PERFILES.values()], "paquetes": paquetes,
            "noSoportado": [
                {"elemento": "mas de dos componentes", "motivo": "el trazador inicial es binario; no se elimina ni "
                 "renormaliza un tercer componente"},
                {"elemento": "diagramas LL, LLV y SLE completos", "motivo": "se detecta y explica el encuentro con otra "
                 "fase; trazar sus regiones queda para otra entrega"},
                {"elemento": "agua-iapws95 y agua-iapws95-hielo-ih", "motivo": "un solo componente: su diagrama es P-T "
                 "(GET /motor/termodinamica/diagrama para el hielo)"},
                {"elemento": "region critica", "motivo": "excluida por los paquetes (T <= 0.9 Tc)"},
                {"elemento": "superficies 3D y cortes multicomponente", "motivo": "fuera de esta entrega"}]}


class _Lector:
    def __init__(self):
        self.diags = []

    def diag(self, estado, codigo, ruta, mensaje, ids=()):
        self.diags.append({"codigo": codigo, "estado": estado, "ruta": ruta, "mensaje": mensaje,
                           "componenteIds": list(ids)})

    def estados(self):
        return {d["estado"] for d in self.diags}


def _vacia(sid, estado, diags, corte=None):
    return {"revision": REVISION, "solicitudId": sid, "estado": estado,
            "identidad": {"modelo": {"id": "", "version": ""}, "huellaModelo": None, "firmaConsulta": None,
                          "trazador": dict(dg.TRAZADOR)},
            "condicion": None, "ramas": [], "puntos": [], "puntosEspeciales": [], "candidatosDescartados": [],
            "incidencias": [], "cobertura": None, "metodo": "", "evidencia": None, "diagnosticos": diags}


def _cantidad(lec, v, ruta, mag):
    unidades = mt.UNIDADES[mag]
    if not isinstance(v, dict) or set(v) != {"valor", "unidad"}:
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", ruta, "Se espera {valor, unidad}.")
        return None
    val, uni = v["valor"], v["unidad"]
    if val is None:
        lec.diag("incompleto", "MOTOR_DIAG_DATO_INVALIDO", ruta + ".valor", "Dato sin especificar (null no es cero).")
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", ruta + ".valor", "Valor no numerico o no finito.")
        return None
    if uni not in unidades:
        lec.diag("invalido", "MOTOR_DIAG_UNIDAD", ruta + ".unidad",
                 f"Unidad {uni!r} incompatible con {mag}; usa {', '.join(unidades)}.")
        return None
    f, d = unidades[uni]
    si = val * f + d
    if not si > 0:
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", ruta + ".valor", f"{mag} debe ser positiva (absoluta).")
        return None
    return si


def trazar(cuerpo):
    lec = _Lector()
    sid = cuerpo.get("solicitudId") if isinstance(cuerpo, dict) and isinstance(cuerpo.get("solicitudId"), str) else ""
    if not isinstance(cuerpo, dict):
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "", "El cuerpo debe ser un objeto.")
        return _vacia(sid, "invalido", lec.diags)
    for k in cuerpo:
        if k not in CAMPOS:
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", k, f"Campo no admitido: {k}.")
    for k in OBLIGATORIOS:
        if k not in cuerpo:
            lec.diag("incompleto", "MOTOR_DIAG_DATO_INVALIDO", k, f"Falta {k}.")
    rev = cuerpo.get("revision")
    if "revision" in cuerpo and (isinstance(rev, bool) or rev != REVISION):
        lec.diag("invalido", "MOTOR_DIAG_REVISION", "revision", f"Revision {rev!r} no admitida; esta es la {REVISION}.")
    if "solicitudId" in cuerpo and (not isinstance(cuerpo["solicitudId"], str) or not cuerpo["solicitudId"]):
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "solicitudId", "Identificador de solicitud vacio.")
    # componentes
    comps = cuerpo.get("componentes")
    ids, cas = [], []
    if "componentes" in cuerpo:
        if not isinstance(comps, list):
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "componentes", "Se espera una lista.")
            comps = []
        elif len(comps) != 2:
            lec.diag("no_soportado", "MOTOR_DIAG_COMPONENTES_NO_SOPORTADO", "componentes",
                     f"El trazador es binario: se declararon {len(comps)} componentes. No se elimina ni renormaliza "
                     "ninguno; un binario distinto es otra solicitud explicita.")
        for k, c in enumerate(comps if isinstance(comps, list) else []):
            cid = c.get("id") if isinstance(c, dict) else None
            ca = ((c.get("identidadQuimica") or {}).get("cas") if isinstance(c, dict) else None)
            if isinstance(cid, bool) or not isinstance(cid, int) or cid < 1:
                lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", f"componentes.{k}.id", "ID entero positivo requerido.")
                continue
            if not isinstance(ca, str) or not mt._cas_valido(ca):
                lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", f"componentes.{k}.identidadQuimica.cas",
                         "Identidad quimica sin CAS valido: el nombre no identifica un modelo.", [cid])
                continue
            ids.append(cid)
            cas.append(ca)
        if len(set(ids)) != len(ids):
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "componentes", "IDs de componente repetidos.")
        if len(set(cas)) != len(cas):
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "componentes", "Dos componentes con la misma sustancia.")
    # modelo
    mod = cuerpo.get("modelo")
    mid = ver = None
    if "modelo" in cuerpo:
        if not isinstance(mod, dict) or set(mod) != {"id", "version"}:
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "modelo", "Se espera {id, version}.")
        else:
            mid, ver = mod["id"], mod["version"]
            if motor_mezclas.MODELOS.get(mid) != ver:
                lec.diag("no_soportado", "MOTOR_DIAG_PAQUETE_NO_DISPONIBLE", "modelo",
                         f"El paquete {mid!r} version {ver!r} no admite diagramas binarios; consulta "
                         "/motor/termodinamica/diagramas/capacidades. No se sustituye por otro paquete.")
    # eje, corte, intervalo, resolucion
    eje = cuerpo.get("componenteEjeId")
    if "componenteEjeId" in cuerpo and (isinstance(eje, bool) or not isinstance(eje, int) or (ids and eje not in ids)):
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "componenteEjeId", "Debe ser el ID de uno de los dos componentes.")
    corte = cuerpo.get("corte")
    tipo = fijo = None
    if "corte" in cuerpo:
        if not isinstance(corte, dict) or corte.get("tipo") not in ("Txy", "Pxy"):
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "corte.tipo", "Corte 'Txy' (con P) o 'Pxy' (con T).")
        else:
            tipo = corte["tipo"]
            clave = "P" if tipo == "Txy" else "T"
            if set(corte) != {"tipo", clave}:
                lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "corte",
                         f"Un corte {tipo} lleva exactamente 'tipo' y '{clave}'.")
            else:
                fijo = _cantidad(lec, corte[clave], f"corte.{clave}", clave)
    inter = cuerpo.get("intervaloComposicion")
    if "intervaloComposicion" in cuerpo:
        ok = (isinstance(inter, list) and len(inter) == 2 and
              all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in inter)
              and 0.0 <= inter[0] < inter[1] <= 1.0)
        if not ok:
            lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "intervaloComposicion",
                     "Dos fracciones molares finitas, ordenadas, dentro de [0, 1].")
            inter = None
    perfil = cuerpo.get("resolucion")
    if "resolucion" in cuerpo and perfil not in dg.PERFILES:
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "resolucion", "Perfil 'exploratoria' o 'refinada'.")
    huella_esp = cuerpo.get("huellaModeloEsperada")
    if huella_esp is not None and not isinstance(huella_esp, str):
        lec.diag("invalido", "MOTOR_DIAG_DATO_INVALIDO", "huellaModeloEsperada", "Se espera texto.")
    if lec.estados() & {"invalido", "incompleto", "no_soportado"}:
        est = next(e for e in ("invalido", "no_soportado", "incompleto") if e in lec.estados())
        r = _vacia(sid, est, lec.diags)
        if mid is not None:
            r["identidad"]["modelo"] = {"id": mid, "version": ver}
        return r

    # especies del paquete y parametros: el MISMO Sistema que los estados
    cap = next(c for c in motor_mezclas.capacidades_mezcla() if c["id"] == mid)
    grupos = mz.PAQUETES[mid].liquido.startswith("unifac_")
    for cid, ca in zip(ids, cas):
        # En un paquete de contribucion de grupos, una especie del catalogo que falta en componentesCAS es una
        # especie sin asignacion de grupos: el Sistema la rechaza con su codigo preciso (UNIFAC_*_AUSENTE).
        if ca not in cap["componentesCAS"] and not (grupos and ca in motor_mezclas.md.especies_disponibles()):
            lec.diag("no_soportado", "MOTOR_DIAG_COMPONENTE_NO_SOPORTADO", "componentes",
                     f"El paquete {mid} no tiene datos de componente puro para {ca}.", [cid])
    if lec.diags:
        return _vacia(sid, "no_soportado", lec.diags)
    from core import catalogo
    try:
        sust = catalogo.leer_sustituciones(cuerpo.get("datosPuros"), "datosPuros", cas)
    except catalogo.SustitucionRechazada as x:
        lec.diag("invalido" if x.codigo == "SUSTITUCION_INVALIDA" else "no_soportado", f"MOTOR_DIAG_{x.codigo}",
                 x.ruta, x.mensaje, ids)
        return _vacia(sid, next(e for e in ("invalido", "no_soportado") if e in lec.estados()), lec.diags)
    try:
        sis = mz.Sistema(mid, cas, sust)
    except mz.FaltaParametro as x:
        lec.diag("no_soportado", f"MOTOR_DIAG_{x.codigo}", "componentes", str(x), ids)
        r = _vacia(sid, "no_soportado", lec.diags)
        r["identidad"]["modelo"] = {"id": mid, "version": ver}
        return r
    huella = sis.huella()
    if huella_esp is not None and huella_esp != huella:
        lec.diag("invalido", "MOTOR_DIAG_HUELLA_DISTINTA", "huellaModeloEsperada",
                 f"La huella esperada no coincide con la del paquete actual ({huella}): los datos o parametros "
                 "cambiaron; vuelve a resolver antes de comparar.")
        r = _vacia(sid, "invalido", lec.diags)
        r["identidad"].update(modelo={"id": mid, "version": ver}, huellaModelo=huella)
        return r
    # dominio del corte
    Tlo, Thi = sis.T_rango
    if tipo == "Txy" and not mz.P_MIN <= fijo <= mz.P_MAX:
        lec.diag("no_soportado", "MOTOR_DIAG_FUERA_DE_DOMINIO", "corte.P",
                 f"P = {fijo:.6g} Pa fuera del dominio [{mz.P_MIN:g}, {mz.P_MAX:g}] Pa del paquete (vapor ideal).")
    if tipo == "Pxy" and not Tlo <= fijo <= Thi:
        lec.diag("no_soportado", "MOTOR_DIAG_FUERA_DE_DOMINIO", "corte.T",
                 f"T = {fijo:.6g} K fuera del dominio [{Tlo:.6g}, {Thi:.6g}] K del par en este paquete.")
    if lec.diags:
        r = _vacia(sid, "no_soportado", lec.diags)
        r["identidad"].update(modelo={"id": mid, "version": ver}, huellaModelo=huella)
        return r

    k_eje = ids.index(eje)            # 0: x_eje = x0; 1: x_eje = 1 - x0
    a, b = inter
    inter0 = (a, b) if k_eje == 0 else (1.0 - b, 1.0 - a)
    tr = dg.trazar(sis, tipo, fijo, inter0, perfil)
    return _respuesta(sid, cuerpo, sis, mid, ver, huella, tipo, fijo, ids, cas, eje, k_eje, inter, perfil, tr, lec)


def _firma(mid, ver, huella, cas, tipo, fijo, k_eje, inter, perfil):
    # clave fisica: componente canonico = menor CAS; el eje no forma parte (x -> 1-x conserva la fisica)
    can = 0 if cas[0] <= cas[1] else 1
    a, b = inter
    if k_eje != can:
        a, b = 1.0 - b, 1.0 - a
    datos = {"modelo": [mid, ver], "huella": huella, "cas": sorted(cas), "corte": [tipo, float(f"{fijo:.12g}")],
             "intervalo": [float(f"{a:.12g}"), float(f"{b:.12g}")], "perfil": perfil, "trazador": dg.TRAZADOR}
    return "sha256:" + hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()


def _respuesta(sid, cuerpo, sis, mid, ver, huella, tipo, fijo, ids, cas, eje, k_eje, inter, perfil, tr, lec):
    int_ = tr["intentos"]
    xe = (lambda x0: x0) if k_eje == 0 else (lambda x0: 1.0 - x0)

    def comp(x0):
        return {str(ids[0]): float(x0), str(ids[1]): float(1.0 - x0)}

    def T_P(var):
        return (var, fijo) if tipo == "Txy" else (fijo, var)

    def est_pub(cert):
        e = dict(cert["estabilidad"])
        if "competidora" in e:
            c = e.pop("competidora")
            e["competidora"] = {"tipo": c["tipo"], "composicionMolar": comp(c["composicion"][0]), "tm": c["tm"]}
        return e
    # orden por x del eje
    orden = sorted(int_.values(), key=lambda it: xe(it.x0))
    puntos, pid = [], {}
    for it in orden:
        if it.estado != "cumple":
            continue
        T, P = T_P(it.var)
        p_id = f"p{len(puntos) + 1:04d}"
        pid[it.x0] = p_id
        puntos.append({"id": p_id, "T": float(T), "P": float(P), "xEje": float(xe(it.x0)),
                       "fases": [{"id": "liquido-limite", "tipo": "liquido", "composicionMolar": comp(it.x0)},
                                 {"id": "vapor-limite", "tipo": "vapor", "composicionMolar": comp(it.y0)}],
                       "certificado": {"estado": it.cert["estado"], "residuos": it.cert["residuos"],
                                       "estabilidad": est_pub(it.cert)},
                       "origen": it.origen})
    # segmentos y huecos sobre la secuencia ordenada de intentos
    segmentos, huecos, incid, descart = [], [], [], []
    run, malos = [], []
    a_ped, b_ped = inter

    def cerrar_hueco(x_ini, x_fin, malos_):
        estados = {m.estado for m in malos_}
        motivo = ("no_convergente" if "fallo" in estados else "fuera_de_dominio" if "dominio" in estados else
                  "sin_lv_estable")
        tipo_inc = {"no_convergente": "no_convergente", "fuera_de_dominio": "fuera_de_dominio",
                    "sin_lv_estable": "fase_competidora"}[motivo]
        inc_id = f"i{len(incid) + 1:03d}"
        comp_txt = ""
        if motivo == "sin_lv_estable":
            cs = [m.cert["estabilidad"].get("competidora") for m in malos_ if m.cert]
            cs = [c for c in cs if c]
            if cs:
                c = min(cs, key=lambda c: c["tm"])
                comp_txt = (f" Fase competidora: {c['tipo']} con x_eje = {xe(c['composicion'][0]):.6g} "
                            f"(tm = {c['tm']:.3g}).")
        causa = {"sin_lv_estable": "Los puntos L-V de este tramo convergen (igualdad de mu) pero la prueba de "
                                   "plano tangente encuentra una fase mas estable: no hay coexistencia L-V estable."
                                   + comp_txt,
                 "fuera_de_dominio": "La coexistencia L-V de este tramo queda fuera del dominio del paquete: " +
                                     "; ".join(sorted({m.motivo for m in malos_ if m.motivo}))[:400],
                 "no_convergente": "Ni la continuacion ni la semilla por flash dieron un punto certificado: " +
                                   "; ".join(sorted({m.motivo for m in malos_ if m.motivo}))[:400]}[motivo]
        accion = {"sin_lv_estable": "tramo no publicado como L-V; frontera localizada por biseccion",
                  "fuera_de_dominio": "tramo no publicado; frontera del dominio localizada por biseccion",
                  "no_convergente": "tramo no publicado; sin extrapolar"}[motivo]
        incid.append({"id": inc_id, "tipo": tipo_inc, "intervaloXEje": [float(x_ini), float(x_fin)],
                      "causa": causa, "accion": accion, "referencias": []})
        huecos.append({"intervaloXEje": [float(x_ini), float(x_fin)], "motivo": motivo, "incidenciaIds": [inc_id]})
        for m in malos_:
            T, P = T_P(m.var) if m.var is not None else (None, None)
            if tipo == "Txy" and m.var is None:
                T, P = None, fijo
            if tipo == "Pxy" and m.var is None:
                T, P = fijo, None
            descart.append({"xEje": float(xe(m.x0)), "T": T, "P": P,
                            "motivo": ("metastable: converge con igualdad de mu pero otra fase es mas estable"
                                       if m.estado == "inestable" else (m.motivo or m.estado)),
                            "incidenciaId": inc_id})
    ultimo_bueno = None
    for it in orden:
        if it.estado == "cumple":
            if malos:
                x_ini = xe(ultimo_bueno.x0) if ultimo_bueno is not None else a_ped
                cerrar_hueco(x_ini, xe(it.x0), malos)
                malos = []
            run.append(it)
            ultimo_bueno = it
        else:
            if run:
                segmentos.append(run)
                run = []
            malos.append(it)
    if run:
        segmentos.append(run)
    if malos:
        cerrar_hueco(xe(ultimo_bueno.x0) if ultimo_bueno is not None else a_ped, b_ped, malos)
    if tr["agotado"]:
        hechos = {round(it.x0, 15) for it in orden}
        pend = [xe(x) for x in tr["malla"] if round(x, 15) not in hechos]
        if pend:
            inc_id = f"i{len(incid) + 1:03d}"
            incid.append({"id": inc_id, "tipo": "presupuesto", "intervaloXEje": [min(pend), max(pend)],
                          "causa": "presupuesto de evaluaciones o tiempo agotado", "accion": "se publica lo calculado",
                          "referencias": []})
            huecos.append({"intervaloXEje": [min(pend), max(pend)], "motivo": "presupuesto", "incidenciaIds": [inc_id]})
    if tr["ambiguas"]:
        incid.append({"id": f"i{len(incid) + 1:03d}", "tipo": "rama_ambigua", "intervaloXEje": [a_ped, b_ped],
                      "causa": f"los dos sentidos de recorrido difieren hasta {max(tr['ambiguas']):.3g}",
                      "accion": "se publica el sentido ascendente; revisar", "referencias": []})
    ramas = [{"id": "lv-1", "tipo": "LV", "segmentos": [
        {"id": f"lv-1-s{k + 1}", "puntoIds": [pid[it.x0] for it in seg],
         "xEje": [float(xe(seg[0].x0)), float(xe(seg[-1].x0))]} for k, seg in enumerate(segmentos)]}] if segmentos else []
    # puntos especiales
    esp = []
    for it in orden:
        if it.estado == "cumple" and it.origen == "extremo_puro":
            T, P = T_P(it.var)
            puro = ids[0] if it.x0 >= 1.0 else ids[1]
            esp.append({"id": f"e{len(esp) + 1:03d}", "tipo": "extremo_puro", "T": float(T), "P": float(P),
                        "xEje": float(xe(it.x0)), "puntoId": pid[it.x0],
                        "descripcion": f"saturacion del componente {puro} puro en el mismo paquete"})
    for az, clase in tr["azeotropos"]:
        if az.estado != "cumple":
            continue
        T, P = T_P(az.var)
        esp.append({"id": f"e{len(esp) + 1:03d}", "tipo": "azeotropo", "T": float(T), "P": float(P),
                    "xEje": float(xe(az.x0)), "puntoId": pid.get(az.x0), "clase": clase,
                    "descripcion": f"azeotropo homogeneo L-V refinado con x = y ({clase} de "
                                   f"{'T' if tipo == 'Txy' else 'P'}); igualdad de mu y estabilidad certificadas",
                    "composiciones": {"liquido-limite": comp(az.x0), "vapor-limite": comp(az.y0)},
                    "residuos": az.cert["residuos"], "estabilidad": est_pub(az.cert)})
    for clase_e, bueno, malo in tr["especiales"]:
        T, P = T_P(bueno.var)
        e = {"id": f"e{len(esp) + 1:03d}", "tipo": clase_e, "T": float(T), "P": float(P), "xEje": float(xe(bueno.x0)),
             "puntoId": pid.get(bueno.x0),
             "composiciones": {"liquido-limite": comp(bueno.x0), "vapor-limite": comp(bueno.y0)}}
        if clase_e == "encuentro_otra_fase":
            c = (malo.cert or {}).get("estabilidad", {}).get("competidora")
            if c:
                e["composiciones"]["competidora"] = comp(c["composicion"][0])
            e["descripcion"] = ("limite de la rama L-V: a partir de aqui otra fase (" + (c["tipo"] if c else "?") +
                                ") es mas estable; con la competidora es un encuentro de tres fases (p. ej. L-L-V). "
                                "La region L-L/L-L-V no se traza en esta entrega.")
            e["estabilidad"] = est_pub(malo.cert) if malo.cert else None
        else:
            e["descripcion"] = "limite del dominio del paquete; mas alla no se evalua ni se extrapola"
        esp.append(e)
    # estado
    if not puntos:
        estado = "no_convergente"
    elif any(h["motivo"] in ("no_convergente", "presupuesto", "no_explorado", "fuera_de_dominio") for h in huecos):
        estado = "parcial"
    else:
        estado = "completo"
    for h in huecos:
        if h["motivo"] == "sin_lv_estable":
            lec.diag("aviso", "MOTOR_DIAG_FASE_COMPETIDORA", "corte",
                     f"Sin L-V estable en x_eje [{h['intervaloXEje'][0]:.6g}, {h['intervaloXEje'][1]:.6g}]: otra fase "
                     "es mas estable (ver incidencias).", ids)
        elif h["motivo"] == "presupuesto":
            lec.diag("aviso", "MOTOR_DIAG_PRESUPUESTO", "resolucion", "Presupuesto agotado: resultado parcial.", ids)
        elif h["motivo"] == "fuera_de_dominio":
            lec.diag("aviso", "MOTOR_DIAG_FUERA_DE_DOMINIO", "corte",
                     f"Parte del intervalo cae fuera del dominio del paquete: x_eje [{h['intervaloXEje'][0]:.6g}, "
                     f"{h['intervaloXEje'][1]:.6g}].", ids)
        elif h["motivo"] == "no_convergente":
            lec.diag("aviso", "MOTOR_DIAG_NO_CONVERGENTE", "corte",
                     f"Sin convergencia en x_eje [{h['intervaloXEje'][0]:.6g}, {h['intervaloXEje'][1]:.6g}].", ids)
    pubs = [s_["xEje"] for s_ in (ramas[0]["segmentos"] if ramas else [])]
    pares, lv, _ = _pares(mid)
    par = None
    if pares is not None:
        par = next((p for p in pares if set(p["componentesCAS"]) == set(cas)), None)
    evid = {"combinacion": "liquido_vapor", "nivel": (par["evidencia"] if par else lv["evidencia"]),
            "motivo": (par["motivo"] if par else lv["motivo"]),
            "pares": [{"componentesCAS": list(par["componentesCAS"]), "evidencia": par["evidencia"],
                       "procedencia": par["procedencia"]}] if par else None}
    corteSI = {"tipo": "Txy", "P": float(fijo)} if tipo == "Txy" else {"tipo": "Pxy", "T": float(fijo)}
    return {
        "revision": REVISION, "solicitudId": sid, "estado": estado,
        "identidad": {"modelo": {"id": mid, "version": ver}, "huellaModelo": huella,
                      "firmaConsulta": _firma(mid, ver, huella, cas, tipo, fijo, k_eje, inter, perfil),
                      "trazador": dict(dg.TRAZADOR)},
        "condicion": {"corte": cuerpo["corte"], "corteSI": corteSI,
                      "componentes": [{"id": i, "cas": c} for i, c in zip(ids, cas)], "componenteEjeId": eje,
                      "intervaloComposicion": [float(inter[0]), float(inter[1])], "resolucion": perfil},
        "ramas": ramas, "puntos": puntos, "puntosEspeciales": esp, "candidatosDescartados": descart,
        "incidencias": incid,
        "cobertura": {"intervaloPedido": [float(inter[0]), float(inter[1])], "intervalosPublicados": pubs,
                      "huecos": huecos, "finalizacion": "presupuesto" if tr["agotado"] else "recorrido_completo",
                      "presupuesto": tr["presupuesto"].resumen(), "reproducibilidad": tr["reproducibilidad"]},
        "metodo": ("Continuacion en x del liquido sobre una malla de Chebyshev, en los dos sentidos, desde la "
                   "saturacion del puro del mismo paquete o desde una semilla por flash TP certificado; Newton en "
                   f"({'ln T' if tipo == 'Txy' else 'ln P'}, logit y) sobre la igualdad de mu del paquete; subdivision "
                   "del paso si falla; refinamiento adaptativo por saltos; biseccion de fronteras estable/inestable y "
                   "de dominio; azeotropos por cambio de signo o minimo de |y - x| refinados con x = y. Certificado "
                   "por punto: igualdad de mu (|dmu|/RT <= 1e-10), normalizacion, condicion fija, distincion de "
                   "fases (volumen molar) y plano tangente con la mu comun (tm >= -1e-9; malla, no demostracion del "
                   "minimo global). Las lineas entre puntos son interpolacion visual."),
        "evidencia": evid, "diagnosticos": lec.diags}
