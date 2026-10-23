# Siguiente entrega: agua pura, saturación y especificaciones inversas

**Referencia histórica:** H3 entregado e integrado dentro del dominio publicado. La continuidad se consulta en el [roadmap principal](../../engine/multiphysics-roadmap.md); este título no abre otra entrega ni reemplaza el trabajo actual.

14 de octubre de 2026. Continúa `docs/history/frontend/contract-claude-thermodynamics-engine.md` después de H0/H1. Encargo para Claude: backend, pruebas y documentación. Codex mantiene frontend. Sin cambios al laboratorio ni a `thermodynamics/proveedor.py`; sin commit/push.

## Orden de trabajo

H0/H1 está recibido: evaluación real TP de agua pura, ramas monofásicas y estabilidad con alcance declarado. El lector TypeScript acepta sus ejemplos reales. Codex añadió el contraste independiente de la masa molar del modelo `agua-iapws95:1`, incluso cuando la solicitud no la declara, y al recuperar una respuesta guardada. No se envían masas molares redondeadas por omisión ni se borran declaraciones contradictorias del usuario.

La próxima entrega física es **H3 estático**, antes de H2/H4 dinámicos. UV/UP son las relaciones que necesitará el coordinador para reconstruir estados desde cantidades y energía. No entregar una trayectoria usando todavía `u(T)` manual como si fueran propiedades IAPWS. El contrato de `validar`/`resolver` independiente se acuerda por separado antes de implementarlo; esta entrega no lo requiere.

Implementar y verificar sucesivamente: (1) coexistencia y propiedades de saturación, (2) PH, (3) UP, (4) UV. Publicar cada capacidad solamente después de sus pruebas. Si una subregión no es viable, mantener el diagnóstico y documentar el alcance, sin completar por aproximaciones no declaradas.

## Física requerida

Mantener la EOS, unidades, masa molar, referencias de u/s, dominio y trazabilidad de H1. La fase se obtiene del estado estable, nunca del nombre del componente ni de `tiposPermitidos`.

Para coexistencia líquido-vapor, resolver y verificar T_l = T_v, P_l = P_v, g_l = g_v. Usar ramas físicas de la EOS y verificar Maxwell; no evaluar la región homogénea espuria de la campana como una tercera fase. Documentar bracketing, tolerancias, escalas, criterios de convergencia y tratamiento de varias raíces. Las restricciones solicitadas se comprueban después de encontrar el equilibrio; no se fuerzan ramas metastables para satisfacerlas.

Con agua pura, q es fracción másica de vapor; coincide con la molar, pero no con la volumétrica:

```
u = (1-q) u_l + q u_v
h = (1-q) h_l + q h_v
v = (1-q) v_l + q v_v
s = (1-q) s_l + q s_v
epsilon_v = q v_v / v
```

Todos los valores de fase corresponden a la misma T/P y referencia. No añadir calor latente como una fuente adicional: ya está en la diferencia entre propiedades de las fases.

| Especificación | Qué fija | Qué reconstruir |
|---|---|---|
| TP | T, P y composición | Sigue indeterminada sobre saturación: no escoge q. |
| PH | P, h y composición | T, fase(s), q cuando procede, u y v. En saturación q=(h-h_l)/(h_v-h_l). |
| UP | U, P y cantidades por componente | m y u=U/m; T y fase(s), con q=(u-u_l)/(u_v-u_l) cuando procede; V=m v. |
| UV | U, V y cantidades por componente | m, u=U/m, v=V/m; T/P y fase(s). En coexistencia resolver simultáneamente las restricciones de u y v, no tomar una fracción distinta para cada una. |

Cantidad nula total, unidades incompatibles, cantidades negativas o identidades incompatibles se diagnostican; cantidades y energía dadas nunca se ajustan para lograr un flash. Las bases másica y molar deben reconstruir el mismo estado con la masa molar publicada por el modelo.

Estabilidad: para UV, derivar/documentar el criterio correspondiente a U,V,n fijos (máximo S) y comprobar candidatos admisibles. Para PH/UP, documentar el criterio de selección y reconstrucción a presión prescrita y comprobar estabilidad de las fases a la T/P resultante. No afirmar un mínimo G a U/V fijos, ni aplicar automáticamente un supuesto máximo de S a UP sin derivación. Una raíz convergida no equivale a equilibrio estable; una ambigüedad no se resuelve eligiendo la primera raíz.

Mantener excluidos sólidos y región crítica hasta disponer de verificación propia. Cerca de Tc, las diferencias u_v-u_l y v_v-v_l tienden a cero: declarar el umbral y diagnosticar el mal condicionamiento; no fabricar calidad. No extrapolar fuera del dominio para cerrar una inversión.

En q=0 o q=1 publicar solo la fase presente. Para fracciones positivas pequeñas, conservar la traza y reconstruir correctamente; no usar recorte/renormalización como corrección física. Cualquier tolerancia de conjunto activo debe quedar documentada junto a sus residuos.

No publicar Cp/Cv de una fase como capacidad del estado bifásico. En revisión 1 omitir Cp/Cv globales bifásicos; las propiedades monofásicas de cada fase pueden seguir presentes. Tampoco interpolar sus Cp para fingir la derivada del estado de equilibrio.

