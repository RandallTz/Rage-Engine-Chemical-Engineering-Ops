# Encargo para Claude: termodinámica del motor independiente

**Referencia histórica de H0/H1 y del fundamento inicial.** Las entregas posteriores y pendientes actuales se siguen en el [roadmap principal](../../engine/multiphysics-roadmap.md). No reiniciar hitos entregados ni ejecutar este contrato como un nuevo plan paralelo.

14 de octubre de 2026. Encargo autorizado por el usuario. Claude implementa backend, propiedades, equilibrio y pruebas físicas; Codex implementa contratos y experiencia del motor `/motor`. No modificar el frontend ni sustituir el laboratorio. No hacer commit/push. Respetar el cambio ajeno de `thermodynamics/proveedor.py`; introducir un adaptador aislado y no sobrescribirlo para este trabajo.

Este documento convierte [docs/history/frontend/plan-thermodynamics-engine.md](plan-thermodynamics-engine.md) en trabajo concreto. Implementar por hitos y publicar soporte solo después de validarlo. La autorización comprende el desarrollo progresivo del plan, pero no permite afirmar soporte universal de fases/modelos que no estén formulados y comprobados.

## A. Primer entregable: contrato y evaluación de estado

Crear un módulo de evaluación termodinámica sin efectos sobre cantidades, flujos, topología o configuración del integrador. El frontend no implementará otro flash. La identificación química no debe exigir UNIFAC: separar identidad, correlaciones y modelo constitutivo.

Rutas iniciales, aditivas y propias del motor independiente:

- `GET /motor/termodinamica/capacidades`
- `POST /motor/termodinamica/evaluar`

El contrato de revisión 1 está implementado en `frontend/app/motor/contratoTermodinamica.ts`. Este archivo es la referencia de nombres, tipos y bases. Mantener los nombres camelCase del contrato HTTP (se pueden utilizar aliases Pydantic). Si alguna decisión física exige cambiarlo, documentar exactamente el cambio antes de modificar las respuestas; no devolver otra forma con el mismo número de revisión.

### Solicitud

```json
{
  "revision": 1,
  "solicitudId": "identificador-opaco-del-cliente",
  "propietarioId": "volumen:dominio",
  "componentes": [
    {
      "id": 1,
      "nombre": "Agua",
      "simbolo": "A",
      "identidadQuimica": {"cas": "7732-18-5"}
    }
  ],
  "declaracion": {
    "modelo": {"id": "id-publicado-en-capacidades", "version": "version-publicada"},
    "especificacion": {
      "tipo": "TP",
      "T": {"valor": 25, "unidad": "degC"},
      "P": {"valor": 1, "unidad": "bar"},
      "composicion": {"base": "molar", "fracciones": {"1": 1}}
    },
    "politica": {
      "cantidad": "sin_restriccion",
      "cambioInterno": "permitido",
      "evaluacion": "equilibrio_estable"
    }
  }
}
```

El nombre y símbolo son presentación. Identificar por CAS o `proveedorId` verificable; no deducir identidad ni masa molar de una etiqueta visual. Los IDs internos vuelven intactos en la respuesta. `propietarioId` identifica al dueño del estado, no define un equipo ni activa un escenario.

Las especificaciones son una unión excluyente:

| tipo | Campos | Significado |
| --- | --- | --- |
| `TP` | T, P, composicion | composición global y dos especificaciones intensivas |
| `PH` | P, h, composicion | entalpía específica de mezcla, no entalpía total |
| `UV` | U, V, cantidades | energía y volumen totales; cantidades por componente |
| `UP` | U, P, cantidades | energía total y presión; cantidades por componente |

`composicion` tiene base `molar` o `masica` y una fracción por ID. `cantidades` tiene base `molar` o `masica` y `valores` por ID, cada uno `{valor, unidad}`. Conservar ceros explícitos de especies ausentes. Un campo `valor: null` significa sin declarar, nunca cero. Rechazar datos adicionales que conviertan una especificación en sobreespecificación; no ignorar campos. La UI puede preparar una especificación aún no admitida: el servidor debe diagnosticarla o publicar que no la soporta.

Unidades de entrada de revisión 1:

- T: K, degC, degF, con desplazamiento absoluto correcto.
- P: Pa, kPa, bar, siempre absoluta.
- h: J/kg, kJ/kg.
- U: J, kJ; V: m3, L.
- cantidades másicas: kg, g; molares: mol, kmol.

