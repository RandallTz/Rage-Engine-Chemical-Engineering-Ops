# Referencia del motor: un volumen, un componente — materia

Fecha: 13 de octubre de 2026. Alcance exclusivo: `/motor`, formulación y pruebas independientes. No se modificó el laboratorio, sus peticiones, su backend, sus simulaciones ni su solver.

> Informe del hito de formulación, anterior al solver. Sus 147 comprobaciones y 66 contrastes siguen vigentes. La resolución numérica añadida después se documenta y verifica por separado en [docs/engine/sheet-solver.md](../../engine/sheet-solver.md); las menciones de ausencia de solver en este informe describen el alcance de aquella auditoría.

## Propósito acordado

Este apartado define de manera visible y verificable la matemática que deberá respetar el motor del laboratorio. Se completará para materia, energía y momento. Después se compararán ambas implementaciones para localizar discrepancias. La prioridad actual es un único dominio y una única especie completa; todavía no el acoplamiento entre dominios.

## Resultado y condiciones

`npm run test:motor-fundamental` pasa. La nueva prueba específica tiene **147 comprobaciones y 66 contrastes con referencias independientes**. Error relativo máximo: **3.32e-11**, normalizado por max(1, |referencia|), en evaluaciones de identidades y diferencias centrales. No mide error de una simulación temporal: no se ejecutó un solver.

La equivalencia que se verifica es:

- Local: ∂ρ/∂t = −∇·(ρv) + γ − χ para una especie completa y velocidad media en masa.
- Integral: d/dt ∫V(t)ρ dV = −∮∂V(t)ρ(v−v_b)·n dA + ∫V(t)(γ−χ)dV.
- Total: dm/dt = Σpuertos declarados de entrada ṁ − Σpuertos declarados de salida ṁ − Φ_resto + G − C.

La integral total conserva fuentes variables, flujo relativo al dominio y la normal exterior. La forma total no presupone mezcla perfecta, densidad constante o un caudal constante. Los puertos declarados y su complemento deben ser una partición sin solapamientos. V es el dominio que se selecciona; si se elige el líquido que ocupa un tanque y cambia de nivel, su dominio puede moverse aunque el recipiente sea rígido.

## Hallazgos corregidos

**M1 — Difusión de una especie completa.** La hoja publicaba j_A=0 entre sus relaciones, pero seguía conservando un término difusivo independiente en la ecuación principal. Con velocidad media en masa, una especie única comparte esa velocidad, por lo que su flujo relativo es cero. Se elimina coherentemente en las formas diferencial, integral y total. La opción se muestra desactivada con el motivo, sin alterar la opción almacenada que podrá reaparecer al añadir otra especie. El índice i genérico no declara que toda la mezcla tenga una sola especie y conserva su forma general.

**M2 — Partición de la frontera.** Un puerto no declarado podía seguir representado por una sumatoria desconocida y, simultáneamente, dentro de Φ como parte de las superficies fuera de los puertos declarados. Ahora el balance solo incluye puertos declarados y su complemento. Un intercambio todavía no clasificado queda en Φ una sola vez. Sin puertos, Φ representa toda la frontera. Marcarla sin flujo declara entonces un dominio cerrado; no se impone ese supuesto por omisión. El catálogo tampoco añade corrientes ficticias.

**M3 — Transporte idénticamente nulo.** v=0, j=0 y frontera fija anulan el transporte relativo. Se retiran términos de flujo de la forma total, igual que de la integral. Con fuentes ausentes se obtiene acumulación nula; si hay fuentes, permanecen. Declarar un puerto constante no le asigna un valor no nulo: su definición sigue imponiendo flujo cero cuando corresponde.

**T1 — Cobertura real de las pruebas.** El cargador TypeScript de algunas pruebas compilaba a un objetivo antiguo que no preservaba correctamente el recorrido de Set. Las relaciones agregadas podían resultar vacías en las pruebas aunque existieran en la aplicación. Los cargadores usan ahora ES2022, compatible con el Node que las ejecuta. Se vuelven a renderizar y comprobar las relaciones reales; no se ha relajado ningún criterio.

## Referencias independientes usadas

