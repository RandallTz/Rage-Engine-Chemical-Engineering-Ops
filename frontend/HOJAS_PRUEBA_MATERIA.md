# Hojas de prueba de materia listas para Resolver

13 de octubre de 2026. Ocho documentos editables de `/motor`, cargados explícitamente desde «Añadir hojas de prueba · materia». No se modifica el backend ni el laboratorio. Son referencias independientes para contrastar el motor posteriormente, no escenarios incorporados al compilador numérico.

En `/motor/hojas`, cada tarjeta tiene «Resolver →». Lleva al formulario completo; basta pulsar Resolver. Todas parten con GL estructural 0, iniciales completas, unidades, horizonte y condiciones de frontera declarados. Las hojas nuevas no contienen resultados precalculados: se ejecuta la ecuación vigente. La derivación y los supuestos se pueden revisar o cambiar desde Ecuaciones.

| Hoja | Datos | Referencia esperada |
| --- | --- | --- |
| 01 · Tanque que se llena | m₀=100 kg; entrada 3 kg/s; salida 2 kg/s; 10 min | m(t)=100+t; final 700 kg |
| 02 · Tanque que se vacía | m₀=100 kg; entrada 1 kg/s; salida 3 kg/s; 30 s | m(t)=100−2t; final 40 kg |
| 03 · Llenado en litros | V₀=100 L; entrada 3 L/s; salida 1 L/s; 5 min | V(t)=0.1+0.002t m³; final 700 L = 0.7 m³ |
| 04 · Entradas y salidas iguales | m₀=100 kg; entrada y salida 2 kg/s; 10 min | m=100 kg en toda la trayectoria |
| 05 · Vaciado hasta agotarse | m₀=100 kg; salida 2 kg/s; horizonte solicitado 120 s | Se vacía en 50 s; `parcial` es el resultado correcto, no un fallo |
| 06 · Conversión de A en B | A₀=1 kg; B₀=0 kg; consumo de A y generación de B = 0.2 m_A kg/s; 20 s | A=e^(−0.2t); B=1−A; final 0.0183156389 / 0.9816843611 kg; total 1 kg |
| 07 · Transporte por convección · 1D | x∈[0,1] m; ρ₀=2+0.3 sin(2πx) kg/m³; v=1 m/s; extremos periódicos; 0.25 s | ρ(x,t)=2+0.3 sin[2π(x−t)]; cantidad por área 2 kg/m² |
| 08 · Difusión de dos componentes · 1D | x∈[0,1] m; ρ_A₀=0.5+0.1 sin(2πx); ρ_B₀=1−ρ_A₀; D_A=D_B=0.05 m²/s; extremos periódicos; 0.5 s | ρ_A=0.5+0.1 e^(−4π²Dt) sin(2πx), ρ_B=1−ρ_A; total espacial 1 kg/m³ |

En las fórmulas de la tabla, t es segundos y x metros; los coeficientes escritos incluyen las unidades correspondientes. A y B son especies genéricas con una conversión que conserva masa. No se atribuyen propiedades de compuestos químicos reales. La generación/consumo está formulada explícitamente mediante expresiones acopladas, sin fabricar una cinética por elegir un tipo de equipo.

La hoja 04 conserva la derivada temporal y obtiene dm/dt=0 de sus datos. No usa la opción de retirar acumulación ni el solver estacionario (que sigue pendiente aquí). La hoja 03 se deriva de m=ρ̄V, densidad media constante y puertos convectivos con densidad común. La densidad se cancela en la ecuación final y no se solicita ni se inventa un valor para ella.

Las hojas 07 y 08 usan 80 celdas y RK45 con límite CFL. La referencia continua no coincide exactamente con la discretización: el upwind introduce difusión numérica y la difusión centrada modifica ligeramente la tasa del modo sinusoidal. Los gráficos de ambas hojas están preparados para mostrar simultáneamente evolución en la celda central y perfiles espaciales; en difusión aparecen A y B juntos.

## Comprobación independiente

`npm run test:hojas-materia` ejecuta las ocho ecuaciones y compara cada trayectoria con las referencias de la tabla. Incluido también en `npm run test:motor-fundamental`.

- **9190 comprobaciones**, incluidas todas las muestras/celdas pertinentes, completitud, datos activos, cantidades no negativas y conservación.
- Llenado/vaciado: error absoluto máximo 5.69e−13 kg.
- Volumen: error máximo 1.12e−16 m³.
- Cantidad constante: exacta.
- Agotamiento: t=49.999999999999815 s, sin valores negativos publicados.
- A→B: error máximo 1.13e−11 kg; masa total conservada.
- Convección: error medio máximo 0.011423 kg/m³ frente a la traslación continua; presupuesto −2.17e−18 kg/m².
- Difusión: error máximo 1.890e−5 kg/m³ frente al campo continuo; suma de densidades y presupuestos correctos.

QA en navegador: las ocho hojas tienen Resolver habilitado, GL 0, valores e iniciales completos. Se han añadido al navegador del usuario, conservando sus documentos anteriores y sus archivados. El formulario y la biblioteca se revisan sin sobrecargar la pantalla con explicaciones.

## Persistencia y archivos

`app/motor/hojasPruebaMateria.ts` solo construye documentos mediante las operaciones existentes del editor. No hay bifurcaciones por nombre/escenario en el solver. Cada hoja es editable, duplicable y archivable. IDs de prueba estables, versionados: añadir la tanda otra vez no duplica, sobrescribe ni desarchiva una variante editada. El guardado de la tanda es único y conserva todas las otras hojas.

Cambios: generador de documentos, guardado aditivo de la tanda en `hojasMotor.ts`, accesos en `BibliotecaHojas.tsx`, estilos locales y `verificar_hojas_prueba_materia.mjs`. No se han cambiado métodos numéricos, backend ni laboratorio; no hay commit ni push.
