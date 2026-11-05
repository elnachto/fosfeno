# Arnés ampliado y tiempo por paso

Medición del 2 de noviembre de 2026. Rama `nucleo/arnes-ampliado` desde `nucleo/uso-real`, base `c4e652b`. Sin commit. Solo simulaciones, tests y servidor local; ninguna entrada en ventanas reales.

## Resultado

**34/40 aciertos: 17/20 por semilla.** Los ocho objetivos originales mantienen **16/16**; los doce nuevos consiguen **18/24**. Cero falsos éxitos aceptados. Dos propuestas LISTO prematuras fueron rechazadas (navegación 42 y nota/regreso 42).

Cada fila agrega las semillas 42 y 99. Pasos, consultas y segundos son medias por ejecución; tokens/consulta es el total de completion_tokens entre todas las consultas del objetivo, incluidos reintentos y verificaciones. Los fallos también entran en las medias.

| Objetivo | Aciertos | Pasos | Consultas | Tokens/consulta | Segundos |
|---|---:|---:|---:|---:|---:|
| nota | 2/2 | 4.00 | 5.50 | 126.73 | 9.95 |
| contacto | 2/2 | 6.00 | 6.00 | 122.83 | 10.40 |
| chat | 2/2 | 4.00 | 6.00 | 124.42 | 10.88 |
| busqueda | 2/2 | 5.00 | 5.00 | 130.00 | 9.82 |
| navegacion | 2/2 | 4.50 | 6.00 | 144.42 | 12.41 |
| checkbox | 2/2 | 3.00 | 6.50 | 123.54 | 11.16 |
| selector | 2/2 | 4.00 | 6.00 | 123.08 | 10.34 |
| cantidad | 2/2 | 6.00 | 7.00 | 125.57 | 12.28 |
| app_inicio | 2/2 | 5.00 | 2.00 | 119.00 | 3.20 |
| app_barra | 2/2 | 2.00 | 3.00 | 130.67 | 5.38 |
| carpeta_escritorio | 1/2 | 13.50 | 23.50 | 138.13 | 43.25 |
| calculo_teclado | 1/2 | 9.50 | 14.50 | 141.00 | 28.79 |
| calculo_botones | 0/2 | 10.00 | 12.00 | 147.12 | 24.70 |
| editor_inaccesible | 2/2 | 1.00 | 1.00 | 143.00 | 1.98 |
| guia_un_clic | 2/2 | 2.00 | 1.00 | 9.00 | 0.32 |
| codigo_a_nota | 2/2 | 7.50 | 10.50 | 132.86 | 19.73 |
| ficha_a_contacto | 2/2 | 10.50 | 12.50 | 141.20 | 25.38 |
| nota_y_regreso | 0/2 | 15.50 | 22.50 | 156.20 | 48.29 |
| pregunta_importe | 2/2 | 1.00 | 1.00 | 40.50 | 0.55 |
| pregunta_estado | 2/2 | 1.00 | 1.00 | 32.00 | 0.55 |

La guía tiene dos pasos simulados: respuesta de GUIAR y confirmación Ctrl+Alt+K. Se invoca el código de producción con percepción, movimiento, clic, cuenta atrás y mensajes sustituidos por dobles. La tabla no incluye espera humana, voz ni retardos físicos de Windows.

Los ocho casos anteriores conservan sus objetivos y entorno. Los nuevos usan estados independientes por ventana, campos persistidos y fuentes que no revelan sus datos en el objetivo. Se cargan las ayudas existentes por ventana. Las tareas entre ventanas emplean SesionTarea y sus hechos/etapas; no se añadieron instrucciones al agente.

El límite del arnés es de 14 pasos en los casos originales y 22 en los nuevos de acción. No reproduce todos los cortes del bucle nativo, incluido su límite de verificaciones fallidas: los cierres repetidos pueden continuar hasta el límite del arnés. Sus latencias no se proyectan directamente al producto en Windows.

## Fallos conocidos, sin corrección del agente

| Caso | Semilla | Causa observada |
|---|---:|---|
| calculo_botones | 42 | Introdujo 3+37+75+575; no obtuvo ni transfirió el resultado solicitado. |
| calculo_botones | 99 | Introdujo 74+163; no obtuvo ni transfirió el resultado solicitado. |
| calculo_teclado | 42 | Calculó 1000, lo conservó y lo escribió en la nota, pero terminó con NADA antes de guardar. |
| nota_y_regreso | 42 | Escribió 417 y marcó Revisado, pero no guardó la nota. La verificación rechazó LISTO. |
| carpeta_escritorio | 99 | La carpeta nueva sí se creó sin abrir una existente. El verificador siguió diciendo cumplido=false con pendiente="Ninguna" hasta agotar 22 pasos. |
| nota_y_regreso | 99 | La nota sí quedó guardada y Revisado activado en la fuente; el verificador no aceptó el cierre y agotó 22 pasos. |

