"""
Registro unico de sustancias del motor y regla unica de admision por paquete (F2.1, docs/engine/multiphysics-roadmap.md).

Separa tres cosas que antes estaban mezcladas en una lista fija:
  1. IDENTIDAD de la sustancia (CAS, nombre, masa molar con su fuente): `REGISTRO`, inmutable.
  2. DATOS PUROS que necesita un paquete de mezcla (Psat, cp de gas ideal, v_L): se cargan de las tablas
     fijadas de `chemicals` en core/mezclas_datos.especie(); aqui solo se declara de donde salen.
  3. REQUISITOS de cada paquete: por especie (datos puros, asignacion de grupos UNIFAC, pertenencia al par
     ajustado NRTL-LLE, formulacion IAPWS-95) y por par o grupo (NRTL, interacciones UNIFAC), que siguen
     comprobandose al construir el modelo de liquido.

Una sustancia registrada NO queda admitida en todos los paquetes: `faltantes(liquido, cas)` lista lo que le falta
a esa especie para un paquete, y es la MISMA regla para el limite puro y para las mezclas (cierra F9-R3: con la
tabla ELL el metanol puro se evaluaba aunque las capacidades lo excluian). Incorporar una sustancia es anadir un
RegistroSustancia con sus fuentes; si alguna tabla no la tiene, `faltantes` lo dice por propiedad.
"""

from dataclasses import dataclass
from types import MappingProxyType

REVISION = 1


@dataclass(frozen=True)
class RegistroSustancia:
    cas: str
    nombre: str
    M: float                # kg/mol
    fuente_M: str
    psat_tabla: str         # 'WagnerPoling' | 'WagnerMcGarry' (tablas de chemicals.vapor_pressure)
    vL: float               # m3/mol a 298.15 K
    metodo_vL: str          # metodo de thermo.VolumeLiquid con que se obtuvo v_L


_M = "thermo (IUPAC)"
_REGISTROS = (
    RegistroSustancia("7732-18-5", "agua", 18.01528e-3, _M, "WagnerMcGarry", 1.8068323953085667e-05, "HEOS_FIT"),
    RegistroSustancia("64-17-5", "etanol", 46.06844e-3, _M, "WagnerPoling", 5.8673800832977466e-05, "HEOS_FIT"),
    RegistroSustancia("71-43-2", "benceno", 78.11184e-3, _M, "WagnerPoling", 8.939778918663944e-05, "HEOS_FIT"),
    RegistroSustancia("108-88-3", "tolueno", 92.13842e-3, _M, "WagnerPoling", 1.0684707573950031e-04, "HEOS_FIT"),
    RegistroSustancia("71-36-3", "1-butanol", 74.1216e-3, _M, "WagnerPoling", 9.218214721157879e-05, "DIPPR_PERRY_8E"),
    RegistroSustancia("141-78-6", "acetato de etilo", 88.10512e-3, _M, "WagnerMcGarry", 9.858272672498358e-05,
                      "DIPPR_PERRY_8E"),
    RegistroSustancia("67-56-1", "metanol", 32.04186e-3, _M, "WagnerPoling", 4.0747926182915573e-05, "HEOS_FIT"),
    # F2.6 (16/10/2026): incorporada solo por registro, con las mismas tablas (chemicals 1.5.2, thermo 0.6.1) y el
    # mismo metodo de v_L que la mayoria; contraste en docs/engine/property-catalog.md
    RegistroSustancia("67-64-1", "acetona", 58.07914e-3, _M, "WagnerPoling", 7.401429647338668e-05, "HEOS_FIT"),
)
# Los v_L son valores FIJADOS al registrar (no se recalculan al arrancar): una nueva version de thermo puede dar
# otro decimal (agua HEOS_FIT hoy 1.80686e-5 frente a 1.80683e-5 registrado) y cambiarlo alteraria las huellas.
REGISTRO = MappingProxyType({r.cas: r for r in _REGISTROS})

