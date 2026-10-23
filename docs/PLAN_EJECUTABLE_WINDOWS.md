# Plan: ejecutable de Windows (.exe) con lo que ya existe

15 de octubre de 2026. **Estado: hay una versión de prueba construida y comprobada** (§0). El resto es el plan para convertirla en producto. Objetivo: que alguien sin Python ni
Node instalados abra el simulador con doble clic, usando el mismo backend y el mismo frontend que hoy, aunque
haya funciones sin terminar.

## 0. Versión de prueba construida (variante de la opción A, en ventana propia)

A petición del usuario («software offline, sin navegador»), se construyó la opción A con **ventana de escritorio**
(pywebview + WebView2) en lugar de abrir el navegador. **No se modificó el frontend**: se compila una copia aparte.

- **Fuentes** en el repositorio: `empaquetado/lanzador.py`, `empaquetado/construir.ps1`, `empaquetado/LEEME.md`.
- **Salida** (fuera del repositorio): `%USERPROFILE%\Desktop\SimuladorDR\SimuladorDR.exe`, 443 MB en carpeta.
  El entorno de construcción está en `%USERPROFILE%\Desktop\SimuladorDR_build`, con un venv propio que respeta
  las versiones de `requirements.txt` más PyInstaller 6.22.3 y pywebview 6.2.1.
- **Puertos propios fijos**: 3317 (web) y 8317 (API), distintos de los de desarrollo. El frontend se compila con
  `NEXT_PUBLIC_API_URL=http://127.0.0.1:8317`, que también resuelve el `localhost:8004` fijo de `calcularReactor`
  (el código usa la variable si existe).
- **Ruta dinámica `/motor/hojas/[id]`**: funciona sin cambios porque Next corre con `node.exe` en modo
  `standalone`. La copia de construcción añade `output: "standalone"` solo a su propio `next.config.ts`.
- **Comprobado** con `SimuladorDR.exe --prueba` (sin ventana):
  - arranque en frío 18.7 s;
  - capacidades con los 5 modelos y `componentesMaximos` 7;
  - `/`, `/motor` y `/motor/hojas/prueba/resolver` → 200;
  - diagrama T–xy etanol–agua completo con el azeótropo a 78.07 °C, igual que en desarrollo;
  - hielo a −10 °C → sólido;
  - al terminar no quedan procesos ni puertos abiertos.
- **No comprobado**: la ventana interactiva (no se abrió en la sesión del usuario para no interrumpirle) y la
  persistencia de hojas entre aperturas.

Para Codex: nada que hacer para usar esta versión de prueba. Los cambios de §4 solo hacen falta para la fase B
(un proceso, sin Node).

## 1. Qué hay hoy (medido en el repositorio)

| Pieza | Estado actual | Consecuencia para el .exe |
|---|---|---|
| Frontend | Next.js 16 + React 19, Tailwind 4, recharts, @xyflow, katex. Sin rutas API (`app/api` no existe) ni server actions | No necesita un servidor Next propio, salvo por la ruta dinámica (fila siguiente) |
| Ruta dinámica | `app/motor/hojas/[id]/{estado,resolver,resultados}`: el `id` lo crea el usuario en el navegador | `output: 'export'` (estático) no puede generar IDs desconocidos: hace falta un pequeño cambio de ruta (§4) o servir Next con Node |
| URL del backend | `process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'` en varios archivos, y **`localhost:8004`** en `calcularReactor` | Se fija en tiempo de compilación; hay que unificarla (§4) |
| Persistencia | 15 archivos usan IndexedDB o localStorage | Los datos dependen del **origen** (esquema + host + puerto). El .exe debe usar siempre el mismo origen o el usuario «pierde» sus hojas |
| Backend | FastAPI 0.104 + uvicorn 0.24, CORS `*`. Python 3.12.10 con versiones fijadas en `requirements.txt` | Empaquetable con PyInstaller |
| Dependencias Python pesadas | scipy 121 MB, chemicals 73 MB, numpy 32 MB, thermo 30 MB; además matplotlib, plotly y python-ternary, que `backend.main` **importa al cargar** | ~350–450 MB desempaquetado; thermo y chemicals llevan tablas de datos que hay que incluir |
| Arranque | `import backend.main` tarda 2.5 s en caliente | Hace falta una pantalla de espera; en frío (antivirus, disco), más |

