# Arquitectura del motor de simulación

**Documento de entrada para cualquier persona o LLM** (Claude, Codex, Gemini…) que vaya a trabajar en este repositorio. Explica qué es el simulador, de qué piezas se compone, qué reglas no se rompen y dónde vive hoy cada pieza. Es la referencia de estructura; el estado de avance de cada fase física sigue en [frontend/ROADMAP_MOTOR_MULTIFISICO.md](frontend/ROADMAP_MOTOR_MULTIFISICO.md).

Versión 1 · 18 de octubre de 2026 · Propuesta aprobada en su enfoque por el usuario; la migración todavía no empieza (ver §10).

---

## 1. Qué es

Un simulador **orientado a ecuaciones** de procesos químicos. El usuario no elige un «equipo» ni un «escenario»:

1. parte de las leyes de conservación generales;
2. las reduce con supuestos explícitos hasta el modelo que quiere;
3. el sistema lo resuelve, lo analiza y lo presenta.

La arquitectura es un **motor de motores**:

- cada motor pequeño hace una sola cosa, tiene un contrato de entrada y otro de salida, y no conoce a los demás;
- todos hablan un único idioma: el **modelo común** (§4);
- la interfaz no calcula; solo compone motores y presenta lo que devuelven.

Analogía de trabajo: cada motor es un engranaje en su eje. Un engranaje nuevo (por ejemplo, la adimensionalización) se monta entre otros dos sin reescribirlos. Un ejemplo, un caso de prueba o una «demo» **no** traen código propio: son documentos (datos) que pasan por los mismos engranajes. Sus gráficas salen del motor de gráficas, no de un componente hecho para ellos.

## 2. Principios que no se rompen

1. **Un solo modelo.** Toda ecuación, variable, unidad, dominio, condición y supuesto vive en la representación común (§4). No hay «una ecuación para mostrar y otra para resolver».
2. **La termodinámica siempre está presente** (§3). Ninguna fase se supone por omisión.
3. **Los supuestos son transformaciones trazables.** Cada reducción es una operación del modelo con su condición de validez, su autor (usuario o regla) y su efecto. Se puede deshacer y auditar.
4. **El cliente no hace ciencia.** El álgebra simbólica, los solvers, la termodinámica y las unidades corren en el backend (Python). El navegador edita documentos y presenta resultados. (Excepción vigente y por migrar: el solver TS del motor, §6.)
5. **Un servicio por responsabilidad.** Un sistema de unidades, un formato de resultados, un motor de gráficas, un almacén de documentos. Duplicar uno de ellos es un defecto.
6. **Contrato primero.** Antes de escribir un motor o una pantalla se fija su contrato (entrada, salida, errores, versión) y su lector estricto. Nunca se inventan campos que el backend no publica.
7. **Nada se publica como demostrado si no se demostró.** Un resultado incierto se marca `no_demostrada`, `pendiente` o `requiere_datos`; un modelo que el motor no sabe tratar se rechaza con el motivo, no se aproxima en silencio.
8. **Toda pieza tiene su prueba contra una referencia independiente** (analítica, publicada o de otro método), no solo contra sí misma.
9. **Sin sesgo hacia ninguna operación.** Las ecuaciones fundamentales dan lo que deben dar para cualquier componente, mezcla o configuración.
10. **Todo modelo parte SIEMPRE de las ecuaciones fundamentales** (regla del usuario, 19 de octubre de 2026). Con los supuestos, uno a uno y registrados, se llega al modelo que se necesita. Nunca se plantea directamente el modelo.
    - Vale para cada familia, cada una en su panel: la conservación local de materia, el primer principio de la energía, el momento y las relaciones termodinámicas fundamentales.
    - **Termodinámica:** los supuestos de estado (número de fases, cambio de fase, densidad constante, u(T) declarada, paquete) se declaran en la derivación termodinámica (`frontend/app/motor/recorridoTermodinamico.ts`), no en la de energía. El balance de energía los usa a través de su formulación efectiva (`formulacionEnergiaHoja`).
    - **Redes termodinámicas:** cada volumen muestra su derivación desde la ecuación fundamental con los supuestos que declara (`DerivacionVolumenRed.tsx`), y después las ecuaciones que ensambla el Engine.
   - Ningún motor tiene ramas por tipo de equipo («tanque», «columna», «reactor») ni por nombre de escenario.
   - Las magnitudes se definen por su dimensión, no por una lista de unidades.
   - Las fases candidatas las fija el paquete, no el caso.
   - Los resultados y las gráficas no saben de dónde vienen.
   - Una operación concreta es una combinación de leyes, supuestos y datos: nunca código propio.

## 3. La termodinámica como parte permanente del modelo

La termodinámica no es una tabla de propiedades que se consulta cuando hace falta. Es un **conjunto de relaciones que forma parte de todo modelo con materia y energía**, aunque en un caso concreto parezca innecesario.

### 3.1 La idea

El estado de cada volumen se describe con **cantidades conservadas**: moles de cada especie nᵢ, energía interna U (o entalpía H si la presión está prescrita) y volumen V. Los balances integran solo esas cantidades. En cada evaluación, el **cierre de equilibrio** resuelve, a partir de (n, U, V) o (n, H, P), la temperatura, la presión, cuántas fases hay y la cantidad y composición de cada una.