# Datos puros que necesita un paquete de mezcla, por especie (id, magnitud, unidad SI)
DATOS_PUROS_MEZCLA = (
    ("masa_molar", "masa molar", "kg/mol"),
    ("presion_vapor", "presion de vapor (correlacion de Wagner)", "Pa"),
    ("cp_gas_ideal", "capacidad calorifica del gas ideal (polinomio de Poling)", "J/(mol K)"),
    ("volumen_liquido", "volumen molar del liquido a 298.15 K (incompresible)", "m3/mol"),
)
CAS_AGUA = "7732-18-5"


def registrada(cas):
    return cas in REGISTRO


def sustancias():
    return list(REGISTRO)


def _falta(cas, dato, codigo, mensaje):
    return {"cas": cas, "dato": dato, "codigo": codigo, "mensaje": mensaje}


def faltantes(liquido, cas, paquete_id=None):
    """Lo que le falta a la especie `cas` para un paquete cuyo liquido es `liquido` ('ideal', 'nrtl', 'nrtl_lle',
    'unifac_<variante>' o 'iapws95'). Lista vacia = admitida. Solo requisitos POR ESPECIE: los de pares o grupos
    (NRTL, interacciones UNIFAC) dependen del conjunto y se comprueban al construir el modelo."""
    nombre = paquete_id or liquido
    if liquido == "iapws95":
        if cas != CAS_AGUA:
            return [_falta(cas, "formulacion_iapws95", "COMPONENTE_NO_SOPORTADO",
                           f"El paquete {nombre} solo describe el agua ({CAS_AGUA}).")]
        return []
    if cas not in REGISTRO:
        return [_falta(cas, "registro", "COMPONENTE_NO_SOPORTADO",
                       f"{cas} no esta en el registro de sustancias del motor: no hay datos de componente puro.")]
    from core import mezclas_datos
    sal = [_falta(cas, d, "DATO_PURO_AUSENTE", f"Falta {d} de {cas}: {m}")
           for d, m in mezclas_datos.datos_puros_faltantes(cas)]
    if liquido == "nrtl_lle":
        from core.mezclas import NRTL_LLE_AGUA_BUTANOL
        if cas not in NRTL_LLE_AGUA_BUTANOL["cas"]:
            sal.append(_falta(cas, "parametros_nrtl_lle", "PARAMETRO_AUSENTE",
                              f"El paquete {nombre} solo tiene parametros para agua y 1-butanol."))
    elif liquido.startswith("unifac_"):
        from core import unifac
        variante = liquido.split("_", 1)[1]
        try:
            unifac.asignacion(cas, variante)
        except unifac.FaltaDatoUNIFAC as x:
            sal.append(_falta(cas, f"asignacion_grupos_{variante}",
                              {"asignacion_ausente": "UNIFAC_ASIGNACION_AUSENTE",
                               "grupo_desconocido": "UNIFAC_GRUPO_DESCONOCIDO"}[x.detalle["tipo"]], x.mensaje))
    return sal


def requisitos(liquido):
    """Requisitos declarados de un paquete: por especie, por par y por grupo (semantica publicada)."""
    if liquido == "iapws95":
        return {"porEspecie": ["formulacion_iapws95"], "porPar": [], "porGrupo": []}
    especie = [d for d, _, _ in DATOS_PUROS_MEZCLA]
    par, grupo = [], []
    if liquido == "nrtl":
        par = ["nrtl_bij_alphaij"]
    elif liquido == "nrtl_lle":
        especie.append("parametros_nrtl_lle")
    elif liquido.startswith("unifac_"):
        especie.append(f"asignacion_grupos_{liquido.split('_', 1)[1]}")
        grupo = ["interaccion_grupos_principales"]
    return {"porEspecie": especie, "porPar": par, "porGrupo": grupo}


