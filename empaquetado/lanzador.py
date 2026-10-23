"""
Lanzador de escritorio del simulador (Windows, offline). Ver docs/PLAN_EJECUTABLE_WINDOWS.md.

Abre una VENTANA propia (pywebview sobre WebView2, que Windows 11 trae), no el navegador:
  1. arranca el backend (FastAPI de backend.main) en 127.0.0.1:8317;
  2. arranca el frontend de Next (build 'standalone', compilado con NEXT_PUBLIC_API_URL=http://127.0.0.1:8317,
     que fija la direccion de TODOS los modulos del frontend) con el node.exe incluido en 127.0.0.1:3317;
  Puertos propios, distintos de los de desarrollo (3000, 8000, 8004): la app de escritorio puede abrirse con los
  servidores de desarrollo en marcha y sus datos quedan separados de los del navegador.
  3. muestra una pantalla de espera hasta que ambos responden y carga la aplicacion;
  4. al cerrar la ventana, termina el proceso de Node.

Solo escucha en 127.0.0.1 (nada sale a la red). Los datos del navegador (hojas en IndexedDB) se guardan en
%LOCALAPPDATA%\\SimuladorDR\\webview; los registros en %LOCALAPPDATA%\\SimuladorDR\\logs. Los puertos son fijos
porque el almacenamiento del frontend depende del origen: si uno esta ocupado, se avisa en vez de cambiarlo.

En desarrollo (sin congelar) se puede probar con:
    python empaquetado/lanzador.py --web <carpeta standalone> --node <ruta a node.exe>
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))     # raiz del repositorio

PUERTO_WEB = 3317
PUERTOS_API = (8317,)
HOST = "127.0.0.1"
TITULO = "Simulador de destilación reactiva"

DATOS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SimuladorDR"
(DATOS / "logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=DATOS / "logs" / "simulador.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("lanzador")

# una aplicacion de ventana no tiene consola: stdout/stderr van al registro
if sys.stdout is None or sys.stderr is None:
    _f = open(DATOS / "logs" / "salida.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _f
    sys.stderr = sys.stderr or _f


def quitar_marca_internet(raiz):
    """Quita la marca «descargado de internet» (flujo NTFS Zone.Identifier) de las DLL y ejecutables de la
    aplicacion. Al extraer un zip descargado, Windows se la pone a todos los archivos, y .NET Framework se niega
    entonces a cargar pythonnet\\runtime\\Python.Runtime.dll: la ventana (WinForms + WebView2) no arranca
    («Failed to resolve Python.Runtime.Loader.Initialize»). Solo afecta a archivos de la propia carpeta; si no
    hay permiso de escritura se deja como esta. SIMULADOR_NO_DESBLOQUEAR=1 lo desactiva (diagnostico)."""
    if os.name != "nt" or os.environ.get("SIMULADOR_NO_DESBLOQUEAR") == "1":
        return 0
    n = 0
    for r, _, archivos in os.walk(raiz):
        for f in archivos:
            if f.lower().endswith((".dll", ".exe", ".pyd")):
                try:
                    os.remove(os.path.join(r, f) + ":Zone.Identifier")
                    n += 1
                except OSError:
                    pass
    if n:
        log.info("marca de internet quitada de %d archivos", n)
    return n


def base():
    """Carpeta del ejecutable (congelado) o de este archivo."""
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def puerto_libre(p):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, p)) != 0


def responde(url, espera=0.5):
    try:
        with urllib.request.urlopen(url, timeout=espera) as r:
            return 200 <= r.status < 500
    except Exception:
        return False


def arrancar_backend():
    import uvicorn
    from backend.main import app
    for p in PUERTOS_API:
        cfg = uvicorn.Config(app, host=HOST, port=p, log_config=None, access_log=False)
        srv = uvicorn.Server(cfg)
        srv.install_signal_handlers = lambda: None      # hilo secundario: sin manejadores de senales
        threading.Thread(target=srv.run, name=f"api-{p}", daemon=True).start()
        log.info("backend en %s:%s", HOST, p)


def arrancar_web(web, node):
    env = dict(os.environ, PORT=str(PUERTO_WEB), HOSTNAME=HOST, NODE_ENV="production", NEXT_TELEMETRY_DISABLED="1")
    salida = open(DATOS / "logs" / "frontend.log", "a", encoding="utf-8")
    flags = 0x08000000 if os.name == "nt" else 0           # CREATE_NO_WINDOW: sin consola de Node
    proc = subprocess.Popen([str(node), "server.js"], cwd=str(web), env=env, stdout=salida, stderr=salida,
                            creationflags=flags)
    log.info("frontend (node %s) pid %s", node, proc.pid)
    return proc


ESPERA_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font-family:Segoe UI,system-ui,sans-serif;
background:#f6f7f9;color:#1d2433}div{text-align:center}p{color:#5b6475;font-size:14px}
.b{width:42px;height:42px;border:4px solid #d5d9e0;border-top-color:#2f6fed;border-radius:50%;margin:0 auto 18px;
animation:g 1s linear infinite}@keyframes g{to{transform:rotate(360deg)}}</style></head><body><div><div class="b"></div>
<h2>{titulo}</h2><p id="m">{mensaje}</p></div></body></html>"""


