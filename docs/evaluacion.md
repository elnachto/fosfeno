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
del estado, validación del foco e inyección de entradas. La memoria de mapas
y recetas aún no llega a la rama nueva que decide acciones; tampoco debe
atribuirse un efecto de aprendizaje a estas cifras.
