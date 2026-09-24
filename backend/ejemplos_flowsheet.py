"""
Casos preset de flowsheet -- replican EXACTAMENTE los dos casos ya
verificados en tests/validar_diagrama_flujo.py (mismos numeros, mismas
conexiones), no numeros nuevos sin validar.
"""
from backend.schemas import EjemploFlowsheet, ResolverFlowsheetRequest, OperacionDef, ConexionDef, RecicloDef

_NOMBRES_FUG = ["propane", "n-butane", "n-pentane", "n-hexane"]
_P_FUG = 101325.0 * 5

EJEMPLOS_FLOWSHEET: list[EjemploFlowsheet] = [
    EjemploFlowsheet(
        id="fug_bomba",
        titulo="Columna FUG -> Bomba (sin reciclo)",
        descripcion="El destilado de una columna FUG alimenta una bomba que duplica su presion.",
        definicion=ResolverFlowsheetRequest(
            operaciones=[
                OperacionDef(
                    nombre="columna",
                    tipo="columna",
                    config={
                        "metodo": "fug",
                        "nombres": _NOMBRES_FUG,
                        "P_sistema": _P_FUG,
                        "q": 1.0,
                        "z_F_fug": [0.10, 0.30, 0.30, 0.30],
                        "indice_LK": 1,
                        "indice_HK": 2,
                        "variables_entrada_extra": ["recuperacion_LK_D", "recuperacion_HK_B", "R"],
                        "variables_salida_extra": ["N", "R_min"],
                    },
                ),
                OperacionDef(nombre="bomba", tipo="bomba", config={}),
            ],
            conexiones=[ConexionDef(origen="columna", puerto_salida="D", destino="bomba", puerto_entrada="entrada")],
            valores_conocidos={
                "columna.F": {
                    "nombres": _NOMBRES_FUG, "composicion": [0.10, 0.30, 0.30, 0.30],
                    "flujo_molar": 100.0, "T": 335.85326040704746, "P": _P_FUG,
                },
                "columna.recuperacion_LK_D": 0.98,
                "columna.recuperacion_HK_B": 0.98,
                "columna.R": 3.0,
                "bomba.factor_P": 2.0,
            },
        ),
    ),
    EjemploFlowsheet(
        id="mezclador_divisor_reciclo",
        titulo="Mezclador + Divisor con reciclo",
        descripcion=(
            "Alimentacion fresca se mezcla con un reciclo, se divide 70/30 en producto/reciclo. "
            "Solucion analitica exacta: reciclo=42.857143 mol/s, producto=100 mol/s."
        ),
        definicion=ResolverFlowsheetRequest(
            operaciones=[
                OperacionDef(
                    nombre="mezclador", tipo="mezclador",
                    config={"nombres": ["n-butane"], "puertos_entrada": ["fresca", "reciclo"]},
                ),
                OperacionDef(
                    nombre="divisor", tipo="divisor",
                    config={"puertos_salida": ["producto", "reciclo"], "fracciones": [0.7, 0.3]},
                ),
            ],
            conexiones=[
                ConexionDef(origen="mezclador", puerto_salida="salida", destino="divisor", puerto_entrada="entrada"),
                ConexionDef(origen="divisor", puerto_salida="reciclo", destino="mezclador", puerto_entrada="reciclo"),
            ],
            valores_conocidos={
                "mezclador.fresca": {
                    "nombres": ["n-butane"], "composicion": [1.0], "flujo_molar": 100.0, "T": 350.0, "P": 101325.0,
                },
            },
            reciclo=RecicloDef(
                conexion=ConexionDef(origen="divisor", puerto_salida="reciclo", destino="mezclador", puerto_entrada="reciclo"),
                valor_inicial={"nombres": ["n-butane"], "composicion": [1.0], "flujo_molar": 0.0, "T": 350.0, "P": 101325.0},
                tolerancia=1e-8,
            ),
        ),
    ),
]

EJEMPLOS_FLOWSHEET_POR_ID = {e.id: e for e in EJEMPLOS_FLOWSHEET}
