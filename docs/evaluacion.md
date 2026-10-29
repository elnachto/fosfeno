# Evaluar Fosfeno sin confundir simulación con escritorio real

## Reproducir

1. Arranca los servidores de los motores a comparar. `D:\LOCALai\iniciar-hibrido.bat`
   deja disponibles Nemotron y LFM3 en sus puertos separados.
2. Ejecuta desde el proyecto:

   ```powershell
   python -m unittest discover -s tests -v
   python evaluacion.py --motores lfm3,nemotron --semillas 42,99 --salida salidas/comparacion
   ```

3. Revisa `resumen.json`, `resultados.json` y `manifiesto.json` en la carpeta
   indicada. Conserva el manifiesto con los resultados: identifica los pesos,
   la versión del servidor y el código evaluado.

## Qué se mide

Las ocho tareas simuladas cubren notas, sustitución de valores de un contacto,
conversación nueva con envío, búsqueda y espera de resultados, navegación a
una URL en una pestaña nueva, casillas, selectores y cantidades numéricas.
Los identificadores cambian durante la tarea. El estado final se comprueba
con el entorno de prueba, independientemente de lo que afirme el modelo.

- `objetivo_logrado`: el entorno confirma los valores y efectos solicitados.
- `correcto`: además de lograrlo, el controlador terminó con verificación positiva.
- `falso_exito_aceptado`: el controlador declaró éxito pero el entorno demuestra
  que faltaba parte del objetivo. Es un fallo aunque la respuesta parezca convincente.
- `segundos`: incluye las consultas, comprobaciones y recuperación en el entorno
  simulado. No incluye movimientos de ratón, pausas visuales ni la voz.
- Las latencias de tareas fallidas no equivalen al tiempo necesario para completarlas.

Cada motor recibe los mismos casos, semillas, muestreo y contexto de 16K en
la instalación de referencia. Las consultas de evaluación desactivan la caché
del prompt y se envían en serie. El orden de motores/casos se mezcla de forma
reproducible. Las peticiones guardan tanto el modelo solicitado como el que
el servidor informa haber usado, para detectar comparaciones mal encaminadas.

## Límites de la comparación

La simulación permite repetir con el mismo estado; no reproduce todos los
problemas de una aplicación real. No mide por sí sola la captura de pantalla,
el reconocimiento de voz, la inyección de teclado o la latencia de Windows.
Tampoco prueba cualquier petición, app o interfaz dibujada sobre un lienzo.

Las capturas de fallos anteriores sirven para regresión. Cuando se usan para
ajustar el controlador, no deben presentarse como tareas nuevas no vistas.
Las pruebas reales deben indicar la aplicación, el objetivo, las acciones
ejecutadas y la evidencia independiente del resultado. Un primer clic correcto
no cuenta como una tarea completa.

La instalación compara Nemotron UD-Q4_K_XL con LFM3-VL Q8_0: son los archivos
disponibles en este equipo, no una comparación de precisión numérica idéntica.
Las cifras son descriptivas de esta muestra; no son un benchmark universal.

## Resultado de la instalación local

La ejecución final en `salidas/comparacion_final_v2` registró 16/16 tareas
completadas y verificadas con Nemotron y 2/16 con LFM3-VL. Ninguno tuvo falsos
éxitos aceptados. LFM3 completó únicamente la nota en las dos semillas.
La mediana de tareas exitosas fue 15,195 segundos para Nemotron y 3,289 para
LFM3; cubren conjuntos de tareas distintos y no son una comparación directa
de velocidad. Se recomienda Nemotron como motor principal en esta instalación.

## Primera ronda posterior en aplicaciones reales

El 28 de octubre de 2026 se evaluó Fosfeno con Nemotron en una tarea por
aplicación: Word (título, tabla y guardado), Explorador (copiar, organizar y
renombrar) y Bloc de notas (reemplazos, cantidad y guardado). Ninguna de las
tres tareas quedó completa.

Word se bloqueó al comprobar el foco antes de escribir. En el Explorador se
creó la carpeta, pero no se copiaron los archivos. En Bloc de notas se
reemplazaron los estados en el editor, sin cambiar la cantidad ni guardar.
El evaluador detuvo ciclos repetidos sin progreso; no agotó el límite de
acciones ni demuestra que el modelo nunca pudiera recuperarse con más intentos.

Se conservaron las fuentes de la comparación simulada. Las decisiones se
obtuvieron con los controles reales de Windows y se ejecutaron mediante un
adaptador de control bajo observación. No es una prueba completa de voz,
atajos globales o inyección nativa del producto. La imagen no se envió en
todas las decisiones. No hubo propuestas LISTO, por lo que esta ronda no
evalúa el rechazo de falsos éxitos finales.

El 16/16 simulado y el 0/3 de esta ronda miden condiciones distintas. Antes
de atribuir los fallos al modelo hay que distinguir planificación, captura
del estado, validación del foco e inyección de entradas. Durante esta ronda la
memoria de mapas y recetas no llegaba a la rama nueva que decidía acciones.
Después se corrigió esa conexión y se añadió una prueba de regresión; estos
resultados históricos no se volvieron a medir y no demuestran un efecto de aprendizaje.

