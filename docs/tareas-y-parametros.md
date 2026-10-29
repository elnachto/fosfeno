# Tareas encadenadas, memoria breve y recetas con parámetros

Esta ampliación experimental conserva los datos que una tarea necesita al cambiar
de aplicación, verifica subtareas y guarda un resultado final. No modifica los
pesos del modelo. Se mantienen separados el objetivo del usuario, los datos
observados y las referencias aprendidas.

## Ejemplos

- «Lee la cantidad de esta nota, luego escríbela en el formulario y guárdalo».
- «Lee las instrucciones de esta nota y ejecútalas en el formulario de prueba».
- «Mírame cómo crear una reserva DHCP para MAC AA:BB:CC:DD:EE:01,
  IP 192.168.20.83, VLAN 20»; después de enseñar y guardar la demostración:
  «Crea una reserva DHCP para MAC AA:BB:CC:DD:EE:02,
  IP 192.168.40.9, VLAN 40».

Los valores son ficticios. El procedimiento de red es un ejemplo de
parametrización, no una configuración probada sobre un router.

Una reserva DHCP identifica un cliente por MAC y le ofrece una IP determinada;
no equivale a configurar una dirección en la interfaz del router. La
[documentación oficial de MikroTik](https://manual.mikrotik.com/docs/network-management/dhcp/server/)
describe esas funciones por separado. Fosfeno no deduce la topología, la subred,
el servidor DHCP o los puertos correctos a partir de tres valores.

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

`parametros.py` reconoce MAC con seis pares hexadecimales, IPv4 con prefijo
opcional y VLAN numérica (1–4094) o nombre explícito. Valida la forma, no su
existencia o disponibilidad en la red. Varias IP/MAC posibles son una ambigüedad,
no una invitación a elegir una.

Al guardar una demostración o receta exitosa se crea una plantilla solo para
los valores nombrados en el objetivo que aparecieron en pasos de escritura.
Se conservan los pasos originales para revisión. La plantilla sustituye esos
literales por `{{mac}}`, `{{ip}}` y `{{vlan}}`; los clics no se parametrizan.
Las recetas antiguas se pueden adaptar en memoria sin reescribirlas en disco.

Al recuperar una plantilla se usan los parámetros de la orden actual. Si faltan
o la operación aprendida no coincide, se muestra una pregunta sin reutilizar
los valores de la demostración. La receta sigue siendo una referencia: deben
volverse a observar los controles y las condiciones reales. Nombres de servidor,
puertos, relaciones VLAN-servidor y otros campos aún no tienen sustitución
automática; requieren enseñanza y comprobación adicionales.

## Resultado final y comprobaciones

Cada ejecución guarda JSON y un resumen Markdown en `salidas/tareas/`, excluido
de Git. Incluye etapas comprobadas y pendientes, datos observados, respuesta y
motivo de detención. El mensaje temporal muestra una versión breve y la consola
indica dónde está el resumen completo. No se añadió síntesis de voz.

`tests/test_tareas.py`, `tests/test_parametros.py` y `tests/test_flujo_tareas.py`
comprueban los límites, procedencia, fases, sustitución de valores y cierre del
coordinador. La integración usa dobles de las entradas, no opera Windows.
`experimentos/evaluar_tareas_variables.py` consulta el modelo real sobre estados
sintéticos y comprueba el resultado con un laboratorio independiente.

Estas pruebas no son operación real de WinBox, RouterOS ni recorrido completo
del micrófono y entradas de Fosfeno. Los resultados del modelo y los cambios
durante el desarrollo se documentan por ronda en el paquete de contexto.

Después se añadió un [ensayo con GUI ficticia visible](mikrotik-simulado.md):
hubo adaptación de controles y parámetros, pero falló la anticipación de una IP
ocupada. Se corrigieron la puntuación final de VLAN y la captura de celdas DataItem
con su fila y columna. La prueba no valida el procedimiento en RouterOS real.