Las ecuaciones de todas las fases posibles **están siempre ahí**:

- **Líquido subenfriado:** el cálculo da β_vapor = 0, la cantidad de vapor es cero y su condición de equilibrio queda como desigualdad (plano tangente no negativo).
- **Al calentar:** la energía acumulada llega al punto de burbuja. Ahí la condición de vapor se vuelve igualdad y β_vapor empieza a crecer desde cero.
- **Al terminar:** si se calienta lo suficiente, el líquido desaparece del mismo modo.

No se cambia de modelo, no se activa un «modo vapor», no hay una ecuación nueva: es la misma formulación, que antes daba cero y ahora no. Así el motor **sabe** cuándo un líquido es un líquido, y no porque el usuario lo haya declarado. Por eso puede atravesar ebullición, condensación o aparición de una segunda fase líquida sin discontinuidades en el modelo.

Matemáticamente es una condición de complementariedad por fase k: βₖ ≥ 0, distancia del plano tangente TPDₖ ≥ 0 y βₖ·TPDₖ = 0.

### 3.2 Lo que sí cambia al aparecer una fase

Las propiedades tienen una **arista** en la frontera de saturación: la derivada de h(T) cambia bruscamente, el cp aparente salta. Eso es física, no un cambio de ecuaciones.

El integrador la trata así:

1. detecta el instante en que cambia el conjunto de fases;
2. lo localiza por bisección;
3. reinicia ahí, para no promediar a través de la arista.

El evento es una técnica numérica para la precisión. El modelo no cambia.

### 3.3 Las tres piezas de la capa termodinámica

| Pieza | Qué es | Ejemplo |
|---|---|---|
| Datos y parámetros | Base de datos con fuente, unidad, dominio y huella | Tc, Pc, Psat(T), Cp ideal, v_L, parámetros NRTL, grupos UNIFAC |
| Modelo de estado | El potencial termodinámico del paquete, del que derivan todas las propiedades | IAPWS-95, gas ideal + solución ideal, NRTL, UNIFAC |
| Cierre de equilibrio | Las relaciones siempre presentes: dado (n, U, V) o (n, H, P), devuelve T, P, fases, βₖ, composiciones, potenciales y certificado de estabilidad | flash UV, PH, TP, con prueba de estabilidad |

Los balances (capa Formular) nunca contienen una propiedad «fija» que contradiga el paquete. Un u(T) lineal o una «fase asumida» solo existen como **supuesto explícito**, registrado por el motor de supuestos, con su dominio de validez vigilado durante el cálculo.

### 3.4 Estado actual frente a este principio

| Camino | ¿Cumple? | Detalle |
|---|---|---|
| Backend de ensamblaje (`core/ensamblaje_dinamico.py`, `core/ensamblaje_red.py`) | **Sí** | Estado (n, U) o (n, H); cierre UV o PH en cada evaluación; eventos de fase solo para reiniciar el integrador; muestras certificadas con flash completo |
| Compilador del modelo común (`core/compilador/`) | **Sí** | Estado (n, U o H); cierre de la capa en cada evaluación; eventos solo para reiniciar el integrador |
| Capa termodinámica del modelo común (`core/termodinamica/capa.py`) | **Sí** | Fases candidatas fijas por paquete; todo estado las publica todas con β, composición y tm; complementariedad β·tm = 0 ([docs/CAPA_TERMODINAMICA.md](docs/CAPA_TERMODINAMICA.md)) |
| Solver TS del motor (`frontend/app/motor/modeloEnergia.ts`) | No | u(T) lineal manual y fase «asumida sin verificación». Debe pasar a ser un supuesto explícito o migrar al cierre real |
| Adimensionalización (`core/adimensionalizacion`) | No aplica todavía | No ve la termodinámica. Al acoplarse, las propiedades entran como funciones con escala declarada, por ejemplo h(T) = c_p,ref·T_ref·ĥ(T̂), sin que el núcleo opere sobre el paquete |

## 4. El modelo común

Es la pieza que hoy falta y la primera que se construye (§10). Una sola representación, versionada, con lector estricto en Python y TypeScript.

| Entidad | Contenido |
|---|---|
| Símbolo | id, rol (tiempo, coordenada, campo, parámetro, constante), dimensión exacta, unidad, signo, dependencias |
| Expresión | árbol tipado: número, símbolo, suma, producto, cociente, potencia, función, llamada a función declarada, derivada, gradiente, divergencia, laplaciano |
| Ecuación | igualdad con id, familia (materia, energía, momento, constitutiva, termodinámica, definición) y procedencia |
| Volumen / dominio | región con sus cantidades conservadas, su frontera y su paquete termodinámico |
| Corriente / conexión | topología: origen, destino, mecanismo, qué transporta |
| Condición | inicial o de frontera, con su ubicación |
| Supuesto | operación aplicada, condición de validez, quién la aplicó, ecuaciones afectadas |
| Función declarada | propiedades y leyes que el modelo usa pero no desarrolla, con dimensión y, si procede, escala (h(T, P, x), D(c)…) |
| Procedencia | de dónde sale cada elemento: plantilla, supuesto, usuario, motor |

