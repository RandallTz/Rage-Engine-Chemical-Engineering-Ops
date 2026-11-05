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
    python run_tests.py --tier fast  solo el nivel rapido (cada push en CI)
    python run_tests.py --tier slow  solo el nivel lento (PR a main, nocturno, manual)
    python run_tests.py --list       muestra el nivel de cada suite y sale

Niveles: tools/ci/test_tiers.json lista las suites LENTAS (con el tiempo
medido); toda suite que no figure ahi es rapida. Asi cada suite esta en
exactamente un nivel y una suite nueva nunca queda sin correr.

Codigo de salida 0 si todas pasan, 1 si alguna falla: es lo que hace falta
para engancharlo a un hook de pre-commit o a CI mas adelante.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIRECTORIO_TESTS = RAIZ / "tests"
ARCHIVO_NIVELES = RAIZ / "tools" / "ci" / "test_tiers.json"


def suites_lentas():
    """Nombres de las suites del nivel lento (tools/ci/test_tiers.json)."""
    return set(_niveles()["slow"])


def _niveles():
    return json.loads(ARCHIVO_NIVELES.read_text(encoding="utf-8"))


def suites_conocidas_fallidas():
    """{nombre: motivo} de las suites que se ejecutan pero no hacen fallar el trabajo."""
    return {k: v for k, v in _niveles().get("known_failing", {}).items() if not k.startswith("_")}


def main():
    argumentos = [a for a in sys.argv[1:]]
    verboso = "-v" in argumentos or "--verbose" in argumentos
    nivel = None
    if "--tier" in argumentos:
        i = argumentos.index("--tier")
        nivel = argumentos[i + 1] if i + 1 < len(argumentos) else None
        if nivel not in ("fast", "slow"):
            print("--tier requiere 'fast' o 'slow'")
            return 2
        del argumentos[i:i + 2]
    filtros = [a for a in argumentos if not a.startswith("-")]

    suites = sorted(DIRECTORIO_TESTS.glob("validar_*.py"))
    lentas = suites_lentas()
    conocidas = suites_conocidas_fallidas()
    existentes = {s.name for s in suites}
    if (lentas | set(conocidas)) - existentes or (lentas & set(conocidas)):
        # Una entrada obsoleta dejaria una suite fuera de todo nivel sin avisar.
        print("tools/ci/test_tiers.json nombra suites que no existen o repetidas en dos niveles: "
              + ", ".join(sorted(((lentas | set(conocidas)) - existentes) | (lentas & set(conocidas)))))
        return 1
    if "--list" in argumentos:
        for s in suites:
            print(f"{'slow' if s.name in lentas else 'fast'}  {s.name}")
        return 0
    if nivel == "fast":
        suites = [s for s in suites if s.name not in lentas]
    elif nivel == "slow":
        suites = [s for s in suites if s.name in lentas]
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
    print(f"VALIDACION COMPLETA -- {len(suites)} suites" + (f" (nivel {nivel})" if nivel else ""))
    print("=" * 78)

    fallidas = []
    conocidos_fallando = []
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
        if suite.name in conocidas:
            # Fallo conocido y documentado: se muestra, no rompe el trabajo.
            print(f"[{'OK   ' if ok else 'CONOC'}] {suite.name:36s} {transcurrido:6.1f}s", flush=True)
            if ok:
                print("    AVISO: pasa otra vez; quitala de known_failing en tools/ci/test_tiers.json", flush=True)
            else:
                print(f"    fallo conocido: {conocidas[suite.name]}", flush=True)
                conocidos_fallando.append(suite.name)
            continue
        print(f"[{'OK   ' if ok else 'FALLA'}] {suite.name:36s} {transcurrido:6.1f}s", flush=True)

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
    extra = f" ({len(conocidos_fallando)} fallo(s) conocido(s) no bloqueante(s): {', '.join(conocidos_fallando)})" if conocidos_fallando else ""
    print(f"TODO VERDE: {len(suites)} suites en {total:.1f}s{extra}")
    return 0


def _ultimas_lineas(texto, n):
    lineas = (texto or "").rstrip().split("\n")
    return "\n".join(lineas[-n:])


def _sangrar(texto, prefijo="    | "):
    return "\n".join(prefijo + l for l in (texto or "").rstrip().split("\n"))


if __name__ == "__main__":
    sys.exit(main())
