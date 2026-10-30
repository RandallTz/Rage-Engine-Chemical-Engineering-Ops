# Estado: primer hito entregado en §19

Codex integró cierre volumen_fijo, tipo transferencia_materia y parámetros por conexión; no habilita energía/reacción ni estacionario. Contrato 5. Este documento es el registro del alcance, no una tarea pendiente. Las entregas posteriores B/C/D siguen pendientes y separadas.

# Entrega siguiente: interfaz de transferencia de materia

## Contexto para un chat nuevo
Proyecto de fundamentos de ingeniería química en modelos concentrados; no CFD ni operaciones completas. Claude modifica solo backend; Codex integra frontend. Sin commit, push ni publicación. Inspeccionar cambios locales y conservar cambios ajenos, especialmente thermodynamics/proveedor.py. Leer docs/ENTREGA_LABORATORIO_CODEX.md §§13–18. Reacción + interfaz térmica y transferencia estacionario → temporal ya están entregadas; no repetirlas.

## Decisión de alcance: un primer modelo pequeño y cerrado
Primera entrega: dos compartimentos perfectamente mezclados, de volúmenes geométricos fijos declarados, cerrados al exterior, isotermos, sin reacción y sin balance energético. Una interfaz sin inventario propio permite el intercambio de una especie seleccionada. El resto no cruza. Se resuelven conjuntamente los inventarios de ambas partes, nunca cada lado por separado. No habilitar una combinación mayor antes de verificar este hito.

Es un modelo de soluto diluido y volúmenes constantes, no una membrana multicomponente general. Declarar limitaciones: coeficientes constantes, equilibrio lineal, sin ósmosis, electromigración, difusión cruzada ni cambio de volumen. No inferir identidad química, coeficientes o unidades del nombre o de la fórmula de una especie.

## Ley inicial propuesta; confirmar y documentar antes de implementarla
Usar una tasa total de transferencia, no confundirla con flujo superficial:

    c_i,1 = n_i,1 / V1
    c_i,2 = n_i,2 / V2
    dot_n_i,12 = L (c_i,1 − c_i,2 / H)
    d n_i,1 / dt = −dot_n_i,12
    d n_i,2 / dt = +dot_n_i,12

L [m3/s] es la conductancia material global declarada (puede representar kA); H > 0 es el coeficiente de reparto, adimensional, definido c2_eq = H c1_eq. c [mol/m3], n [mol], V [m3], tasa [mol/s]. L >= 0; L = 0 es explícito, ausencia de L es dato pendiente. H = 1 también se declara, no se supone. La ley es fenomenológica para ese dominio, no reemplaza un cierre termodinámico general de potencial químico.

## Punto crítico: cierre material
NO reutilizar sum(n) = rho V como restricción de ambos lados. El intercambio selectivo cambia el número de moles de cada compartimento; imponer inventario constante sin mecanismo compensatorio sería contradictorio. V fijo no significa N fijo. Definir un cierre explícito de almacenamiento a volumen geométrico fijo para este modelo diluido, sin introducir una densidad molar total constante. Los inventarios de especies no transferidas permanecen constantes. No inventar una corriente compensatoria ni proyectar estados.

La temperatura isotérmica aquí es parámetro del alcance, sin balances ni calor calculado. No presentar este modelo como conservación energética demostrada.

## Ensamblaje y trazabilidad
- Proponer esquema aditivo: tipo de conexión inequívoco distinto de corriente material y de interfaz térmica; parámetros por ID de conexión, especie por identidad canónica; documentar unidades y validación.
- Conservar ni como estados y ci/tasa como algebraicas derivadas. No duplicar estados de interfaz ni añadir igualdad innecesaria.
- Construir terminos[], LaTeX, cancelaciones y residuo_terminos desde el mismo ensamblaje que se evalúa. Signo negativo en origen, positivo en destino; citar pieza y conexión.
- Declarar método elegido, dominio, tolerancias, eventos y restricciones. El frontend solo consulta y representa respuestas.
- Actualizar modelo_id, huellas por elemento, capacidades.combinaciones y ejemplos. No habilitar por suma de capacidades individuales.
- Mantener contratos y resultados existentes; códigos específicos con pieza y conexión afectadas.

## Estacionario: no elegir un inventario total arbitrario
Dos compartimentos cerrados tienen una familia de equilibrios determinada por el inventario total inicial conservado. El temporal puede mostrar el límite de su trayectoria. Un estacionario sin total impuesto debe declararse indeterminado; no introducir un valor por omisión ni declarar estabilidad asintótica global en toda la dimensión (hay un modo conservado).

Para el primer hito basta el temporal. Si se incluye estacionario, exigir explícitamente el total conservado y documentar su restricción independiente. La transferencia estacionario → temporal queda deshabilitada para esta combinación hasta tener un origen único y restricciones verificadas.

## Aceptación independiente
1. Solución analítica para N = n1(0)+n2(0): n1_eq = N V1/(V1+H V2), n2_eq = N H V2/(V1+H V2), tau = 1/[L(1/V1 + 1/(H V2))], para L > 0. Verificar inventarios y tasa fuera del motor.
2. L = 0 conserva ambos inventarios; fuerza impulsora cero conserva el reparto aunque c1 != c2 si H != 1.
3. Conservación de la especie, elementos y masa globales. Las especies impermeables no cambian. No confundir cierre numérico con precisión independiente.
4. Invertir extremos requiere H' = 1/H y L' = L/H para representar la MISMA ley con esta convención; verificar trayectoria física idéntica y signo opuesto. No asumir que basta invertir la flecha conservando L,H.
5. Volúmenes distintos, lado receptor vacío, altas conductancias, inventarios no negativos y escalas temporales extremas. Comparar integradores apropiados y declarar rigidez.
6. Rechazos: datos sin unidad, V <= 0, H <= 0, L < 0, especie ausente, inicial negativa, interfaz hacia una corriente, reacción/energía/topología no verificadas, cierre incompatible.
7. Persistencia JSON sin mutación, identidad por conexión, términos opuestos y cancelación global exacta estructural.

## Entregas posteriores, no incluir silenciosamente
B: transporte material + energía con entalpía del material transferido, orientación y referencia coherentes; calor sensible/químico sin doble conteo. C: reacción + transporte selectivo, cinética acoplada y restricciones. D: actividad/potencial químico y equilibrio no ideal con proveedor y datos disponibles. Cada combinación necesita capacidad, contrato y referencias propios.

## Qué devolver a Codex
Sección nueva de entrega con esquema exacto, límites, códigos, migración, ejemplos ejecutados petición/respuesta y resultados de suites. Indicar explícitamente si se cambió el cierre o las condiciones de estacionario. No exigir cálculo, selección de solver ni correcciones físicas en el frontend.