Base de partida: el documento v2 de la adimensionalización ([frontend/app/adimensionalizacion/contrato.ts](frontend/app/adimensionalizacion/contrato.ts) y [frontend/CONTRATO_NUCLEO_ADIMENSIONALIZACION.md](frontend/CONTRATO_NUCLEO_ADIMENSIONALIZACION.md)). Es la representación más completa que existe hoy: tiene dimensiones exactas, operadores diferenciales, dominios, condiciones ubicadas y funciones con escala. Le faltan volúmenes, corrientes, supuestos y la capa termodinámica, que se añaden.

## 5. Los motores

Cada motor: un contrato de entrada, uno de salida, errores tipados, sin interfaz, sin conocer a otros motores salvo por el modelo común, y con sus propias pruebas.

### Formular

| Motor | Hace | Entrada → salida |
|---|---|---|
| Balances | Biblioteca de leyes generales en forma local: materia por especie, energía (primera ley), momento, entropía | familia + componentes → ecuaciones locales |
| Supuestos | Reduce el modelo con operaciones trazables: integrar sobre el volumen, Gauss, Reynolds, invariancias, uniformidad, puertos, estacionario… | modelo + operación → modelo + registro |
| Constitutivas | Leyes que se enchufan en términos: Fick, Fourier, cinéticas, leyes de descarga, transferencia entre fases | término + ley → término desarrollado |
| Topología | Compone varios volúmenes y corrientes en un modelo único; incidencias, conexiones internas | volúmenes + corrientes → modelo ensamblado |
| Termodinámica | Añade a cada volumen su cierre de equilibrio (§3) | volumen + paquete → relaciones de estado |

### Transformar y analizar

| Motor | Hace | Entrada → salida |
|---|---|---|
| Unidades y dimensiones | Interpreta unidades, convierte a SI, infiere dimensiones, comprueba homogeneidad | modelo → diagnóstico + dimensiones |
| Estructura | Grados de libertad, datos frente a incógnitas, tipo de sistema (EDO, DAE, algebraico), rango e índice | modelo + datos → recuento + clasificación |
| Adimensionalización | Escalas, formulaciones certificadas, grupos, teorema Π | modelo → modelo escalado + grupos |
| Discretización | EDP → sistema semidiscreto con el esquema elegido (volúmenes finitos, método de líneas, orden del esquema) | modelo + malla → sistema de EDO o DAE |

### Calcular

| Motor | Hace | Entrada → salida |
|---|---|---|
| Propiedades | Evalúa el modelo de estado y el cierre de equilibrio de un paquete | (n, U, V) o (T, P, x) → estado certificado |
| Compilador | Modelo + datos → funciones numéricas (lado derecho, jacobiano, eventos) | modelo + datos → sistema numérico |
| Solvers | Integran o resuelven sin saber de física: EDO explícitas e implícitas, DAE, estacionario (Newton), continuación | sistema numérico → trayectoria |
| Estudios | Estabilidad, régimen dominante, sensibilidad, continuación, simetrías | modelo (+ valores) → análisis |

### Presentar y comprobar

| Motor | Hace | Entrada → salida |
|---|---|---|
| Resultados | Formato único de serie: variable, unidad, dominio, tiempo, procedencia, firma | trayectoria → conjunto de resultados |
| Gráficas | Único motor de gráficas y diagramas; recibe resultados y una especificación | resultados + especificación → figura |
| Verificación | Residuos de conservación, segunda ley, certificados, comparación con referencias | resultados + modelo → informe de verificación |
| Informes | LaTeX, CSV, PDF/HTML, script de Python | modelo + resultados → archivo |

### Transversales

| Motor | Hace |
|---|---|
| Documento | La hoja es el proyecto: modelo, datos, supuestos, resultados y vistas. Un almacén, versiones, firmas que invalidan lo dependiente |
| Catálogo | Componentes, paquetes y **plantillas** (los ejemplos son plantillas: documentos, nunca código) |
| Orquestador | El recorrido de una hoja: qué motor se llama en cada paso y con qué |

### Recorrido de una hoja

Formular (balances → supuestos → constitutivas → topología → termodinámica) → Datos → Unidades y Estructura → (Adimensionalizar, opcional) → Discretizar → Compilar → Resolver → Resultados → Gráficas, Verificación, Estudios, Informes.

En la interfaz cada paso es **la vista de un motor**, no un módulo independiente.

## 6. Dónde está hoy cada pieza

Lo que existe funciona y está probado, pero repartido y duplicado. Esta tabla es el punto de partida de la migración.

