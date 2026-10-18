"""
Genera los ejemplos canonicos solicitud/resultado del nucleo de
adimensionalizacion en docs/ejemplos/adimensionalizacion-*.json.

Son la referencia para el lector del cliente: cada resultado lo produce el
nucleo actual a partir de su solicitud (la suite
tests/validar_adimensionalizacion.py comprueba que siguen coincidiendo).

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_adimensionalizacion.py
"""

import copy
import itertools
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

from casos_adimensionalizacion import (FORMAS_SECCION3, OBJ_K, TERMINO_K, cantidad, d, dim, documento, escala, forma_seccion3,
                                       igualdad, n, neg, objetivo, prod, reaccion_difusion, s, simbolo, solicitud)

DIRECTORIO = RAIZ / "docs" / "ejemplos"


def _seccion3(nombre):
    return lambda: solicitud(forma_seccion3(FORMAS_SECCION3[nombre]))


def _analizar():
    return solicitud(forma_seccion3([]), "analizar")


def _condiciones():
    simb, ecs, doms = reaccion_difusion()
    simb += [simbolo("c0", "parametro", dim(N=1, L=-3)), simbolo("q", "parametro", dim(N=1, L=-2, T=-1)), simbolo("tf", "parametro", dim(T=1))]
    doms += [{"id": "intervalo-t", "variableId": "t", "desde": n(0), "hasta": s("tf")}]
    conds = [{"id": "ci", "tipo": "inicial", "dominioId": "intervalo-t", "ecuacion": igualdad("ci-eq", s("c"), s("c0"))},
             {"id": "flujo", "tipo": "flujo", "dominioId": "intervalo-x", "ecuacion": igualdad("flujo-eq", neg(prod(s("D"), d(s("c"), "x"))), s("q"))}]
    from casos_adimensionalizacion import OBJ_A
    return solicitud(documento(simb, ecs, [escala("t"), escala("c"), escala("x")], [OBJ_K, OBJ_A], dominios=doms, condiciones=conds))


def _parcial():
    simb, ecs, doms = reaccion_difusion()
    return solicitud(documento(simb, ecs, [escala("t", cantidad(2, "s")), escala("c", transformar=False), escala("x", cantidad(1, "cm"))], dominios=doms))


def _signo_negativo():
    return solicitud(forma_seccion3([objetivo("lineal", "balance", TERMINO_K, -1)], signo_k="negativo"))


def _suma_incompatible():
    simb, ecs, doms = reaccion_difusion()
    ecs[0]["derecha"]["argumentos"].append(s("a"))
    return solicitud(documento(simb, ecs, [escala("t"), escala("c"), escala("x")]))


def _forma_desactualizada():
    doc = forma_seccion3([OBJ_K])
    doc["modelo"]["revision"] = 2
    return solicitud(doc)


def _explorar():
    from core.adimensionalizacion import procesar
    doc = forma_seccion3([])
    tids = [t["id"] for t in procesar(solicitud(doc, "analizar"))["terminos"]]
    propuestas = [{"id": "propuesta-0", "estado": "sin_evaluar", "objetivos": []}]
    for k in range(1, 4):
        for comb in itertools.combinations(tids, k):
            propuestas.append({"id": f"propuesta-{len(propuestas)}", "estado": "sin_evaluar",
                               "objetivos": [{"terminoId": t, "operacion": "normalizar_magnitud_coeficiente", "conservarSigno": True} for t in comb]})
    config = {"presupuesto": 200, "maxObjetivos": 3, "respetarEscalasFijadas": True, "incluirGruposPi": True, "maxExponentePi": 4, "maxDenominadorPi": 4}
    return {"formato": "solicitud_exploracion_adimensional", "version": 1, "documentoId": doc["id"], "modelo": copy.deepcopy(doc["modelo"]),
            "formaBase": copy.deepcopy(doc["formas"][0]), "config": config,
            "terminos": [], "propuestas": propuestas,
            "cobertura": {"combinacionesEnAlcance": str(len(propuestas)), "propuestasPreparadas": len(propuestas), "limitadoPorPresupuesto": False,
                          "orden": "numero_de_objetivos_y_orden_del_modelo", "alcance": "terminos_aditivos_explicitos_sin_desarrollar_productos"},
            "politica": {"incluirFamiliasLibres": True, "resolverPorRango": True, "deduplicarTrasResolver": True}}


