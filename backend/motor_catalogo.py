"""
Catalogo publicado del motor (F2.1-F2.3, revision 1): GET /motor/catalogo.

Una sola fuente para descubrir que sustancias hay, con que datos y procedencia, y en que paquetes y operaciones
estan admitidas. Se construye a partir de:
  * core/catalogo.REGISTRO (identidad y procedencia) y core/mezclas_datos.especie (datos puros realmente usados);
  * core/catalogo.faltantes (regla UNICA de admision por especie, la que aplica el Sistema);
  * las capacidades ya publicadas de cada ruta (estado puntual, ensamblaje v2, diagramas) para las operaciones.
No duplica la fisica ni los limites numericos: los tamanos admitidos/contrastados siguen en sus rutas.
Contrato: docs/contratos/contratoCatalogo.ts. Documento: docs/MOTOR_CATALOGO_PROPIEDADES.md.
"""

import copy
import dataclasses
import functools
import hashlib
import json

from core import catalogo
from core import mezclas as mz
from core import mezclas_datos as md

REVISION = catalogo.REVISION


def huella_datos_puros(cas):
    """sha256 de los datos puros con que se construye la especie (los mismos que entran en la huella del
    paquete): cambia si cambia cualquier coeficiente, rango, v_L, M o fuente."""
    texto = json.dumps(dataclasses.asdict(md.especie(cas)), sort_keys=True, separators=(",", ":"), default=repr)
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _sustancia(cas):
    r = catalogo.REGISTRO[cas]
    falt = md.datos_puros_faltantes(cas)
    sal = {"id": cas, "cas": cas, "nombre": r.nombre,
           "masaMolar": {"valor": r.M, "unidad": "kg/mol", "fuente": r.fuente_M},
           "datosPuros": {"estado": "completos" if not falt else "incompletos",
                          "faltantes": [{"dato": d, "motivo": m} for d, m in falt]}}
    if falt:
        return sal
    e = md.especie(cas)
    sal["datosPuros"].update({
        "propiedades": [
            {"id": "presion_vapor", "unidad": "Pa", "forma": f"Wagner ({e.psat_forma})", "fuente": md.fuente_psat(e),
             "coeficientes": {"A": e.psat[0], "B": e.psat[1], "C": e.psat[2], "D": e.psat[3], "Tc": e.psat[4],
                              "Pc": e.psat[5]},
             "dominio": {"T": list(e.T_psat)}},
            {"id": "cp_gas_ideal", "unidad": "J/(mol K)", "forma": "cp/R = a0 + a1 T + a2 T^2 + a3 T^3 + a4 T^4",
             "fuente": "Poling, The Properties of Gases and Liquids 5a ed., apendice A (chemicals)",
             "coeficientes": {f"a{k}": a for k, a in enumerate(e.cp)}, "dominio": {"T": list(e.T_cp)}},
            {"id": "volumen_liquido", "unidad": "m3/mol", "valor": e.vL, "condicion": "298.15 K; liquido incompresible",
             "fuente": e.fuente_vL},
        ],
        "dominioLiquido": {"T": list(e.T_rango),
                           "motivo": "interseccion de los rangos de Psat y cp y T <= 0.9 Tc"},
        "huella": huella_datos_puros(cas)})
    return sal


def _operaciones():
    """Operaciones publicadas por paquete, tomadas de las capacidades de cada ruta."""
    from backend import motor_diagramas, motor_ensamblaje_v2, motor_termodinamica
    estado = {m["id"]: {"especificaciones": list(m["especificaciones"]), "version": m["version"], "nombre": m["nombre"],
                        "componentesCAS": list(m["componentesCAS"])}
              for m in motor_termodinamica.capacidades()["modelos"]}
    ens = {p["modelo"]["id"]: p for p in motor_ensamblaje_v2.capacidades_v2()["paquetes"]}
    diag = {p["modelo"]["id"]: p for p in motor_diagramas.capacidades()["paquetes"]}
    return estado, ens, diag


def _liquido(mid):
    if mid.startswith("agua-iapws95"):
        return "iapws95"
    return mz.PAQUETES[mid].liquido


@functools.lru_cache(maxsize=1)
def _catalogo():
    estado, ens, diag = _operaciones()
    sustancias = [_sustancia(c) for c in catalogo.sustancias()]
    paquetes = []
    for mid, info in estado.items():
        liq = _liquido(mid)
        especies = []
        for c in catalogo.sustancias():
            f = catalogo.faltantes(liq, c, mid)
            especies.append({"cas": c, "admitida": not f,
                             "faltantes": [{"dato": x["dato"], "codigo": x["codigo"], "mensaje": x["mensaje"]} for x in f]})
        admitidas = [e["cas"] for e in especies if e["admitida"]]
        # coherencia: lo admitido por la regla es exactamente lo que publica la ruta de estado
        assert sorted(admitidas) == sorted(info["componentesCAS"]), (mid, admitidas, info["componentesCAS"])
        ops = {"estado": {"especificaciones": info["especificaciones"]},
               "ensamblaje": {"disponible": bool(ens.get(mid, {}).get("dinamica"))},
               "diagramas": {"disponible": mid in diag,
                             "operaciones": list(diag[mid]["operaciones"]) if mid in diag else []}}
        if mid in ens and "coberturaGrupos" in ens[mid]:
            ops["ensamblaje"]["coberturaGrupos"] = True
        paquetes.append({"modelo": {"id": mid, "version": info["version"]}, "nombre": info["nombre"],
                         "requisitos": catalogo.requisitos(liq), "operaciones": ops, "especies": especies})
    return {"revision": REVISION, "sustancias": sustancias, "paquetes": paquetes,
            "regla": "una especie esta admitida en un paquete si no le falta ningun requisito porEspecie; la misma "
                     "regla vale para la especie pura y para las mezclas. Los requisitos porPar y porGrupo dependen "
                     "del conjunto y se diagnostican al evaluar (PARAMETRO_AUSENTE, UNIFAC_INTERACCION_AUSENTE).",
            "noDisponible": [
                {"elemento": "incorporar sustancias desde la peticion", "motivo": "el registro es del servidor (F2.3)"},
                {"elemento": "overrides de propiedades", "motivo": "pendiente de F2.4"},
                {"elemento": "alineacion de referencias entre paquetes", "motivo": "pendiente de F2.5"}]}


def catalogo_publico():
    return copy.deepcopy(_catalogo())