| Motor | Hoy | Observación |
|---|---|---|
| Modelo común | `core/modelo/`, `frontend/motores/modelo/` | v0: representación, lector y relaciones; todavía no la consume ningún solver ni pantalla |
| Capa termodinámica | `core/termodinamica/` | Fases candidatas fijas y complementariedad sobre `core/mezclas` y `core/agua_iapws95` |
| Balances + Supuestos | **Motor de balances en el servidor: `core/balances/`** ([docs/MOTOR_BALANCES.md](docs/MOTOR_BALANCES.md)): genera las ecuaciones de materia (redes de volúmenes) y de energía con u(T) supuesta desde los supuestos de cada volumen. Sigue en el cliente la derivación que se muestra: `frontend/app/motor/recorridoMateria.ts`, `operadores.ts`, `recorridoEnergia.ts` | La derivación visible y la generación ejecutable conviven; momento solo simbólico |
| Topología | `frontend/app/motor/ensamblajeMateria.ts` (masa, TS); `backend/motor_ensamblaje_v2.py` + `core/ensamblaje_red.py` (red termodinámica) | Dos implementaciones |
| Termodinámica | `core/agua_iapws95.py`, `core/mezclas.py`, `core/unifac.py`, `core/hielo_ih.py`, `core/coexistencia_lv.py`, `core/catalogo.py`, `backend/motor_termodinamica.py` | Correcta y contrastada (miles de comprobaciones). Base para §3 |
| Unidades | **Servicio único `core/unidades/`** (`/unidades/*`, [docs/SERVICIO_UNIDADES.md](docs/SERVICIO_UNIDADES.md)). Siguen en uso, por migrar: `frontend/app/motor/unidadesMotor.ts`, `backend/motor_ensamblaje.UNIDADES`, `core/adimensionalizacion/dimensional.py`, `core/dimensiones.py` | Equivalencia comprobada unidad por unidad con los cuatro |
| Expresiones | `frontend/app/motor/expresionesMotor.ts`, `core/expresiones_motor.py`, `frontend/app/adimensionalizacion/contrato.ts` | **Tres representaciones** |
| Estructura | `analizarMotor` en `modeloNumerico.ts` (recuento estructural) | Solo recuento |
| Adimensionalización | `core/adimensionalizacion/` (núcleo), `frontend/app/adimensionalizacion/` | Cerrada en su alcance: [frontend/ADIMENSIONALIZACION_ALCANCE.md](frontend/ADIMENSIONALIZACION_ALCANCE.md) |
| Discretización | Volúmenes finitos upwind en `modeloNumerico.ts`; método de líneas centrado en `core/adimensionalizacion/simulacion.py` | Dos esquemas en dos lugares |
| Compilador + Solvers | **Propios del modelo común: `core/compilador/` y `core/solvers/`** (corte vertical). Siguen en uso: TS `modeloNumerico.ts` e `integracionMotor.ts`; Python `core/ensamblaje_*.py` y `core/adimensionalizacion/simulacion.py` (BDF, método de líneas) | El compilador propio reproduce los ensamblajes del motor; el 1D y el solver TS quedan por migrar |
| Estudios | `core/adimensionalizacion/{estudio,dinamica,asintotica,simetrias}.py` | Atados al modelo adimensional; deben aceptar cualquier modelo |
| Resultados | **Formato común `core/resultados/` y `frontend/motores/resultados/`** ([docs/FORMATO_RESULTADOS.md](docs/FORMATO_RESULTADOS.md)). La simulación del núcleo lo publica; el ensamblaje v2 y el solver TS tienen adaptador | `ResultadoMotor` y `RespuestaResolucionV2` siguen como salidas propias hasta migrar sus motores |
| Gráficas | **Motor único `frontend/componentes/graficas/`** (datos puros + renderizador); lo usa la adimensionalización. Por migrar: `frontend/app/motor/TableroMotor.tsx` y `frontend/app/components/Diagrama*.tsx` | `GraficoXY.tsx` archivado |
| Verificación | Residuos y certificados del backend; comparación en `diferenciaMotor.ts` | Repartida |
| Informes | `frontend/app/adimensionalizacion/{informe,exportar,exportarDesarrollo}.ts`, CSV del motor | Repartida |
| Documento | localStorage `rage.motor.hojas.v1` + IndexedDB `rage-motor-resultados`; localStorage `rage.adimensionalizacion.hojas.v1` + IndexedDB `rage-adimensionalizacion-resultados` | **Dos almacenes** |

Mapa funcional detallado del motor actual: [frontend/MAPA_MOTOR.md](frontend/MAPA_MOTOR.md).

**Fuera del motor nuevo** (anteriores, no se modifican sin encargo expreso): `/laboratorio`, `/columna`, `/flowsheet`, `/termodinamica`, `thermodynamics/`, y los módulos clásicos de `core/` (McCabe-Thiele, Ponchon-Savarit, FUG, CSTR, PFR, columna…). Su destino está pendiente de decisión (§9).

## 7. Organización objetivo del código

```
core/                     Python: un paquete por motor
  modelo/                 representación común, lector y versión
  balances/  supuestos/  constitutivas/  topologia/
  termodinamica/          datos, modelos de estado, cierre de equilibrio
  unidades/  estructura/  adimensionalizacion/  discretizacion/
  compilador/  solvers/  estudios/  resultados/  verificacion/  informes/
backend/                  FastAPI: una ruta por motor, sin lógica física
frontend/
  motores/<motor>/        contrato TS, cliente HTTP y lector estricto (sin UI)
  componentes/            piezas visuales compartidas: gráfica, fórmula,
                          campo con unidad, panel de cifras, tablas
  app/hojas/[id]/<paso>/  páginas del recorrido de una hoja; componen
                          motores, no calculan
docs/                     fundamentos matemáticos por motor
tests/                    pruebas por motor contra referencias independientes
```

