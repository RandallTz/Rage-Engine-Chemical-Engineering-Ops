#!/usr/bin/env python
"""
Corre TODAS las suites de validacion y devuelve un codigo de salida real.

Por que existe: las suites siempre fueron buenas por dentro, pero no habia
forma de lanzarlas todas de una. Cada una se ejecutaba a mano, se leia su
salida con los ojos, y nada garantizaba que no se hubiera olvidado
ninguna. Eso significa que no habia un "el proyecto esta verde" que se
pudiera comprobar, solo un "las que mire estaban bien".

Uso:
    python run_tests.py              todas
    python run_tests.py flash        solo las que contengan 'flash'
    python run_tests.py -v           mostrando la salida completa de cada una

Codigo de salida 0 si todas pasan, 1 si alguna falla: es lo que hace falta
para engancharlo a un hook de pre-commit o a CI mas adelante.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIRECTORIO_TESTS = RAIZ / "tests"


def main():
    argumentos = [a for a in sys.argv[1:]]
    verboso = "-v" in argumentos or "--verbose" in argumentos
    filtros = [a for a in argumentos if not a.startswith("-")]

    suites = sorted(DIRECTORIO_TESTS.glob("validar_*.py"))
    if filtros:
        suites = [s for s in suites if any(f.lower() in s.name.lower() for f in filtros)]

    if not suites:
        print("No se encontro ninguna suite" + (f" que case con {filtros}" if filtros else ""))
        return 1

    # Las suites imprimen simbolos griegos; en una consola Windows por
    # defecto (cp1252) eso reventaba la ejecucion entera. Cada suite ya se
    # protege por dentro, y esto lo refuerza para los subprocesos.
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

    print("=" * 78)
    print(f"VALIDACION COMPLETA -- {len(suites)} suites")
    print("=" * 78)

    fallidas = []
    inicio_total = time.time()

    for suite in suites:
        inicio = time.time()
        proceso = subprocess.run(
            [sys.executable, str(suite)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=str(RAIZ), env=entorno,
        )
        transcurrido = time.time() - inicio
        ok = proceso.returncode == 0
        print(f"[{'OK   ' if ok else 'FALLA'}] {suite.name:36s} {transcurrido:6.1f}s")

        if verboso:
            print(_sangrar(proceso.stdout))
        if not ok:
            fallidas.append(suite.name)
            # De una suite que falla SIEMPRE se muestra el porque, aunque
            # no se haya pedido -v: un fallo silencioso no sirve de nada.
            if not verboso:
                print(_sangrar(_ultimas_lineas(proceso.stdout, 25)))
            if proceso.stderr.strip():
                print(_sangrar(_ultimas_lineas(proceso.stderr, 15)))

    print("-" * 78)
    total = time.time() - inicio_total
    if fallidas:
        print(f"FALLARON {len(fallidas)} de {len(suites)} en {total:.1f}s: " + ", ".join(fallidas))
        return 1
    print(f"TODO VERDE: {len(suites)} suites en {total:.1f}s")
    return 0


def _ultimas_lineas(texto, n):
    lineas = (texto or "").rstrip().split("\n")
    return "\n".join(lineas[-n:])


def _sangrar(texto, prefijo="    | "):
    return "\n".join(prefijo + l for l in (texto or "").rstrip().split("\n"))


if __name__ == "__main__":
    sys.exit(main())
