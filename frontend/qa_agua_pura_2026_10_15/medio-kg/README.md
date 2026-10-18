# Revisión del escenario actualizado: 0.5 kg en 3 L

Se leyó la solicitud/respuesta real de la hoja, sin cambiar sus datos: 0.5 kg de agua total, 3 L rígidos, 10 °C iniciales, **10 kW netos**, sin corrientes ni válvula. La masa de agua total incluye la pequeña cantidad de vapor de equilibrio inicial (aproximadamente 23.5 mg), no aire. Quedan inicialmente aproximadamente 2.5 L de espacio de vapor a presión baja.

`python frontend/qa_agua_pura_2026_10_15/medio-kg/verificar.py`: **125 comprobaciones correctas**. Se conservaron masa, volumen, energía y normalización/reconstrucción por fases. No se modificó el backend.

| t [s] | T [°C] | P absoluta [bar] | Fracción másica vapor |
| --- | --- | --- | --- |
| 0 | 10 | 0.012282 | 0.00004703245 |
| 18 | 94.7403 | 0.83803 | 0.00248361 |
| 45 | 204.3214 | 17.0050 | 0.04188349 |
| 81 | 305.7257 | 93.0245 | 0.25028645 |
| 113.049225 | 365.0595 | 198.3549 | 1 |
| 114.511611 | 372.3594 | 209.6080 | 1 |

La presión aumenta por calentamiento de una cantidad fija de agua en volumen fijo. Menos masa con el mismo aporte no implica menos presión a un tiempo dado: Q/m pasa de 5 a **20 kJ/(kg s)** respecto al ejemplo de 2 kg. La energía entregada hasta detenerse es 1.145116 MJ. Se evapora completamente a los 113.049 s; después continúa como vapor denso. No aplicar la ley de gases ideales como cierre cuantitativo de este vapor de alta densidad.

Contraste con [IAPWS-IF97 R7-97(2012)](https://iapws.org/technical-guidance/release/IF97-Rev), formulación distinta de la IAPWS-95 usada por el motor:

- Presión de saturación en las 13 muestras con dos fases: diferencia relativa máxima 0.01702 %.
- Presión final calculada con la ecuación de Helmholtz de la región 3 a T y rho = 166.666667 kg/m³: **209.601799 bar**, frente a 209.608000 bar del motor (diferencia relativa 0.002958 %).
- Diferencia de energía interna específica final: 182.64 J/kg.
- Error máximo U−U0−Qt: 2.92e-11 J.

Se detiene por la banda crítica excluida del paquete a los 114.511611 s; no completa 15 minutos. Esta detención **no** es una predicción de apertura o rotura del recipiente. No hay aire, pérdidas, capacidad de pared, resistencia de tapa ni relación de descarga. La presión resulta coherente para este recipiente ideal, no valida una olla doméstica real ni su seguridad. IF97 e IAPWS-95 comparten datos físicos de referencia; el contraste no son mediciones nuevas.

Archivos: `respuesta-ui.json` conserva la solicitud/respuesta original, `verificar.py` reproduce la auditoría y `evidencias.json` registra los máximos medidos.