## Tutor experimental con manuales

La [evaluación del tutor](tutor-experimental.md) separa tres diagnósticos
textuales de una red construida en Packet Tracer. La red pasó de Successful
a Failed al cambiar una IP, volvió a Successful con la corrección y superó
una prueba nueva después de guardar y reabrir. El operador tradujo la guía
a acciones; no fue autonomía completa de Fosfeno ni una prueba de visión.
La consulta documental produjo errores técnicos y de restricciones, y el
revisor del mismo modelo produjo falsos rechazos. No se suma esta red a las
tareas simuladas ni al 0/3 histórico de otras aplicaciones.

## Segunda ronda de escritorio: 29 de octubre

El [informe de la segunda ronda](pruebas-escritorio-2026-10-29.md) documenta
las correcciones del controlador y 15 registros entre diagnósticos, casos de
desarrollo y regresiones. Una regresión nueva del Explorador, con código fijo
durante el caso, completó seis acciones con copias idénticas y final aceptado.
Otra copió correctamente, pero el verificador produjo un falso rechazo.
Las tareas de texto y guardado mejoraron; reconocer el final de una nota
requirió rechazar reemplazos idénticos. El formato complejo de Word sigue
incompleto, incluso con una referencia experimental por aplicación.

Se mantienen separados éxito funcional, aceptación del verificador y
asistencia del operador. Las correcciones durante una tarea no cuentan como
ejecuciones nuevas con código fijo. Se comprobaron archivos reales y hashes,
y pasaron 87 pruebas automatizadas del programa. Solo se usó Nemotron; no se
repitió la comparación con LFM3 ni el recorrido nativo completo de voz y
entradas. Esta ronda no cambia las cifras históricas anteriores.

## Memoria breve y parámetros: ampliación posterior

La [ampliación de tareas y parámetros](tareas-y-parametros.md) tiene 124 pruebas
automatizadas del programa. Se ensayaron tres escenarios sintéticos con dos
semillas: leer y usar una cantidad en otro formulario, ejecutar instrucciones
breves de una nota y reutilizar una receta con otra MAC/IPv4/VLAN. Tras cinco
rondas de desarrollo sobre esos mismos casos, la última registró seis resultados
correctos y seis finales aceptados, sin falsos éxitos en la muestra. Se conservan
los fallos y cambios de las rondas anteriores.

La importación literal de notas breves y la transición a verificar la lectura
incluyen adaptaciones del controlador identificadas en la traza. La quinta ronda
también alinea la recuperación NADA del laboratorio con la existente en Jarvis.
Los planes iniciales se proporcionaron al laboratorio. No son casos independientes,
escritorio real ni operación de MikroTik. No se modifica la comparación histórica
de modelos ni la limitación de formato complejo de Word. La entrada máxima de
esta matriz fue de 2394 tokens sin imágenes, sobre contexto del servidor 16384.

Como regresión separada se repitieron nota, contacto y selector, semilla 42:
tres de tres completas y verificadas, sin falsos éxitos. Son casos conocidos
del laboratorio previo y tampoco prueban el escritorio real.

## Interfaz visible ficticia de MikroTik

El [ensayo de reservas DHCP](mikrotik-simulado.md) usa una GUI Qt visible,
captura UIA real y entradas mediante adaptador. La receta se registró con
señales de los controles y se guardó en memoria aislada; no se probó el grabador
de voz/atajos. Se comparó con/sin receta y se hizo una contraprueba con el servidor
correcto segundo. Las tareas válidas completaron el guardado exacto; la condición
sin receta también lo consiguió. No hay evidencia de mejora causal por aprender.

El caso de IP ocupada falló antes de aplicar: aun recibiendo las celdas de la
tabla, el modelo intentó guardar. El backend ficticio rechazó el cambio, después
el modelo explicó el conflicto y volvió a proponer Guardar; el operador detuvo
ese segundo intento. Con producción no identificada pidió aclaración antes de
aplicar, pero hubo un desvío al selector de escenarios. Se conservaron los fallos,
las preinspecciones y una incidencia DPI del adaptador. Los detalles distinguen
protecciones del controlador, del simulador y decisiones del modelo. Pasan 128
pruebas automatizadas. No se configura ni valida un router real.

## Ampliación posterior: GNS3 y revisión de formularios

Se preparó un [laboratorio CHR real en GNS3](gns3-mikrotik.md) y pasaron siete
comprobaciones funcionales de VLAN/DHCP/ping por consola. Se repitieron después
de reiniciar para comprobar persistencia. No son acciones autónomas de Fosfeno
en WinBox/WebFig. El controlador incorpora revisión antes de confirmar y bloqueo
de envíos idénticos rechazados; pasan 140 pruebas del programa y una regresión
Nemotron separada de tres casos conocidos. El revisor logró 8/12 decisiones
exactas en su tercera ronda, con cuatro aclaraciones innecesarias. El documento
enlazado conserva el historial de desarrollo y distingue todas estas mediciones.