## 2. Opciones

| Opción | Cómo funciona | Ventajas | Inconvenientes |
|---|---|---|---|
| **A. Lanzador Python + Next con Node** | Un .exe (PyInstaller) arranca uvicorn en `127.0.0.1:8000` y un `node.exe` incluido con el servidor `output: 'standalone'` de Next en `127.0.0.1:3000`, y abre el navegador | **Sin cambios en el frontend**; la ruta `[id]` funciona tal cual | Dos procesos y dos puertos; incluye Node (~80 MB); la app vive en una pestaña del navegador |
| **B. Un solo proceso: FastAPI sirve el frontend estático** | `next build` con `output: 'export'`; FastAPI monta la carpeta `out/` y sirve la API en el mismo origen; se abre en una ventana propia con pywebview (WebView2, que Windows 11 ya trae) | Un proceso, un puerto, sin Node, sin CORS; ventana de aplicación; almacenamiento en una carpeta controlada | Requiere los cambios de §4 (ruta de hojas y URL relativa), que son de Codex |
| C. Electron o Tauri | Shell de escritorio con el backend como proceso hijo («sidecar») | Experiencia de escritorio completa, actualizaciones | Otra pila que mantener (Electron +150 MB; Tauri necesita Rust); no aporta nada esencial frente a B |

**Recomendación:** empezar por **A como prueba de concepto**, porque funciona sin tocar el frontend y valida el
empaquetado de Python, que es lo difícil. Después, pasar a **B como producto**, cuando Codex haga los dos
cambios de §4. C solo si más adelante hacen falta funciones nativas (menús, actualizaciones automáticas,
asociación de archivos).

## 3. Cómo lo construiría (fase A, prueba de concepto)

1. **Entorno de construcción limpio**: un venv con exactamente `requirements.txt` más `pyinstaller`. Nunca el Python
   del sistema, para que el .exe no arrastre paquetes ajenos.
2. **Lanzador** `empaquetado/lanzador.py`:
   - comprobar que los puertos fijos están libres; si no, avisar en vez de cambiar de puerto en silencio (los
     datos del navegador dependen del origen);
   - arrancar uvicorn con `backend.main:app` en `127.0.0.1` (nunca `0.0.0.0`: solo local) en un hilo;
   - arrancar `node server.js` del build standalone de Next como proceso hijo;
   - esperar a que `GET /motor/termodinamica/capacidades` responda;
   - abrir `http://127.0.0.1:3000` y cerrar los procesos hijos al salir;
   - escribir los registros en `%LOCALAPPDATA%\SimuladorDR\logs`.
3. **Especificación de PyInstaller** (`empaquetado/simulador.spec`):
   - modo **onedir** (carpeta), no onefile: arranca más rápido y los antivirus lo marcan menos;
   - `collect_data_files` / `collect_submodules` para `thermo`, `chemicals`, `fluids`, `scipy` y `pint`;
   - incluir `core/`, `backend/`, `config/`, `api/` y `thermodynamics/` del proyecto, sin `tests/`, `docs/` ni `archive/`.
4. **Frontend**: `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 next build` con `output: 'standalone'` (un cambio de
   una línea en `next.config.ts`, a acordar con Codex), y copiar `.next/standalone`, `.next/static` y `public/`
   junto a un `node.exe` portable.
5. **Instalador**: Inno Setup, que empaqueta la carpeta y crea un acceso directo. El resultado se zipea o se
   instala en `%LOCALAPPDATA%\Programs\SimuladorDR` (sin pedir administrador).
6. **Prueba de humo** del .exe en una máquina o usuario sin Python ni Node:
   - arranca;
   - `/motor/termodinamica/capacidades` lista los 5 modelos;
   - se resuelve un ejemplo de `docs/ejemplos/motor-v2/`;
   - un diagrama T–xy;
   - una hoja guardada sobrevive a cerrar y reabrir.

## 4. Cambios del frontend que necesita la fase B (para Codex)