def _con_mapas(doc, mapas, operacion="transformar"):
    sol = solicitud(doc, operacion)
    sol["transformaciones"] = mapas
    return sol


def _constante(i, papel="escala", valor=None):
    return {"id": i, "nombre": i, "papel": papel, "dimension": None, "valor": valor or {"tipo": "libre"}}


def _mapa_log():
    from casos_adimensionalizacion import coc, fun
    simb, ecs, doms = reaccion_difusion()
    mapa = {"variableId": "c", "nuevoId": "u", "directa": prod(s("C"), fun("exp", s("u"))), "inversa": fun("log", coc(s("c"), s("C"))),
            "constantes": [_constante("C")], "dominio": {"original": "positivo", "nuevo": None}}
    return _con_mapas(documento(simb, ecs, [escala("t"), escala("x")], dominios=doms), [mapa])


def _mapa_afin():
    from casos_adimensionalizacion import coc, suma
    simb = [simbolo("t", "tiempo", dim(T=1)), simbolo("T", "campo", None, ["t"], unidad="degC"), simbolo("k", "parametro", dim(T=-1)),
            simbolo("Ta", "parametro", dim(Theta=1))]
    ec = igualdad("enfriamiento", d(s("T"), "t"), neg(prod(s("k"), suma(s("T"), neg(s("Ta"))))))
    mapa = {"variableId": "T", "nuevoId": "theta", "directa": suma(s("Tr"), prod(s("dT"), s("theta"))), "inversa": coc(suma(s("T"), neg(s("Tr"))), s("dT")),
            "constantes": [_constante("Tr", "referencia", cantidad(25, "degC")), _constante("dT", "escala", cantidad(10, "K"))],
            "dominio": {"original": None, "nuevo": None}}
    return _con_mapas(documento(simb, [ec], [escala("t")]), [mapa])


def _automatico():
    simb, ecs, doms = reaccion_difusion()
    return solicitud(documento(simb, ecs, [], dominios=doms), "adimensionalizar")


def _requiere_datos():
    simb, ecs, doms = reaccion_difusion()
    return solicitud(documento([dict(x, dimension=None) for x in simb], ecs, [], dominios=doms), "adimensionalizar")


def _v2_funcion_escalada():
    """Documento v2: D(c) = Dstar Dh(u) y objetivo por terminoId sobre la divergencia."""
    from casos_adimensionalizacion import div, grad, llam
    simb = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
            simbolo("Dstar", "parametro", None)]
    fD = {"id": "Dc", "nombre": "D", "entradas": [dim(N=1, L=-3)], "salida": dim(L=2, T=-1), "dependeDe": [],
          "escala": {"simboloId": "Dstar", "funcionAdimensional": "Dh"}}
    ec = igualdad("balance", d(s("c"), "t"), div(prod(llam("Dc", s("c")), grad(s("c"), "x")), "x"))
    doc = documento(simb, [ec], [escala("t"), escala("c"), escala("x")], funciones=[fD])
    doc["version"] = 2
    doc["formas"][0]["objetivos"] = [{"id": "difusion", "ecuacionId": "balance", "terminoId": "balance:ecuaciones[0].derecha", "valor": 1, "accion": "normalizar"}]
    return solicitud(doc)


