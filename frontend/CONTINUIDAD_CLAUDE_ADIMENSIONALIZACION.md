# Continuidad: núcleo de adimensionalización (Claude)

Fecha: 17 de octubre de 2026. Sirve para retomar el trabajo en una sesión nueva de Claude Code sin el historial del chat. No sustituye al plan (`PLAN_ADIMENSIONALIZACION_ECUACIONES.md`, único plan y registro) ni al contrato (`CONTRATO_NUCLEO_ADIMENSIONALIZACION.md`).

## Mensaje de arranque

> Retoma el núcleo de adimensionalización. Lee, en este orden: `frontend/CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md`, `frontend/ENTREGA_CLAUDE_ADIMENSIONALIZACION.md` (puede tener correcciones nuevas del usuario o de Codex), `frontend/CONTRATO_NUCLEO_ADIMENSIONALIZACION.md` y las secciones «Implementación Claude» y «Ampliación Claude» de `frontend/PLAN_ADIMENSIONALIZACION_ECUACIONES.md`. Ejecuta `python tests/validar_adimensionalizacion.py` para confirmar el estado antes de cambiar nada. Sin commit ni push.

## Reparto y reglas que no cambian

- **Claude:** núcleo científico en Python, sus pruebas, el contrato y los ejemplos canónicos.
- **Codex:** interfaz `/adimensionalizacion`, lectores, persistencia y exportación. Desde el 18 de octubre de 2026 el usuario encargó a Claude también esa interfaz («en este momento tú trabajarás»), con la estética del motor y sin sobrecargar las páginas.
- Codex edita el plan, la entrega y a veces el contrato **en paralelo**: hay que releerlos antes de tocarlos.
- El cliente no hace álgebra científica; no se duplica el núcleo en el navegador.
- No se modifican `/motor`, `/laboratorio`, sus solvers, termodinámica ni `core/dimensiones.py`. Del frontend, solo `/adimensionalizacion`.
- Sin dependencias nuevas: sympy está instalado pero **no** figura en `requirements.txt` y no se usa. El álgebra es propia (`fractions`); pint solo interpreta unidades.
- Sin commit ni push salvo petición expresa.
- Nunca se publica como «demostrado» algo que no se demostró; ante la duda, `no_demostrada`, `pendiente` o un diagnóstico.

## Dónde está cada cosa

| Archivo | Contenido |
|---|---|
| `core/adimensionalizacion/racional.py` | Fracciones, eliminación gaussiana incremental exacta, espacio nulo |
| `core/adimensionalizacion/algebra.py` | Forma canónica; modos `conservar`, `cartesiano`, `expandir`; `es_cero` por denominadores |
| `core/adimensionalizacion/dimensional.py` | A1: inferencia, compatible/incompatible/indeterminado, `faltantes`, unidades con pint |
| `core/adimensionalizacion/lector.py` | Lector estricto: documento v1 y v2, `transformaciones`, `referencias`, `prioridadEscalas`, `opciones`, configuración de exploración |
| `core/adimensionalizacion/transformacion.py` | `Preparado`: mapas v = g(v′) (las escalas son el caso multiplicativo), regla de la cadena, factor global, A3 por rango; `ALCANCE_EQUIVALENCIA` |
| `core/adimensionalizacion/formulacion.py` | Formulación publicada, grupos, restricciones, certificado por sustitución inversa |
| `core/adimensionalizacion/desarrollo.py` | Traza `desarrollo: PasoDesarrollo[]` |
| `core/adimensionalizacion/grupos_pi.py` | Grupos Π y bases alternativas |
| `core/adimensionalizacion/nucleo.py` | `procesar(solicitud)` y `capacidades()`; operaciones `analizar`, `transformar`, `adimensionalizar`, `explorar` |
| `core/adimensionalizacion/transformacion.py` (v2) | `escalar_llamadas` / `deshacer_llamadas` (escala de funciones), `_preparar_prioridad`, referencias en `_transformar_igualdad` |
| `tests/validar_adimensionalizacion.py` | Suite (249 comprobaciones al 17 de octubre, sección «Contrato v2 del documento»); entra en `python run_tests.py` |
| `tests/casos_adimensionalizacion.py` | Constructores de documentos de prueba |
| `tests/generar_ejemplos_adimensionalizacion.py` | Genera los 18 pares `docs/ejemplos/adimensionalizacion-*-{solicitud,resultado}.json` (2 de v2) |

## Estado al 17 de octubre de 2026

**Hecho en el núcleo:**

- A0: contrato publicado.
- A1: dimensiones, con `requiere_datos` y los datos indispensables.
- A2: transformación con certificado.
- A3: objetivos por rango exacto.
- Búsqueda automática completa desde la ecuación sola.
- Mapas afines y no lineales invertibles, con la inversa demostrada.
- Grupos Π.
- Traza completa.

**Hecho por Codex (conectado, no tocar desde el núcleo):**

- Endpoint: `backend/api_adimensionalizacion.py`, registrado en `backend/main.py` (§7 del contrato), con `GET /capacidades`, `POST ""` y `POST /dimensiones`.
- Capa dimensional `backend/dimensiones_adimensionalizacion.py` (§12), con su suite `tests/validar_capa_dimensional.py`.
- Lector `frontend/app/adimensionalizacion/lecturaNucleo.ts`, regla de vigencia, botón «Adimensionalizar» y cuaderno de hojas.
- Documento **local** v2 con `Forma.transformaciones`. El adaptador `prepararSolicitud` envía al núcleo una copia v1 y traslada los mapas a `SolicitudNucleo.transformaciones`.

