# Agua de 10 a 200 °C con presión calculada

15 de octubre de 2026. Hoja creada y resuelta desde la interfaz:

[Agua · 10 a 200 °C · Recipiente rígido](http://localhost:3000/motor/hojas/f8346222-26e0-4658-bfa0-45c6ee2832f2/resultados).

Una copia independiente del ejemplo de condensación; el original y las hojas del usuario se conservan. Modelo genérico existente, sin añadir una rama de escenario ni otro solver.

- Agua pura, CAS 7732-18-5; modelo IAPWS-95.
- Masa total 1 kg; recipiente rígido de 200 L; sin entradas/salidas ni aire.
- Temperatura inicial 10 °C; calor impuesto 2 kW; duración 1287.2729020225838 s.
- Equilibrio líquido–vapor permitido. La presión es resultado del cierre UV, no un dato impuesto.

El volumen específico de 0.2 m³/kg permite acabar como vapor a 200 °C. A 10 °C hay un pequeño vapor de equilibrio: 0.1872 % de la masa. El líquido representa el 99.8128 % de la masa pero solo aproximadamente 1 L del recipiente. No se presenta como un recipiente lleno de líquido ni con aire atmosférico: ese sería otro modelo.

Un recipiente rígido lleno inicialmente de líquido conserva su elevada densidad media al calentarse y no llega al mismo estado de vapor a 200 °C. Aquí la coexistencia comienza desde el estado inicial y sigue la curva de saturación con presión variable; no hay una meseta obligatoria a 100 °C. El líquido desaparece cerca de 178.58 °C y 9.7046 bar absolutos, tras 1267.73 s. Al finalizar hay vapor a 200 °C y 10.28168 bar absolutos.

La duración se eligió a partir de los estados TV inicial/final y de U_final−U_inicial = Q·t. No es una nueva capacidad de parada por temperatura ni un solver inverso: en la petición temporal se especifica esa duración. El calor latente ya está en el modelo de propiedades.

La base física del recipiente es dm/dt=0, dV/dt=0, dU/dt=Q, y el cierre de equilibrio UV obtiene T/P/fases. La EOS utilizada es la formulación [IAPWS-95](https://iapws.org/technical-guidance/release/IAPWS-95).

`respuesta-ui.json` es la exportación original de Solicitud enviada y certificados de muestra; no se modifican sus valores. Desde `frontend`, ejecutar:

```
node qa_calentamiento_2026_10_15/verificar.mjs
```

Comprueba el lector de producción, masa/volumen, presupuesto energético, crecimiento de T/P, transición y estado final. Las referencias TV/saturación usan la misma EOS por otro camino y la primera ley, no otra formulación termodinámica independiente. Reproducir el archivo guardado no vuelve a ejecutar el servicio.

Al preparar la hoja se detectó y corrigió, con autorización del usuario, un `else` mal asociado en la guarda de frontera de `backend/motor_ensamblaje.py`. Ver `../INCIDENCIA_CLAUDE_GUARDA_FRONTERA_2026_10_15.md`. Se conservó el resto del trabajo en curso de Claude. No se flexibilizó ningún lector ni se cambiaron ecuaciones.