## API y compatibilidad

Mantener revisión 1 y las rutas existentes: capacidades y evaluar. Los tipos PH/UV/UP ya están definidos; no cambiar su significado ni introducir campos obligatorios adicionales. Mantener IDs de solicitud, propietario, componente y modelo, rechazo con `evaluacion:null`, códigos/rutas y campos opcionales omitidos según el contrato.

Actualizar `especificaciones` solo para las inversiones verificadas. Mantener `dinamica:false`. Una vez disponibles, el diagnóstico TP de saturación ofrece alternativas válidas PH/UV/UP, sin afirmar que cualquiera de ellas está soportada antes de estarlo. La UI solo ofrece especificaciones publicadas.

Además de las verificaciones de H1, un resultado de varias fases necesita `equilibrio`, reconstrucción de componentes, bases de fase, energía y volumen cuando están dados. Publicar residuos y escalas reales, no ceros para comprobaciones ausentes. El método de estabilidad debe declarar su alcance físico y numérico. `cambioInterno:prohibido` sigue sin certificar una trayectoria en esta API puntual.

No transformar una consulta guardada en condiciones iniciales de un volumen ni mezclar la referencia IAPWS con la relación afín manual. La firma de la consulta y la del modelo dinámico siguen separadas.

## Pruebas de aceptación

1. Regresión completa H1: TP monofásico, exclusiones, estabilidad y referencias intactas.
2. Propiedades y curvas de coexistencia frente a valores publicados; contraste independiente de implementación (por ejemplo IF97), declarando la relación física entre formulaciones.
3. Ida y vuelta TP -> PH/UP/UV -> mismo estado en líquido comprimido, vapor y fluido supercrítico dentro del dominio.
4. Coexistencia con diversas q, incluyendo extremos y trazas; reconstrucción independiente de u,h,v,s, cantidades y fracciones en las tres bases. La fracción volumétrica debe diferir de q donde corresponda.
5. UV: soluciones monofásicas y de coexistencia, múltiples semillas, unicidad/ambigüedad documentada, criterios de estabilidad y residuos simultáneos. No presentar como pruebas independientes dos llamadas al mismo flash.
6. Datos equivalentes en unidades y bases distintas; invariancia al escalar U,V y cantidades conjuntamente. No cambiar el estado intensivo ni las fracciones.
7. Datos incompatibles, saturación TP incompleta, restricciones de fase, región crítica, cantidades nulas y límites de dominio: rechazos con rutas y sin último resultado reciclado.
8. Misma referencia para todas las fases; identidades h=u+Pv y g=h-Ts; tolerancias escaladas y refinamiento de inversión. No certificar una transición temporal ni producción global de entropía en una consulta.
9. Respuestas reales Python -> JSON -> lector TypeScript. Ejecutar `npm run test:motor-fundamental`; se incluye ahora la suite de integración real H0/H1. No cambiar ejemplos anteriores para esconder regresiones.

Generar pares petición/respuesta desde endpoints. Documentar decisiones, resultados, dominio, modelos/versiones y pendientes. Si H3 cambia el método/identidad física de estados TP, declarar y justificar la versión del modelo; no ampliar silenciosamente el significado de una versión ya auditada.

## Entrega posterior de ensamblaje (no implementar en este hito)

**Seguimiento:** H3 entregado en `docs/engine/thermodynamics-h3.md` y recibido por Codex el 14 de octubre de 2026. Sus respuestas reales pasan el lector y las 67 comprobaciones específicas nuevas de integración. El siguiente encargo es E0 de [docs/history/frontend/contract-claude-assembly-dynamic-engine.md](contract-claude-assembly-dynamic-engine.md); este documento H3 ya no es la tarea pendiente.

**Consolidación posterior:** el usuario pidió una sola entrega. El contrato de ensamblaje enlazado reúne ahora E0–E3 en el mismo encargo, con validación e inicialización antes de las trayectorias. La indicación anterior de entregar solo E0 queda sustituida. H3 permanece cumplido y no debe repetirse.

Preparar el borrador de contrato `validar`/`resolver`: formulación efectiva y trazabilidad de términos, catálogo único, topología/puertos, cantidades por componente y energía como estados, variables algebraicas T/P/V/fases, geometría rígida o presión prescrita, estados independientes de corrientes y referencias coherentes. Separar declaración de valores de una evaluación calculada.

Debe explicar inicialización, recuento estructural/rango y límites, datos/iniciales pendientes por ruta, sistema ODE/DAE o matriz de coeficientes, derivadas completas de V y trabajo de frontera, eventos y comprobaciones de fase. Proveedor local durante RK/Newton; no una petición HTTP por etapa. Los cierres contradictorios se diagnostican juntos, sin reglas OR ni ecuaciones adicionales para forzar resolución.

Para presión prescrita puede elegirse H como coordenada si se deriva y verifica `dH/dt = J_E + V dP/dt` en el régimen correspondiente. No reutilizar `P dm/dt / rho` fuera de densidad constante. Materia y energía conservan las mismas corrientes compartidas. Este borrador necesita revisión antes de H2/H4; su existencia no habilita aún el solver termodinámico.
