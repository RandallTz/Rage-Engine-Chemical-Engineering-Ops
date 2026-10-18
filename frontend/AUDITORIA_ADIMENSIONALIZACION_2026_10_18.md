# Auditoría de `/adimensionalizacion` y de su núcleo (17–18 de octubre de 2026)

Claude. Encargo del usuario: auditar y mejorar el frontend que dejó Gemini y hacer reales sus ideas («si consideras que puedes lograr hacerlo bien, hazlo»). Sin commit ni push. Este documento resume qué se encontró, qué se cambió y cómo se verificó. El plan de conexión con el motor está en [PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md](PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md).

## 1. Hallazgos

### 1.1 Análisis presentados como cálculos que no lo eran

`ARQUITECTURA_INTEGRACION_MULTIFISICA.md` describía como «certificados» 17 módulos. Al leer el código, la mayoría no calculaba nada a partir del modelo del usuario:

| Módulo | Qué hacía en realidad |
|---|---|
| `clasificadorFormulaciones.ts`, `MapaRegimenes.tsx`, `analisisCapaLimite.ts` | Decidían por subcadenas del id del grupo (`includes("pe")`, `includes("da")`, `includes("k")`). El núcleo llama `G1`, `G2`… a los grupos, así que casi siempre caían en el caso por defecto. |
| `analisisEstabilidad.ts` | Usaba un jacobiano fijo (0.6, −1.0, 1.2, −0.8) para cualquier sistema de dos campos. |
| `analisisEstabilidadNumerica.ts` | Partía de Pe = 10 y Da = 2 inventados y presentaba con ellos una «auditoría de malla». |
| `analisisSimetriasLie.ts` | Afirmaba siempre que el modelo admite autosimilitud. Para reacción-difusión publicaba una EDO reducida que no es válida, porque el término de reacción rompe la invariancia de escala. |
| `analisisCondicionesFrontera.ts` | Añadía condiciones de Robin, Neumann, Dirichlet e inicial que el usuario no había declarado. |
| `SimuladorEnVivo.tsx` | No era el modelo del usuario: integraba una convección-difusión-reacción genérica. Usaba Euler explícito con Δt = 4·10⁻⁴ cuando el límite de estabilidad era ≈ 8·10⁻⁵, y sustituía los NaN por 0, lo que ocultaba la divergencia. |
| `exportarSimulacion.ts`, `ModalPreacondicionamientoMotor.tsx` | Generaban código con una cinética fija (u − u³ − v; Langmuir con Pe = 5 y Da = 2), presentado como generado por el núcleo. |
| `paquetePublicacion.ts` | Contenía un manuscrito fijo con afirmaciones («demostramos…») que no dependen del modelo. |
| `puenteMotor.ts` | No leía las ecuaciones de las hojas de `/motor`: fabricaba una ecuación genérica según un indicador. |
| `exportarPdf.ts` | Publicaba en el PDF todos los análisis anteriores como derivaciones. |

Otros defectos de la interfaz:

- La explicación «¿por qué hasta 68 formulaciones?» era un texto fijo sobre destilación reactiva y atribuía a cada formulación un «régimen físicamente distinguible». En realidad todas son el mismo modelo.
- `interpretarGrupo` reconocía nombres clásicos con expresiones regulares sobre el texto.
- «Restablecer 5 modelos canónicos» **sustituía el cuaderno entero sin confirmación**: se perdían las hojas.
- La disciplina de cada hoja se adivinaba por subcadenas del nombre.
- El tema mezclaba paneles oscuros de Tailwind (`bg-zinc-900`) con la paleta clara de la ruta.
- ESLint daba 10 errores y 20 avisos.

### 1.2 Defectos reales fuera del código de Gemini

| Defecto | Dónde | Consecuencia |
|---|---|---|
| Extracción de escalas de una suma ya adimensional (1 + K c → c_ref (K u + 1/c_ref)) | `core/adimensionalizacion/algebra.py` (mío) | Un objetivo igualaba a 1 un coeficiente con dimensiones. El certificado lo detectaba: 38 formulaciones de 3 ejemplos salían «no demostradas». |
| El cliente admitía tan, tanh, sinh, cosh, atan y erf, pero el núcleo no | Desajuste entre contrato y núcleo | Cualquier ecuación con `tanh` (hay un botón para insertarla) se rechazaba. |
| Al releer el texto se perdían los símbolos que solo usan las condiciones o el dominio | `entradaEcuaciones.ts` | Las hojas de ejemplo con condiciones no se podían calcular («El cambio afecta símbolos…»). |
| 3 de los 21 ejemplos del catálogo no calculaban | `ejemplos.ts` | Brusselator dimensionalmente incorrecto (`−u` sin constante cinética). Polimerización y Hatta perdían unidades porque el lector renombra `cP` a `c_P` y `k2` a `k_2`. |
| El backend del usuario (puertos 8004/8005) corre sin recarga | Entorno | No tiene `estudiar` ni las correcciones: **hay que reiniciarlo** para usar esta entrega. |

## 2. Qué se hizo

### 2.1 Las ideas, ahora calculadas

Nueva operación del núcleo, `estudiar` (contrato §14). Toma una formulación y, opcionalmente, valores físicos con unidades. Cada análisis publica su estado (`calculado`, `requiere_datos`, `no_aplicable`, `no_soportado`) y el método que usó.

