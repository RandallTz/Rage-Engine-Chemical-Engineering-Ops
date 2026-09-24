"""
Casos preset -- para que el frontend pueda ofrecer "elige un ejemplo" en
vez de exigir que el usuario llene cada campo desde cero. Los valores
numericos (R, recuperaciones, etc.) son los mismos ya validados en
tests/validar_fug.py, tests/validar_diagrama_flujo.py y
ejemplo_columna_destilacion.py -- no son numeros nuevos sin verificar.
"""
from backend.schemas import EjemploPreset, CorrienteFeed

EJEMPLOS: list[EjemploPreset] = [
    EjemploPreset(
        id="mccabe_thiele_benceno_tolueno",
        titulo="McCabe-Thiele: Benceno / Tolueno",
        descripcion="Sistema binario casi ideal, caso clasico de libro de texto. R dado, resuelve N.",
        metodo="mccabe_thiele",
        nombres=["benzene", "toluene"],
        feed=CorrienteFeed(composicion=[0.40, 0.60], flujo_molar=100.0, T=None, P=101325.0),
        parametros={"x_D": 0.95, "x_B": 0.05, "q": 1.0, "R": 3.0597377228491056},
    ),
    EjemploPreset(
        id="ponchon_savarit_benceno_tolueno",
        titulo="Ponchon-Savarit: Benceno / Tolueno",
        descripcion="Mismo sistema que McCabe-Thiele, metodo riguroso de entalpia-composicion (sin CMO). Qc_D dado, resuelve N.",
        metodo="ponchon_savarit",
        nombres=["benzene", "toluene"],
        feed=CorrienteFeed(composicion=[0.40, 0.60], flujo_molar=100.0, T=None, P=101325.0),
        parametros={"x_D": 0.95, "x_B": 0.05, "Qc_D": 131942.94936979646},
    ),
    EjemploPreset(
        id="fug_alcanos",
        titulo="FUG: Propano / n-Butano / n-Pentano / n-Hexano",
        descripcion="Shortcut multicomponente a 5 atm, claves adyacentes (n-butano/n-pentano), caso sharp-split.",
        metodo="fug",
        nombres=["propane", "n-butane", "n-pentane", "n-hexane"],
        feed=CorrienteFeed(composicion=[0.10, 0.30, 0.30, 0.30], flujo_molar=100.0, T=None, P=101325.0 * 5),
        parametros={"recuperacion_LK_D": 0.98, "recuperacion_HK_B": 0.98, "R": 3.0},
        indice_LK=1,
        indice_HK=2,
    ),
]

EJEMPLOS_POR_ID = {e.id: e for e in EJEMPLOS}