1. **Ruta de hojas sin segmento dinámico generado en el servidor.** Dos alternativas:
   - `/motor/hojas?id=<id>` (+ `/estado`, `/resolver`, `/resultados` como `?id=&vista=`);
   - mantener `[id]` con `generateStaticParams` que devuelva un marcador y leer el `id` real de
     `window.location` en `HojaGuardada`; el backend sirve esa página para cualquier `/motor/hojas/*`.

   Conservar las URLs actuales como redirección para los enlaces guardados.
2. **URL del backend unificada y relativa**: un único módulo de configuración que use `''` (mismo origen) en el
   .exe y `NEXT_PUBLIC_API_URL` en desarrollo. Eliminar el `localhost:8004` fijo de `calcularReactor`.
3. **`output: 'export'`** en `next.config.ts` para el build del .exe (o una variable que lo active), y
   comprobar que ninguna página use funciones de servidor.
4. **Migración de almacenamiento**: el origen cambia al pasar de `localhost:3000` (desarrollo) a la ventana del
   .exe, así que hace falta exportar/importar hojas (JSON) para trasladar el trabajo. Las firmas y revisiones
   actuales ya permiten validar lo importado.

## 5. Backend: cambios pequeños que puedo hacer yo (fase B)

- Montar `StaticFiles` del frontend exportado con una ruta de reserva para `/motor/hojas/*`, sin afectar a las
  rutas API actuales (todas bajo `/motor`, `/diagrama`, etc.; se comprobaría que no colisionan).
- Un `backend/escritorio.py` con el arranque (uvicorn programático, puerto fijo, comprobación de instancia única,
  registros) y la ventana pywebview con su carpeta de datos fija.
- Cargar matplotlib, plotly y ternary solo cuando se usen (hoy se importan al arrancar), para reducir arranque y
  tamaño si alguna ruta no los necesita.
- Ruta `GET /salud` para la pantalla de espera.

## 6. Riesgos y decisiones abiertas

- **SmartScreen y antivirus**: un .exe sin firmar muestra el aviso de «editor desconocido». Firmar requiere un
  certificado de firma de código (de pago). Mientras tanto: onedir + instalador y explicar el aviso.
- **Tamaño**: ~450–550 MB desempaquetado en la fase A (Python + Node + Next); ~350–450 MB en la B. Se puede reducir
  algo excluyendo pruebas de scipy y el backend de Tk de matplotlib.
- **Licencias**: thermo, chemicals y fluids (MIT), FastAPI, Next y React (MIT). Hay que revisar las condiciones de
  redistribución de los parámetros ChemSep que trae thermo y citar IAPWS e IUPAC en un «Acerca de».
- **Puerto ocupado**: con origen fijo, si otro programa ocupa el puerto la app no debe cambiarlo en silencio. En la
  fase B, la ventana pywebview puede usar un puerto libre y un almacenamiento fijo por carpeta, lo que elimina el
  problema.
- **Un solo usuario y solo local**: el servidor escucha en 127.0.0.1. No es un despliegue multiusuario.
- **Funciones sin terminar**: se distribuyen como están. Las capacidades publicadas ya dicen qué está soportado y
  qué no, y el frontend lo muestra; no hace falta ocultar nada.
- **Versionado**: número de versión visible y en los registros, ligado al commit de la build, para poder
  reproducir un resultado («qué motor produjo esto»), coherente con las huellas de modelo ya existentes.

## 7. Orden propuesto y quién hace qué

| Paso | Quién | Entregable |
|---|---|---|
| A1 | Claude | Venv de construcción, `lanzador.py`, `simulador.spec`, script `construir.ps1`; backend empaquetado y comprobado solo (sin frontend) |
| A2 | Claude + Codex | `output: 'standalone'` en Next, Node portable, lanzador con los dos procesos; prueba de humo §3.6 |
| B1 | Codex | Cambios de §4 (ruta de hojas, URL relativa, export estático, exportar/importar hojas) |
| B2 | Claude | §5 (StaticFiles, `escritorio.py`, pywebview, `/salud`, importaciones perezosas) |
| B3 | Claude | Instalador Inno Setup, prueba en un usuario limpio, documento de instalación |

A1 no depende de Codex y se puede empezar ya.