| Idea de Gemini | Versión real |
|---|---|
| Regímenes y etiquetas de grupo | `estructura`: cada término se clasifica por sus operadores (acumulación, difusión, convección, reacción, fuente, flujo, valor). Cada grupo se lee como el cociente entre su término y el de referencia o los de coeficiente 1. El nombre clásico (Fourier, Péclet, Damköhler, Biot…) solo aparece cuando el par de términos lo determina. |
| Sensibilidad | `sensibilidad`: d ln G / d ln p como exponente racional exacto. |
| Calculadora de grupos | `valores`: escalas, grupos y coeficientes en SI con unidades convertidas por pint, y dispersión de magnitudes. |
| Capa límite | `asintotica`: envolvente de Kruskal / polígono de Newton con los coeficientes reales. Detecta la perturbación singular, el espesor de capa, su ubicación (solo con balance interior lineal) y la ecuación reducida. |
| Auditoría de malla | `escalas`: linealización exacta (paso complejo), difusividad y velocidad efectivas, longitudes internas, nodos por Péclet de celda, pasos explícitos máximos y cociente de rigidez del operador discreto. |
| Simetrías de Lie | `simetrias`: dilataciones por espacio nulo racional de los pesos, traslaciones y reducción **comprobada** a EDO de semejanza y de onda viajera. |
| Estabilidad y curva S | `estabilidad`: estados homogéneos y σ(k) = autovalores de J + Σ (ik)ⁿ Cₙ (Turing, Hopf). `continuacion`: longitud de arco con pliegues refinados por Newton y Hopf. |
| Simulador y exportación de código | `simulacion`: método de líneas sobre **las ecuaciones del usuario**, con condiciones declaradas, BDF y verificación con la malla refinada. El script de Python exportado reproduce la misma discretización. |

Pruebas contra resultados analíticos (`tests/validar_estudio_adimensionalizacion.py`, 55 comprobaciones):

- calor con sin(πξ) e^(−π²τ), y con flujo nulo cos(πξ/2) e^(−π²τ/4); en ambos el script exportado se ejecuta y coincide;
- la EDO reducida F'' + (η/2) F' = 0 del calor;
- Fisher-KPP sin dilataciones, con su EDO de onda;
- la capa de convección-difusión con δ = 1/Pe en el extremo de salida y 501 nodos por Péclet de celda;
- en el Brusselator, Turing para B > (1 + A/√d)², Hopf en B = 1 + A² con frecuencia A, y k_c ≈ √(A/√d);
- los pliegues de p + u − u³ en ±2/(3√3).

### 2.2 Interfaz

- **Retirado:** 23 módulos, archivados sin cambios en `docs/archivo/adimensionalizacion-gemini-2026-10-17/`, con un LEEME. No estaban en git y no se borró nada.
- **Resultados:** `ResultadosNucleo.tsx` reescrito. Selector de formulaciones con escalas libres y estado; pestañas Resultado, Estudio, Desarrollo y Comparar; exportaciones en un menú (informe HTML/PDF, LaTeX, JSON).
- **Estudio:** `EstudioFormulacion.tsx` con valores físicos y unidades (guardados por documento en el navegador) y cinco vistas: grupos y valores, regímenes y malla, estabilidad (con dispersión y continuación), simetrías y simulación (perfil animado, unidades SI, CSV y script).
- **Comparar:** `ComparadorFormulaciones.tsx` pone dos formulaciones lado a lado con métricas del núcleo evaluadas con los mismos valores.
- **Informe:** `informe.ts` sustituye al PDF anterior y solo contiene lo publicado por el núcleo.
- **Cuaderno:**
  - «Añadir modelos de partida» ya no borra nada;
  - el catálogo se busca por texto;
  - sin disciplinas adivinadas;
  - sin el importador falso.
- **Estilo:**
  - un solo tema claro (las utilidades oscuras del editor se reasignan desde `estudio.css`);
  - `focus-visible`;
  - tablas legibles y gráficos SVG adaptables con paleta sobria;
  - tarjeta de ecuación corregida (botón de copiar y factor global, que la regla CSS anterior deformaba).

## 3. Verificación

| Comprobación | Resultado |
|---|---|
| `python tests/validar_adimensionalizacion.py` | 264 correctas (incluye la regresión de 1 + K c, las funciones ampliadas y 21 ejemplos canónicos) |
| `python tests/validar_estudio_adimensionalizacion.py` | 55 correctas |
| `python tests/validar_capa_dimensional.py`, `validar_api_adimensionalizacion.py` | Correctas |
| `node verificar_adimensionalizacion.mjs` / `verificar_integracion_…` / `verificar_capa_dimensional.mjs` | 103 / 79 / 33 correctas |
| `node verificar_estudio_adimensionalizacion.mjs` (nuevo) | 66 correctas: lector estricto (rechaza respuestas alteradas), KaTeX, informe sin contenido inventado, regresión del lector de ecuaciones y módulos retirados |
| `npx tsc --noEmit`, `npx eslint app/adimensionalizacion` | Sin errores (antes, 10 errores y 20 avisos de ESLint) |
| Los 21 ejemplos del catálogo con el núcleo | Calculan todos, con todas sus formulaciones demostradas (antes, 3 fallaban y 38 formulaciones no se demostraban) |
| Navegador (servidor de desarrollo del usuario en el 3000 + backend propio en el 8011) | Recorrido real con: cálculo, estudio con valores, grupos (Fo = 0,01, Da = 1 y 0,2 comprobados a mano), estabilidad (σ = 1 − 0,01 k²), simulación del calor con unidades SI y editor avanzado |

## 4. Pendiente

- Reiniciar los backends del usuario (8004/8005) para que la interfaz use `estudiar`.
- Simulación en una sola coordenada y derivadas de orden ≤ 2. Las funciones declaradas sin definición no son evaluables numéricamente: se declaran fuera de alcance.
- Selección automática de mapas no lineales (pendiente previo).
- La conexión con el motor: ver el plan.