| Referencia | Qué comprueba |
| --- | --- |
| m(t)=m₀+(F_ent−F_sal)t, incluidos F variables | Signos, llenado, vaciado y balance entre entrada y salida |
| Un puerto de entrada de 3 y una salida no clasificada de 1 | Φ incluye esa salida una sola vez: dm/dt=2 |
| Sin puertos y Φ positivo/negativo | Signo exterior/interior sin inventar corrientes |
| Frontera completa impermeable, sin fuentes | dm/dt=0 |
| ρ(x)=2+x, v=0, L(t)=1+t | Campo estacionario y dominio móvil: dm/dt=(2+L)dL/dt, distinto de cero |
| ρ=2, v=3, dL/dt=0.75 | El flujo de salida es ρ(v−v_b), no ρv: acumulación 1.5 |
| ρ̄(t)=2+t y V(t)=3+2t | Regla del producto conserva V·dρ̄/dt y ρ̄·dV/dt |
| Densidad 1000, Q_ent y Q_sal declarados | Misma conservación en kg/s y m³/s; las fuentes también se dividen por densidad |
| γ(x)=x² en [0,3] | G=9; usar γ del punto medio por V daría 6.75 y sería incorrecto |
| Generación uniforme de 2 en V=3 | Solo declarar uniformidad permite G=γV=6 |
| G=C=8 | Tasas brutas presentes aunque el neto sea cero |
| v=a·x y ρ(t)=2 exp(−3at) en cubo, cilindro y esfera | Continuidad local, factores métricos, integral de flujo y conservación total |

Los datos de estas referencias existen solamente en las pruebas. No se han añadido presets físicos ni escenarios al editor. El script evalúa los términos estructurados que usa la ecuación total, con valores de referencia calculados por separado. También verifica las identidades mediante cuadratura de polinomios y diferencias centrales, sin integrar una trayectoria.

## Implementación y reproducción

- `app/motor/recorridoMateria.ts`: campo efectivo por número de especies y términos totales con rol, signo, componente, puerto y forma de fuente. El renderizador consume esos términos.
- `app/motor/MateriaFundamental.tsx`: motivo visible de difusión cero y aclaración del complemento de frontera.
- `app/motor/catalogoMateria.ts`: variables de puertos reales; flujo restante explícito y ausencia de difusividades que no intervienen.
- `verificar_un_volumen_materia.mjs`: referencias independientes, sin importar ni llamar al laboratorio.
- Cargadores de `verificar_operadores_materia.mjs` y `verificar_recorrido_materia.mjs`: objetivo ES2022.

Desde `frontend`: `npm run test:motor-fundamental`, `npx tsc --noEmit --incremental false` y `npx eslint app/motor`.

## Revisión visual

Se probó en una pestaña de QA independiente: añadir solo Agua desactiva difusión con su motivo; las tres formas conservan velocidad relativa y fuentes; cerrar toda la frontera y retirar fuentes da dm/dt=0; declarar una entrada y una salida recupera sus caudales; las relaciones elegidas de densidad y puertos producen dV/dt=Q₁−Q₂ en m³/s; fijar además el dominio produce 0=Q₁−Q₂. Deshacer recupera la formulación anterior y retira la fila cancelada. Sin errores de consola, fórmulas sin fallbacks y sin desborde horizontal de la página. La pestaña del usuario y el laboratorio no se alteraron.

## Límites que permanecen

La comprobación cubre las transformaciones implementadas y las referencias indicadas. No certifica cualquier combinación arbitraria de hipótesis, leyes constitutivas, geometrías o datos. Las tasas γ y χ son fuentes volumétricas genéricas; no se ha declarado una reacción química. Una reacción futura necesitará estequiometría, bases consistentes y conservación de masa del conjunto completo, no tasas arbitrarias de creación de masa.

No hay todavía un árbol general de expresiones tipadas, un comprobador completo de contradicciones entre hipótesis, discretización de campos, comprobación de geometría real, positividad sobre una trayectoria ni solver de esta hoja. Los términos estructurados del balance total son un avance acotado, no un ensamblador multifísico completo. La reducción m=ρ̄V exige V>0 y dividir por ρ̄ exige ρ̄>0. Los ejes singulares de coordenadas curvas requieren límites regulares. No se ha afirmado verificar un estado de tanque vacío ni un modelo bifásico con estas expresiones.

La siguiente implementación se mantendrá en este apartado: representar las expresiones y condiciones de validez de un solo dominio, luego formular energía y momento en el mismo dominio, verificar cada familia y sus variables comunes. La comparación con el laboratorio se hará después, con referencias acordadas, sin modificarlo como parte de esta auditoría.

## Fuentes técnicas

[COMSOL: transporte de masa y flujos respecto a la velocidad media en masa](https://www.comsol.com/multiphysics/what-is-mass-transfer) fundamenta la convención de difusión y su suma nula. Para una única especie, j=0 es la consecuencia usada aquí.

[Universidad de Cambridge: volúmenes de control móviles](https://www-mdp.eng.cam.ac.uk/web/library/enginfo/aerothermal_dvd_only/aero/fprops/cvanalysis/node31.html) fundamenta el uso de velocidad relativa al dominio.
