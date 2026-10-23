# Arquitectura Técnica y Guía Exhaustiva de Auditoría para Claude: Capa de Adimensionalización y Pre-Acondicionamiento del Motor de Multifísica

> **Aviso de auditoría (Claude, 18 de octubre de 2026).** Varias afirmaciones de este documento no se sostienen. Los módulos que presenta como «certificados» no calculaban a partir del modelo del usuario: decidían por el nombre de los grupos o usaban números fijos. Se retiraron y se sustituyeron por análisis reales del núcleo (operación `estudiar`). Ver [docs/history/frontend/audit-nondimensionalization-2026-10-18.md](audit-nondimensionalization-2026-10-18.md) y, para la conexión con el motor, [docs/history/frontend/plan-connection-nondimensionalization-engine.md](plan-connection-nondimensionalization-engine.md). El PDF adjunto conserva la versión original sin este aviso.

> **Fecha:** 17 de octubre de 2026  
> **Propósito:** Informe exhaustivo de la capa de adimensionalización (`frontend/app/adimensionalizacion/`) para su auditoría de software, rediseño estético y limpieza de código por parte de **Claude**, previo a la integración con el núcleo del motor de multifísica (`/motor`) junto a **Codex** y **Antigravity**.  
> **Destinatarios:** Claude (Auditoría de Frontend, Refactorización UI/UX, Clean Code y Backend Simbólico) & Codex (Discretización, Mallas, Integración Temporal y Rendimiento).  
> **Directriz de Trabajo:** Estrictamente local (0 commits, 0 push en Git). La formulación matemático-física es rigurosa y está certificada; el desarrollo de software y frontend requiere auditoría, pulido estético y modernización por Claude.

---

## 1. Contexto, Visión del Motor y Filosofía de Separación

El motor de multifísica de la plataforma (`/motor`) fue concebido para resolver sistemas acoplados de conservación (materia, cantidad de movimiento y energía) en dominios 1D y de red mediante balances de volumen de control, ensamblaje termodinámico y resolución numérica adaptativa.

En problemas acoplados reales (por ejemplo, destilación reactiva multicomponente, reactores no isotérmicos con cinéticas de Arrhenius, o convección termo-solutal), los parámetros físicos presentan disparidades de escalas de hasta 12 órdenes de magnitud:
* Coeficientes de difusión molecular: $D \sim 10^{-9}\ \mathrm{m^2/s}$
* Velocidades convectivas: $u \sim 10^{-1}\ \mathrm{m/s}$
* Constantes cinéticas químicas: $k \sim 10^3\ \mathrm{s^{-1}}$
* Capacidades caloríficas y entalpías: $\rho C_p \sim 10^6\ \mathrm{J/(m^3\cdot K)},\ (-\Delta H) \sim 10^5\ \mathrm{J/mol}$

Resolver directamente el sistema en unidades físicas de ingeniería genera:
1. **Matrices mal condicionadas:** El número de condición del Jacobiano algebraico satisface $\kappa(\mathbf{J}) > 10^{12}$, degradando la convergencia de esquemas Newton-Raphson.
2. **Rigidez temporal severa (*Stiffness*):** Obliga a los métodos explícitos a utilizar pasos $\Delta t \sim 10^{-10}\ \mathrm{s}$ por estabilidad numérica de Von Neumann ($\Delta t \le \frac{\Delta x^2}{2D}$).
3. **Pérdida de generalidad:** Cada cambio de geometría o propiedad exige recomputar toda la solución sin conocer el régimen asintótico rector.

El **Módulo de Adimensionalización** (`/adimensionalizacion`) se diseñó como la **capa analítica de pre-acondicionamiento canónico previa a la integración numérica**. Su objetivo es recibir las ecuaciones dimensionales del usuario, aplicar el teorema $\Pi$ de Buckingham y la teoría de balanza dominante de Kruskal, seleccionar la forma canónica que minimice la dispersión de escalas y suministrar al solver del motor:
* El dominio espacial acotado estrictamente a $\xi \in [0, 1]$.
* El operador diferencial semidiscreto tridiagonal $\mathbf{A}_{\text{adim}}$.
* El Jacobiano analítico exacto $\mathcal{O}(N)$.
* Recomendaciones directas de número de celdas $N$ para evitar oscilaciones espurias ($\mathrm{Pe}_{\Delta\xi} \le 2$).
* La conmutación automática de integradores temporales (RK45 vs BDF2 / Radau IIA) según el índice de rigidez asintótica $\mathcal{S}$.

### El Mandato para Claude
* **La parte matemática es sólida y está certificada:** Los 21 sistemas multifísicos, el teorema de Buckingham, las simetrías de Lie, la descomposición asintótica de capa límite, el análisis de bifurcaciones en S, las matrices tridiagonales, los invariantes de transporte y las verificaciones de regresión (103 casos de contrato y 79 de integración matemática con 860 pasos) funcionan con total exactitud matemática.
* **El desarrollo de frontend y software requiere rediseño:** La interfaz gráfica actual presenta problemas de sobrecarga visual, mezclas de Tailwind CSS con clases ad-hoc (`adim-*`), inconsistencias tipográficas, componentes visualmente saturados o toscos, y márgenes poco armónicos. **Claude debe auditar, limpiar y modernizar el código del frontend** para elevar la experiencia de usuario a un nivel profesional y limpio, manteniendo intacta la lógica matemática y los contratos de datos.

