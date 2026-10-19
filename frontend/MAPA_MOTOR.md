# Mapa del motor (`/motor`)

18 de octubre de 2026. Qué hace el motor, qué tiene hoy, hasta dónde llega y por dónde se le puede acoplar la adimensionalización. Es un mapa de lo que existe: el estado y la prioridad de las fases siguen en [ROADMAP_MOTOR_MULTIFISICO.md](ROADMAP_MOTOR_MULTIFISICO.md), y la lista fina de casillas en [CHECKLIST_MOTOR.md](CHECKLIST_MOTOR.md). Para escribirlo no se modificó el motor. La estructura objetivo del proyecto, de la que este mapa es el inventario, está en [../ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md).

## 1. En una frase

El motor parte de las leyes de conservación (materia, energía, momento) y deja que el usuario las reduzca paso a paso, con hipótesis explícitas, hasta un sistema que se resuelve en el tiempo. Ese sistema puede ser un volumen, una red de volúmenes, un campo 1D o volúmenes con termodinámica real. No tiene escenarios precocinados: cada caso es una hoja con su derivación y sus datos.

```mermaid
flowchart LR
  B[Biblioteca de hojas<br/>/motor/hojas] --> E[Ecuaciones<br/>derivación paso a paso]
  E --> S[Estado<br/>componentes, paquete termodinámico]
  E --> R[Resolver<br/>datos, unidades, GL, horizonte]
  S --> R
  R -->|materia 1 volumen o red,<br/>energía u(T) manual| TS[Solver TS en el navegador<br/>RK45 · Euler implícito · VF 1D]
  R -->|mezclas, fases,<br/>varios volúmenes| PY[Backend Python<br/>/motor/ensamblajes · RK45 con eventos de fase]
  S -->|estado puntual, diagramas| TD[Backend Python<br/>/motor/termodinamica]
  TS --> G[Resultados<br/>gráficos, tabla, detalles]
  PY --> G
```

## 2. Recorrido del usuario

| Pantalla | Ruta | Qué hace |
|---|---|---|
| Biblioteca | `/motor/hojas` | Crear, abrir, duplicar, archivar hojas; añadir conjuntos de prueba (demostración, materia, energía, acoplamiento, multicomponente, multifásico, N componentes, UNIFAC) |
| Ecuaciones | `/motor/hojas/[id]` | Derivación desde la ecuación local: forma diferencial → integral → total; supuestos (fijo, invariancias, sin convección/difusión, fuentes uniformes, puertos, densidad media…); cuatro paneles con su propia vista: tres balances (materia, energía, momento) y la **termodinámica**, siempre presente (relaciones, cierre de cada volumen y supuestos termodinámicos). Las hojas de red termodinámica muestran los mismos paneles |
| Estado | `/motor/hojas/[id]/estado` | Catálogo de componentes (por nombre o CAS), paquete termodinámico por volumen, datos puros y sustituciones, equilibrio de una muestra, diagramas |
| Resolver | `/motor/hojas/[id]/resolver` | Ecuaciones finales, datos por grupo con unidad, iniciales, horizonte, fronteras 1D; recuento (variables/ecuaciones, GL estructural, datos e iniciales definidos); Opciones avanzadas (método, celdas, muestras, tolerancias) |
| Gráficos | `/motor/hojas/[id]/resultados` | Tablero de gráficas configurable, tabla, CSV y detalles técnicos (residuos, certificados, eventos) |
| Fundamentos | `/motor`, `/motor/materia`, `/motor/energia`, `/motor/momento` | Hoja sin guardar y vistas de la derivación fundamental |

## 3. Tres caminos de cálculo

