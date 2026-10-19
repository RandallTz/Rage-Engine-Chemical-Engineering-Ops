# Adimensionalización: qué hace, cómo se usa y qué queda fuera

Estado al 18 de octubre de 2026: **módulo cerrado en este alcance**. Lo que no figura en «Qué hace» no se ofrece, y la interfaz lo dice cuando aparece; no hay paneles que aparenten un cálculo.

La adimensionalización es una extensión del motor (`/motor`). Lee sus hojas de materia sin modificarlas y comparte su estética: el cuaderno importa los módulos CSS del motor.

## Qué hace

**Núcleo** (`core/adimensionalizacion`, Python, álgebra exacta propia; pint solo para unidades):

- **Dimensiones:** comprueba la homogeneidad de cada ecuación, infiere las dimensiones que faltan y pide solo las unidades indispensables.
- **Transformación y búsqueda:**
  - cambios de variable multiplicativos, afines y no lineales declarados, con su inversa;
  - búsqueda automática de todas las normalizaciones de la familia (objetivos por rango exacto);
  - cada formulación se certifica por sustitución inversa.
- **Grupos:** grupos de la formulación, teorema Π del sistema y bases alternativas; traza completa del desarrollo algebraico.
- **Documento v2:**
  - objetivos por término y referencias de factor global;
  - prioridad de escalas;
  - ubicación de las condiciones de frontera;
  - funciones con escala declarada, D(c) = D* D̂(u).
- **Estudio de una formulación** (operación `estudiar`):
  - lectura física de los grupos (Fourier, Péclet, Damköhler…);
  - sensibilidad y valores en SI;
  - régimen dominante con capas límite;
  - escalas, malla recomendada y rigidez;
  - simetrías y reducción por semejanza u ondas viajeras;
  - estabilidad lineal σ(k) con Turing y Hopf;
  - continuación con pliegues;
  - simulación por método de líneas con BDF, en una coordenada o sin ella, con frontera periódica opcional y tiempo final en segundos, y script de Python exportable.

**Interfaz** (`frontend/app/adimensionalizacion`):

- **Cuaderno (desde el 19 de octubre de 2026):** Desde el Engine · Adimensionalizadas · Archivadas · Retiradas. Exportar e importar el cuaderno.
  - **Única entrada:** una hoja del Engine. La adimensionalización trabaja solo sobre ecuaciones derivadas de las fundamentales con supuestos (ARQUITECTURA_MOTOR.md §2, principio 10).
  - Ya no se escriben modelos aquí: desaparecieron «Nueva hoja», el «Catálogo» y «Añadir modelos de partida».
  - En un documento derivado, las ecuaciones se muestran solo para leer, con el enlace a su hoja del Engine. Para cambiarlas, se edita la hoja y se vuelve a importar.
  - La edición del modelo en JSON y la ubicación de las condiciones quedan cerradas. Sí se trabaja lo propio de la adimensionalización: escalas, objetivos, mapas, signo de las variables y estudios.
  - **Retiradas:** al abrir el cuaderno, o al importarlo, todo documento sin origen en el Engine (`adim.motor.<id>`) queda retirado (`hojas.ts`, `retirarEscritas`). Se conserva, con su motivo y su fecha, para exportarlo; no se abre para trabajar.
  - `ejemplos.ts` y los `docs/ejemplos/adimensionalizacion-*` siguen como fixtures de prueba del núcleo y del formato; no se ofrecen en la interfaz.
- **Hoja**, con el recorrido del motor (← Hojas · Ecuaciones · Formulaciones · Estudio · Desarrollo · Comparar). Cada página tiene tarjeta, panel con cifras y un botón principal:
  - Ecuaciones: texto, vista previa, unidades y «Opciones avanzadas» (búsqueda, escalas fijadas, signos, dominios y condiciones, JSON, importar o exportar el documento);
  - Formulaciones: ecuaciones adimensionales, grupos y detalles técnicos plegados;
  - Estudio: valores físicos como filas del motor y pestañas de análisis;
  - Desarrollo: la traza paso a paso;
  - Comparar: las formulaciones lado a lado con tus valores.
- **Resultados guardados** como en el motor, en IndexedDB `rage-adimensionalizacion-resultados`. Solo se reutilizan si el documento y el texto no cambiaron; renombrar la hoja no los invalida.
- **Del motor:** importa una hoja de materia (total, local temporal o campo 1D), precarga sus valores en SI, simula hasta su tiempo final y da una cifra: la diferencia con el resultado guardado del motor.
- **Informe imprimible y exportaciones:** LaTeX del desarrollo, JSON, CSV y script de Python.

## Qué queda fuera de este alcance

Se declaran; no se aproximan.

- **Búsqueda automática:**
  - no propone cambios de variable logarítmicos o de potencias (se declaran a mano en la forma);
  - no admite objetivos no monomiales.
- **Geometría y escalas:** sin coordenadas curvilíneas acopladas ni escalas que dependan de t o x.
- **Simulación:**
  - una coordenada espacial;
  - diferencias centradas, que pueden oscilar con convección dominante si se fuerza una malla menor que la recomendada;
  - sin eventos: no se detiene si un campo llega a cero, a diferencia del motor;
  - solo derivadas de orden 1 y 2.
- **Importación del motor:**
  - no traduce `step`, las reglas de estado ni la densidad media variable;
  - tampoco la energía, los ensamblajes de varios volúmenes ni la termodinámica, que son materia de la conexión siguiente (fase M3).
- **Almacenamiento:** los estudios (gráficas de simulación, continuación) no se guardan; se recalculan. Sí se guardan los valores físicos y las formulaciones.

## Verificación

Desde la raíz, con `PYTHONIOENCODING=utf-8`:

- `python tests/validar_adimensionalizacion.py`: 264 comprobaciones del núcleo.
- `python tests/validar_estudio_adimensionalizacion.py`: 63 comprobaciones contra soluciones analíticas.
- `python tests/validar_capa_dimensional.py` y `python tests/validar_api_adimensionalizacion.py`.

Desde `frontend/`:

- `node verificar_adimensionalizacion.mjs` (103), `verificar_integracion_adimensionalizacion.mjs` (79), `verificar_capa_dimensional.mjs` (33), `verificar_estudio_adimensionalizacion.mjs` (66) y `verificar_importacion_motor.mjs` (117; las 8 hojas de prueba del motor frente al motor y a la solución analítica).
- `npx tsc --noEmit --incremental false` y `npx eslint app/adimensionalizacion`.

## Documentos relacionados

- [CONTRATO_NUCLEO_ADIMENSIONALIZACION.md](CONTRATO_NUCLEO_ADIMENSIONALIZACION.md): el contrato del núcleo.
- [PLAN_ADIMENSIONALIZACION_ECUACIONES.md](PLAN_ADIMENSIONALIZACION_ECUACIONES.md): plan y registro.
- [PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md](PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md): M1 hecha; M2–M4 pendientes.
- [CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md](CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md): para retomar.