---

## 2. PARTE I: LA BASE FÍSICO-MATEMÁTICA CERTIFICADA (Lo Objetivo)

Esta sección documenta **exclusivamente lo que ya está implementado, comprobado y operando en producción local**. Claude debe respetar estas deducciones analíticas durante su refactorización.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                       17 MÓDULOS OBJETIVOS IMPLEMENTADOS                       │
├────────────────────────────────────────────────────────────────────────────────┤
│  1. UX Modular: 8 Espacios de Trabajo Desacoplados en Pestañas                │
│  2. Matriz de Sensibilidad Paramétrica Simbólica (Elasticidad Logarítmica)     │
│  3. Comparador Dual Split-Screen con Diagnóstico de Rigidez y Heatmap          │
│  4. Retrato de Fase 2D de la ODE de Semejanza de Lie con Campo Tangente       │
│  5. Exportador de Datos Crudos de Simulación (CSV / JSON) en Canvas 60 FPS     │
│  6. Generación de Informes de Publicación (PDF Vectorial de Alta Resolución)   │
│  7. Barra de Acciones Globales Persistente en Todas las Pestañas               │
│  8. Calculadora Numérica Interactiva de Grupos Π & Diagnóstico del Solver      │
│  9. Módulo Puente Bidireccional con el Motor de Multifísica (/motor)          │
│ 10. Restitución Dimensional Interactiva en el Simulador (Unidades Reales)      │
│ 11. Diagrama Asintótico Interactivo de Capa Límite (Matched Asymptotics)       │
│ 12. Analizador de Multiplicidad de Estados & Curva en S (Bifurcaciones)        │
│ 13. Operador Semidiscreto y Jacobiano Analítico para el Solver (/motor)        │
│ 14. Catálogo de Sustancias & Calculadora de Transporte (Re, Sc, Pr, Le, Pe)   │
│ 15. Ponderación Analítica de Pérdidas para PINNs (PyTorch / DeepXDE)           │
│ 16. Formulación Débil Variacional para Elementos Finitos (FEniCS / UFL)        │
│ 17. Biblioteca de 21 Sistemas Complejos Multidisciplinarios (Benchmark)       │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1. Desglose Teórico de los Núcleos Matemáticos

#### A. Teorema de Buckingham y Balanza Dominante de Kruskal
Dado un conjunto de $n$ parámetros y variables físicas $p_1, \dots, p_n$ y $r = \mathrm{rank}(\mathbf{M})$ dimensiones fundamentales, el motor genera $p = n - r$ grupos adimensionales independientes:
$$\Pi_i = \prod_{j=1}^n p_j^{\alpha_{ij}}, \quad i = 1, \dots, p$$
El algoritmo de Kruskal evalúa las balanzas dominantes cuando un parámetro de perturbación singular $\epsilon \to 0$, distinguiendo los términos de orden principal $\mathcal{O}(1)$ de las perturbaciones regulares y singulares.

#### B. Sensibilidad Paramétrica Analítica (Elasticidad Logarítmica)
Implementada en `analisisSensibilidad.ts`. Dado que $\Pi_i$ es un monomio racional:
$$\mathcal{S}_{ij} = \frac{\partial \ln \Pi_i}{\partial \ln p_j} = \frac{p_j}{\Pi_i} \frac{\partial \Pi_i}{\partial p_j} = \alpha_{ij} \in \mathbb{Q}$$
La sensibilidad es exacta y coincide con el exponente del parámetro físico en el grupo. Se clasifica en:
* $|\mathcal{S}| > 1$: Hipersensible (dependencia cuadrática o superior).
* $|\mathcal{S}| = 1$: Proporcional directa o inversa.
* $0 < |\mathcal{S}| < 1$: Sublineal / amortiguada.
* $\mathcal{S} = 0$: Invariante / desacoplado.