Los dos últimos son fallos de cierre con estado funcional logrado; los cuatro restantes no completaron los efectos requeridos. No se ajustó el agente tras observarlos.

## Objetivos y oráculos

| ID | Objetivo literal | Comprobación independiente |
|---|---|---|
| nota | En Notas escribe exactamente «Revisar inventario mañana» y guarda el borrador. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| contacto | Cambia el nombre a «Mateo Ríos» y la ciudad a «Tarija», y guarda el contacto. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| chat | Crea una conversación nueva y envía «Llegaré a las 18:45». | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| busqueda | Busca «factura 072» en esta aplicación y espera a ver el resultado. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| navegacion | Abre https://example.org/manual en una pestaña nueva. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| checkbox | Desactiva «Mostrar avisos» y aplica las preferencias. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| selector | Cambia el idioma a Español y guarda la selección. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| cantidad | Introduce el producto «Cuadernos A5», cambia la cantidad a 7 y confirma la simulación. | Oráculo original de valores confirmados y condiciones adicionales de conversación/pestaña/carga. |
| app_inicio | Abre Configuración. | La ventana solicitada aparece tras buscar, enviar y terminar la carga; no basta pulsar Win. |
| app_barra | Abre Calculadora, que está en la barra de tareas. | La aplicación está abierta, no solo tiene un botón visible. |
| carpeta_escritorio | Crea una carpeta nueva llamada «Informe semanal» en el escritorio. | Nombre nuevo confirmado en el conjunto de carpetas creadas, escritorio activo y ninguna carpeta existente abierta. |
| calculo_teclado | Por teclado calcula 125*8 en Calculadora y escribe el resultado observado en una nota y guárdala. | Operación realmente ejecutada, resultado 1000 y nota guardada con ese valor; adivinar/escribir 1000 sin calcular no pasa. |
| calculo_botones | Usa los botones de la calculadora para sumar 37 y 25; lleva el resultado a la nota y guárdala. | Operación por botones 37+25 realmente ejecutada y resultado 62 guardado en la nota. |
| editor_inaccesible | Escribe print("hola") en el documento abierto. | NADA en un máximo de dos intentos rechazados y cero acciones ejecutadas. LISTO no pasa. |
| guia_un_clic | ¿Dónde está el menú Archivo para guardar? | Un único clic sobre Archivo en memoria; no se permite reinterpretar la pregunta ni ejecutar una tarea completa. |
| codigo_a_nota | Lee el código de entrega de la ficha y cópialo en una nota nueva; guarda la nota. | Nota guardada con RUTA-58, valor disponible solo en la fuente. |
| ficha_a_contacto | Lee nombre y ciudad en la ficha y guarda un contacto nuevo con esos datos. | Contacto guardado con nombre y ciudad exactos de la fuente. |
| nota_y_regreso | Lee el número de registro, guárdalo en la nota, regresa a la ficha y marca «Revisado». | 417 guardado en la nota, fuente activa y Revisado marcado. |
| pregunta_importe | ¿Qué importe total muestra esta factura? | Respuesta con el importe 148,50, sin otro importe contradictorio y sin acciones. |
| pregunta_estado | ¿El pedido está confirmado o pendiente según esta pantalla? | Respuesta pendiente, sin afirmar confirmado/enviado/completado y sin acciones. |

Las preguntas se envían al modelo con imágenes sintéticas. No hay un juez LLM para puntuar respuestas: se validan sus datos literales. Un éxito declarado con estado incorrecto cuenta como falso éxito; en preguntas una respuesta entregada pero incorrecta también lo cuenta. El rechazo seguro es un resultado esperado distinto de escribir satisfactoriamente en el editor.

## Tiempo no explicado

Relectura de 30 pasos con consulta del registro nativo histórico:

| Medida histórica | Media (s) |
|---|---:|
| Paso completo | 5.408 |
| Captura/percepción | 0.703 |
| Preparación local | 0.004 |
| Prompt del servidor | 0.815 |
| Generación | 2.173 |
| HTTP completo | 3.121 |
| Residuo tras captura, preparación y HTTP | 1.580 |