| | A. Solver propio en el navegador | B. Ensamblaje termodinámico (backend) | C. Estado y diagramas (backend) |
|---|---|---|---|
| Código | `app/motor/modeloNumerico.ts`, `integracionMotor.ts`, `ensamblajeMateria.ts`, `modeloEnergia.ts` | `backend/motor_ensamblaje.py` (v1), `motor_ensamblaje_v2.py` (red multifásica, revisión 2), `core/ensamblaje_dinamico.py`, `core/ensamblaje_red.py` | `backend/motor_termodinamica.py`, `motor_diagramas.py`, `motor_mezclas.py`, `motor_hielo.py`, `motor_catalogo.py` |
| Rutas | ninguna (local) | `GET /motor/ensamblajes/capacidades`, `POST …/validar`, `POST …/resolver` | `GET /motor/termodinamica/capacidades`, `POST …/evaluar`, `…/diagramas/{capacidades,trazar}`, `GET …/diagrama`, `GET /motor/catalogo` |
| Ecuaciones | Materia: total dmᵢ/dt (puertos, resto, G, C), volumétrica dV/dt, local temporal dρᵢ/dt, campo 1D cartesiano (convección, difusión laplaciana/Fick/flujo, fuentes). Red de volúmenes de masa con corrientes compartidas. Energía: 1 volumen, 1 especie, U = m·u(T) manual | Materia y energía por volumen y fase con estados del paquete; corrientes convectivas (por componente o total del donante, internas, con inversión); fronteras rígida o presión prescrita; contacto térmico (impuesto o conductancia); extracción homogénea o por fase; segunda ley | Estado de equilibrio TP, PH, UP, UV (y TV en dinámica); flashes; potenciales; diagramas T–xy, P–xy y P–T del agua con hielo |
| Método | RK45 Dormand–Prince o Euler implícito adaptativo; 1D por volúmenes finitos conservativos, **convección upwind de 1er orden**, difusión centrada, ≤ 160 celdas, ≤ 201 muestras, ≤ 150 000 pasos | RK45 con eventos de fase, ≤ 1001 muestras | Solvers de equilibrio con certificados de estabilidad |
| Tamaño | 1–8 especies por dominio; red de volúmenes de masa | ≤ 3 volúmenes, ≤ 7 componentes por volumen, ≤ 3 fases | según paquete (abajo) |
| Resultado | `ResultadoMotor` en IndexedDB `rage-motor-resultados`, clave [hoja, firma] | adaptado al mismo `ResultadoMotor` | respuesta puntual o trazado |

Las hojas viven en localStorage `rage.motor.hojas.v1`. La firma de cada resultado incluye la formulación, los datos y la versión del solver; cualquier edición la invalida.

## 4. Qué tiene hoy

### Materia
Hecho: derivación local → integral → total con supuestos; catálogo de componentes por ID; corrientes por componente o total + composición; acumulación, llenado y vaciado (evento de agotamiento); generación y consumo declarados; varios volúmenes acoplados con balance global; convección y difusión 1D cartesiana; recuento estructural; unidades y resultados.
Falta: transferencia selectiva acoplada a termodinámica; cinética reactiva con termodinámica real; caudales desde momento; otras geometrías y dimensiones; resolución inversa general.

### Energía
Hecho: primera ley local → integral → total con Gauss y Reynolds; transporte de entalpía; calor y trabajo de frontera; recipiente rígido con presión calculada; presión prescrita; contacto térmico entre volúmenes; cambio de fase en la trayectoria; extracción por fase y eventos de fase ausente; conservación y segunda ley con T de frontera conocida.
Falta: energía de reacción; sólido en dinámica; transporte energético espacial; transferencia fuera del equilibrio; trabajo mecánico desde momento; presiones discontinuas.

### Termodinámica (paquetes publicados)

| Paquete | Especies | Fases | Dominio T [K] | En dinámica |
|---|---|---|---|---|
| `agua-iapws95` | agua | L, V, fluido | 273.16–1073.15 (sin banda crítica) | sí |
| `agua-iapws95-hielo-ih` | agua | S, L, V | 200–300 | no (solo estático) |
| `mezcla-ideal` | 8 | L, V | 159–583, P ≤ 5 bar | sí (contrastado hasta 7) |
| `nrtl-chemsep` | 8 | L, V | 159–583 | sí (contrastado hasta 4) |
| `nrtl-lle-agua-butanol` | 2 | L, L, V | 293–373 | sí |
| `unifac-original-public`, `unifac-dortmund-public` | 8 | L, V | 159–583 | sí |
| `unifac-original-lle-public` | 7 (sin metanol) | L, L, V | 283–313 | sí (2 especies contrastadas) |

