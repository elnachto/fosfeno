# Tareas encadenadas, memoria breve y demostraciones

Esta ampliación experimental conserva los datos que una tarea necesita al cambiar
de aplicación, verifica subtareas y guarda un resultado final. No modifica los
pesos del modelo. Se mantienen separados el objetivo del usuario, los datos
observados y las referencias aprendidas.

## Ejemplos

- «Lee la cantidad de esta nota, luego escríbela en el formulario y guárdalo».
- «Lee las instrucciones de esta nota y ejecútalas en el formulario de prueba».
- «Mírame cómo crear un contacto llamado Elena»; después de guardar la
  demostración: «Crea un contacto llamado Lucas».

La demostración queda como referencia de la aplicación. Los valores del pedido
actual guían la nueva tarea; el modelo debe preguntar si falta uno necesario.
No hay un catálogo de campos ni procedimientos de aplicaciones precargado.

## Memoria y estados

`tareas.SesionTarea` conserva hasta seis etapas. Cada una pasa de pendiente a
activa y solo después de una verificación a comprobada. El pedido original se
mantiene para la verificación global. Los hechos de una nota pueden sobrevivir
al cambio de ventana, pero no prueban que se escribieron o guardaron en otra app.

La memoria de trabajo admite hasta ocho datos de 500 caracteres, con origen y
etapa. Su representación serializada tiene un límite de 6000 caracteres; si se
llena, se pide dividir el trabajo en vez de olvidar silenciosamente datos
anteriores. No se recuperan automáticamente hechos de tareas anteriores.

El planificador tiene un presupuesto de 24.000 caracteres para el mensaje de
usuario. Reduce referencias, historial y controles, conserva el foco y declara
los recortes. No es un contador exacto de tokens ni incluye el coste de las
imágenes. El servidor local está configurado con contexto **16.384 tokens**;
no se aumentó. Las peticiones registran el consumo real informado por el servidor.

## Operaciones del controlador

- `RECORDAR`: solicita guardar un dato literal observado. Se comprueba que exista
  en el contenido capturado, se rechazan contraseñas, duplicados e inferencias y
  se conservan nombres distintos cuando los valores cambian.
  Admite hasta cuatro datos por acción; el lote se rechaza completo si alguno
  no está observado. No se acepta prosa como si fuera un comando.
- `SIGUIENTE`: solicita verificar la etapa activa. No marca éxito por sí sola.
- `IMPORTAR_PLAN`: requiere que el usuario haya pedido expresamente leer y
  realizar instrucciones. Importa una vez hasta cuatro pasos literales de 240
  caracteres de la fuente actual. Conserva obligaciones adicionales del usuario
  y el pedido original. No es un permiso para sustituir instrucciones del sistema
  ni garantiza resistencia completa a instrucciones maliciosas.
- `PREGUNTAR`: detiene la ejecución y conserva la aclaración necesaria en el
  resultado. Se debe dar una nueva orden completa con los datos aclarados;
  todavía no hay reanudación conversacional automática.
- `DECIR`: conserva la respuesta del modelo además de mostrarla.
- `LISTO`: solicita la verificación de la etapa y del conjunto del pedido.

La lectura se protege antes de saltar a un destino mencionado en etapas
posteriores. No se incorpora todavía lectura paginada completa de documentos
largos ni selección automática fiable de la fuente correcta en cualquier app.

Para una nota o documento solicitado, enfocado y capturado por completo, un
adaptador puede importar automáticamente de una a cuatro líneas imperativas
literales (máximo 1000 caracteres de fuente), tras comprobar el pedido explícito
de realizarlas. Si el modelo intenta salir cuando los datos ya están conservados,
el adaptador solicita verificar la lectura; no ejecuta el clic propuesto ni marca
éxito. Las adaptaciones quedan identificadas en la traza y no se atribuyen al
modelo solo. Otros tipos de fuente conservan el recorrido interpretado por el
modelo y pueden necesitar aclaración.

## Recetas parametrizadas

La parametrización automática específica de redes fue retirada del asistente.
Sus utilidades históricas están aisladas en `experimentos/parametros_red.py`.

El modo «Mírame» conserva objetivo y pasos, con su aplicación y procedencia. Se
recuperan solo recetas de la aplicación activa y se refrescan esas referencias
cuando cambia la aplicación durante una tarea. Los metadatos `plantilla` antiguos
se conservan en disco pero no se ejecutan ni se inyectan como reglas. El modelo
adapta las demostraciones al pedido actual y a los controles observados; esta
adaptación puede fallar. Ver [aprendizaje general](aprendizaje-general.md).

## Resultado final y comprobaciones

Cada ejecución guarda JSON y un resumen Markdown en `salidas/tareas/`, excluido
de Git. Incluye etapas comprobadas y pendientes, datos observados, respuesta y
motivo de detención. El mensaje temporal muestra una versión breve y la consola
indica dónde está el resumen completo. No se añadió síntesis de voz.

`tests/test_tareas.py`, `tests/test_aprendizaje_general.py` y `tests/test_flujo_tareas.py`
comprueban los límites, procedencia, fases, sustitución de valores y cierre del
coordinador. La integración usa dobles de las entradas, no opera Windows.
`tests/test_parametros.py` conserva únicamente comprobaciones de las utilidades
de red aisladas en `experimentos/`; no valida una función del asistente habitual.
`experimentos/evaluar_tareas_variables.py` consulta el modelo real sobre estados
sintéticos y comprueba el resultado con un laboratorio independiente.

Estas pruebas no son operación real de WinBox, RouterOS ni recorrido completo
del micrófono y entradas de Fosfeno. Los resultados del modelo y los cambios
durante el desarrollo se documentan por ronda en el paquete de contexto.
