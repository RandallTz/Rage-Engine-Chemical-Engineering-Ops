# Integración de fundamentos del laboratorio

Actualización tras 9041197: la primera entrega de balances estacionarios por especie y tasas especificadas ya está implementada por Claude. Este documento conserva el contrato original; la lista vigente de trabajo restante está en PENDIENTES_BACKEND_CLAUDE.md. Cinética general, dinámica y equilibrio calculado siguen pendientes.

El frontend contiene una biblioteca de 72 fundamentos y una reducción didáctica del balance de especie. No se modificó el backend. El motor térmico existente debe seguir funcionando sin cambios incompatibles.

## Primera entrega numérica solicitada

Extender el ensamblador con balances molares por especie y transformación estequiométrica en volúmenes concentrados. Empezar por régimen estacionario con reacción de tasa especificada o cinética explícitamente soportada; no implementar CFD ni interpretar LaTeX como código.

- Cada corriente conserva un estado compartido y sus caudales por especie. La producción y desaparición química pertenecen al volumen, no son alimentaciones ficticias.
- Exponer generación G_i y consumo C_i [mol/s], ambos no negativos, y fuente neta G_i−C_i. Derivarlos de estequiometría y tasas: no añadir dos incógnitas libres por especie.
- Declarar ν positivo para productos y negativo para reactivos. Para reacción reversible, especificar tasas directa/inversa o dirección efectiva. Un mismo evento produce unos componentes y consume otros.
- Conservar elementos y masa total; el caudal molar total puede cambiar. Rechazar estequiometría incompatible y estados negativos.
- Sin reacción elimina simultáneamente producción, consumo y cierres cinéticos. Estado estacionario elimina acumulación, no las fuentes.
- Mantener contratos térmicos existentes. Los nuevos bloques/capacidades deben anunciarse explícitamente en capacidades y diagnosticarse cuando no están soportados.
- Respuesta trazable: id de ecuación, volumen y conexiones de origen, símbolos, unidades, valores, restricciones y ecuaciones efectivamente resueltas. LaTeX generado por el motor.
- Método real, grados de libertad, residuos escalados y conservación elemental/global. No declarar un algoritmo que no se ejecuta.
- Energía reactiva: declarar referencias químicas y evitar duplicar calor de reacción si la entalpía ya incluye formación.

## Aceptación

1. A → B, una entrada y salida: consumo de A y generación de B iguales a la tasa de avance; masa y elementos conservados.
2. A → 2B con especies físicamente compatibles: cambia caudal molar total, conserva masa.
3. Reacción reversible: dirección inversa intercambia producción y consumo correctamente.
4. Dos volúmenes comparten una corriente, sin duplicar variables del estado intermedio.
5. Sin reacción recupera balance no reactivo; falta de cierre devuelve diagnóstico por bloque.
6. Datos negativos, unidades ambiguas y estequiometría inválida devuelven diagnósticos claros.
7. Repetir los casos térmicos anteriores para garantizar compatibilidad.

## Entregas posteriores, separadas por capacidad

Termodinámica: s, μ, actividades/fugacidades y estados estándar trazables; segunda ley necesita temperaturas de frontera; exergía necesita ambiente y referencias.

Calor: sólidos/capas 1D estacionarios, Fourier, resistencias de contacto y condiciones de frontera; luego modelos concentrados transitorios con condiciones iniciales.

Materia: difusión binaria y películas con bases de flujo y equilibrio interfacial declarados.

Momento: balances concentrados y tuberías, viscosidad, Darcy y rangos de correlaciones. No solver de campos 3D.

Antes de conectar una capacidad, incluir casos analíticos independientes, límites físicos y diagnóstico de modelos fuera de alcance. Las fichas de consulta no implican que el motor pueda resolverlas.

## Precisión obligatoria: fuentes brutas y netas

La fuente neta no determina generación y consumo brutos. En equilibrio una reacción reversible puede tener r+=r−>0 y fuente neta cero. Si el motor solo conoce tasa neta, devolver fuente_neta y declarar generacion_bruta/consumo_bruto no disponibles; no inventarlas con max(fuente_neta,0). Si usa esa descomposición, identificarla explícitamente como descomposición neta, distinta de intercambio bruto.

Agregar aceptación con tasas directa e inversa positivas e iguales y comprobar fuente neta cero con producción/consumo brutos positivos. La API debe distinguir base volumétrica [mol/(m³·s)] de tasa integrada [mol/s].

La biblioteca incluye Hess, Kirchhoff, reactivo limitante, órdenes, rendimiento/selectividad, diseño ideal y catálisis. Son consulta; no implican implementación numérica. Antes de energía reactiva, declarar base de reacción, fases y referencias; no duplicar calor químico.

## Módulo independiente de reacciones del frontend

Ruta /laboratorio/reacciones: balanceo elemental y de carga con aritmética racional; reactivo limitante cerrado; Hess con entalpías de formación introducidas y Kirchhoff con Cp constante; lote analítico de primer orden. Son cálculos educativos locales, no llamadas al motor. No convertir automáticamente fórmulas del editor en sustancias soportadas por el proveedor. Redes cinéticas, equilibrio y acoplamiento térmico general siguen pendientes del backend.

Ampliación local: tabla periódica con fórmulas y carga; Hess por combinación de pasos; inventarios/conversión/rendimiento; órdenes 0/1/2 analíticos; cuaderno persistente. Fórmulas no se vinculan automáticamente a sustancias del motor; actividades, fases, cinética experimental y redes generales siguen requiriendo API validada.

Exploración adicional local: Arrhenius referenciado (primer orden), conversiones analíticas lote/CSTR/PFR a densidad constante, y lote consecutivo A→B→C de primer orden 1:1. No se vinculan automáticamente a especies ni cinética del motor.

## Editor de redes de reacción (frontend)

La ruta /laboratorio/reacciones incorpora un quinto paso con especies compartidas por ID, pasos reversibles, matriz estequiométrica y balances por especie junto al diagrama. Permite explorar redes cerradas isotérmicas a volumen constante, con pasos 1:1 de primer orden. El cálculo local usa exponencial matricial por uniformización (λt≤100), no un solver general del backend. Comprueba conservación elemental y carga, no negatividad y casos analíticos consecutivos, paralelos y reversibles. Las fórmulas iguales pueden representar especies distintas; no identifican estructuras químicas.

Pendiente para Claude: contrato general de especies y reacciones con coeficientes arbitrarios y múltiples reactivos/productos; leyes cinéticas con unidades y procedencia; generación y consumo brutos separados; ensamblaje de balances y resolución con diagnóstico, conservación y trazabilidad. Equilibrio y acoplamiento energético requieren modelos físicos explícitos. No interpretar el LaTeX. El frontend actual no envía la red local al backend ni promete resolver estos casos generales.
