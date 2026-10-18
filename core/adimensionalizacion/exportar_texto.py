"""Texto plano de un AST, solo para mensajes de diagnostico (la fuente
matematica es siempre el arbol)."""

from .racional import fraccion


def texto(e, contexto=0):
    t = e["tipo"]
    prioridad = 4
    if t == "numero":
        s = str(e["valor"])
        if e["valor"] < 0:
            prioridad = 2
    elif t == "simbolo":
        s = e["id"]
    elif t == "suma":
        partes = []
        for i, a in enumerate(e["argumentos"]):
            x = texto(a, 1)
            if i and x.startswith("-"):
                partes.append(" - " + x[1:])
            else:
                partes.append((" + " if i else "") + x)
        s, prioridad = "".join(partes), 1
    elif t == "producto":
        args = e["argumentos"]
        if args and args[0]["tipo"] == "numero" and args[0]["valor"] == -1 and len(args) > 1:
            s = "-" + "*".join(texto(a, 2) for a in args[1:])
        else:
            s = "*".join(texto(a, 2) for a in args)
        prioridad = 2
    elif t == "cociente":
        s, prioridad = f"{texto(e['numerador'], 2)}/{texto(e['denominador'], 3)}", 2
    elif t == "potencia":
        s, prioridad = f"{texto(e['base'], 4)}^{texto(e['exponente'], 4)}", 3
    elif t == "funcion":
        s = f"{e['nombre']}({', '.join(texto(a) for a in e['argumentos'])})"
    elif t == "llamada":
        s = f"{e['funcionId']}({', '.join(texto(a) for a in e['argumentos'])})"
    elif t == "derivada":
        o = "" if e["orden"] == 1 else f"^{e['orden']}"
        s = f"d{o}({texto(e['expresion'])})/d{e['respecto']}{o}"
        prioridad = 2
    else:
        nombre = {"gradiente": "grad", "divergencia": "div", "laplaciano": "lap"}[t]
        s = f"{nombre}_{','.join(e['coordenadas'])}({texto(e['expresion'])})"
    return f"({s})" if prioridad < contexto else s


def numero_texto(q):
    q = fraccion(q)
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"