def _v2_referencias_ubicacion():
    """Documento v2: condiciones ubicadas, referencia de factor global en el
    flujo, prioridad de escalas y objetivo por terminoId."""
    simb, ecs, doms = reaccion_difusion()
    simb += [simbolo("c0", "parametro", dim(N=1, L=-3)), simbolo("q", "parametro", dim(N=1, L=-2, T=-1)), simbolo("tf", "parametro", dim(T=1))]
    doms += [{"id": "intervalo-t", "variableId": "t", "desde": n(0), "hasta": s("tf")}]
    conds = [{"id": "ci", "tipo": "inicial", "dominioId": "intervalo-t", "ecuacion": igualdad("ci-eq", s("c"), s("c0")),
              "ubicacion": {"variableId": "t", "extremo": "desde"}},
             {"id": "flujo", "tipo": "flujo", "dominioId": "intervalo-x", "ecuacion": igualdad("flujo-eq", neg(prod(s("D"), d(s("c"), "x"))), s("q")),
              "ubicacion": {"variableId": "x", "extremo": "hasta"}}]
    doc = documento(simb, ecs, [escala("t"), escala("c"), escala("x")], dominios=doms, condiciones=conds)
    doc["version"] = 2
    forma = doc["formas"][0]
    forma["objetivos"] = [{"id": "difusion", "ecuacionId": "balance", "terminoId": "balance:ecuaciones[0].derecha.argumentos[0]", "valor": 1, "accion": "normalizar"}]
    forma["referencias"] = [{"ecuacionId": "flujo", "terminoId": "flujo:condiciones[1].ecuacion.derecha"}]
    forma["prioridadEscalas"] = ["x"]
    return solicitud(doc)


def _estudio_calor():
    """estudiar: calor 1D con Dirichlet en ambos extremos (v2) y simulacion."""
    from casos_adimensionalizacion import coc, fun, lap
    simb = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)), simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
            simbolo("D", "parametro", dim(L=2, T=-1)), simbolo("ell", "parametro", dim(L=1)), simbolo("c0", "parametro", dim(N=1, L=-3)),
            simbolo("tf", "parametro", dim(T=1))]
    TERM = prod(s("D"), lap(s("c"), "x"))
    conds = [{"id": "ci", "tipo": "inicial", "dominioId": "it", "ecuacion": igualdad("ci-eq", s("c"), prod(s("c0"), fun("sin", prod(n(3.141592653589793), coc(s("x"), s("ell"))))))},
             {"id": "izq", "tipo": "dirichlet", "dominioId": "ix", "ecuacion": igualdad("izq-eq", s("c"), n(0)), "ubicacion": {"variableId": "x", "extremo": "desde"}},
             {"id": "der", "tipo": "dirichlet", "dominioId": "ix", "ecuacion": igualdad("der-eq", s("c"), n(0)), "ubicacion": {"variableId": "x", "extremo": "hasta"}}]
    doms = [{"id": "ix", "variableId": "x", "desde": n(0), "hasta": s("ell")}, {"id": "it", "variableId": "t", "desde": n(0), "hasta": s("tf")}]
    doc = documento(simb, [igualdad("balance", d(s("c"), "t"), TERM)], [escala("t"), escala("c"), escala("x")], [objetivo("dif", "balance", TERM)],
                    dominios=doms, condiciones=conds)
    doc["version"] = 2
    sol = solicitud(doc)
    sol["operacion"] = "estudiar"
    sol["estudio"] = {"valores": [{"simboloId": "D", "valor": 1e-9, "unidad": "m^2/s"}, {"simboloId": "ell", "valor": 1, "unidad": "cm"},
                                  {"simboloId": "c0", "valor": 50, "unidad": "mol/m^3"}, {"simboloId": "tf", "valor": 1, "unidad": "s"},
                                  {"simboloId": "x_ref", "valor": 1, "unidad": "cm"}, {"simboloId": "c_ref", "valor": 50, "unidad": "mol/m^3"}],
                      "simulacion": {"tFinal": 0.2, "nodos": 21, "muestras": 6, "verificarMalla": False}}
    return sol


