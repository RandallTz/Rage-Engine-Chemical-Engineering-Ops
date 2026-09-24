"""
Capa de persistencia (solo lectura) para el simulador quimico.

RepositorioQuimico consulta base_termodinamica.db (SQLite, generado por
etl_yaws.py) y expone metodos de lectura simples. No construye matrices,
no aplica modelos termodinamicos ni hace ningun calculo: es unicamente el
puente entre la base de datos y el resto de la aplicacion.
"""

import re
import sqlite3
from pathlib import Path

_SLUG_VALIDO = re.compile(r"^\w+$")


class RepositorioQuimico:
    def __init__(self, ruta_db="base_termodinamica.db"):
        if not Path(ruta_db).exists():
            raise FileNotFoundError(
                f"No se encontro '{ruta_db}'. Ejecuta etl_yaws.py primero."
            )
        self._con = sqlite3.connect(ruta_db)
        self._con.row_factory = sqlite3.Row

        self._slugs = [
            fila["slug"]
            for fila in self._con.execute("SELECT slug FROM metadatos_propiedades")
            if _SLUG_VALIDO.match(fila["slug"])
        ]

    def close(self):
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def _normalizar(nombre):
        return nombre.strip().lower()

    def _fila_compuesto(self, nombre):
        return self._con.execute(
            "SELECT id, nombre, formula FROM compuestos WHERE clave = ?",
            (self._normalizar(nombre),),
        ).fetchone()

    def obtener_propiedades_puras(self, lista_nombres):
        """
        Devuelve un diccionario {nombre_solicitado: propiedades} con todas
        las propiedades puras (Antoine, criticas, Cp, etc.) tal como estan
        en la base de datos. Si un compuesto no existe, su valor es None.
        """
        resultado = {}
        for nombre in lista_nombres:
            fila = self._fila_compuesto(nombre)
            if fila is None:
                resultado[nombre] = None
                continue

            propiedades = {}
            for slug in self._slugs:
                registros = self._con.execute(
                    f'SELECT * FROM "{slug}" WHERE compuesto_id = ?', (fila["id"],)
                ).fetchall()
                if registros:
                    propiedades[slug] = [
                        {k: r[k] for k in r.keys() if k not in ("id", "compuesto_id")}
                        for r in registros
                    ]

            resultado[nombre] = {
                "nombre": fila["nombre"],
                "formula": fila["formula"],
                "propiedades": propiedades,
            }
        return resultado

    def obtener_parametros_binarios(self, lista_nombres):
        """
        Devuelve los parametros de interaccion binaria (p.ej. NRTL: g_ij,
        alpha_ij) para cada par posible de la lista, exactamente como
        vienen almacenados en la tabla 'parametros_binarios'.

        Cada par se busca en ambos ordenes ("A","B") y ("B","A"). Si no hay
        datos para un par, su valor es None.
        """
        resultado = {}
        for i in range(len(lista_nombres)):
            for j in range(i + 1, len(lista_nombres)):
                a, b = lista_nombres[i], lista_nombres[j]
                na, nb = self._normalizar(a), self._normalizar(b)
                filas = self._con.execute(
                    "SELECT parametro, valor FROM parametros_binarios "
                    "WHERE (compuesto_a = ? AND compuesto_b = ?) "
                    "   OR (compuesto_a = ? AND compuesto_b = ?)",
                    (na, nb, nb, na),
                ).fetchall()
                resultado[(a, b)] = (
                    {f["parametro"]: f["valor"] for f in filas} if filas else None
                )
        return resultado

    def obtener_metadatos_propiedad(self, slug_propiedad):
        """Devuelve la ecuacion/unidades documentadas para una tabla de Yaws."""
        fila = self._con.execute(
            "SELECT * FROM metadatos_propiedades WHERE slug = ?",
            (slug_propiedad,),
        ).fetchone()
        return dict(fila) if fila else None

    def listar_compuestos(self):
        """Devuelve la lista de nombres de todos los compuestos disponibles."""
        return [
            f["nombre"] for f in self._con.execute("SELECT nombre FROM compuestos")
        ]
