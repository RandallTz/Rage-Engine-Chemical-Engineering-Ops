# Hojas multicomponente del motor independiente

2026-10-13. Solo `/motor`. Sin cambios en el laboratorio ni en el backend de Claude.

En `/motor/hojas`, **Añadir ejemplos multicomponente** incorpora cuatro hojas completas sin sobrescribir las existentes. Cada hoja conserva sus componentes, volúmenes, corrientes, expresiones, supuestos y datos. Los ejemplos son documentos editables para el ensamblador genérico; el solver no identifica ni trata especialmente sus nombres.

| Hoja | Componentes | Volúmenes / balances | Qué observar |
| --- | --- | --- | --- |
| Mezcla en serie | A, B, C | 2 / 6 | Cada entrada, transferencia y salida aporta una tasa distinta por componente. A 10 s: v1 = [30, 35, 37.5] kg; v2 = [47.5, 52.5, 60] kg. |
| Intercambio selectivo | A, B, C, D | 2 / 8 | Volúmenes de 1 y 2 m³. A cruza hacia v2; B hacia v1. C tiene concentraciones iguales y no cruza; D tiene tasa cero explícita. |
| Conversión y transporte | A, B, C, D | 3 / 12 | Conversión másica A → B → C en todos los volúmenes, con las mismas leyes; D inerte. Las corrientes transportan los cuatro componentes. La masa total se mantiene en 3 kg. |
| Ocho componentes y trazas | A–H | 2 / 16 | Intercambio cerrado, con tasas diferentes. Cantidades iniciales desde 4 kg hasta 1e-8 kg; conservación de cada componente. |

A–H son componentes simbólicos, sin atribuirles fórmulas químicas ni propiedades de thermo. La conversión declara tasas másicas de generación y consumo compatibles; no deduce estequiometría molecular, masas molares ni energía de reacción.

## Ecuaciones y resolución

Cada volumen aporta un estado y un balance por componente. Cada corriente aporta una tasa por componente, compartida por sus dos extremos, con signos opuestos. Los datos están completos, GL estructural = 0 y todas las condiciones iniciales están declaradas.

Las referencias se calculan aparte del ensamblador y del integrador:

- Serie: incrementos lineales dados por entrada − salida de cada especie.
- Intercambio selectivo: `m_A,v1 = 1 + 2 exp(-0.45t)`; `m_B,v1 = 2 - 2 exp(-0.15t)`. El total inicial determina las masas de v2. C y D permanecen constantes.
- Conversión: fracciones reactivas `[exp(-0.1t), 0.1t exp(-0.1t), 1-(1+0.1t)exp(-0.1t)]`. Se multiplican por los pesos de transporte `[exp(-0.2t), 0.2t exp(-0.2t), 1-(1+0.2t)exp(-0.2t)]` de los tres volúmenes. D conserva 2 kg distribuidos con los mismos pesos.
- Ocho componentes: `m_i,v1 = m_i,0 (1+exp(-2k_i t))/2`; `m_i,v2 = m_i,0 - m_i,v1`. `k_i` va de 0.10 a 0.45 s⁻¹. La tolerancia absoluta declarada en esta hoja es 1e-16 kg.

## Resultados

Los tableros nuevos de varias especies muestran todos los estados, agrupados por volumen con hasta cuatro curvas por gráfica. El ejemplo de trazas lleva ocho gráficas: una por componente, comparando los dos volúmenes con una escala propia. Las gráficas se pueden editar, mover, ampliar y quitar. Los tableros que el usuario ya personalizó se conservan.

La tabla incluye todos los estados y los totales. Tabla, ejes y tooltips presentan cantidades pequeñas en notación científica, para no mostrar como cero los valores en trazas. Los límites de ejes usan la escala real de los datos para distinguir una trayectoria pequeña del ruido relativo en una señal constante. Estas decisiones solo afectan a la presentación; el CSV y las series conservan sus números originales.

## Verificación

`npm run test:multicomponente-materia`: **13150 comprobaciones**, con referencias analíticas en cada muestra, conservación local/global, una variable por corriente y componente, GL pendiente, ocho especies reordenadas, renderizado KaTeX, catálogo sin duplicados, tabla, selección completa de gráficas, números y ejes en trazas. También pasa la batería anterior de `test:motor-fundamental`; TypeScript y ESLint verificados.

Revisión en navegador: cuatro hojas añadidas al almacenamiento existente sin reemplazar documentos; caso de ocho componentes resuelto; dieciséis balances y condiciones iniciales visibles; tabla con 1e-4, 1e-6 y 1e-8 kg; ocho gráficas guardadas; reordenación por teclado y escalas de G/H comprobadas. Las otras tres hojas permanecen listas para que el usuario pulse Resolver.

La revisión visual sí pudo completarse en esta entrega. No se comparó contra el backend ni se ampliaron geometrías, dimensiones espaciales, energía o momento. No hay commit ni push.