La migración es incremental (§10): ningún módulo actual se reescribe de golpe, y sus suites deben seguir pasando en cada paso.

## 8. Reglas de trabajo para cualquier agente

- **Leer antes de tocar:** este documento; después el documento de continuidad del motor afectado (`frontend/CONTINUIDAD_*.md`, `frontend/ROADMAP_MOTOR_MULTIFISICO.md`) y su contrato.
- **No modificar el motor actual (`frontend/app/motor`, `backend/motor_*.py`, `core/ensamblaje_*.py`) sin encargo expreso del usuario.** La migración se hará por pasos aprobados.
- **Contrato primero:** cada cambio de salida de un motor actualiza su contrato, sus ejemplos canónicos (`docs/ejemplos/`) y su lector estricto en el mismo cambio.
- **Pruebas:** cada motor tiene su suite. Cambiar un motor exige correr la suya y las de quienes lo consumen.
  - adimensionalización: [frontend/ADIMENSIONALIZACION_ALCANCE.md](frontend/ADIMENSIONALIZACION_ALCANCE.md) §Verificación;
  - motor: `npm run test:motor-fundamental` y `tests/validar_motor_*.py`.
- **Git:** sin commit ni push salvo petición. Al commitear, archivo por archivo, nunca `git add -A`: el árbol tiene cambios de varios autores. Rama de trabajo: `fase-a-adopcion`.
- **Procesos:** los backends del usuario corren en 8004 (general) y 8005 (adimensionalización) y el frontend en 3000. Para probar, usa otro puerto. No detengas procesos ajenos y, si hay que detener uno propio, hazlo por PID, nunca por nombre.
- **Edición:** `backend/main.py` tiene fines de línea mixtos; edítalo con un script que abra con `newline=''`. No uses heredocs para scripts con barras invertidas.
- **Cada ecuación va en su lugar** (regla del usuario, 19 de octubre de 2026). Un panel de la hoja muestra solo las ecuaciones de su familia física, nunca «todas las del sistema»:
  - **Materia:** conservación por componente, caudal y composición de cada corriente, comprobación global de materia.
  - **Energía:** primera ley, entalpía de las corrientes, calor entre volúmenes, trabajo de frontera, comprobación global de energía.
  - **Momento:** cantidad de movimiento.
  - **Termodinámica:** cierre de estado y equilibrio entre fases, con su estabilidad.
  - La clasificación vive en un solo sitio, `frontend/app/motor/ubicacionEcuaciones.ts`. Una ecuación sin lugar es un error del motor. `frontend/verificar_ubicacion_ecuaciones.mjs` comprueba que cada ecuación publicada por el Engine en los ejemplos tiene exactamente un lugar.
  - Una familia nueva de ecuaciones se clasifica ahí antes de mostrarse.
- **Ciencia:** toda fórmula o API que venga de otra fuente (incluido otro LLM) se implementa y se comprueba numéricamente contra una referencia antes de darla por buena.

## 9. Decisiones del usuario

### 9.1 Tomadas (18 de octubre de 2026)

1. **UNIFAC tiene prioridad completa; NRTL no se trata.** Los paquetes NRTL siguen publicados y sus suites deben seguir pasando, pero no se amplían, no se contrastan más y no se usan como caso guía de piezas nuevas. Toda prueba nueva de mezclas no ideales usa UNIFAC (`unifac-original-public`, `unifac-dortmund-public`, `unifac-original-lle-public`).
2. **Prioridad a pulir la termodinámica** (§10, bloque A).
3. **Discretización y mallado no son adimensionalización.** Pertenecen al motor de transformación/solvers y son un paso **posterior** al escalado en el recorrido de la hoja (§5, §11). El método de líneas que hoy vive en `core/adimensionalizacion/simulacion.py` se trasladará a un motor de discretización propio (`core/discretizacion/`); la adimensionalización conserva escalas, grupos, formulaciones certificadas y estudios.
4. **Pulir los balances** según lo pendiente del checklist (`/checklist`, `frontend/app/checklist/datos.ts`) (§10, bloque B).
5. **Unificar Ecuaciones y Adimensionalización** en un recorrido único de la hoja, para que el usuario vea cómo funciona el motor (§11).
6. **Dónde vive el cálculo:** en Python (aprobado con el paso 5). El solver TS del motor se sustituye por el compilador y los solvers comunes cuando haya paridad demostrada.
7. **El objetivo final es simular multifísica, no tener UNIFAC al 100 %.** El contraste experimental de UNIFAC (y de cualquier paquete) se hace **al final**. Ahora importa que el Engine funcione de punta a punta: se parte de las ecuaciones fundamentales, se simplifican con supuestos y se resuelve. El modelo es general: nada se sesga para que resuelva un tipo de modelo.
8. **Nombre visible:** la página que la barra llamaba «Ecuaciones» (`/motor`) se llama **Engine**. Las rutas y el código conservan `motor`; el paso «Ecuaciones» dentro de cada hoja sigue siendo el paso de las ecuaciones.
9. **Batería multifísica:** `frontend/verificar_bateria_multifisica.mjs` pasa todas las hojas de prueba por el camino común y escribe `docs/BATERIA_MULTIFISICA.md`, con lo que resuelve y lo que falta por motivo. Es la lista de trabajo del Engine común.