def pagina(mensaje, error=False):
    h = ESPERA_HTML.replace("{titulo}", TITULO).replace("{mensaje}", mensaje)
    return h.replace('class="b"', 'class="b" style="display:none"') if error else h


def prueba(web, node, demostracion=False):
    """Prueba de humo sin ventana del ejecutable empaquetado. Devuelve 0 si todo responde. Con `demostracion`
    resuelve ademas las peticiones de la carpeta demostracion/ (los ejemplos de la biblioteca de hojas)."""
    import json
    res = []
    proc = None
    try:
        ocupados = [p for p in (PUERTO_WEB,) + PUERTOS_API if not puerto_libre(p)]
        if ocupados:
            res.append(f"FALLO puertos ocupados {ocupados}")
            return 1
        t0 = time.time()
        arrancar_backend()
        proc = arrancar_web(web, node)
        api = f"http://{HOST}:{PUERTOS_API[0]}"
        while time.time() - t0 < 180 and not (responde(api + "/motor/termodinamica/capacidades", 2.0)
                                               and responde(f"http://{HOST}:{PUERTO_WEB}/", 2.0)):
            time.sleep(0.3)
        res.append(f"arranque {time.time() - t0:.1f} s")
        try:
            import clr  # noqa: F401  (pythonnet: lo necesita la ventana WinForms/WebView2)
            res.append("pythonnet (ventana) carga")
        except Exception as x:
            res.append(f"FALLO pythonnet (ventana) no carga: {type(x).__name__}: {x}")

        def get(url):
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.status, r.read()

        def post(url, cuerpo):
            req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.status, json.loads(r.read())
        st, b = get(api + "/motor/termodinamica/capacidades")
        modelos = [m["id"] for m in json.loads(b)["modelos"]]
        res.append(f"capacidades {st}: {modelos}")
        st, b = get(api + "/motor/ensamblajes/capacidades?revision=2")
        res.append(f"capacidades v2 {st}: componentesMaximos {json.loads(b)['componentesMaximos']}")
        st, b = get(api + "/motor/catalogo")
        cat = json.loads(b)
        res.append(f"catalogo {st}: {len(cat['sustancias'])} sustancias, {len(cat['paquetes'])} paquetes")
        for ruta in ("/", "/motor", "/motor/hojas/prueba/resolver"):
            res.append(f"web {ruta} {get(f'http://{HOST}:{PUERTO_WEB}{ruta}')[0]}")
        cas = {"etanol": "64-17-5", "agua": "7732-18-5"}
        st, r = post(api + "/motor/termodinamica/diagramas/trazar", {
            "revision": 1, "solicitudId": "humo", "modelo": {"id": "nrtl-chemsep", "version": "1"},
            "componentes": [{"id": 1, "nombre": "etanol", "simbolo": "E", "identidadQuimica": {"cas": cas["etanol"]}},
                            {"id": 2, "nombre": "agua", "simbolo": "W", "identidadQuimica": {"cas": cas["agua"]}}],
            "componenteEjeId": 1, "corte": {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}},
            "intervaloComposicion": [0, 1], "resolucion": "exploratoria"})
        az = [e for e in r["puntosEspeciales"] if e["tipo"] == "azeotropo"]
        res.append(f"diagrama T-xy etanol-agua {st}: {r['estado']}, {len(r['puntos'])} puntos, azeotropo "
                   f"{az[0]['T'] - 273.15:.2f} C" if az else f"diagrama {st}: {r['estado']}")
        st, r = post(api + "/motor/termodinamica/evaluar", {
            "revision": 1, "solicitudId": "humo2", "propietarioId": "p",
            "componentes": [{"id": 1, "nombre": "agua", "simbolo": "A", "identidadQuimica": {"cas": cas["agua"]}}],
            "declaracion": {"modelo": {"id": "agua-iapws95-hielo-ih", "version": "1"},
                            "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                                         "evaluacion": "equilibrio_estable"},
                            "especificacion": {"tipo": "TP", "T": {"valor": -10, "unidad": "degC"},
                                               "P": {"valor": 1, "unidad": "bar"},
                                               "composicion": {"base": "molar", "fracciones": {"1": 1}}}}})
        res.append(f"hielo -10 C {st}: {r['estado']} {[f['tipo'] for f in (r['evaluacion'] or {}).get('fases', [])]}")
        if demostracion:
            carpeta = base() / "demostracion"
            peticiones = sorted(carpeta.glob("*-peticion.json"))
            if not peticiones:
                res.append(f"FALLO sin peticiones de demostracion en {carpeta}")
            for f in peticiones:
                t1 = time.time()
                st, r = post(api + "/motor/ensamblajes/resolver", json.loads(f.read_text(encoding="utf-8")))
                cert = ((r.get("resultados") or {}).get("certificacion") or {}).get("estado")
                bien = r.get("estado") == "resuelto" and cert == "cumple"
                res.append(f"{'' if bien else 'FALLO '}demostracion {f.stem}: {r.get('estado')}, certificacion {cert}, "
                           f"{time.time() - t1:.0f} s")
        ok = all(not x.startswith("FALLO") for x in res)
        res.append("OK" if ok else "FALLO")
        return 0 if ok else 1
    except Exception as x:
        log.exception("prueba")
        res.append(f"FALLO {type(x).__name__}: {x}")
        return 1
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
        (DATOS / "logs" / "prueba.txt").write_text("\n".join(res), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default=None)
    ap.add_argument("--node", default=None)
    ap.add_argument("--prueba", action="store_true",
                    help="sin ventana: arranca todo, comprueba rutas, escribe logs/prueba.txt y termina")
    ap.add_argument("--prueba-demostracion", action="store_true",
                    help="como --prueba y ademas resuelve los ejemplos de demostracion (unos 2 min)")
    a = ap.parse_args()
    quitar_marca_internet(base())
    raiz = base()
    web = Path(a.web) if a.web else raiz / "web"
    node = Path(a.node) if a.node else raiz / "node" / "node.exe"

    if a.prueba or a.prueba_demostracion:
        sys.exit(prueba(web, node, demostracion=a.prueba_demostracion))
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True              # exportar CSV/JSON desde la interfaz
    ocupados = [p for p in (PUERTO_WEB,) + PUERTOS_API if not puerto_libre(p)]
    if ocupados:
        msg = (f"Los puertos {', '.join(map(str, ocupados))} de este equipo están ocupados (¿otra copia abierta, o "
               "el servidor de desarrollo?). Ciérralos y vuelve a abrir el simulador. No se usa otro puerto porque "
               "tus hojas guardadas dependen de él.")
        log.error(msg)
        webview.create_window(TITULO, html=pagina(msg, error=True), width=760, height=420)
        webview.start()
        return
    proc = {"web": None}

    def preparar(ventana):
        try:
            arrancar_backend()
            proc["web"] = arrancar_web(web, node)
            t0 = time.time()
            while time.time() - t0 < 180:
                if (responde(f"http://{HOST}:{PUERTOS_API[0]}/motor/termodinamica/capacidades", 2.0)
                        and responde(f"http://{HOST}:{PUERTO_WEB}/", 2.0)):
                    log.info("listo en %.1f s", time.time() - t0)
                    ventana.load_url(f"http://{HOST}:{PUERTO_WEB}/")
                    return
                if proc["web"].poll() is not None:
                    raise RuntimeError("el proceso del frontend terminó al arrancar (ver logs/frontend.log)")
                time.sleep(0.3)
            raise RuntimeError("tiempo de arranque agotado (180 s)")
        except Exception as x:
            log.exception("arranque fallido")
            ventana.load_html(pagina(f"No se pudo arrancar: {x}. Registros en {DATOS / 'logs'}.", error=True))

    ventana = webview.create_window(TITULO, html=pagina("Arrancando el motor termodinámico…"),
                                    width=1440, height=900, min_size=(960, 640))
    try:
        webview.start(preparar, ventana, private_mode=False, storage_path=str(DATOS / "webview"))
    finally:
        if proc["web"] is not None and proc["web"].poll() is None:
            proc["web"].terminate()
            try:
                proc["web"].wait(5)
            except Exception:
                proc["web"].kill()
        log.info("cerrado")


if __name__ == "__main__":
    main()
