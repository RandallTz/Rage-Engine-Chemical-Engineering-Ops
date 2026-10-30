# Escenarios de agua: integración y validación

11 de octubre de 2026. Cinco ejemplos conectados al servicio real, sin solver ni curvas precalculadas en el frontend.

## Abrir y usar

En una mesa: **Experimentar → Ajustes → Montajes de ejemplo**. Elegir una tarjeta carga su montaje y sus datos explícitos de ejemplo; reemplaza el montaje de la mesa actual. Volver a los valores, modificar los datos si se desea y pulsar Resolver cuando el recuento lo permita. Los demás ejemplos del servidor quedan en “Otros montajes del motor”. La disponibilidad de las tarjetas depende de las combinaciones temporales anunciadas por el servicio.

| Ejemplo | Física actual | Referencia independiente |
|---|---|---|
| Llenar un tanque | Entrada 10, salida 9 mol/s, cantidad inicial 100 mol, 10 min | n=100+t; final 700 mol |
| Vaciar un tanque | Entrada 1, salida 2 mol/s, inicial 100 mol | n=100−t; evento a 100 s, resultado parcial |
| Entrar agua más caliente | Cantidad constante 5500 mol, entrada 10 mol/s a 330 K, inicial 300 K | T=330+(300−330)exp(−10t/5500) |
| Entrar agua más fría | Mismo modelo, entrada a 280 K, inicial 320 K | T=280+(320−280)exp(−10t/5500) |
| Intercambiar calor entre dos tanques | Dos volúmenes cerrados, 350/300 K, G=100 W/K | T1/2=325±25exp(−t/τ), τ=5500×75.3/(2×100) s |

Llenar/vaciar muestran cantidad de agua; no prometen un nivel geométrico calculado sin densidad y área. Los ejemplos térmicos usan líquido ideal incompresible, Cp manual constante de 75.3 J/(mol·K), densidad molar declarada de 55000 mol/m³ y dominio explícito. Son ejemplos del modelo, no sustitutos de propiedades rigurosas variables con T. En calentamiento/enfriamiento, la energía entra con la corriente, sin fuente exterior Q. En el último ejemplo no hay circulación de agua ni almacenamiento independiente de una pared.

## Correspondencia entre vistas

Los componentes se muestran como Agua conservando el id `water`. Ecuaciones → Detallada lista las variables del catálogo vigente y sus datos declarados; pulsar una variable editable abre Experimentar y enfoca su campo. El balance general conserva Dato/Calcular, valores y unidades. Un resultado vigente sigue disponible al volver a sus valores. En compacta se mantiene la lectura de ecuaciones sin agregar otra lista visible.

Las referencias de §23.7 localizan propiedades ausentes por campo y componente. Falta abre Propiedades y enfoca la entrada correspondiente. No se adivinan datos ni se resuelve automáticamente al navegar.

Al cargar otro montaje se retira la configuración de gráficas del anterior para evitar ejes de variables que ya no existen. Los ejemplos térmicos de Agua abren por defecto las temperaturas de sus volúmenes; en el intercambio se ven ambas curvas juntas. La escala de temperatura se ajusta al intervalo observado y conserva unidad y marcas visibles. La edición libre de gráficas sigue disponible.

## Comprobaciones ejecutadas

- `npm run test:escenarios-tanque`: envía las cinco solicitudes a `/validar` y `/resolver`, comprueba el contrato, el recuento coincidente y las referencias anteriores en todos los puntos de la trayectoria. También verifica conservación y cancelación de la interfaz térmica, y la referencia exacta del Cp ausente en el caso de benzene. Las referencias analíticas solo están en la prueba.
- `npm run test:recuento-servicio`: estados, números, cotas, referencias y 80 respuestas contra el servicio activo.
- `npm test`, TypeScript y ESLint de los archivos modificados.
- Navegador: mesa independiente “Escenarios de agua · verificación”; carga y resolución del llenado; enlace de F desde Ecuaciones a su casilla; propiedad Cp ausente localizada al pulsar Falta; restauración y resolución térmica; dos curvas de temperatura del intercambio visibles. Los datos de otras mesas permanecen intactos.

La batería de 33 suites del backend es la reportada por Claude; no se atribuye a estas comprobaciones de integración.

## Siguiente física, en entregas separadas

El llenado/vaciado **con energía**, el serpentín con circuito propio, la pared sólida con estado independiente y la condensación no se habilitan como si fueran variantes de estos cinco ejemplos. Su modelo, esquema y criterios de aceptación están en [SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md](SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md). La fuente de verdad para habilitarlos será cada combinación verificada en capacidades.
