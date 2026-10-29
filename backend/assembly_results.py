"""Shared certified trajectory publication for native v2 and the common compiler.

The existing v2 publication equations, thresholds and state packaging are reused
unchanged. This module never validates a request or invokes an integrator.
"""
import numpy as np
import scipy
from core import ensamblaje_red as er
from core import mezclas as mz
from core import paquetes_volumen as pv
from core import expresiones_motor as expressions
from core.dynamic_common import Detencion


def publish(ctx, val, red, sis, tray, *, capture_sample=None, method="RK45 Dormand-Prince 5(4)", expected_failures=()):
    # Transitional reuse of existing packaging helpers; no second implementation.
    from backend.motor_ensamblaje_v2 import (
        evaluacion_volumen, potenciales, _seguir_ids, _certificacion,
        _procedencia, _DESCRIPCION_EVENTO, REVISION)
    vols, comps, est = ctx['vols'], ctx['comps'], ctx['est']
    vsi, csi, isi = red.volumenes, red.corrientes, red.intercambios
    tf = red.tf
    gidx = {c: k for k, c in enumerate(comps)}
    diags = val['diagnosticos']
    sample_errors = (mz.FueraDeAlcance, Detencion, expressions.ErrorExpresion) + expected_failures
    def rechazo(estado):
        return {'revision': REVISION, 'validacion': val, 'estado': estado, 'resultados': None}
    # muestras certificadas
    tiempos, filas, estados = [], [], {v.id: [] for v in vsi}
    detenida = tray.detenida
    semillas = [ctx["ini"][v.id]["estado"] for v in vsi]
    ids_previos = [None] * len(vsi)
    ids_usados = [set() for _ in vsi]
    ids_muestra = {v.id: [] for v in vsi}
    for t, y in er.muestras(red, tray):
        try:
            evs = []
            for j, v in enumerate(vsi):
                event_context = tray.phase_event_states.get(t)
                seed = event_context[j] if event_context is not None else semillas[j]
                e = (v.paquete.certify_state(seed) if event_context is not None and isinstance(v.paquete, pv.PaqueteMezcla)
                     else sis.estado_vol(t, y, j, certificar=True, semilla=seed))
                if event_context is not None and er.firma(e) != er.firma(event_context[j]):
                    raise mz.FueraDeAlcance("no_convergente", "The certified event state disagrees with the located phase transition.")
                evs.append(e)
            evals = []
            for j, v in enumerate(vsi):
                e = evs[j]
                _seguir_ids(e, ids_previos, j, ids_usados[j])
                ev = evaluacion_volumen(v.paquete, e, vols[j]["comp"], v.politica)
                if any(x["estado"] == "no_cumple" for x in ev["verificaciones"]):
                    raise mz.FueraDeAlcance("no_convergente", f"Volumen {v.id}: verificación no cumplida.")
                evals.append({"volumenId": v.id, "evaluacion": ev, "potenciales": potenciales(e, v.paquete, vols[j]["comp"])})
            fl = sis.flujos(t, y, evs)
            sis.calores(t, evs)
            if capture_sample is not None:
                capture_sample(t, y, evs)
        except sample_errors as x:
            diags.append({"codigo": "MOTOR_ENS_MUESTRA_NO_CERTIFICADA", "estado": "invalido",
                          "mensaje": f"t = {t:.9g} s: {getattr(x, 'mensaje', str(x))}", "variableIds": [],
                          "origen": {"propietarioId": "red", "ruta": "/estudio"}})
            detenida = detenida or Detencion("muestra_no_certificada", "", t)
            break
        semillas = evs
        tiempos.append(t)
        filas.append((t, y, evs, fl))
        for j, v in enumerate(vsi):
            estados[v.id].append(evals[j])
            ids_muestra[v.id].append([f.id for f in evs[j].fases])
    if not filas:
        d = tray.detenida
        if d is not None and d.t == 0.0:
            # la red no puede arrancar (p. ej. extraer una fase ausente): el motivo es la detencion, no una
            # falta de convergencia; se publica como tal y la respuesta es invalida, sin muestras
            diags.append({"codigo": f"MOTOR_ENS_DETENIDO_{d.codigo.upper()}", "estado": "invalido",
                          "mensaje": f"La red no puede arrancar en t = 0: {d.mensaje}", "variableIds": [],
                          "origen": {"propietarioId": "red", "ruta": "/corrientes"}})
            return rechazo("invalido")
        return rechazo("no_convergente")
    series = []
    catalogo = []
    vars_val = {x["id"] for x in val.get("variables") or []}

    def serie(id_, uni, vals, magnitud, papel, propietario, procedencia):
        series.append({"variableId": id_, "unidadSI": uni, "valores": [float(x) for x in vals]})
        catalogo.append({"variableId": id_, "propietarioId": propietario, "unidadSI": uni, "magnitud": magnitud,
                         "papel": papel, "variableEnsamblajeId": id_ if id_ in vars_val else None,
                         "procedencia": procedencia})
    for j, v in enumerate(vsi):
        pref = f"volumen.{v.id}"
        pv_ = f"volumen:{v.id}"
        o = sis.offs[j]
        for k, c in enumerate(vols[j]["comp"]):
            serie(f"{pref}.n.{c}", "mol", [f[1][o + k] for f in filas], "cantidad", "estado_integrado", pv_,
                  f"estado diferencial: balance de materia del componente {c} en {v.id}")
        if v.frontera == "rigida":
            serie(f"{pref}.U", "J", [f[2][j].U for f in filas], "energia", "estado_integrado", pv_,
                  "estado diferencial (frontera rigida); valor del estado certificado de la muestra")
        else:
            serie(f"{pref}.U", "J", [f[2][j].U for f in filas], "energia", "algebraica", pv_,
                  "U = H - P V del estado certificado")
            serie(f"{pref}.H", "J", [f[1][o + len(v.comp)] for f in filas], "energia", "estado_integrado", pv_,
                  "estado diferencial (presion prescrita): dH/dt = J_E + V dP/dt")
            serie(f"{pref}.W", "J", [f[1][sis.i_W + j] for f in filas], "energia", "integral_auxiliar", pv_,
                  "trabajo de frontera acumulado int P dV/dt dt (no es un estado del sistema fisico)")
        serie(f"{pref}.T", "K", [f[2][j].T for f in filas], "temperatura", "algebraica", pv_,
              "cierre de equilibrio del paquete (estado certificado)")
        serie(f"{pref}.P", "Pa", [f[2][j].P for f in filas], "presion", "algebraica" if v.frontera == "rigida" else "dato",
              pv_, "cierre de equilibrio del paquete" if v.frontera == "rigida" else "presion prescrita (dato)")
        serie(f"{pref}.V", "m3", [f[2][j].V for f in filas], "volumen", "dato" if v.frontera == "rigida" else "algebraica",
              pv_, "volumen geometrico (dato)" if v.frontera == "rigida" else "cierre de equilibrio del paquete")
        serie(f"{pref}.masa", "kg", [f[2][j].masa for f in filas], "masa", "derivada", pv_,
              "sum_i n_i M_i con las masas molares del paquete; presentacion, sin ecuacion propia")
        serie(f"{pref}.S", "J/K", [f[2][j].S for f in filas], "entropia", "derivada", pv_,
              "entropia del estado certificado (referencia del paquete); presentacion, sin ecuacion propia")
    for s_ in csi:
        serie(f"corriente.{s_.id}.ndot", "mol/s",
              [next((ndot if (o_ == s_.desde) else -ndot) for c_, ndot, o_, d_, *_ in f[3] if c_ is s_) for f in filas],
              "caudal_molar", "algebraica", f"corriente:{s_.id}",
              "caudal molar total en el sentido declarado desde -> hasta (negativo: invertido)")
    for q in isi:
        serie(f"calor.{q.id}.Q", "W", [next(Q for q_, Q in sis.calores(f[0], f[2]) if q_ is q) for f in filas],
              "potencia", "dato" if q.ley == "impuesto" else "algebraica", f"calor:{q.id}",
              "potencia impuesta (dato)" if q.ley == "impuesto" else "Q = G (T_desde - T_hasta)")
    # residuos (max sobre la trayectoria) y su valor por muestra, para la certificacion
    U0 = sum(ctx["ini"][v.id]["U"] for v in vsi)
    escala_n = est["atol"]["cantidad"] + est["rtol"] * max(
        float(sum(np.sum(f[1][sis.offs[j]:sis.offs[j] + len(v.comp)]) for j, v in enumerate(vsi))) for f in filas)
    P0V0 = [filas[0][2][j].P * filas[0][2][j].V for j in range(len(vsi))]

    def W_partes(f, j):
        # trabajo de frontera por partes: int P dV = [P V] - int V dP/dt dt (sin derivar V)
        return 0.0 if vsi[j].frontera == "rigida" else f[2][j].P * f[2][j].V - P0V0[j] - f[1][sis.i_VdP + j]
    # escala de energia: la mayor de |U|, |int E_ext| y |W| a lo largo de la trayectoria (no solo |U|, que
    # depende del cero de la referencia y puede pasar por 0)
    escala_E = est["atol"]["energia"] + est["rtol"] * max(
        max(abs(sum(e.U for e in f[2])) for f in filas), max(abs(f[1][sis.i_E]) for f in filas),
        max(abs(sum(W_partes(f, j) for j in range(len(vsi)))) for f in filas), 1.0)
    residuos, por_muestra = [], {}

    def residuo(id_, valores, tol, definicion):
        por_muestra[id_] = (valores, tol)
        residuos.append({"ecuacionId": id_, "maximoEscalado": float(max(valores)), "tolerancia": tol,
                         "definicion": definicion})
    for c in comps:
        g = gidx[c]
        n0 = sum(v.n0[v.comp.index(g)] for v in vsi if g in v.comp)
        residuo(f"global.materia.{c}",
                [abs(sum(f[1][sis.offs[j] + v.comp.index(g)] for j, v in enumerate(vsi) if g in v.comp)
                     - n0 - f[1][sis.i_mat + g]) / escala_n for f in filas], 10.0,
                "max_t |sum_v n_v,i - n_i(0) - int ndot_ext,i dt| / (atol + rtol max_t sum_v,i n); las "
                "transferencias internas se suman y restan como el mismo número")
    residuo("global.energia",
            [abs(sum(e.U for e in f[2]) - U0 - (f[1][sis.i_E] - sum(W_partes(f, j) for j in range(len(vsi)))))
             / escala_E for f in filas], 10.0,
            "max_t |sum U_v - U(0) - (int E_ext dt - sum W_v)| / (atol + rtol max_t(|sum U|, |int E_ext|, |sum W|)), "
            "con W_v = [P V] - int V dP/dt dt: U de los estados certificados frente a la contabilidad de "
            "transferencias exteriores y trabajo")
    for j, v in enumerate(vsi):
        if v.frontera == "rigida":
            continue
        escala_W = est["atol"]["energia"] + 1e-5 * max(max(abs(W_partes(f, j)) for f in filas),
                                                       max(abs(f[2][j].P * f[2][j].V) for f in filas) * 1e-3)
        residuo(f"mecanica.{v.id}.trabajo", [abs(f[1][sis.i_W + j] - W_partes(f, j)) / escala_W for f in filas], 1.0,
                "max_t |int P dV/dt dt (dV/dt total de V(H, P, n) por diferencia centrada) - ([P V] - int V dP)| / "
                "(atol + 1e-5 max|W|): verifica la derivada total de V (diferencia centrada, integrada a traves de "
                "las aristas de cambio de fase; acuerdo medido ~2e-6 relativo, tolerancia 1e-5 declarada)")
    for j, v in enumerate(vsi):
        o = sis.offs[j]
        m = len(v.comp)
        residuo(f"estado.{v.id}.energia",
                [abs((f[2][j].U if v.frontera == "rigida" else f[2][j].H) - f[1][o + m]) / escala_E for f in filas], 1.0,
                "max |E del estado certificado - E integrada| / escala de energia")
        if v.frontera == "rigida":
            residuo(f"estado.{v.id}.volumen", [abs(f[2][j].V - v.V) / v.V / 1e-9 for f in filas], 1.0,
                    "max |V del estado - V geométrico| / V / 1e-9")
    # segunda ley
    S0 = sum(e.S for e in filas[0][2])
    gen = [sum(e.S for e in f[2]) - S0 - f[1][sis.i_S] for f in filas]
    tol_S = est["atol"]["energia"] / 300.0 + est["rtol"] * max(abs(S0), 1.0) * 10
    primera_S = None
    if not sis.segunda_ley_evaluable:
        sl = {"estado": "no_evaluable", "motivo": "Hay intercambios de calor con el exterior sin temperatura de frontera "
              "(temperaturaFronteraId): no se sustituye por la T del fluido.", "generacionMinima": None,
              "tolerancia": None, "unidad": "J/K"}
    else:
        dif = [gen[k] - gen[k - 1] for k in range(1, len(gen))]
        mn = min([0.0] + gen + dif)
        sl = {"estado": "cumple" if mn >= -tol_S else "no_cumple",
              "motivo": "S_gen(t) = sum_v S_v(t) - S(0) - int (sum ndot s + Q/T_frontera)_ext dt evaluada en las "
                        "muestras certificadas: debe ser >= 0 y no decreciente. Contactos internos y mezcla de "
                        "corrientes generan entropía dentro del conjunto; no se exige que cada volumen abierto la aumente.",
              "generacionMinima": float(mn), "tolerancia": float(tol_S), "unidad": "J/K"}
        primera_S = next((k for k in range(len(gen)) if gen[k] < -tol_S or (k > 0 and gen[k] - gen[k - 1] < -tol_S)),
                         None)
        serie("red.Sgen", "J/K", gen, "entropia", "derivada", "red",
              "S_gen(t) de la segunda ley (ver segundaLey); presentacion, sin ecuacion propia")
    # eventos con los IDs reales de las fases que aparecen o desaparecen
    eventos = []
    for c, t, j, msj in tray.eventos:
        if t > tiempos[-1]:
            continue
        ev_ = {"codigo": c, "tiempo": t, "volumenId": vsi[j].id if j is not None else None, "faseIds": [],
               "variableIds": [f"volumen.{vsi[j].id}.fases"] if j is not None else []}
        if j is not None:
            k = next((k for k, tk in enumerate(tiempos) if abs(tk - t) <= 1e-12 * max(tf, 1.0)), None)
            if k is not None and k > 0:
                antes, despues = ids_muestra[vsi[j].id][k - 1], ids_muestra[vsi[j].id][k]
                ev_["faseIds"] = sorted(set(antes) ^ set(despues))
                ev_["faseIdsAntes"], ev_["faseIdsDespues"] = list(antes), list(despues)
        ev_["descripcion"] = _DESCRIPCION_EVENTO.get(c, msj)
        eventos.append(ev_)
    if tray.detenida is not None:
        d = tray.detenida
        diags.append({"codigo": f"MOTOR_ENS_DETENIDO_{d.codigo.upper()}", "estado": "invalido",
                      "mensaje": f"Trayectoria detenida en t = {d.t:.9g} s: {d.mensaje}", "variableIds": [],
                      "origen": {"propietarioId": "red", "ruta": "/volumenes"}})
    cert = _certificacion(por_muestra, sl, primera_S, tiempos, tf, detenida, estados)
    if cert["estado"] == "no_cumple":
        diags.append({"codigo": "MOTOR_ENS_CERTIFICACION_NO_CUMPLE", "estado": "invalido",
                      "mensaje": "La trayectoria se calculó, pero no está físicamente certificada: " + cert["motivo"],
                      "variableIds": [], "origen": {"propietarioId": "red", "ruta": "/resultados/certificacion"}})
    metodo = (f"{method} (scipy {scipy.__version__}), rtol {est['rtol']:g}, atol cantidad "
              f"{est['atol']['cantidad']:g} mol, atol energía {est['atol']['energia']:g} J; {tray.pasos} pasos, "
              f"{tray.reintentos} reintentos. Estados por volumen: n_i y U (rígido) o H (presión prescrita). Etapas "
              "con flashes con semilla; muestras certificadas con prueba de estabilidad completa. Eventos de fase "
              "vigilados en 3 puntos interiores y el extremo de cada paso aceptado (vigilancia puntual, no continua).")
    return {"revision": REVISION, "validacion": val, "estado": "parcial" if detenida is not None else "resuelto",
            "resultados": {"metodo": metodo, "tiempos": [float(t) for t in tiempos], "series": series,
                           "estados": estados, "eventos": eventos, "residuos": residuos, "segundaLey": sl,
                           "catalogoSeries": catalogo, "certificacion": cert,
                           "procedenciaModelo": _procedencia(vols)}}