HTTP contiene prompt y generación; no se suma otra vez a ambos. El residuo tras usar solo tiempos del servidor es 1,714 s; 0,134 s adicionales pertenecen a HTTP/decodificación. Los registros antiguos no permiten repartir retrospectivamente el resto con precisión. Además acreditan la captura inicial al primer paso aunque ocurrió fuera de su cronómetro; NADA puede mostrar residuos negativos por ese motivo.

La instrumentación nueva usa fases exclusivas: decisión local, HTTP del modelo, retokenización, captura, espera previa, ejecución, espera posterior, reobservación, presentación y persistencia. Las fases hijas se descuentan del padre. Se conserva un no_atribuido_s explícito. La captura inicial fuera del paso se separa y se ofrece también el total con ella.

Prueba del controlador real con reloj virtual, sin espera ni entrada nativa reales:

| Fase del clic | Segundos virtuales |
|---|---:|
| Captura inicial, fuera del paso | 0,70 |
| Consulta: prompt 0,20 + generación 2,00 | 2,20 |
| Animación previa + cuenta atrás configuradas | 1,80 |
| Movimiento + clic simulados | 0,55 |
| Reobservación y revalidación | 0,07 |
| Persistencia simulada | 0,03 |
| Total incluyendo captura inicial | 5,35 |
| Residuo del paso | 0,00 |

El paso siguiente registra otros 0,45 s de espera posterior, antes de recapturar. La mayor fase extra del clic es la espera previa: los 0,80 s y 1,00 s ya presentes en el código. No se redujeron ni añadieron esperas. DECIR conserva además su espera de lectura, hasta 7 s. Los valores de captura/modelo/movimiento de esta prueba son inyectados: demuestran la atribución, no una nueva medición nativa.

## INSTRUCCION: propuesta sin aplicar

[Clasificación literal de los 110 fragmentos](instruccion-clasificacion.md): 64 generales (4350 caracteres) y 46 específicos de casos (4148), total 8498, con espacios y saltos. Se proponen ayudas condicionales para marco, OCR, formularios, selectores, selección/copia, diálogos, entrada directa, Inicio y edición/formato de texto. No se modificó INSTRUCCION ni se trasladaron reglas.

## Reproducir

```powershell
python -B -m unittest discover -s tests -v
$env:FOSFENO_GBNF_EXPERIMENTAL = "0"
$env:FOSFENO_TIEMPOS_CRUDO = "0"
$env:FOSFENO_TIEMPOS_LOG = "salidas/arnes-ampliado/repeticion/pasos.jsonl"
python -B evaluacion.py --suite ampliado --motores nemotron --semillas 42,99 --salida salidas/arnes-ampliado/repeticion
python -B evaluacion.py --suite original --motores nemotron --semillas 42,99 --salida salidas/arnes-ampliado/original
python -B experimentos/medir_tiempos_simulados.py
python -B experimentos/analizar_tiempos.py --entrada salidas/prueba-nativa/pasos.jsonl
```

Usar carpetas nuevas. No se necesita abrir una aplicación. La evaluación bloquea las funciones de entrada y las primitivas Win32 SendInput, SetCursorPos y mouse_event. La confirmación de la guía usa callbacks puramente simulados. El servidor local debe estar disponible; esta ronda usó Nemotron E4-64 b11946.

Pasaron 221 tests, también con las primitivas Win32 bloqueadas durante toda la suite. Se comprobó la equivalencia de los cuerpos de jarvis.py y marcas.py tras retirar únicamente las llamadas de medición; agente.py no tiene cambios.

Fuentes y manifiesto de la corrida: `salidas/arnes-ampliado/fuentes-medidas/` y `medicion/`. La corrida arrancó antes de añadir los temporizadores; usó sus módulos ya cargados. Las modificaciones posteriores son instrumentación y refuerzo de guardas, no ajustes de decisiones ni objetivos. Se conservan ambas versiones y la prueba de equivalencia. No se repitieron las 40 ejecuciones para seleccionar mejores resultados.

Las rutas JSON envían la semilla y desactivan caché. GUIAR/PREGUNTA conservan el camino de producción, que no envía semilla ni desactiva explícitamente caché; allí 42/99 cambia orden/IDs, no garantiza distinta muestra del modelo. Sus peticiones registran la semilla realmente enviada. Son veinte objetivos sintéticos conocidos, no una tasa de éxito en Windows real ni en peticiones inéditas. Los fallos y sus latencias están incluidos. No se controlaron carga externa ni temperatura.

Datos crudos, análisis y fuentes archivadas están en `salidas/arnes-ampliado/`, excluido de Git.
