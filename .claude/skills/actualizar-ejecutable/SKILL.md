---
name: actualizar-ejecutable
description: Reconstruye y verifica la aplicación de escritorio offline SimuladorDR.exe (Windows) con el código actual del repositorio. Usar cuando el usuario pida actualizar, reconstruir, regenerar o arreglar el ejecutable, la app de escritorio o SimuladorDR.
---

# Actualizar el ejecutable de escritorio

Sigue `empaquetado/MANTENIMIENTO.md` (léelo primero; es la fuente de verdad). Resumen operativo:

1. **Comprobar el estado**:
   - `Get-Process SimuladorDR` → si está abierto, pedir al usuario que lo cierre. No matarlo sin permiso: puede
     tener trabajo sin guardar.
   - Leer `%USERPROFILE%\Desktop\SimuladorDR\VERSION.txt` para saber qué commit tiene la versión instalada.
2. **Elegir el modo**: si desde ese commit solo cambió Python (`git diff --stat <commit> -- frontend` vacío), usar
   `-SoloEmpaquetar`; si no, la construcción completa.
3. **Construir**, en segundo plano (tarda varios minutos), desde la raíz del repositorio:
   `powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1 [-SoloEmpaquetar]`
4. **Verificar**:
   - el script termina con «Listo» y muestra la prueba de humo;
   - si falla, leer `%LOCALAPPDATA%\SimuladorDR\logs\` (`simulador.log`, `frontend.log`, `prueba.txt`) y la salida
     del script, y corregir en `empaquetado/` (nunca en `frontend/`).
   - Si la prueba falla, la versión anterior sigue instalada: no hay que deshacer nada.
5. **Informar al usuario**: versión instalada (commit de `VERSION.txt`), resultado de la prueba de humo, tamaño, qué
   cambió y si algo requiere probar la ventana a mano.

Reglas que no se negocian:
- no editar `frontend/` (se compila una copia);
- no cambiar los puertos 3317/8317;
- no tocar `%LOCALAPPDATA%\SimuladorDR\webview` (hojas del usuario);
- no detener procesos que no hayas arrancado: los servidores de desarrollo usan 3000, 8000 y 8004;
- no hacer capturas de pantalla para verificar: usar `SimuladorDR.exe --prueba`;
- no hacer commit ni push salvo que el usuario lo pida.