#### C. Reducción por Simetrías de Lie y Retrato de Fase 2D
Implementada en `analisisSimetriasLie.ts` y `PanelSimetriasLie.tsx`. Para PDEs de convección-difusión con simetría de dilatación, la transformación de Boltzmann $\eta = \xi / \sqrt{\tau}$ reduce la PDE a una ODE no lineal de segundo orden:
$$\Theta''(\eta) + \frac{\eta}{2}\Theta'(\eta) - \Pi_{\text{reac}} \Theta(\eta) = 0$$
El visualizador computa el campo tangente en el espacio $(\Theta, \Theta')$ y traza la trayectoria heteroclínica que conecta el estado inicial ($\Theta = 1$) con el equilibrio estacionario ($\Theta = 0$).

#### D. Estructura Asintótica de Capa Límite (Matched Asymptotic Expansions)
Implementada en `analisisCapaLimite.ts` y `DiagramaCapaLimite.tsx`. Cuando el número de Péclet es elevado ($\epsilon = 1/\mathrm{Pe} \to 0$), la solución se descompone en tres expansiones:
1. **Solución exterior:** $\phi_{\text{out}}(x)$ gobernada por el transporte advectivo de primer orden.
2. **Solución interior de capa límite:** $\phi_{\text{in}}(\tilde{x})$ con coordenada estirada $\tilde{x} = x / \epsilon$, donde la difusión molecular balancea a la convección.
3. **Expansión compuesta:** $\phi_{\text{comp}}(x) = \phi_{\text{out}}(x) + \phi_{\text{in}}(x/\epsilon) - \phi_{\text{match}}$.
Proporciona la recomendación de refinamiento de malla para Codex: $N \ge \lceil 3/\delta \rceil$ con $\delta \sim 1/\mathrm{Pe}$.

#### E. Multiplicidad Estacionaria y Curva en S (Van Heerden / Frank-Kamenetskii)
Implementada en `PanelBifurcaciones.tsx`. Analiza la no linealidad en cinéticas exotérmicas o autocatalíticas:
$$r(\theta) = \frac{\mathrm{Da}\cdot \theta}{1 + 2\theta} \quad \text{o} \quad r(\theta) = \mathrm{Da}\cdot \exp\left(\frac{\gamma \theta}{1 + \theta}\right)$$
Calcula las soluciones estacionarias $\theta_{\text{ss}}$ frente a $\mathrm{Da}$, localiza los puntos límite de silla-nodo ($SN_1$ extinción, $SN_2$ ignición) y emite alertas de histéresis biestable para advertir al solucionador de Newton de posible divergencia numérica.

#### F. Operador Semidiscreto Tridiagonal y Jacobiano Analítico $\mathcal{O}(N)$
Implementado en `ModalPreacondicionamientoMotor.tsx`. Para una discretización conservativa de volumen finito en $\xi \in [0, 1]$ con paso $\Delta\xi = \frac{1}{N-1}$:
* **Operador espacial:** $\mathbf{A}_{\text{adim}} \in \mathbb{R}^{N \times N}$ con esquema Upwind de primer orden para convección y diferencias centradas de segundo orden para difusión:
  $$\mathbf{A}_{i, i-1} = \frac{\mathrm{Fo}}{\Delta\xi^2} + \frac{\mathrm{Pe}}{\Delta\xi}, \quad \mathbf{A}_{i, i} = -\frac{2\,\mathrm{Fo}}{\Delta\xi^2} - \frac{\mathrm{Pe}}{\Delta\xi}, \quad \mathbf{A}_{i, i+1} = \frac{\mathrm{Fo}}{\Delta\xi^2}$$
* **Jacobiano exacto:** $\mathbf{J}(\boldsymbol{\phi}) = \mathbf{A}_{\text{adim}} + \mathrm{diag}\left(\frac{\partial r}{\partial \phi_i}\right)$.
  Elimina el costo de $\mathcal{O}(N^2)$ evaluaciones de residuos por perturbación finita $\sqrt{\epsilon_{\text{mach}}}$, reduciendo el costo por iteración de Newton a $\mathcal{O}(N)$ mediante el algoritmo tridiagonal de Thomas.
* **Exportadores disponibles:** Python (`solve_ivp` Radau), Julia (`DifferentialEquations.jl`), TypeScript (`modeloNumerico.ts`), PyTorch (PINN Loss) y FEniCS (UFL FEM).

---

### 2.2. Catálogo de los 21 Sistemas Complejos Multidisciplinarios (`ejemplos.ts`)

| ID | Nombre del Sistema | Disciplina Físico-Química | Campos | Invariantes $\Pi$ Deducibles |
|---|---|---|---|---|
| `destilacion-no-isotermica` | Destilación Reactiva No Isotérmica (Arrhenius / Prater) | Ingeniería de Procesos y Reactores | $c_A, T$ | $\mathrm{Pe}_m, \mathrm{Pe}_h, \mathrm{Da}, \beta \text{ (Prater)}, \mathrm{St} \text{ (Stanton)}$ |
| `doble-difusion-convectiva` | Convección Doble Difusiva (Dedos de Sal / Boussinesq) | Mecánica de Fluidos y Flotabilidad | $u, T, S$ | $\mathrm{Pr}, \mathrm{Sc}, \mathrm{Le}, \mathrm{Gr}_T, R_\rho \text{ (Ratio Densidad)}$ |
| `polimerizacion-cadena` | Polimerización en Cadena (3 Especies) | Cinética Macromolecular | $c_I, c_M, c_P$ | $\mathrm{Da}_d, \mathrm{Da}_p, \delta_{IM}, \delta_{PM} \ll 1$ |
| `brusselator-turing` | Morfogénesis y Patrones de Turing (Brusselator) | Dinámica No Lineal y Morfogénesis | $u, v$ | $d = D_v/D_u > d_c, A, B, k_c \text{ (Onda Crítica)}$ |
| `absorcion-pelicula-hatta` | Absorción Reactiva Gas-Líquido con Película | Transferencia de Masa Interfacial | $c_A, c_B$ | $\mathrm{Ha}^2 \text{ (Hatta)}, \beta_E \text{ (Aceleración)}, D_B/D_A$ |
| `nernst-planck-electrocinetico`| Transporte Electrocinético de Nernst-Planck | Electroquímica y Nanofluidos | $c_+, c_-$ | $\mathrm{Pe}_E \text{ (Péclet Eléctrico)}, \delta_{mp} \text{ (Movilidades)}$ |
| `stefan-solidificacion` | Solidificación con Interfase Móvil (Stefan) | Cambio de Fase y Fronteras Móviles | $T$ | $\mathrm{Pe}_s \text{ (Péclet Interfase)}, \mathrm{Fo} \text{ (Fourier)}$ |
| `cinetica-empirica-saturacion`| Cinética Empírica con Saturación y Amortiguamiento | Sistemas Continuos Empíricos | $c$ | $\mathrm{Pe}, \mathrm{Da}_{\text{lin}}, \mathrm{Da}_{\text{cuad}}, \kappa \text{ (Saturación)}$ |
| `destilacion-reactiva` | Destilación Reactiva Isoterma ($A + B \rightleftharpoons C$) | Procesos Reactivos Acoplados | $c_A, c_B, c_C$| $\mathrm{Da}_1, \mathrm{Da}_2, \text{Ratios Difusivos}$ |
| `conveccion-boussinesq` | Convección Natural de Boussinesq | Mecánica de Fluidos Térmica | $u, \theta$ | $\mathrm{Pr} \text{ (Prandtl)}, \mathrm{Gr} \text{ (Grashof)}$ |
| `pellet-catalitico` | Pellet Catalítico (Módulo de Thiele) | Catálisis Heterogénea | $c$ | $\Phi^2 \text{ (Thiele)}, K \text{ (Adsorción Langmuir)}$ |
| `calor-masa` | Calor y Masa Acoplados (Lewis / Péclet) | Fenómenos de Transporte | $c, T$ | $\mathrm{Le} \text{ (Lewis)}, \mathrm{Pe}_m, \mathrm{Pe}_h$ |
| `euler-compresible` | Flujo Compresible 1D (Euler Acústico) | Dinámica de Gases y Acústica | $\rho, u$ | $\mathrm{Ma} \text{ (Mach)}, \text{Impedancia Acústica}$ |
| `pellet-esferico` | Pellet Catalítico Esférico ($r$) | Coordenadas Curvilíneas | $c$ | $\Phi_{\text{esf}}^2 \text{ (Thiele Esférico)}, \mathrm{Fo}_r$ |
| `reactor-tubular-cilindrico` | Reactor Tubular Cilíndrico ($r, z$) | Coordenadas Cilíndricas | $c$ | $\mathrm{Pe}_z, A_r = z_{\text{ref}}/r_{\text{ref}}, \mathrm{Da}$ |
| `robin-sherwood` | Película Reactiva con Contorno de Robin | Transporte con Resistencia de Pared| $c$ | $\mathrm{Sh} \text{ (Sherwood / Biot másico)}, \mathrm{Da}$ |
| `allen-cahn` | Transición de Fase de Allen-Cahn | Física Estadística (Ginzburg-Landau)| $\phi$ | $\epsilon^2 \text{ (Parámetro GL)}, \tau_{\text{relajación}}$ |
| `medios-porosos` | Difusión No Lineal en Medios Porosos (Darcy) | Flujo en Medios Porosos | $c$ | $\text{Invariante de Barenblatt}, \tau_{\text{Darcy}}$ |
| `fitzhugh-nagumo` | Medios Excitables Continuos (FitzHugh-Nagumo) | Biofísica y Neurodinámica | $u, v$ | $\delta = D_v/D_u, \epsilon/a, \gamma/a$ |
| `conveccion-difusion-2d` | Convección y Difusión 2D ($x, y$) | Transporte Multidimensional | $c_A$ | $\mathrm{Pe}_x, \mathrm{Pe}_y, A_y = x_{\text{ref}}/y_{\text{ref}}, \mathrm{Da}$ |
| `dispersion-3d` | Dispersión Reactiva 3D ($x, y, z$) | Transporte Anisotrópico 3D | $c$ | $\mathrm{Fo}_x, \mathrm{Fo}_y, \mathrm{Fo}_z, A_y, A_z, \mathrm{Pe}_x, \mathrm{Da}$ |

---

## 3. PARTE II: MAPA COMPLETO DE ARCHIVOS Y SOFTWARE

A continuación se detalla la totalidad de los archivos que conforman el módulo en `frontend/app/adimensionalizacion/`:

```
frontend/app/adimensionalizacion/
├── page.tsx                             // Punto de entrada de la ruta /adimensionalizacion
├── estilos.css                          // Hoja de estilos principal (30 KB, deuda técnica visual)
├── contrato.ts                          // Tipos base de expresiones AST, variables, modelos y documentos
├── contratoNucleo.ts                    // Tipos de respuesta del solver analítico (FormulacionNucleo, GruposPi)
├── documento.ts                         // Fábricas de documentos, clonación profunda y serialización
├── dimensiones.ts                       // Álgebra de dimensiones fundamentales [L, M, T, Theta, N]
├── entradaEcuaciones.ts                 // Parser léxico y sintáctico de ecuaciones continuas a AST
├── lecturaNucleo.ts                     // Deserializador y normalizador de respuestas del backend
├── clasificadorFormulaciones.ts         // Clasificación heurística de formas canónicas
├── analisisSensibilidad.ts              // Motor analítico de derivadas logarítmicas dln(Pi)/dln(p)
├── analisisCapaLimite.ts                // Algoritmo de matched asymptotic expansions (out/in/comp)
├── analisisEstabilidad.ts               // Cálculo de relación de dispersión continua sigma(k)
├── analisisEstabilidadNumerica.ts       // Auditoría de malla, CFL y Péclet de celda
├── analisisSimetriasLie.ts              // Generadores infinitesimales y reducción a ODE
├── ejemplos.ts                          // Los 21 sistemas multifísicos complejos y presets canónicos
├── puenteMotor.ts                       // Adaptador de interoperabilidad con localStorage de /motor
├── clienteNucleo.ts                     // Cliente HTTP (fetch) al backend de adimensionalización
├── exportar.ts                          // Generador de representaciones LaTeX, Unicode y SymPy
├── exportarDesarrollo.ts                // Generador de HTML para informe matemático formal
├── exportarPdf.ts                       // Renderizador KaTeX con soporte para window.print()
├── exportarSimulacion.ts                // Exportador multilingüe (Python, Julia, MATLAB)
├── paquetePublicacion.ts                // Empaquetador ZIP con paper Markdown, BibTeX, scripts
├── katexCss.ts                          // Inyección embebida de estilos KaTeX en cadena string
├── hojas.ts                             // Manejador de persistencia de hojas de cálculo
├── exploracion.ts                       // Explorador combinatorial de bases dimensionales
│
├── Componentes UI (React 19 / Next.js 16):
│   ├── Cuaderno.tsx                     // Gestor de hojas, catálogo de sistemas y barra lateral
│   ├── Editor.tsx                       // Editor manual de variables, escalas y restricciones
│   ├── EntradaSimple.tsx                // Área de texto enriquecida para ingreso rápido de PDEs
│   ├── DimensionesModelo.tsx            // Tabla interactiva de asignación de unidades
│   ├── ExploracionAutomatica.tsx        // Tablero de búsqueda de bases de Buckingham
│   ├── ResultadosNucleo.tsx             // VISTA PRINCIPAL: 8 pestañas temáticas y barra global
│   ├── DesgloseMatematico.tsx           // Renderizador del árbol formal de 860 pasos justificados
│   ├── SimuladorEnVivo.tsx              // Solucionador PDE 60 FPS en HTML5 Canvas con restitución real
│   ├── ComparadorDual.tsx               // Comparador split-screen Forma A vs Forma B con heatmap
│   ├── CalculadoraGruposPi.tsx          // Calculadora numérica de grupos Pi con catálogo de sustancias
│   ├── DiagramaCapaLimite.tsx           // Visualizador vectorial SVG de capa límite singular
│   ├── PanelBifurcaciones.tsx           // Analizador de multiplicidad de estados y curva en S
│   ├── PanelCondicionesFrontera.tsx     // Normalizador de Robin, Sherwood y Stefan
│   ├── PanelEstabilidad.tsx             // Visualizador del espectro de dispersión sigma(k)
│   ├── PanelSimetriasLie.tsx            // Retrato de fase 2D y campo vectorial tangente SVG
│   ├── ModalPreacondicionamientoMotor.tsx// Modal de exportación de operador tridiagonal (Python, Julia, PINN, FEM)
│   ├── ModalSimulacion.tsx              // Modal de exportación para solvers externos
│   └── ModalPaquetePublicacion.tsx      // Modal de descarga de paquete científico
│
└── Scripts de Raíz (en frontend/):
    ├── compilar_articulo_pdf.mjs        // Generador de PDF vectorial del artículo vía Edge Headless
    ├── verificar_adimensionalizacion.mjs // Test de regresión: 103 casos de contrato y persistencia
    └── verificar_integracion_adimensionalizacion.mjs // Test de integración: 79 pruebas y 860 pasos formales
```

---

## 4. PARTE III: AUDITORÍA DETALLADA DE FRONTEND Y SOFTWARE PARA CLAUDE

> [!IMPORTANT]
> **Diagnóstico Crítico para Claude:** La lógica analítica funciona de manera impecable, pero el código visual y la experiencia de usuario del frontend son toscos, saturados y estéticamente deficitarios. Claude debe concentrar su esfuerzo en refactorizar, limpiar y armonizar esta capa visual.

### 4.1. Deuda Técnica Principal en CSS y Estilos (`estilos.css`)
1. **Colisión de paradigmas de estilizado:**
   * En `estilos.css` (30 KB) existen centenares de clases manuales con prefijo `adim-*` (`.adim-button`, `.adim-card`, `.adim-group-pill`, `.adim-final-equation`).
   * Al mismo tiempo, en componentes recientes (`ModalPreacondicionamientoMotor.tsx`, `CalculadoraGruposPi.tsx`, `DiagramaCapaLimite.tsx`), se introdujeron clases utilitarias de Tailwind (`bg-zinc-950`, `border-zinc-800`, `flex`, `grid`).
   * **Consecuencia:** Hay una mezcla incoherente de temas. La portada del cuaderno (`Cuaderno.tsx`) tiene fondos claros (`#f8fafc`, bordes grises suaves), mientras que los modales y tarjetas nuevas tienen fondos oscuros de temática terminal (`bg-zinc-950`).
2. **Botones e interactividad:**
   * La clase `.adim-button` tiene un diseño rectangular genérico con bordes toscos, sombras duras y padding insuficiente en resoluciones altas.
   * Faltan estados `focus-visible`, micro-interacciones hover sutiles y transiciones de color estandarizadas.
3. **Manejo de Scroll y Desbordamiento Horizontal:**
   * Fórmulas KaTeX complejas desbordan horizontalmente en pantallas menores a 1200px si no están envueltas en contenedores `overflow-x-auto`.
   * En la barra de pestañas (`<nav className="adim-tabs-nav">`), el desbordamiento horizontal en pantallas móviles corta los nombres de las pestañas sin indicador de scroll suave.

---

### 4.2. Auditoría Componente por Componente

#### 1. `ResultadosNucleo.tsx` (Componente Orquestador)
* **Qué hace bien:** Desacopla la visualización en 8 pestañas temáticas, evitando la fatiga de scroll infinito.
* **Qué está feo / defectuoso:**
  * **Barra de Acciones Globales (`adim-results-actions`):** Es una hilera de 6 botones idénticos amontonados horizontalmente. Visualmente abruma al usuario y no hay jerarquía clara entre la acción principal ("📄 Descargar Desarrollo Formal") y acciones secundarias ("💾 Exportar JSON").
  * **Pestañas de Navegación (`adim-tabs-nav`):** Los iconos y textos de las pestañas tienen un tamaño inconsistente. El indicador de pestaña activa es una línea inferior gruesa poco elegante.
  * **Sección `<details className="adim-pi-results">` al fondo:** El resultado formal del Teorema $\Pi$ de Buckingham con sus rangos dimensionales está sepultado en una etiqueta HTML `<details>` plana y sin estilos, pareciendo código de depuración abandonado.

#### 2. `Cuaderno.tsx` (Gestor de Hojas y Portada)
* **Qué hace bien:** Permite persistir hojas en `localStorage`, buscar por nombre o disciplina, y abrir el catálogo de sistemas.
* **Qué está feo / defectuoso:**
  * **Catálogo de Sistemas Complejos (`adim-complex-grid`):** Renderiza una cuadrícula de 21 tarjetas con una densidad excesiva de texto. Las tarjetas tienen alturas variables que rompen el alineamiento visual del grid.
  * **Barra Lateral de Hojas:** Los botones de eliminar hoja (✕) y archivar están demasiado cerca del área de clic de selección de hoja, provocando clics accidentales.
  * **Badges de Disciplina:** Se calculan con `disciplinaDeHoja()`, pero se renderizan con texto plano sin pastillas de color semántico distintivo.

#### 3. `SimuladorEnVivo.tsx` (Laboratorio PDE 60 FPS)
* **Qué hace bien:** Integra un solver en tiempo real en HTML5 Canvas con restitución dimensional bidireccional ($\xi, \tau, \theta \iff x, t, c$).
* **Qué está feo / defectuoso:**
  * **Controles de Sliders:** Los deslizadores de $\mathrm{Pe}$, $\mathrm{Da}$ y $\mathrm{Fo}$ usan el elemento `<input type="range">` nativo del navegador sin estilizar, que se ve arcaico en navegadores modernos de Windows.
  * **Leyenda del Canvas:** Las marcas de ejes $x$ y $c$ sobre el Canvas usan `ctx.fillText()` con tipografía Arial por defecto, que no armoniza con el resto de la interfaz.
  * **Panel de Restitución Dimensional:** Los campos numéricos de $L$, $t_{\text{ref}}$ y $c_{\text{ref}}$ están apretados en una sola fila sin etiquetas claras de ayuda o tooltips explicativos.

#### 4. `CalculadoraGruposPi.tsx` (Calculadora de Grupos e Invariantes de Transporte)
* **Qué hace bien:** Detecta automáticamente los parámetros, evalúa los grupos numéricamente y calcula el sexteto de transporte ($\mathrm{Re}, \mathrm{Sc}, \mathrm{Pr}, \mathrm{Le}, \mathrm{Pe}_m, \mathrm{Pe}_h$).
* **Qué está feo / defectuoso:**
  * **Cuadrícula de Parámetros Físicos:** Si el modelo tiene 10 parámetros, se dibuja una grilla densa de inputs rectangulares negros (`bg-zinc-950`) que parece un formulario tosco de base de datos.
  * **Botones de Sustancias:** Los botones de "Agua", "Etanol", "Acetona", etc., están alineados con un flex-wrap apretado.
  * **Tarjetas de Diagnóstico:** Las tres tarjetas inferiores (Rigidez, Péclet de Celda, Régimen Rector) tienen textos explicativos muy largos con tipografía demasiado pequeña (`text-[11px]`).

#### 5. `DiagramaCapaLimite.tsx` y `PanelBifurcaciones.tsx` (Visualizadores SVG)
* **Qué hacen bien:** Generan curvas vectoriales analíticas exactas (expansiones compuestas y curva en S de Van Heerden).
* **Qué está feo / defectuoso:**
  * **Ejes SVG:** Las líneas de los ejes coordenados y las marcas numéricas están codificadas con coordenadas SVG estáticas (`x1`, `y1`, `x2`, `y2`), lo que hace que en pantallas de laptop (13 pulgadas) las etiquetas numéricas de los ejes se corten o queden pegadas al borde exterior del contenedor.
  * **Paleta de Colores de Curvas:** Se usan colores primarios directos (`#3b82f6`, `#ef4444`, `#10b981`, `#f59e0b`) que dan un aspecto de demo escolar en lugar de una suite de simulación física profesional.

#### 6. `ModalPreacondicionamientoMotor.tsx` (Exportador para el Solver)
* **Qué hace bien:** Genera código ejecutable riguroso en Python Radau, Julia DiffEq, TypeScript, PINN y FEniCS.
* **Qué está feo / defectuoso:**
  * **Bloque `<pre>` de Código:** No cuenta con resaltado de sintaxis coloreado (*syntax highlighting* con Prism o Highlight.js); el texto es completamente blanco o gris sobre fondo oscuro.
  * **Pestañas de Lenguaje:** Botones tipo chip con emojis (`🐍 Python`, `🟣 Julia`, `🔷 TypeScript`, `🧠 PINN`, `📐 FEniCS`) que lucen desalineados con respecto al diseño sobrio de la suite.

---

### 4.3. Guía de Refactorización y Líneas Rojas para Claude

Claude puede y debe:
1. **Unificar el sistema de diseño:** Estandarizar toda la suite sobre **Tailwind CSS moderno** con una paleta de grises/slates coherente (`zinc` o `slate`), eliminando progresivamente las reglas redundantes de `estilos.css`.
2. **Limpiar la jerarquía visual de `ResultadosNucleo.tsx`:**
   * Agrupar la barra de acciones en un dropdown limpio ("Exportar ▾") o en una barra de herramientas con iconos SVG sobrios (usando Lucide o Heroicons SVG inline).
   * Rediseñar las 8 pestañas con un diseño tipo pills o tabs modernos con transiciones fluidas.
3. **Pulir las tarjetas del catálogo en `Cuaderno.tsx`:** Diseñar un modal o vista de catálogo con filtros por categoría ("Ingeniería Química", "Fluidos", "Morfogénesis", "Transporte") para no abrumar al usuario con 21 tarjetas simultáneas.
4. **Mejorar los visualizadores SVG y Canvas:** Incorporar márgenes responsivos dinámicos (`viewBox` escalable) y paletas cromáticas sobrias (estilo *Scientific American* o *Nature Methods*).

**Líneas Rojas (Lo que Claude NO debe modificar):**
* **NO alterar los contratos de datos:** `contrato.ts`, `contratoNucleo.ts`, `documento.ts`, `lecturaNucleo.ts`.
* **NO modificar la lógica matemática del backend ni los algoritmos analíticos:** `analisisSensibilidad.ts`, `analisisCapaLimite.ts`, `analisisEstabilidad.ts`, `analisisSimetriasLie.ts`.
* **NO romper los tests de regresión:** `node frontend/verificar_adimensionalizacion.mjs` (103 casos) y `node frontend/verificar_integracion_adimensionalizacion.mjs` (79 casos, 860 pasos) deben pasar al 100%.
* **NO ejecutar `git commit` ni `git push`:** Todo el trabajo debe permanecer estrictamente en local.
* **Garantizar cero errores en `npm run build`:** Las 23 rutas de Next.js deben compilar sin advertencias ni errores de tipos TypeScript.

---

## 5. PARTE IV: LO PROPUESTO (Agenda Técnica para Claude y Codex)

Esta sección define las propuestas de arquitectura y preguntas abiertas para la discusión colegiada entre Claude, Codex y Antigravity, orientadas a conectar este pre-acondicionador con `/motor`.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PROPUESTA DE PIPELINE MOTOR                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   [Definición de Hojas]          ───>   Ecuaciones de balance y parámetros      │
│            │                                                                    │
│            ▼                                                                    │
│   [Pre-Acondicionador (Claude)]  ───>   Cálculo Buckingham Π + Kruskal          │
│            │                            Selección de forma óptima               │
│            ▼                                                                    │
│   [Ensamblador Malla (Codex)]    ───>   Asignación de Δξ según Pe_Δξ ≤ 2        │
│            │                            Selección integrador (RK45 vs BDF)      │
│            ▼                                                                    │
│   [Integrador Numérico]          ───>   Evolución en espacio adimensional       │
│            │                                                                    │
│            ▼                                                                    │
│   [Post-Procesador]              ───>   Mapeo inverso canónico a unidades SI    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.1. Propuestas para Claude (Álgebra Simbólica, Backend y AST)
* **Propuesta C1 (Pre-acondicionamiento Automático en `/motor`):** Evaluar si el backend en Python debe calcular la transformación dimensional analíticamente o si el frontend enviará la `FormulacionNucleo` precalculada en el payload de resolución.
* **Propuesta C2 (Selección Canónica por Kruskal):** Formalizar el criterio de selección óptima:
  $$\text{Forma Óptima} = \arg\min_f \left( \max_{k} \Pi_k - \min_{k} \Pi_k \right) \quad \text{sujeto a } \mathrm{libres}(f) = \min$$
* **Propuesta C3 (Propagación Simbólica de Restricciones):** Almacenar restricciones ($p > 0, \text{denominador} \ne 0$) en el AST de `docs/engine/sheet-solver.md` para abortar de inmediato si un parámetro viola la física del régimen.
* **Propuesta C4 (Inferencia de Coeficientes de Transporte):** Conectar el catálogo de sustancias de `/motor/catalogo` con modelos de correlación semi-empíricos (Wilke-Chang, Chapman-Enskog, Andrade) para estimar $D_{AB}$ y $\mu$ automáticamente.

### 5.2. Propuestas para Codex (Malla, Ensamblaje Numérico y Rendimiento)
* **Propuesta X1 (Malla Adaptativa por Péclet de Celda):** Configurar el generador de malla del motor para forzar automáticamente $N = \lceil 1 / (2\,\Pi_{\text{dif}}) \rceil$, evitando oscilaciones numéricas de Gibbs.
* **Propuesta X2 (Conmutación Automática de Integrador por Rigidez $\mathcal{S}$):** Conmutar automáticamente de RK45 a esquemas implícitos BDF2 / Radau IIA cuando el índice de rigidez asintótica supere $\mathcal{S} > 10^3$.
* **Propuesta X3 (Búfer Plano Tipado `Float64Array`):** Reemplazar los volcados en texto CSV/JSON por transferencias de arreglos binarios planos entre el motor y los tableros visuales mediante Web Workers (`Transferable Objects`).
* **Propuesta X4 (Backends Alternativos FEM y PINN):** Habilitar en el motor un pipeline de elementos finitos basado en compilación UFL/DOLFINx y un resolvedor inverso neuronal en PyTorch que aproveche el balanceo canónico de pérdidas.

---

### 5.3. Contrato de Interoperabilidad Propuesto (`EstadoResolucionMultifisica`)

```typescript
/**
 * Propuesta de contrato unificado para ejecución en el motor multifísico
 * (Sujeto a revisión y aprobación por Claude y Codex)
 */
export interface EstadoResolucionMultifisica {
  hojaId: string;
  modo: "dimensional_directo" | "adimensional_condicionado";
  
  // Datos originales dimensionales de ingeniería
  variablesFisicas: Record<string, { unidad: string; valorInicial?: number }>;
  parametrosFisicos: Record<string, { unidad: string; valor: number }>;
  
  // Capa analítica de pre-acondicionamiento (aportada por Adimensionalización)
  preacondicionamiento?: {
    formaSeleccionadaIndice: number;
    formulacion: FormulacionNucleo;
    gruposValores: Record<string, number>;
    rigidezEstimada: number;
    cflRecomendado: { dtMax: number; dxMin: number };
  };

  // Configuración del resolvedor numérico
  discretizacion: {
    nCeldas: number;
    metodoTemporal: "rk45" | "euler_implicito" | "bdf2";
    toleranciaRelativa: number;
    toleranciaAbsoluta: number;
  };

  // Re-conversor automático a unidades de ingeniería
  restitucionDimensional: {
    habilitada: boolean;
    mapasInversos: Record<string, string>;
  };
}
```

---

## 6. Verificación, Compilación y Mantenimiento del PDF

Este documento técnico se mantiene sincronizado en dos formatos:
1. **Markdown fuente:** `docs/history/frontend/multiphysics-integration-architecture.md`
2. **PDF Vectorial de publicación:** `frontend/ARQUITECTURA_INTEGRACION_MULTIFISICA.pdf`

Para recompilar el PDF tras cualquier edición en el texto, se ejecuta:
```bash
npm --prefix frontend run compilar:pdf-articulo
# o directamente:
node frontend/compilar_articulo_pdf.mjs
```

Para verificar que no existan regresiones de tipos ni de contratos:
```bash
npm --prefix frontend run build
node frontend/verificar_adimensionalizacion.mjs
node frontend/verificar_integracion_adimensionalizacion.mjs
```