Valores finitos; T/P/V positivos; cantidades por componente no negativas y total positivo. U/h/s pueden ser negativos por referencia. Una masa molar opcional de `Componente` tiene la estructura actual `{cantidad:{valor,unidad},fuente}`; contrastarla con la identidad/modelo, no usar un valor contradictorio para convertir bases. Nunca hacer una conversión masa/moles universal.

### Capacidades

```text
{revision:1, modelos:[{
 id, version, nombre,
 componentesCAS: string[] | null,
 especificaciones: ("TP"|"PH"|"UV"|"UP")[],
 fases: ("liquido"|"vapor"|"solido"|"fluido")[],
 dominio:{T:[min,max],P:[min,max]},
 referencia:{id,descripcion}, propiedades:string[], dinamica:boolean
}]}
```

Dominios en K/Pa. El rectángulo T/P publicado es una envolvente, no sustituye la comprobación del dominio real, límites de fase y combinaciones del paquete. `componentesCAS:null` no significa todas las sustancias conocidas: validar el paquete y parámetros necesarios para cada petición. Una capacidad debe corresponder a una versión fija y una referencia identificada. `dinamica:false` mientras solo exista evaluación puntual. La ejecución dinámica necesita un contrato propio y un ensamblador independiente; no activar esa bandera por tener un flash estático.

### Respuesta

```text
{
 revision:1, solicitudId: echo,
 modelo:{id,version},
 estado:"evaluado"|"incompleto"|"invalido"|"no_soportado"|"no_convergente",
 evaluacion: EvaluacionEstado | null,
 diagnosticos:[{codigo,mensaje,ruta,componenteIds,propietarioId,alternativas?}]
}
```

`evaluacion` incluye:

- T [K], P [Pa], `composicionMolar` global por ID.
- `componentes`: ID, CAS cuando exista, `masaMolarKgMol` positiva y `fuente` del valor realmente usado.
- `mezcla`: u [J/kg], h [J/kg], v [m3/kg], s [J/(kg K)]. Cp/Cv opcionales en J/(kg K), solo cuando tengan definición pertinente. No publicar una capacidad monofásica ponderada como capacidad genérica de una mezcla bifásica.
- `fases`: ID estable, tipo, `regimen:ordinario|supercritico`, `fraccionMolar`, `fraccionMasica`, `fraccionVolumen`, `composicionMolar` y propiedades u/h/v/s de cada fase en las mismas unidades SI. Omitir fases de cantidad cero; no asignarles composiciones ficticias. Dos líquidos necesitan IDs distintos. Un estado supercrítico tiene una fase de tipo `fluido`, sin calidad de vapor artificial.
- El régimen supercrítico se identifica en la fase fluida; la coexistencia con otras familias, por ejemplo sólidos, necesita modelos propios y soporte declarado. No convertir su fracción de fase en una calidad líquido/vapor.
- `referencia:{id,descripcion}` común y trazable.
- `estabilidad:{estado:estable|metastable|no_evaluada,alcance:[tipos],metodo}`. La primera API entrega como `evaluado` solamente estados estables y certificados dentro del alcance real del paquete.
- `verificaciones:[{id,estado:cumple|no_cumple|no_evaluable,residuo:number|null,tolerancia:number|null,motivo?}]`. Residuos absolutos/escalados no negativos según la definición documentada de cada ID; `cumple` exige respetar la tolerancia cuando se publica un residuo. Nunca publicar cero para algo que no se evaluó.

IDs obligatorios de verificación: `estabilidad`; `equilibrio` cuando hay varias fases. Añadir reconstrucción material, energía/volumen cuando estén especificados, dominio e identidades constitutivas. Documentar escala/unidades de cada residuo. Una desigualdad de estabilidad necesita su criterio, alcance de búsqueda y tolerancia; no afirmar mínimo global por haber encontrado una raíz.

Todo rechazo usa `evaluacion:null` y al menos un diagnóstico. No devolver el último estado convergido. Errores físicos/preparación conocidos deben salir con diagnóstico del contrato; no solo con un 422 genérico. El cliente revalida las respuestas, pero no sustituye la auditoría de la EOS ni la estabilidad.

Política de fase:

- `cantidad:monofasico`: evaluar estabilidad frente a las fases candidatas del paquete y comprobar que el estado estable tiene una fase. No forzar líquido/vapor para ocultar una segunda fase estable.
- `tiposPermitidos` opcional: restricción del usuario. Un estado estable incompatible debe diagnosticarse; no buscar solo la rama permitida y llamarla estable globalmente.
- `cambioInterno:prohibido`: restricción temporal. En una consulta puntual sin trayectoria puede registrarse como no evaluable; no implica monofásico ni prueba ausencia de transición futura. En ejecución dinámica se compara con el régimen inicial y eventos.
- La primera entrega no ofrece ramas metastables forzadas. Si se añaden después, deberán tener modo y certificación distintos.

## B. Secuencia física obligatoria

### H0: fundamento y auditoría del proveedor

Documentar la relación fundamental dU=T dS−P dV+sum(mu_i dn_i), potenciales H/G/A, variables independientes y alcance de equilibrio macroscópico sin capilaridad/electricidad. Separar EOS, propiedades de fase, correlaciones, actividad y estabilidad. Enumerar qué suministra realmente cada adaptador y qué derivadas faltan. Fijar versiones, referencias y procedencia; aislar instancias mutables del proveedor por evaluación.

No reinterpretar `c_u` manual como Cp por comodidad. No extrapolar fuera del dominio ni asumir parámetros binarios nulos. No modificar el proveedor actual para aceptar automáticamente todo: introducir el adaptador nuevo por separado.

### H1: estado puro monofásico real

Primera sustancia: agua identificada inequívocamente. Auditar IAPWS-95 y el adaptador disponible antes de seleccionarlo. Entregar T/P → u/h/v/s y derivadas necesarias dentro de un dominio inicialmente acotado, con comprobación de estado estable y fase. La identificación no requiere grupos UNIFAC.

Un punto T/P en saturación de una sustancia pura no determina la fracción de fases: `incompleto`, con alternativas PH/UV/UP cuando se admitan. No elegir 0, 0.5 o 1 por omisión. Datos del sólido o región crítica fuera del alcance deben rechazarse con motivo, sin reclasificarlos como líquido. Comparar valores oficiales y conservar h=u+Pv.

### H2: un volumen monofásico y geometría compatible

Recipiente rígido: cantidades y U, V fijo → T/P. Frontera a presión prescrita: cantidades y U o H equivalente → T/V y trabajo de frontera. Una corriente usa estado de transporte independiente, inicialmente TP y posteriormente PH.

No imponer densidad constante del modelo manual al nuevo modelo variable. Si V=V(U,n,P), incluir su derivada completa en el trabajo P dV/dt. Se requiere matriz de coeficientes, eliminación justificada o DAE; no reutilizar P dm/dt/rho fuera de su hipótesis. Con presión uniforme, H=U+PV puede ser otra coordenada: dH/dt=J_E+V dP/dt. Probar equivalencia con la primera ley y datos de frontera.

El tanque con líquido y espacio de vapor es un sistema con volumen total y fases. No confundir volumen ocupado por líquido con geometría fija total. P calculada por EOS bajo equilibrio mecánico no equivale a un balance de momento distribuido.

### H3: equilibrio líquido/vapor puro estático

Implementar saturación y especificaciones inversas justificadas (PH, UV, UP), reconstrucción de cantidades/energía/volumen y estabilidad. Fracciones molares/másicas/volumétricas claramente distintas. En un componente las dos primeras coinciden, la volumétrica no. Respetar referencias comunes entre líquido/vapor.

### H4: cambio de fase temporal de un volumen

Conservar cantidades totales y energía; recuperar algebraicamente T/P/fases por las restricciones del volumen. Resolver equilibrio en cada estado candidato necesario y certificar pasos aceptados. Aparición/desaparición de fase con conjunto activo o complementariedad documentada; no corregir cantidades para forzar fracciones admisibles.

El calor latente está en las propiedades de fase; no añadirlo de nuevo como fuente. Un fallo de flash de una etapa no permite mantener propiedades de la etapa anterior. Localizar eventos, inicialización compatible, escalado por magnitud y tolerancias térmicas/materiales/algebraicas separadas. Derivadas monofásicas no se extrapolan a la región bifásica.

### H5: mezclas monofásicas

