"""
Constructor de solicitudes de la revision 2 del ensamblaje para las pruebas
y los ejemplos (tests/validar_motor_ensamblaje_v2.py,
tests/generar_ejemplos_motor_ensamblaje_v2.py). Usa las formulaciones REALES
que prepara el frontend (tests/fixtures_ensamblaje/), copiadas por volumen.
"""

import copy
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIX = RAIZ / "tests" / "fixtures_ensamblaje"
_R = json.loads((FIX / "rigida_cerrada_U0.json").read_text(encoding="utf-8"))["solicitud"]["volumen"]
_P = json.loads((FIX / "abierta_presion.json").read_text(encoding="utf-8"))["solicitud"]["volumen"]

CAS = {"agua": "7732-18-5", "etanol": "64-17-5", "benceno": "71-43-2", "tolueno": "108-88-3",
       "butanol": "71-36-3", "acetato": "141-78-6", "metanol": "67-56-1", "acetona": "67-64-1"}
POL = {"cantidad": "sin_restriccion", "cambioInterno": "permitido", "evaluacion": "equilibrio_estable"}


def dato(mag, texto, unidad, funcion="frontera", prop="red", ruta="/prueba"):
    return {"magnitud": mag, "funcion": funcion, "declaracion": {"texto": str(texto), "unidad": unidad},
            "origen": {"propietarioId": prop, "ruta": ruta}}


class Red:
    def __init__(self, sid="v2", componentes=("agua",), tf=("100", "s"), muestras=11, rtol=1e-8):
        self.s = {"revision": 2, "solicitudId": sid,
                  "componentes": [{"id": i + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                                  for i, n in enumerate(componentes)],
                  "paquetes": [], "volumenes": [], "corrientes": [], "intercambiosTermicos": [], "datos": {},
                  "estudio": {"tipo": "temporal", "tiempoId": "estudio.tf", "metodoSolicitado": "rk45",
                              "muestras": muestras, "rtol": rtol, "atol": {"cantidad": 1e-10, "energia": 1e-6}}}
        self.ids = {n: i + 1 for i, n in enumerate(componentes)}
        self.s["datos"]["estudio.tf"] = dato("tiempo", *tf, funcion="estudio", prop="estudio")

    def paquete(self, pid, modelo):
        self.s["paquetes"].append({"id": pid, "modelo": {"id": modelo, "version": "1"}})
        return self

    def volumen(self, vid, paquete, cantidades, energia, V=None, P=None, base="masica", politica=None,
                adiabatico=False):
        """cantidades: {nombre: (texto, unidad)}; energia: ('U'|'T', texto, unidad)."""
        rig = V is not None
        plantilla = copy.deepcopy(_R if rig else _P)
        pol = dict(politica or POL)
        fe = plantilla["formulacionEnergia"]
        fe["monofasico"] = pol["cantidad"] == "monofasico"
        fe["sinCambioFase"] = pol["cambioInterno"] == "prohibido"
        fe["adiabatico"] = adiabatico
        fe["entalpia"] = True
        comp = [self.ids[n] for n in cantidades]
        d = self.s["datos"]
        ids0 = {}
        for n, (txt, uni) in cantidades.items():
            k = f"volumen.{vid}.n0.{self.ids[n]}"
            d[k] = dato("masa" if base == "masica" else "cantidad", txt, uni, "inicial", f"volumen:{vid}")
            ids0[str(self.ids[n])] = k
        ke = f"volumen.{vid}.{energia[0]}0"
        d[ke] = dato("energia" if energia[0] == "U" else "temperatura", energia[1], energia[2], "inicial",
                     f"volumen:{vid}")
        if rig:
            d[f"volumen.{vid}.V"] = dato("volumen", *V, "geometria", f"volumen:{vid}")
            fr = {"tipo": "rigida", "datoId": f"volumen.{vid}.V"}
        else:
            d[f"volumen.{vid}.P"] = dato("presion", *P, "frontera", f"volumen:{vid}")
            fr = {"tipo": "presion_prescrita", "presionId": f"volumen.{vid}.P"}
        self.s["volumenes"].append({
            "id": vid, "componenteIds": comp, "balances": {"materia": True, "energia": True, "momento": False},
            "formulacionMateria": plantilla["formulacionMateria"], "formulacionEnergia": fe,
            "paqueteId": paquete, "politica": pol, "frontera": fr,
            "inicial": {"cantidades": {"base": base, "datoIds": ids0},
                        "energia": {"tipo": energia[0], "datoId": ke}}})
        return self

    def corriente(self, cid, desde, hasta, componentes, F, base="masica", T=None, P=None, composicion=None,
                  extraccion=None, por_componente=None):
        d = self.s["datos"]
        comp = [self.ids[n] for n in componentes]
        if por_componente:
            ids = {}
            for n, val in por_componente.items():
                k = f"corriente.{cid}.F.{self.ids[n]}"
                d[k] = dato("caudal" if base == "masica" else "caudal_molar", *val, prop=f"corriente:{cid}")
                ids[str(self.ids[n])] = k
            mat = {"modo": "por_componente", "base": base, "caudalIds": ids}
        else:
            d[f"corriente.{cid}.F"] = dato("caudal" if base == "masica" else "caudal_molar", *F, prop=f"corriente:{cid}")
            mat = {"modo": "total_desde_donante", "base": base, "caudalId": f"corriente.{cid}.F"}
        c = {"id": cid, "desde": desde, "hasta": hasta, "componenteIds": comp, "mecanismo": "convectivo",
             "materia": mat}
        if T is not None:
            d[f"corriente.{cid}.Text"] = dato("temperatura", *T, prop=f"corriente:{cid}")
            if P == "continuidad":
                pres = {"tipo": "continuidad", "volumenId": desde or hasta}
            else:
                d[f"corriente.{cid}.Pext"] = dato("presion", *P, prop=f"corriente:{cid}")
                pres = {"tipo": "dato", "datoId": f"corriente.{cid}.Pext"}
            ext = {"tipo": "TP", "temperaturaId": f"corriente.{cid}.Text", "presion": pres}
            if composicion is not None:
                ext["composicion"] = {"base": composicion[0],
                                      "fracciones": {str(self.ids[n]): f for n, f in composicion[1].items()}}
            c["estadoExterior"] = ext
        if extraccion:
            c["extraccion"] = extraccion
        self.s["corrientes"].append(c)
        return self

    def calor(self, qid, desde, hasta, Q=None, G=None, Text=None, Tfrontera=None):
        d = self.s["datos"]
        if Q is not None:
            d[f"calor.{qid}.Q"] = dato("potencia", *Q, prop=f"calor:{qid}")
            ley = {"tipo": "impuesto", "potenciaId": f"calor.{qid}.Q"}
        else:
            d[f"calor.{qid}.G"] = dato("conductancia", *G, "parametro", f"calor:{qid}")
            ley = {"tipo": "conductancia", "conductanciaId": f"calor.{qid}.G"}
            if Text is not None:
                d[f"calor.{qid}.Text"] = dato("temperatura", *Text, prop=f"calor:{qid}")
                ley["temperaturaExteriorId"] = f"calor.{qid}.Text"
        q = {"id": qid, "desde": desde, "hasta": hasta, "ley": ley}
        if Tfrontera is not None:
            d[f"calor.{qid}.Tf"] = dato("temperatura", *Tfrontera, prop=f"calor:{qid}")
            q["temperaturaFronteraId"] = f"calor.{qid}.Tf"
        self.s["intercambiosTermicos"].append(q)
        return self

    def solicitud(self):
        return copy.deepcopy(self.s)
