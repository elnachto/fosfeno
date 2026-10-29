# WinBox real: lectura visual y bloqueo de navegación

Se comprobó WinBox 4.4 conectado al CHR propio `FOSFENO-GNS3-LAB`, por
`127.0.0.1:18291`. El usuario inició sesión manualmente. Nemotron decidió con
semilla 42, sin recetas ni notas de la aplicación ni un recorrido de menús.
Se usó el evaluador de decisiones y Sky; no se probaron voz, clasificación
inicial ni el ejecutor SendInput nativo completo.

## Resultado

| Comprobación | Resultado observado |
|---|---|
| Consultar IP por interfaz, DHCP y reserva existente | Bloqueada: la imagen muestra menús, pero UIA solo entrega cuatro controles del marco de Windows. Con la corrección, el modelo reconoció Interfaces/IP y pidió identificadores para interactuar. No se ejecutó ninguna entrada. |
| Leer nombre, modelo y versión ya visibles | Correcta: `FOSFENO-GNS3-LAB`, `CHR innotek GmbH VirtualBox`, `7.23.8 (long-term)`. DECIR, LISTO y verificación final aceptada; los datos coinciden con la pantalla. |
| Crear una nueva reserva | No ejecutada por la limitación anterior. |
| Resolver el conflicto de IP previsto | No ejecutada; no se creó antes la reserva necesaria para ese escenario. |

La lectura de identidad se añadió como **control positivo exploratorio después
del bloqueo**, con una orden fijada antes de consultarlo. No sustituye la tarea
original ni constituye una tasa de éxito general. Nombre/modelo también aparecen
en el título; la versión se lee en la imagen. Texto UIA y valor del foco estaban
vacíos. Se registró `vision=true` en las peticiones.

La lectura tomó unos 14 segundos entre propuesta y cierre, sin entradas GUI.
El operador comunicó literalmente DECIR al usuario y confirmó esa comunicación.
No se probó su presentación en la bolita ni la voz. La consulta de navegación
tardó unos 29 segundos: hubo un reintento HTTP por límite de salida, no dos
acciones ni dos decisiones del planificador.

No se dieron al modelo comandos ni resultados de consola del router. Una
comprobación independiente de solo lectura no encontró las nuevas reservas
MAC `02:11:22:33:44:62` y `02:11:22:33:44:63`.

## Incidencia de la base

Antes de corregirlo, la primera consulta no recibió imagen y confundió Sistema
del marco de Windows con un menú del router. Durante el intento de ese clic,
Sky devolvió `window is not a usable app window` y la ventana/proceso desapareció.
No se determinó si falló el input o su recaptura, ni la causa del cierre.

Se envió por error una confirmación antes de inspeccionar la salida de Sky.
Se corrigió la atribución a **ejecución desconocida**, se invalidó ese historial
para medir ejecución y se conservaron el JSON original y la auditoría. La
propuesta textual sí se observó; no demuestra navegación realizada. El ensayo
posterior se inició desde cero tras la reconexión manual.

## Cambios generales posteriores

- `marcas.py` identifica el marco por la jerarquía UIA TitleBar/MenuBar, sin
  usar nombres de aplicaciones.
- `agente.py` distingue marco y contenido, rechaza usar el marco para tareas
  internas y conserva operaciones de ventana pedidas por el usuario.
- Si solo se expone el marco, la imagen se envía desde la primera consulta.
- El evaluador permite ocultar una franja externa conservando tamaño y
  coordenadas. Se ocultaron 200 píxeles de la derecha, donde un panel externo
  mostraba el informe con respuestas del laboratorio. La región se registró;
  los menús de la izquierda y los datos leídos permanecían visibles.

Pasan **144 pruebas del programa**, cuatro nuevas para marco e imagen inicial.
Regresión de Nemotron, casos conocidos nota/contacto/selector, semilla 42:
**3/3**, con cero falsos éxitos en esa muestra. No modifica el benchmark histórico.

Esto **no implementa clics por coordenadas ni foco/escritura visual**. La pregunta
del modelo sobre IDs es una limitación del ejecutor, no un dato que deba aportar
el usuario. Se detuvo esa prueba. Hace falta una vía general de localización
visual y acciones verificadas para operar los controles internos de esta app.

## Ayudas y alcance

Hay reglas, validadores, prompts y ejemplos. El revisor contiene ejemplos DHCP
afinados con los casos sintéticos previos. No se afirma cero hardcoding o
hardprompting. No se encontró una macro de WinBox ni se añadió un recorrido de
sus menús. Los comandos fijos del montaje CHR anterior no fueron autonomía.

Se inspeccionó también la pantalla de conexión de WinBox 3.43 oficial: expone
File/Tools y el marco, pero no los campos. No se inició sesión ahí ni se probó
su panel administrativo; no se generaliza ese hallazgo a toda la versión 3.

WinBox 4 queda conectado. Se conservan condiciones, trazas, metadatos de visión,
incidencias y verificaciones. El token del evaluador y las credenciales quedan
fuera de Git y del paquete compartible.

## Continuación experimental

Se implementó después un [piloto OCR de percepción híbrida](percepcion-hibrida.md),
desactivado por defecto. Permitió navegar a Interfaces e IP/Addresses con posiciones
detectadas en cada captura, sin una macro de menús. La lectura compuesta sigue
incompleta y presentó asociaciones incorrectas; no sustituye los resultados de
esta primera ronda ni acredita configuración autónoma de RouterOS.
