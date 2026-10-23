# Simulador de destilación reactiva — aplicación de escritorio (prueba)

Versión de prueba, offline, para Windows 10/11 de 64 bits. Abre una **ventana propia**, no el navegador. No
necesita Python, Node ni conexión a internet.

## Uso

1. Copia la carpeta `SimuladorDR` completa donde quieras. No muevas el `.exe` fuera de su carpeta: necesita
   `_internal\`, `web\` y `node\`.
2. Doble clic en `SimuladorDR.exe`. La primera vez el arranque tarda unos 20 s (Windows y el antivirus revisan las
   librerías); se ve una pantalla de espera.
3. Si Windows muestra «Windows protegió su PC» (el ejecutable no está firmado): «Más información» → «Ejecutar de
   todas formas».

## Ejemplos de demostración

1. En la aplicación, ir a **Motor → Mis sistemas** (biblioteca de hojas).
2. Pulsar **Añadir ejemplos de demostración**. Se guardan dos hojas en este equipo.
3. Abrir una y pulsar **Resolver**.

| Hoja | Qué muestra | Tiempo aproximado |
|---|---|---|
| Agua y 1-butanol: dos líquidos, heteroazeótropo y vapor | Calentamiento a 1 atm con UNIFAC: dos líquidos; a 366.18 K aparece el vapor y la temperatura se queda fija mientras coexisten tres fases (L–L–V); luego desaparece el líquido acuoso y finalmente todo es vapor | 1.5–3 min |
| Destilación diferencial etanol–agua (Rayleigh) | Calentamiento con extracción continua del vapor (NRTL): el líquido se empobrece en etanol y la temperatura de burbuja sube de 355 a 367 K | ~10 s |

En una memoria USB: copiar la carpeta `SimuladorDR` completa y ejecutar `SimuladorDR.exe` desde ahí. Necesita el
componente WebView2 de Windows, que Windows 11 y Windows 10 actualizado ya traen. Las hojas se guardan en el
equipo donde se abre (`%LOCALAPPDATA%`), no en la memoria.

## Dónde quedan los datos

- Hojas y preferencias: `%LOCALAPPDATA%\SimuladorDR\webview`. Son independientes de las del navegador de
  desarrollo; borrar esa carpeta las elimina.
- Registros: `%LOCALAPPDATA%\SimuladorDR\logs` (`simulador.log`, `frontend.log`, `salida.log`).

## Puertos

Solo escucha en el propio equipo (127.0.0.1): **3317** (interfaz) y **8317** (motor). No usa los de desarrollo
(3000, 8000, 8004), así que puede abrirse con los servidores de desarrollo en marcha. Si 3317 u 8317 están
ocupados (otra copia abierta), lo avisa en vez de cambiar de puerto, porque las hojas guardadas dependen de él.

## Comprobación sin ventana

`SimuladorDR.exe --prueba` arranca el motor y la interfaz y comprueba:
- capacidades;
- páginas, incluida una hoja;
- un diagrama T–xy etanol–agua;
- hielo a −10 °C.

Escribe el resultado en `logs\prueba.txt` y termina (código 0 si todo responde).

## Qué contiene

Es el mismo código del repositorio en el momento de construirlo: backend FastAPI (`backend.main`, con todo
`core/`), frontend Next compilado con la API en `http://127.0.0.1:8317`, y un `node.exe` para servirlo.
Las funciones sin terminar están igual que en desarrollo; las capacidades publicadas dicen qué está soportado.

## Reconstruir

Desde la raíz del repositorio, en PowerShell:

```
powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1
```

Crea `%USERPROFILE%\Desktop\SimuladorDR_build` (entorno y copia del frontend, fuera del repositorio) y deja la
aplicación en `%USERPROFILE%\Desktop\SimuladorDR`. Con `-SoloEmpaquetar` reutiliza el entorno y la web ya
construidos.