### 9.2 Abiertas

1. **Dónde vive el cálculo.** *(Resuelta en 9.1.6; se conserva el texto original.)* Propuesta: todo en Python, migrando el solver TS del motor. Alternativa: conservar un solver ligero en el navegador para respuesta inmediata.
2. **Qué entra en el motor.** ¿`/laboratorio`, `/columna`, `/flowsheet` y `/termodinamica` se rehacen como plantillas y estudios del motor, o quedan como legado?
3. **Reparto de trabajo.** Hoy trabaja solo Claude. Con motores separados, cada agente puede tomar motores concretos sin pisar a otro.

## 10. Orden de trabajo

1. **Modelo común v0** — **hecho el 18 de octubre de 2026.**
   - Contrato: [docs/CONTRATO_MODELO_COMUN.md](docs/CONTRATO_MODELO_COMUN.md).
   - Código: `core/modelo/` (lector, relaciones siempre presentes, adaptadores) y `frontend/motores/modelo/` (tipos, lector y adaptador de hojas del motor).
   - Pruebas: `tests/validar_modelo_comun.py` (102) y `frontend/verificar_modelo_comun.mjs` (117).
   - Los tres casos (hojas de materia del motor TS, solicitudes v2 del ensamblaje termodinámico y documentos de adimensionalización) caben sin pérdida. Las relaciones estructurales del modelo coinciden con las ecuaciones que genera el backend en 23 ensamblajes.
2. **Termodinámica como capa del modelo** — **hecho el 18 de octubre de 2026** para los paquetes de mezcla: [docs/CAPA_TERMODINAMICA.md](docs/CAPA_TERMODINAMICA.md), `core/termodinamica/`.
   - Cada volumen tiene un conjunto fijo de fases candidatas. En todo estado se publica, por fase, su cantidad, su composición (o la incipiente) y su distancia al plano tangente, con complementariedad β·tm = 0.
   - Prueba guía `tests/validar_capa_termodinamica.py` (179 comprobaciones): benceno y tolueno calentados hasta evaporarse por completo. Las mismas ecuaciones de principio a fin; burbuja y rocío iguales a Raoult en forma cerrada (1e-4 K) y a Antoine (0,02 K).
   - Agua pura (IAPWS-95) envuelta con su prueba de ebullición `tests/validar_capa_agua.py` (161 comprobaciones), contrastada con IF97 y con tablas publicadas.
3. **Un servicio de unidades**, **un formato de resultados** y **un motor de gráficas** — **hecho el 18 de octubre de 2026.**
   - Unidades: `core/unidades/` y `/unidades/*`. 264 comprobaciones, más 235 contra la tabla del motor; equivalencia exacta con los cuatro sistemas anteriores.
   - Resultados: `core/resultados/` y `frontend/motores/resultados/`. 34 comprobaciones.
   - Gráficas: `frontend/componentes/graficas/`. 175 comprobaciones con resultados de tres motores distintos graficados por el mismo código.
   - Los sistemas antiguos siguen funcionando hasta que se migre cada motor (paso 5).
4. **Corte vertical** — **hecho el 18 de octubre de 2026:** [docs/CORTE_VERTICAL.md](docs/CORTE_VERTICAL.md).
   - El modelo común se resuelve con el compilador y el solver propios (`core/compilador`, `core/solvers`), con salida en el formato común y en el motor de gráficas.
   - Rutas: `POST /modelo/validar` y `POST /modelo/resolver`.
   - Pruebas: `tests/validar_corte_vertical.py` (71) y `frontend/verificar_corte_vertical.mjs` (14).
   - El mismo código, sin ramas por caso, reproduce la prueba guía, el agua que hierve y los cuatro ensamblajes del motor, entre 1e-7 y 1e-16 del motor existente.
   - Las pantallas actuales siguen funcionando.