Conservación por componente, composición variable y energía de mezcla. Añadir primero una familia ideal declarada para referencias; después una familia real apropiada. Respetar términos composicionales y relaciones parciales. No inventar entalpía/densidad de mezcla a partir de una media de puros cuando el modelo necesita exceso o propiedades parciales.

Para modelos de actividad, auditar G^E, H^E=G^E−T dG^E/dT, derivadas y volúmenes requeridos. Para EOS, auditar propiedades residuales y fugacidades derivadas consistentemente. Un parámetro de mezcla faltante genera pendiente o no soportado.

### H6: equilibrio de mezclas

Implementar flashes T/P y luego las especificaciones inversas verificadas. Igualdad de fugacidades, reconstrucción z_i=sum(beta_alpha x_i_alpha), energía, volumen y estabilidad frente a todas las fases pertinentes. Probar burbuja/rocío, trazas y límites. Un algoritmo VLE no debe entregar una raíz arbitraria para una región con separación líquido/líquido. Habilitar LLE/VLLE solo cuando los modelos y búsqueda estén verificados.

### H7: acoplamiento de volúmenes

Un solo ensamblaje genérico, sin ramas por nombre/ID de ejemplo. Corrientes compartidas con los mismos flujos de componentes y energía en ambos lados. La extracción especifica fase o arrastre; no usar composición global para una salida líquida de un sistema bifásico. Compartir referencias y modelos compatibles en la conexión.

Transferencia selectiva/difusiva requiere propiedades parciales y convención de energía/trabajo compatible; no heredar la fórmula convectiva de h de mezcla sin derivarla. Si hay balances por fase fuera del equilibrio, las transferencias internas se cancelan globalmente.

### H8: extensión auditada

Sólidos, reacción, electrolitos, desequilibrio, capilaridad/nucleación y transporte espacial requieren formulación propia. Entregar auditoría de viabilidad/modelos/datos para cada familia y soporte solo con verificación específica. Reacción: estequiometría, referencias químicas/datos de formación y potenciales consistentes; no contar calor de reacción dos veces. Electrolitos: electroneutralidad, especiación y estados estándar apropiados. No incluir capacidades por analogía con un fluido puro.

## C. Ejecución y comunicación con frontend

La evaluación estática tiene su pantalla de Estado en `/motor/hojas/[id]/estado`; no modifica cantidades ni simula automáticamente. Codex mantiene el modelo manual y bloqueará que una consulta se use como cierre dinámico. La nueva API de propiedades no necesita el montaje de `/laboratorio/estudios` ni sus presets.

Antes de H2/H4, entregar contrato adicional de `validar`/`resolver` del ensamblaje independiente: formulaciones estructuradas, relaciones de estado, restricciones mecánicas, puertos, catálogos de variables y datos/pendientes. Debe conservar el desglose matemático del usuario. No enviar miles de consultas HTTP desde etapas RK/Newton: el coordinador numérico debe invocar el proveedor localmente durante la resolución. Definir qué estados son diferenciales, cuáles algebraicos y cómo se inicializan.

Recuento: rango/estructura del ensamblaje efectivo, restricciones realmente activas, datos/iniciales, redundancias y conflictos. La regla de fases es una comprobación termodinámica, no la resta de todos los grados de libertad del proceso. Parámetros constitutivos no pasan a incógnitas sin relaciones que los identifiquen. Publicar recuento con alcance/tolerancia y rutas por variable, antes de resolver.

Supuestos de materia/energía de un propietario deben resolverse conjuntamente, con procedencia y diagnóstico de contradicciones. No aplicar OR entre declaraciones discrepantes. Una fase asumida no tiene la misma evidencia que una fase calculada. Una verificación puntual no certifica toda la trayectoria.

Conservar módulos de materia/energía manual existentes y sus referencias. La selección de modelo es explícita; sin la capa nueva todo sigue funcionando. Modelo, parámetros, referencias, hipótesis y unidades normalizadas participan en identidad física. Una respuesta calculada no forma parte de la especificación y no se reutiliza después de cambiar datos/modelo/componentes.

## D. Pruebas de aceptación

