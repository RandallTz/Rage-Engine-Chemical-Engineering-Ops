"""
Formato común de resultados (docs/FORMATO_RESULTADOS.md): lo que todo motor
de cálculo publica y lo que consume el motor de gráficas.

  formato.conjunto(...), formato.eje(...), formato.serie(...)  -> construir
  formato.leer_resultados(dato)                                -> validar
  adaptadores.desde_ensamblaje_v2(respuesta)                  -> motor de ensamblaje
"""

from .formato import ErrorResultados, VERSION, conjunto, eje, evento, leer_resultados, serie
from .adaptadores import desde_ensamblaje_v2

__all__ = ["ErrorResultados", "VERSION", "conjunto", "eje", "evento", "leer_resultados", "serie", "desde_ensamblaje_v2"]
