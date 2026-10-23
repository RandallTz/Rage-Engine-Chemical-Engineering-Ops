# Mantenimiento del ejecutable de escritorio

Para cualquier sesión (Claude o Codex) que actualice `SimuladorDR.exe`. En Claude Code basta con
`/actualizar-ejecutable`, que sigue esta guía.

## Qué es

Una ventana de escritorio (pywebview + WebView2) que arranca dentro el backend FastAPI (`backend.main`) y el
frontend Next compilado, servido por un `node.exe` incluido. Funciona offline y solo escucha en 127.0.0.1:
3317 (web) y 8317 (API). Detalle y fases futuras: `docs/PLAN_EJECUTABLE_WINDOWS.md`.

| Dónde | Qué |
|---|---|
| `empaquetado/lanzador.py` | el programa: arranque, ventana, pantalla de espera, `--prueba` (sin ventana) |
| `empaquetado/construir.ps1` | construcción completa, prueba de humo y reemplazo con respaldo |
| `empaquetado/LEEME.md` | instrucciones de uso; se copia dentro de la aplicación |
| `%USERPROFILE%\Desktop\SimuladorDR_build` | entorno de construcción (venv, copia del frontend, web, dist). Fuera del repo; se puede borrar y se regenera |
| `%USERPROFILE%\Desktop\SimuladorDR` | la aplicación instalada, con `VERSION.txt` |
| `%USERPROFILE%\Desktop\SimuladorDR-anterior` | la versión previa, por si hay que volver atrás |
| `%LOCALAPPDATA%\SimuladorDR` | datos del usuario (`webview\`: hojas) y registros (`logs\`) |

## Actualizar (lo normal)

1. Cerrar la aplicación si está abierta.
2. Desde la raíz del repositorio, en PowerShell:
   `powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1`
   - Solo cambió Python (backend, `core/`): añadir `-SoloEmpaquetar`, que no recompila el frontend y es más rápido.
   - Cambió `requirements.txt`: el script lo detecta (hash) y reinstala el venv.
3. El script construye la versión nueva aparte y la prueba sin ventana (`--prueba`: capacidades, páginas, un
   diagrama T–xy, hielo). **Solo si la prueba pasa** reemplaza la aplicación; la anterior queda en
   `SimuladorDR-anterior`.
4. Revisar `VERSION.txt` (commit, fecha, versiones) y, si hubo cambios de interfaz, abrir la aplicación y probar
   lo nuevo.

Tiempo orientativo: 5–10 min completo; 2–3 min con `-SoloEmpaquetar`.

**Ejemplos de demostración:** `SimuladorDR.exe --prueba-demostracion` hace lo mismo que `--prueba` y además
resuelve las peticiones de `demostracion\` (copiadas de `docs/ejemplos/demostracion/` al construir). Las hojas
correspondientes están en el botón «Añadir ejemplos de demostración» de la biblioteca de hojas
(`frontend/app/motor/hojasDemostracion.ts`). Se regeneran con `python tests/generar_ejemplos_demostracion.py`.
Tarda unos 2 min, casi todo en el ejemplo de agua y butanol.

## Reglas

- **No modificar `frontend/`** para el ejecutable: se compila una copia. Si el ejecutable necesita un cambio de
  frontend, se documenta para Codex (`docs/PLAN_EJECUTABLE_WINDOWS.md` §4).
- **No cambiar los puertos 3317/8317** sin una migración: las hojas guardadas dependen del origen
  (`http://127.0.0.1:3317`). Cambiarlos «pierde» las hojas del usuario.
- **No borrar `%LOCALAPPDATA%\SimuladorDR\webview`**: son los datos del usuario.
- **Procesos**: detener solo los que arranca la construcción, por PID. Los servidores de desarrollo (3000, 8000,
  8004) pueden estar en marcha y no deben tocarse. No usar capturas de pantalla para verificar: usar `--prueba`.
- **Volver atrás**: cerrar la aplicación, borrar `SimuladorDR` y renombrar `SimuladorDR-anterior` a `SimuladorDR`.
- **No commit ni push** del entorno de construcción. En el repositorio solo viven los archivos de `empaquetado/`.

## Problemas conocidos y qué hacer

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| La aplicación avisa de puertos ocupados | otra copia abierta | cerrarla (Administrador de tareas: `SimuladorDR`) |
| Ventana en blanco o error de arranque | ver `%LOCALAPPDATA%\SimuladorDR\logs\simulador.log` y `frontend.log` | `SimuladorDR.exe --prueba` y leer `logs\prueba.txt` |
| `ModuleNotFoundError` en el registro | módulo importado dentro de una función, que PyInstaller no vio | añadir `--collect-submodules <paquete>` o `--hidden-import` en `construir.ps1` |
| Faltan datos de thermo, chemicals o pint | archivos de datos no incluidos | `--collect-data <paquete>` |
| La web llama a otro puerto | build sin `NEXT_PUBLIC_API_URL` | el script ya lo comprueba (falla si los chunks no apuntan a 8317) |
| «Windows protegió su PC» | ejecutable sin firmar | «Más información» → «Ejecutar de todas formas»; firmar requiere certificado |
| Arranque lento la primera vez (~20 s) | antivirus y caché fría | normal; las siguientes veces es más rápido |

## Si se añade una función al backend

Rutas nuevas en `backend/main.py` o módulos nuevos en `backend/` y `core/` entran solos (`--collect-submodules`).
Si se añade una dependencia a `requirements.txt` con datos propios, añadir su `--collect-data` y comprobarlo con
`--prueba`. Si la función nueva es importante, añadir una comprobación a `prueba()` en `lanzador.py`.