1. H1: puntos oficiales monofásicos, unidades de T/P, identidad h−u−Pv, derivadas y dominio. Valores publicados y evaluación independiente; dos wrappers de la misma EOS no son dos referencias físicas distintas.
2. Sustancia pura en saturación TP indeterminada; rechazo de fase restringida incompatible y región no soportada. No fabricar fracciones.
3. Transformación TP → PH y estados → UV/UP → mismo estado, incluyendo reconstrucción de composición y referencias.
4. Líquido/vapor puros y trazas de fases, energía/volumen reconstruidos. En la frontera de aparición no generar composiciones de una fase ausente.
5. Recipiente rígido con P variable, calentamiento a P constante, llenado/vaciado con densidad variable, condensación; contra referencias físicas independientes y primera ley completa.
6. Mezcla ideal y no ideal; componentes reordenados, trazas, calor de mezcla, datos binarios, burbuja/rocío y estabilidad. LLE/VLLE solo si se habilitan.
7. Corrientes compartidas, extracción por fase, inversión de dirección y referencias equivalentes: conservación global material/energética.
8. Segunda ley en casos donde estén dados todos los intercambios/temperaturas de frontera. No certificar producción global de entropía sin esos datos.
9. Estado inválido en t=0, fuera de dominio durante trayectoria, etapa no convergente, modelo/datos incompletos, unidades incompatibles, parámetros contradictorios, capacidad no publicada. Diagnósticos con rutas y propietario.
10. Refinamiento temporal y tolerancias de flash, residuos/derivadas escalados, estabilidad y continuidad al cambiar fases. No recortar ni renormalizar soluciones para aprobar las pruebas.
11. API Python → JSON → TypeScript y regreso sin cambios semánticos; null ausente, cero explícito, IDs estables, revisiones/modelos y solicitudes coincidentes.
12. Regresiones completas anteriores de backend y `npm run test:motor-fundamental`, sin atribuir al backend pruebas de propiedades que solo usan datos sintéticos del protocolo frontend.

Generar ejemplos de peticiones/respuestas ejecutando endpoints reales. Publicar dominios, tolerancias, errores medidos, propiedades pendientes y modelos usados. No generar resultados numéricos de muestra escritos a mano como evidencia de física.

## E. Entrega y seguimiento

Cada hito necesita documentación de decisiones físicas, esquema exacto, referencias y evidencia. H0/H1 primero; no saltar a H4 para producir gráficas. La primera entrega permite evaluar un estado real de agua dentro de un dominio monofásico verificado y mantiene diagnósticos de los demás regímenes. Las entregas posteriores amplían capacidades sin cambiar el significado de campos antiguos.

Referencias oficiales a consultar para la auditoría: [IAPWS-95](https://iapws.org/technical-guidance/release/IAPWS-95), [thermo.flash](https://thermo.readthedocs.io/thermo.flash.html), [thermo.phases](https://thermo.readthedocs.io/thermo.phases.html) y [thermo.activity](https://thermo.readthedocs.io/thermo.activity.html). La biblioteca ofrece mecanismos; su presencia no demuestra que el adaptador o el ensamblaje cumplan este encargo.

## Seguimiento tras H0/H1

H0/H1 entregados y recibidos el 14 de octubre de 2026. El frontend acepta las respuestas reales y añadió el contraste independiente de masa molar IAPWS-95, sin modificar el backend. La consulta fue comprobada visualmente con el servicio.

La prioridad física siguiente queda concretada en [docs/history/frontend/contract-claude-thermodynamics-h3.md](contract-claude-thermodynamics-h3.md): saturación y especificaciones inversas estáticas, antes de conectar un solver dinámico. H2/H4 mantienen el requisito de acordar el contrato de ensamblaje independiente. No interpretar H1 como soporte de flashes bifásicos ni de dinámica.

El borrador concreto de ese ensamblaje ya está disponible en [docs/history/frontend/contract-claude-assembly-dynamic-engine.md](contract-claude-assembly-dynamic-engine.md), con tipos y adaptador frontend. Después de recibir H3, revisar/confirmar E0 antes de implementar H2/H4; la preparación no activa un solver ni cambia la API puntual.

**Actualización de alcance por el usuario:** el archivo de ensamblaje enlazado es ahora el único encargo activo y reúne E0–E3 en una sola entrega final. Formalizar E0 sigue siendo el primer paso técnico, pero ya no es un encargo separado ni un motivo para detener el trabajo antes de H2/H4. Usar el documento consolidado para conocer el alcance pendiente.