# ----------------------------------------------------------------------------------------------------------------
# F2.4 · Sustitucion de datos puros (overrides)
#
# Solo se sustituyen ENTRADAS del potencial de cada especie en los paquetes de mezcla: v_L, los coeficientes de
# cp del gas ideal y los de Psat, cada uno con su fuente y su dominio. h, s, mu, cp del liquido y densidades se
# DERIVAN de esas entradas (core/mezclas_datos.Especie), asi que una sustitucion cambia el mismo potencial con
# todas sus derivadas, sin parchear una propiedad aislada de un estado. No se sustituyen: la masa molar
# (identidad de la sustancia: cambiarla altera los inventarios), las propiedades del estado ni nada de IAPWS-95.
# ----------------------------------------------------------------------------------------------------------------
SUSTITUIBLES = ("volumen_liquido", "cp_gas_ideal", "presion_vapor")
_UNIDADES_VL = {"m3/mol": 1.0, "cm3/mol": 1e-6, "L/mol": 1e-3}
_MOTIVO_NO = {
    "masa_molar": "la masa molar es identidad de la sustancia (convierte masa en cantidad): no se sustituye",
}


class SustitucionRechazada(Exception):
    def __init__(self, codigo, ruta, mensaje):
        super().__init__(mensaje)
        self.codigo, self.ruta, self.mensaje = codigo, ruta, mensaje


def _num(v, ruta, nombre):
    import math
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", ruta, f"{nombre}: se espera un numero finito.")
    return float(v)


def _fuente(d, ruta):
    f = d.get("fuente")
    if not isinstance(f, str) or not f.strip():
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{ruta}/fuente",
                                   "Toda sustitucion declara su fuente (texto no vacio).")
    return f.strip()


def _dominio(d, ruta):
    dom = d.get("dominio")
    if not isinstance(dom, dict) or not isinstance(dom.get("T"), list) or len(dom["T"]) != 2:
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{ruta}/dominio", "dominio: {T: [Tmin, Tmax]} en K.")
    lo, hi = (_num(x, f"{ruta}/dominio/T", "T") for x in dom["T"])
    if not 0 < lo < hi:
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{ruta}/dominio/T", "Se requiere 0 < Tmin < Tmax.")
    return lo, hi


def _campos(d, ruta, admitidos):
    if not isinstance(d, dict):
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", ruta, "Se espera un objeto.")
    extra = sorted(set(d) - set(admitidos))
    if extra:
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{ruta}/{extra[0]}", f"Campo «{extra[0]}» no admitido.")