def _estudio_brusselator():
    """estudiar: Brusselator con B > B_Turing (estabilidad, simetrias, asintotica)."""
    from casos_adimensionalizacion import lap, pot, suma
    sim = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)),
           simbolo("u", "campo", {}, ["t", "x"], signo="positivo"), simbolo("w", "campo", {}, ["t", "x"], signo="positivo"),
           simbolo("k", "parametro", dim(T=-1)), simbolo("A", "parametro", {}), simbolo("B", "parametro", {}),
           simbolo("Du", "parametro", dim(L=2, T=-1)), simbolo("Dw", "parametro", dim(L=2, T=-1))]
    T_UUW = prod(s("k"), pot(s("u"), 2), s("w"))
    T_DU = prod(s("Du"), lap(s("u"), "x"))
    ecu = igualdad("u", d(s("u"), "t"), suma(prod(s("k"), s("A")), neg(prod(s("k"), suma(s("B"), n(1)), s("u"))), T_UUW, T_DU))
    ecw = igualdad("w", d(s("w"), "t"), suma(prod(s("k"), s("B"), s("u")), neg(T_UUW), prod(s("Dw"), lap(s("w"), "x"))))
    doc = documento(sim, [ecu, ecw], [escala("t"), escala("x"), escala("u", transformar=False), escala("w", transformar=False)],
                    [objetivo("reac", "u", T_UUW), objetivo("dif", "u", T_DU)])
    sol = solicitud(doc)
    sol["operacion"] = "estudiar"
    sol["estudio"] = {"valores": [{"simboloId": "k", "valor": 1, "unidad": "1/s"}, {"simboloId": "A", "valor": 2}, {"simboloId": "B", "valor": 3},
                                  {"simboloId": "Du", "valor": 1e-9, "unidad": "m^2/s"}, {"simboloId": "Dw", "valor": 1e-8, "unidad": "m^2/s"}],
                      "analisis": ["estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias", "estabilidad"]}
    return sol


def _estudio_pliegues():
    """estudiar: continuacion de u' = k (p + u - u^3), pliegues en p = +-2/(3 sqrt 3)."""
    from casos_adimensionalizacion import pot, suma
    sim = [simbolo("t", "tiempo", dim(T=1)), simbolo("u", "campo", {}, ["t"]), simbolo("k", "parametro", dim(T=-1)),
           simbolo("p", "parametro", {}, signo="desconocido")]
    T_KU = prod(s("k"), s("u"))
    doc = documento(sim, [igualdad("e", d(s("u"), "t"), suma(prod(s("k"), s("p")), T_KU, neg(prod(s("k"), pot(s("u"), 3)))))],
                    [escala("t"), escala("u", transformar=False)], [objetivo("k", "e", T_KU)])
    sol = solicitud(doc)
    sol["operacion"] = "estudiar"
    sol["estudio"] = {"valores": [{"simboloId": "k", "valor": 1, "unidad": "1/s"}, {"simboloId": "p", "valor": 0.0}],
                      "analisis": ["estabilidad", "continuacion"], "continuacion": {"parametroId": "p", "desde": -1, "hasta": 1}, "cajaEstados": 3}
    return sol


EJEMPLOS = {
    "automatico": _automatico,
    "requiere-datos": _requiere_datos,
    "mapa-logaritmico": _mapa_log,
    "mapa-afin-temperatura": _mapa_afin,
    "analizar": _analizar,
    "general": _seccion3("general"),
    "tiempo-difusivo": _seccion3("tiempo-difusivo"),
    "tiempo-reactivo": _seccion3("tiempo-reactivo"),
    "campo-cinetico": _seccion3("campo-cinetico"),
    "longitud-parametrica": _seccion3("longitud-parametrica"),
    "condiciones": _condiciones,
    "parcial": _parcial,
    "signo-negativo": _signo_negativo,
    "rechazo-suma-incompatible": _suma_incompatible,
    "rechazo-forma-desactualizada": _forma_desactualizada,
    "explorar": _explorar,
    "v2-funcion-escalada": _v2_funcion_escalada,
    "v2-referencias-ubicacion": _v2_referencias_ubicacion,
    "estudio-calor": _estudio_calor,
    "estudio-brusselator": _estudio_brusselator,
    "estudio-pliegues": _estudio_pliegues,
}


def main():
    from core.adimensionalizacion import procesar
    DIRECTORIO.mkdir(parents=True, exist_ok=True)
    for nombre, construir in EJEMPLOS.items():
        sol = construir()
        res = procesar(copy.deepcopy(sol))
        for sufijo, dato in (("solicitud", sol), ("resultado", res)):
            ruta = DIRECTORIO / f"adimensionalizacion-{nombre}-{sufijo}.json"
            with open(ruta, "w", encoding="utf-8", newline="\n") as f:
                json.dump(dato, f, ensure_ascii=False, indent=1)
                f.write("\n")
        print(f"{nombre}: {res['estado']}")


if __name__ == "__main__":
    main()