5. **Migración por motor:** balances y supuestos al backend; solver TS sustituido por el compilador y los solvers comunes; la adimensionalización y los estudios consumen el modelo común.
   - **5.1 hecho en su núcleo el 18 de octubre de 2026:** el compilador tiene una segunda entrada que ejecuta ecuaciones escritas (`core/compilador/explicito.py`); el solver admite BDF y eventos de dominio (detiene en el instante exacto en que una variable no negativa se agotaría). Contrato: `restricciones` y valores `datos["matematico.<id>"]` ([docs/CONTRATO_MODELO_COMUN.md](docs/CONTRATO_MODELO_COMUN.md)). Evidencia en [docs/CORTE_VERTICAL.md](docs/CORTE_VERTICAL.md) §5: `tests/validar_compilador_explicito.py` (27, contra analíticas) y `frontend/verificar_compilador_explicito.mjs` (76: las seis hojas de materia sin campo espacial, con RK45 y con el método implícito, iguales al solver TS y a la analítica).
   - **5.1 cerrado el 18 de octubre de 2026:** el Resolver del Engine (`frontend/app/motor/resolverEngine.ts`, `resolverHojaEngine`) calcula en el servidor (`POST /modelo/resolver`) toda hoja que llega al Engine común: 21 hojas de prueba (materia de un dominio, redes de volúmenes y energía con u(T)).
     - El resultado común se traduce al `ResultadoMotor` que ya leen las vistas. Estados, magnitudes derivadas (`observables`) y cierres de presupuesto (`verificaciones`) los publica el servidor.
     - `frontend/verificar_resolver_engine.mjs` (178) comprueba, campo por campo, que es igual al cálculo anterior del navegador. Se probó también en el navegador.
     - El solver del navegador queda solo para los campos 1D y la sustitución por volumen. `resolverHoja`, el solver local, sigue existiendo para esas formas y para las suites que lo prueban.
     - **Requisito:** el backend que usa la interfaz (8004) debe tener cargadas las rutas `/modelo/*` y `core/balances`; si es anterior, el Resolver responde «Servicio del Engine no disponible (HTTP 404)».
   - **5.3, 5.4 y el núcleo de 5.5, hechos el 18 de octubre de 2026:** el motor de balances (`core/balances`, [docs/MOTOR_BALANCES.md](docs/MOTOR_BALANCES.md)) genera en el servidor las ecuaciones de las redes de volúmenes y de la energía con u(T) supuesta, desde los supuestos de cada volumen. `tests/validar_motor_balances.py` (27, contra analíticas) y la batería multifísica: las 10 redes y las 6 hojas de energía iguales al Engine actual.
   - **Resto del paso 5:** 5.2 discretización (motor propio, §9.1.3); el resto de 5.5 (sustitución por volumen, reglas de estado, momento); 5.6 adimensionalización y estudios sobre el modelo común.
6. **Reorganización del frontend** según §7, con el recorrido de la hoja como única navegación (§11).

### Orden vigente (18 de octubre de 2026, decisiones §9.1)

**A. Termodinámica (primero), solo UNIFAC para mezclas no ideales.**

1. Capa termodinámica y compilador común probados con los tres paquetes UNIFAC — **hecho el 18 de octubre de 2026:** `tests/validar_capa_unifac.py` (82), [docs/CAPA_TERMODINAMICA.md](docs/CAPA_TERMODINAMICA.md) §4.
   - Las siete solicitudes dinámicas UNIFAC del motor dan el mismo estado y los mismos eventos que el motor. Las apariciones de fase coinciden con referencias independientes (`thermo`): burbuja γ-φ, binodal ELL y plano tangente.
   - El compilador honra ahora la política de fases (evento `politica_incumplida`).
   - **Hallazgo, corregido el mismo día:** el motor existente publicaba 28 s tarde la segunda fase líquida de la red de cinco especies, porque aceptaba un paso sin evento al no reencontrar el cambio en el estado reintegrado. Corregido en `core/ensamblaje_red.py` y ejemplo regenerado; motor, compilador común y referencia independiente coinciden (`frontend/MAPA_MOTOR.md` §6).
   - **Siguiente dentro de A:** el rendimiento de la capa con UNIFAC (la red de cinco especies tarda ~255 s) y los pendientes del punto 2.
2. Pendientes del checklist de termodinámica que aplican: corrientes materiales entre IAPWS y paquetes de mezcla; diagramas completos L–L y L–L–V (hoy el L–L se detecta pero no se traza); continuación de curvas con pliegues; cortes multicomponente. El contraste experimental de UNIFAC queda **aplazado al final** (§9.1.7).
3. Aplazados por alcance físico (cada uno pide un modelo nuevo, no pulido): vapor no ideal y alta presión, regiones críticas, equilibrio sólido-líquido de mezclas, equilibrio químico acoplado a reacciones.
4. Fuera por decisión: «parámetros completos y contrastes NRTL con 5 o más componentes».

**B. Balances: lo pendiente del checklist.**

| Pendiente | Clase | Va con |
|---|---|---|
| Transferencia selectiva acoplada a termodinámica en /motor | pulido de balances | A + red v2 |
| Cinética reactiva acoplada a la termodinámica real | pulido de balances (constitutivas) | con energía de reacción |
| Energía de reacción con referencias termodinámicas coherentes | pulido de balances | con la anterior |
| Cambio de fase sólido durante la dinámica | balances + termodinámica | hielo Ih ya existe en estático |
| Transferencia de calor y materia fuera del equilibrio | constitutivas | después de las dos primeras |
| Detección de transiciones no capturadas por el muestreo de pasos | solver | eventos de firma del solver común |
| Presiones discontinuas con regla física de salto | balances | — |
| Caudales y trabajo acoplados al balance de momento | balances (momento) | después |
| Resolución inversa general de sistemas ensamblados | estructura + solvers | después |
| Resolución espacial en otras geometrías y dimensiones; transporte energético espacial | **discretización** (§9.1.3) | 5.2, paso posterior |

**C. Hoja única** (§11), empezando por el puente de solo lectura.