Especies: agua, etanol, benceno, tolueno, 1-butanol, acetato de etilo, metanol y acetona. Corrientes solo entre paquetes con la misma referencia energética (no agua IAPWS ↔ mezcla). Sustituciones admitidas: v_L, Cp ideal y Psat por especie.

### Momento
Solo la vista fundamental simbólica; no se ejecuta.

## 5. Estado verificado hoy

Suites ejecutadas el 18 de octubre de 2026, sin cambios en el motor:

| Suite | Resultado |
|---|---|
| `npm run test:motor-fundamental` (31 scripts de frontend: materia, solver, energía, acoplamiento, multicomponente, termodinámica, red, diagramas, UNIFAC, catálogo) | todas pasan |
| `tests/validar_motor_termodinamica.py` | 585 correctas |
| `tests/validar_motor_termodinamica_h3.py` | 3729 correctas |
| `tests/validar_motor_ensamblaje.py` | 245 correctas |
| `tests/validar_motor_ensamblaje_v2.py` | 114 correctas |
| `tests/validar_motor_consolidacion_v2.py` | 128 correctas |
| `tests/validar_motor_n_componentes.py` | 82 correctas |
| `tests/validar_motor_unifac.py` | 136 correctas |
| `tests/validar_motor_diagramas_equilibrio.py` | 78 correctas |
| `tests/validar_motor_catalogo.py` | 125 de 126: **1 fallo de la propia prueba, no del motor** (abajo) |

**El fallo del catálogo.** La comprobación «capacidades puntuales = las de F1 + la acetona» quita la acetona de las capacidades actuales y las compara con `docs/ejemplos/motor-unifac/motor-termodinamica-capacidades.json`, que debería ser la foto de F1. Esa foto se regeneró el 16 de octubre (08:03) ya con la acetona, después de escribirse la prueba (07:52). Las capacidades no cambiaron; la referencia dejó de ser la de F1. Se arregla restaurando la foto de F1 o comparando sin quitar la acetona. No se tocó: pertenece al motor.

## 6. Alcance y límites conocidos

- **No resuelve**: estacionario, problemas inversos, DAE generales, forma integral sin reducir, 2D/3D, coordenadas curvilíneas, mallas móviles, momento, reacción química con termodinámica, energía en 1D.
- **Numérico 1D**: upwind de primer orden. En la advección pura de la hoja de prueba 07, con 80 celdas, se separa 8e-3 de la solución exacta, frente a 9e-5 de la simulación del núcleo de adimensionalización con el mismo dato. Con 20, 40 y 80 celdas los errores medios son 0.042, 0.022 y 0.011 (orden 1).
- **Expresiones libres**: AST seguro sin certificación dimensional interna; `step` y pulsos requieren resolución temporal suficiente.
- **Incidencias abiertas (F9)**: R1, criterios de fase inconsistentes entre búsqueda y publicación al cambiar la semilla; R2, candidatos fuera de dominio.
- **Pruebas**: la referencia de F1 de `validar_motor_catalogo.py` quedó sobrescrita (ver §5).
- **Aparición tardía de una fase (ensamblaje v2): corregida el 18 de octubre de 2026.**
  - **Síntoma.** En el ejemplo `motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante`, el motor publicaba la segunda fase líquida de A a 141,41 s. El límite de estabilidad independiente (plano tangente LL con `thermo`) está entre 113,5860 y 113,5861 s.
  - **Causa.**
    - La vigilancia sí detectaba el cambio y la bisección lo localizaba en 113,5860 s.
    - Pero el estado reintegrado hasta ese instante seguía siendo monofásico, porque difiere del interpolante en ~rtol justo en la arista.
    - La búsqueda posterior por pasos que se duplican terminaba con un subintegrado fallido, y el paso entero (111 → 142 s) se aceptaba **sin evento**.
  - **Corrección** (`core/ensamblaje_red.py`, `integrar`): si esa búsqueda no encuentra el cambio, el evento se toma en el instante de la bisección con el estado del interpolante, que la bisección ya demostró que cambia de conjunto de fases. El paso solo se acepta sin evento si tampoco ese estado cambia.
  - **Resultado.** Aparición a 113,58592 s (frente al compilador común, 113,58602 s); trayectoria igual a la del compilador común a 3e-7, antes 6e-5. Se regeneró el ejemplo (solo cambió ese archivo; los diagramas cambiaron únicamente su campo `segundos` y se restauraron).
  - **Suites.** `validar_motor_ensamblaje_v2` 114, `validar_motor_consolidacion_v2` 128, `validar_motor_n_componentes` 82, `validar_motor_unifac` 136, `verificar_contrato_unifac`, `npm run test:motor-fundamental`, `validar_corte_vertical` 71 y `validar_capa_unifac` 82: todas pasan.
  - **Alcance.** No cierra el pendiente general del checklist «Detección de transiciones no capturadas por el muestreo de pasos»: una fase que aparece y desaparece entre dos puntos vigilados sigue sin verse. El integrador v1 (`core/ensamblaje_dinamico.py`) no tenía este camino.