**Hecho en el núcleo el 17 de octubre: documento v2** (§13 del contrato). Admite `terminoId` en objetivos, `condiciones[].ubicacion`, `funciones[].escala` (`D(c) = D* D̂(u)`), `Forma.referencias`, `Forma.prioridadEscalas` y `Forma.transformaciones`, más `opciones.referencias` y `opciones.prioridadEscalas` en la búsqueda automática. La salida de v1 no cambia. Codex todavía no envía v2: le toca actualizar tipos, lector y entradas, y resolver las llamadas a `D̂` contra `funcionesAdimensionales`.

**Hecho el 17–18 de octubre: auditoría del frontend de Gemini y estudios reales.**

- Operación `estudiar` (contrato §14) con nueve análisis, en `estudio.py`, `asintotica.py`, `dinamica.py`, `simetrias.py`, `simulacion.py` y `numerico.py`.
- Interfaz nueva: `EstudioFormulacion.tsx`, `Vista*.tsx`, `GraficoXY.tsx`, `ComparadorFormulaciones.tsx`, `informe.ts`, `lecturaEstudio.ts`, `contratoEstudio.ts`, `usoEstudio.ts` y `estudio.css`.
- 23 módulos retirados a `docs/archivo/adimensionalizacion-gemini-2026-10-17/`.
- Informe: `AUDITORIA_ADIMENSIONALIZACION_2026_10_18.md`.
- Plan con el motor: `PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md`, fases M1–M4, con cuatro decisiones del usuario pendientes (§5).

**Hecho el 18 de octubre: fase M1 con el motor.** `desdeMotor.ts` traduce una hoja de materia del motor (solo lectura) a documento v2 + valores SI; `origenMotor.ts` guarda el vínculo en `adim.motor.<documentoId>`; `ComparacionMotor.tsx` + `diferenciaMotor.ts` comparan con el resultado guardado del motor. El cuaderno usa los módulos CSS del motor (`trabajoMotor`, `balances`, `motor`). Núcleo: `simulacion.periodica` y `simulacion.tFinalSI`.

**Hecho el 18 de octubre: cierre del módulo.** Alcance en `ADIMENSIONALIZACION_ALCANCE.md`. La hoja sigue el recorrido del motor (`EntradaSimple.tsx` lleva la navegación y la página de ecuaciones; `ResultadosNucleo.tsx`, las de formulaciones, estudio, desarrollo y comparar). `Editor.tsx` aporta las «Opciones avanzadas». Los resultados se guardan en `resultadosAdim.ts` (IndexedDB).

**Pendiente** (fuera del alcance cerrado; ver el documento de alcance):

- Fases M2 (diagnóstico de malla con los límites del motor) y M3 (volúmenes termodinámicos) del plan del motor.
- Traducir `step`, reglas de estado y densidad media variable al importar.
- Propuesta automática de mapas no lineales (log, potencias).
- Cambios de coordenadas acoplados o curvilíneos y escalas dependientes de t/x.
- Objetivos no monomiales y expansión de `div(D(c) grad c)` a petición.
- Simulación en más de una coordenada.

## Trampas conocidas

- **Ejemplos canónicos.** Si cambia cualquier campo de salida, hay que correr `python tests/generar_ejemplos_adimensionalizacion.py`; si no, la suite falla, y eso es intencional: detecta ejemplos viejos.
- **Alcance del certificado.** Si cambian las identidades que usa el álgebra, hay que actualizar a la vez `ALCANCE_EQUIVALENCIA` y la sección «Certificado» del contrato.
- **Scripts de parcheo.** Escribirlos con Write, nunca como heredoc de bash, que se come las barras invertidas y las comillas. Abrir los archivos con `newline=''` para no cambiar LF por CRLF.
- **Matemática de Gemini.** Lo que no esté calculado por el núcleo y probado contra una referencia analítica no es un resultado, aunque un documento lo llame «certificado» (ver auditoría).
- **Backends del usuario sin recarga.** Los puertos 8004/8005 se arrancan sin `--reload`: tras cambiar el núcleo hay que reiniciarlos. Para probar, usa un backend propio en otro puerto (por ejemplo, 8011) y no detengas los ajenos.
- **Estudios.** La suite `tests/validar_estudio_adimensionalizacion.py` tarda unos 40 s. Los ejemplos `estudio-*` se regeneran con el mismo generador.
- **Ejecución.** Correr las suites desde la raíz con `PYTHONIOENCODING=utf-8`. Tras cambiar el núcleo, correr también `python tests/validar_capa_dimensional.py` (la envoltura de Codex depende de la salida del núcleo).
- **`backend/main.py`** tiene fines de línea mixtos: no editarlo con Edit.
- **Comprobaciones del frontend** (desde `frontend/`): `node verificar_adimensionalizacion.mjs`, `verificar_integracion_adimensionalizacion.mjs`, `verificar_capa_dimensional.mjs`, `verificar_estudio_adimensionalizacion.mjs`, `verificar_importacion_motor.mjs` (llama a Python, ~1 min), `npx tsc --noEmit --incremental false` y `npx eslint app/adimensionalizacion`.
- **Nombres de archivo en Windows:** no distinguen mayúsculas; `comparacionMotor.ts` y `ComparacionMotor.tsx` chocan. Por eso el módulo puro se llama `diferenciaMotor.ts`.
- **Motor:** no se modifica. Desde adimensionalización solo se importan funciones puras y módulos CSS suyos.