def leer_sustituciones(obj, ruta, cas_validos):
    """Valida `datosPuros` de una peticion: {cas: {propiedad: {...}}}. Devuelve el diccionario canonico (SI) o
    lanza SustitucionRechazada con codigo, ruta y motivo. La comprobacion fisica (cp > 0, Psat creciente y por
    debajo de Pc en su dominio) se hace aqui; la coherencia con el potencial la da la construccion de Especie."""
    import math
    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise SustitucionRechazada("SUSTITUCION_INVALIDA", ruta, "datosPuros: objeto {cas: {propiedad: dato}}.")
    sal = {}
    for cas, props in obj.items():
        r = f"{ruta}/{cas}"
        if cas not in cas_validos:
            raise SustitucionRechazada("SUSTITUCION_INVALIDA", r,
                                       f"{cas} no es un componente de esta peticion con este paquete.")
        if not isinstance(props, dict) or not props:
            raise SustitucionRechazada("SUSTITUCION_INVALIDA", r, "Se espera {propiedad: dato} no vacio.")
        canon = {}
        for prop, d in props.items():
            rp = f"{r}/{prop}"
            if prop not in SUSTITUIBLES:
                raise SustitucionRechazada(
                    "SUSTITUCION_NO_ADMITIDA", rp,
                    _MOTIVO_NO.get(prop, f"«{prop}» no es un dato de entrada sustituible: las propiedades del estado "
                                         "(h, s, mu, cp del liquido, densidad) se derivan del potencial. "
                                         f"Sustituibles: {', '.join(SUSTITUIBLES)}."))
            if prop == "volumen_liquido":
                _campos(d, rp, ("valor", "unidad", "fuente"))
                if d.get("unidad") not in _UNIDADES_VL:
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/unidad",
                                               f"Unidad de v_L: {', '.join(_UNIDADES_VL)}.")
                v = _num(d.get("valor"), f"{rp}/valor", "valor") * _UNIDADES_VL[d["unidad"]]
                if v <= 0:
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/valor", "v_L debe ser positivo.")
                canon[prop] = {"valor": v, "unidad": "m3/mol", "fuente": _fuente(d, rp)}
            elif prop == "cp_gas_ideal":
                _campos(d, rp, ("coeficientes", "dominio", "fuente"))
                c = d.get("coeficientes")
                if not isinstance(c, dict) or set(c) != {"a0", "a1", "a2", "a3", "a4"}:
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/coeficientes",
                                               "coeficientes {a0..a4} de cp/R = sum a_k T^k.")
                a = tuple(_num(c[f"a{k}"], f"{rp}/coeficientes/a{k}", f"a{k}") for k in range(5))
                lo, hi = _dominio(d, rp)
                for k in range(201):
                    T = lo + (hi - lo) * k / 200
                    if not sum(ak * T ** j for j, ak in enumerate(a)) > 0:
                        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/coeficientes",
                                                   f"cp del gas ideal no positivo a {T:.6g} K dentro del dominio.")
                canon[prop] = {"coeficientes": a, "dominio": (lo, hi), "fuente": _fuente(d, rp)}
            else:
                _campos(d, rp, ("forma", "coeficientes", "dominio", "fuente"))
                if d.get("forma") not in ("WagnerPoling", "WagnerMcGarry"):
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/forma",
                                               "forma: WagnerPoling o WagnerMcGarry.")
                c = d.get("coeficientes")
                if not isinstance(c, dict) or set(c) != {"A", "B", "C", "D", "Tc", "Pc"}:
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/coeficientes",
                                               "coeficientes {A, B, C, D, Tc [K], Pc [Pa]}.")
                p = tuple(_num(c[k], f"{rp}/coeficientes/{k}", k) for k in ("A", "B", "C", "D", "Tc", "Pc"))
                lo, hi = _dominio(d, rp)
                if not (p[4] > 0 and p[5] > 0 and hi <= p[4]):
                    raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/coeficientes",
                                               "Se requiere Tc > 0, Pc > 0 y Tmax del dominio <= Tc.")
                ex = (2.5, 5) if d["forma"] == "WagnerPoling" else (3, 6)
                previo = -math.inf
                for k in range(201):
                    T = lo + (hi - lo) * k / 200
                    tau = 1 - T / p[4]
                    try:
                        lnP = (p[0] * tau + p[1] * tau ** 1.5 + p[2] * tau ** ex[0] + p[3] * tau ** ex[1]) * p[4] / T
                    except (OverflowError, ValueError):
                        lnP = math.nan
                    if not math.isfinite(lnP) or lnP <= previo or lnP > 1e-9:
                        raise SustitucionRechazada("SUSTITUCION_INVALIDA", f"{rp}/coeficientes",
                                                   f"Psat no finita, no creciente o por encima de Pc a {T:.6g} K.")
                    previo = lnP
                canon[prop] = {"forma": d["forma"], "coeficientes": p, "dominio": (lo, hi), "fuente": _fuente(d, rp)}
        sal[cas] = canon
    return sal


def aplicar_sustituciones(especie, sust):
    """Especie con sus entradas sustituidas (dataclass nueva; el registro y la cache no cambian)."""
    import dataclasses
    cambios = {}
    if "volumen_liquido" in sust:
        cambios.update(vL=sust["volumen_liquido"]["valor"],
                       fuente_vL=f"sustituido: {sust['volumen_liquido']['fuente']}")
    if "cp_gas_ideal" in sust:
        cambios.update(cp=tuple(sust["cp_gas_ideal"]["coeficientes"]), T_cp=tuple(sust["cp_gas_ideal"]["dominio"]))
    if "presion_vapor" in sust:
        cambios.update(psat_forma=sust["presion_vapor"]["forma"], psat=tuple(sust["presion_vapor"]["coeficientes"]),
                       T_psat=tuple(sust["presion_vapor"]["dominio"]))
    return dataclasses.replace(especie, **cambios)