- **Interfaz**: un botón verde sin texto en la fila de acciones de `/motor/hojas`, observado durante la integración con adimensionalización.

## 7. Dónde se acopla la adimensionalización

La adimensionalización es una extensión del motor: lee sus hojas y no las modifica. Cada camino de cálculo ofrece un punto de enganche distinto.

| # | Enganche | Camino | Qué aporta | Estado | ¿Toca el motor? |
|---|---|---|---|---|---|
| 1 | Hoja de materia de un dominio → documento (`desdeMotor.ts`) | A | Grupos, régimen, simulación independiente y comparación con el resultado del motor | **Hecho (M1)**, 117 comprobaciones | no |
| 2 | Red de volúmenes de masa (`ensamblajeMateria.ts`) → sistema de EDO por volumen y especie | A | Escalas por volumen, números de residencia y rigidez de la red | Propuesto | no |
| 3 | Energía de un volumen con u(T) manual → [m, U] o [m, T] | A | Grupos térmicos (Stanton, cociente de capacidades, Damköhler térmico) | Propuesto | no |
| 4 | Diagnóstico de malla y rigidez con los límites del motor (≤ 160 celdas, upwind, 0.4 Δx/v, 0.2 Δx²/D) | A | Péclet de celda, celdas necesarias, aviso antes de resolver | Propuesto (M2) | no |
| 5 | Red termodinámica v2 → balances con propiedades como funciones con escala declarada, por ejemplo h(T) = c_p,ref·T_ref·ĥ(T̂) | B | Grupos de una red con fases y estados reales, sin álgebra sobre el paquete | Propuesto (M3) | no |
| 6 | Mostrar grupos y avisos de malla dentro del Resolver del motor; esquema convectivo de mayor orden | A/B | El motor usa lo que calcula la extensión | Requiere tu aprobación (M4) | sí |

Orden recomendado: 2 → 4 → 3 → 5. Los puntos 2 y 4 reutilizan casi todo lo de M1. El 5 necesita leer el contrato v2 del ensamblaje y decidir qué propiedades se escalan. El 6 se decide al final, contigo.

## 8. Fuentes

[ROADMAP_MOTOR_MULTIFISICO.md](ROADMAP_MOTOR_MULTIFISICO.md) · [CHECKLIST_MOTOR.md](CHECKLIST_MOTOR.md) · [SOLVER_HOJAS_MOTOR.md](SOLVER_HOJAS_MOTOR.md) · [ACOPLAMIENTO_MATERIA_MOTOR.md](ACOPLAMIENTO_MATERIA_MOTOR.md) · [FUNDAMENTO_ENERGIA_MOTOR.md](FUNDAMENTO_ENERGIA_MOTOR.md) · [UI_BALANCES_MOTOR.md](UI_BALANCES_MOTOR.md) · [INTEGRACION_MULTIFASICA_V2.md](INTEGRACION_MULTIFASICA_V2.md) · [../docs/MOTOR_ENSAMBLAJE_DINAMICO.md](../docs/MOTOR_ENSAMBLAJE_DINAMICO.md) · capacidades en vivo de `/motor/termodinamica/capacidades` y `/motor/ensamblajes/capacidades?revision=2` · [PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md](PLAN_CONEXION_ADIMENSIONALIZACION_MOTOR.md).