**Transversal a A, B y C: que el Engine funcione** (§9.1.7). Cada bloque se prueba con la batería multifísica (§9.1.9), y lo que la batería no resuelve por el camino común se ataca primero, si es general.

**D. Resto del paso 5 y el paso 6.**

Cada paso se cierra con sus pruebas y con la actualización de este documento.

## 11. Hoja única: Ecuaciones y Adimensionalización en un solo recorrido

Hoy son dos páginas con dos almacenes: `/motor/hojas/[id]` (derivación de balances, estado, resolver, gráficos) y `/adimensionalizacion` (cuaderno de documentos de ecuaciones, escalado, grupos, estudios, simulación). El usuario no ve que son **el mismo modelo** en pasos distintos. La propuesta es que haya **un documento, la hoja (modelo común), y un recorrido**; cada paso es la vista de un motor:

| Paso | Motor | Hoy está en | Qué ve el usuario |
|---|---|---|---|
| 1. Formular | balances + supuestos, y la derivación termodinámica | Ecuaciones de `/motor` | La ecuación local, cada supuesto aplicado y la ecuación final, por familia. **No hay hojas de «ecuaciones escritas»** (principio 10): todo modelo se deriva de las ecuaciones fundamentales |
| 2. Estado | termodinámica | Estado de `/motor` | Componentes, paquete (UNIFAC), fases candidatas, muestra de equilibrio, diagramas |
| 3. Datos y estructura | unidades + estructura | parte del Resolver de `/motor` | Datos con unidad, recuento de variables y ecuaciones, grados de libertad |
| 4. Escalar (opcional) | adimensionalización | `/adimensionalizacion` | Escalas, grupos adimensionales, formulaciones certificadas, régimen dominante, estudios. **No integra ni malla** |
| 5. Discretizar (solo con campos espaciales) | discretización | Opciones avanzadas del Resolver; método de líneas de la adimensionalización | Malla, esquema, diagnóstico de Péclet y de celdas |
| 6. Resolver | compilador + solvers | solver TS; simulación de la adimensionalización; ensamblaje v2 | Método, tolerancias, estado y eventos |
| 7. Resultados | resultados + gráficas | Gráficos de `/motor`; vistas de la adimensionalización | Un solo tablero; las mismas series en variables físicas o escaladas con las escalas del paso 4 |

**Reglas.**

- El paso 4 lee y escribe `motores.adimensionalizacion` del mismo modelo común; nunca copia el modelo. Las escalas no cambian las ecuaciones del paso 1: son una vista y una transformación registrada.
- La simulación deja de ser una vista de la adimensionalización: es el paso 6 sobre el mismo modelo (compilador explícito, §10 paso 5.1), con discretización del paso 5 cuando haya campos espaciales.
- Un almacén de hojas (§6, Documento). La adimensionalización trabaja sobre las ecuaciones que deriva la hoja, nunca sobre un modelo escrito a mano (principio 10).
  - **Decidido (19 de octubre de 2026):** la adimensionalización trabaja solo sobre ecuaciones derivadas en una hoja del Engine.
    - Su única entrada es importar una hoja; las ecuaciones de un documento derivado no se editan allí.
    - Los documentos escritos directamente quedan retirados (se conservan para exportarlos). Detalle en [frontend/ADIMENSIONALIZACION_ALCANCE.md](frontend/ADIMENSIONALIZACION_ALCANCE.md).
    - Lo que hoy no llega por esta vía (reacción con su termodinámica, energía en 1D, sistemas no materiales) llegará cuando el Engine sepa derivarlo.
  - La entrada de ecuaciones escritas del compilador (`core/compilador/explicito.py`) se queda: es como el Engine ejecuta lo que genera el motor de balances, no una forma de plantear modelos.
- La biblioteca muestra plantillas, no ejemplos con código propio.

**Hecho (18 de octubre de 2026):**

- Toda hoja, incluidas las de red termodinámica de los ejemplos, muestra los mismos cuatro paneles: Materia, Energía, Momento y Termodinámica (§3; [docs/CAPA_TERMODINAMICA.md](docs/CAPA_TERMODINAMICA.md) §4 bis).
- El panel Termodinámica muestra las relaciones siempre presentes, el cierre de cada volumen (desde `POST /modelo/termodinamica`) y los supuestos termodinámicos posibles.
- El Resolver calcula en el Engine común (§10, 5.1).

**Orden incremental** (cada etapa deja ambas páginas funcionando y sus suites en verde):

1. *Puente de solo lectura:* en la hoja del motor, una pestaña «Escalar» que monta las vistas de la adimensionalización sobre `modeloDesdeHojaMotor(hoja)`; desaparece la importación manual («Del motor»).
2. *Resolver común:* el Resolver de la hoja usa `POST /modelo/resolver` (cierra 5.1) y la vista de simulación de la adimensionalización usa el mismo resultado.
3. *Almacén único:* la adimensionalización usa el almacén de hojas del Engine. Sus documentos escritos a mano se tratan según la decisión pendiente de arriba.
4. *Rutas:* `/hojas/[id]/<paso>` (§7); `/motor` y `/adimensionalizacion` quedan como redirecciones.
