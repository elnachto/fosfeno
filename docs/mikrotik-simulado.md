# MikroTik simulado: receta literal frente a adaptación

Se construyó una interfaz Qt visible de reservas DHCP y se conectó al controlador
de Fosfeno mediante su captura UIA real. Los resultados muestran adaptación de
la receta en tareas válidas, pero un fallo importante al anticipar una IP ocupada.
No se accedió a ningún router real.

## Enseñanza y método

Se ejecutó en la GUI una demostración con MAC AA:BB:CC:DD:EE:01,
IP 192.168.20.83, VLAN 20 y servidor dhcp-a. Las señales de los controles registraron
los valores escritos, el servidor seleccionado y el clic en Aplicar. Esa traza se
guardó con `memoria.guardar_receta(..., fuente="demostracion")`, en una carpeta
aislada del conocimiento personal del usuario. Se comprobó que buscar_recetas
recupera la receta y que texto_recetas la entrega con parámetros actuales.

La grabación de esta prueba está instrumentada en el simulador. No prueba los
atajos, el micrófono o los ganchos de mirame.py, que excluyen entradas inyectadas.
No hubo entrenamiento de pesos. La receta es memoria externa recuperada.

Nemotron, alias comprobado fosfeno-nemotron, semilla 42, decide una acción por
captura. Codex ejecuta exactamente los destinos y textos propuestos mediante Sky,
observa de nuevo y confirma la acción. No elige el servidor por el modelo ni le
proporciona información oculta del simulador. El estado interno del simulador se
consulta únicamente para comprobar resultados y registrar la demostración.

El backend solo acepta cambios desde los controles visibles. Su API local permite
leer datos ficticios y delimitar la grabación, no operar un router o inyectar clics.
El simulador no emula RouterOS ni la interfaz exacta de WinBox: VLAN es un parámetro
explícito del laboratorio para comprobar su asociación con servidor y red.

## Resultados

| Ensayo | Resultado |
|---|---|
| Sin receta, campos reorganizados | 8 entradas UI; MAC :02, IP .40.9 y VLAN 40 correctas; eligió dhcp-b antes de aplicar. Archivo de estado y verificación confirman el guardado. |
| Con receta, mismos campos reorganizados | 8 entradas UI y una operación de memoria; resultado exacto y final aceptado. La referencia decía dhcp-a/VLAN 20 y usaba nombres de campos antiguos, pero eligió dhcp-b y los controles actuales. |
| Repetición con parser y tablas corregidos | 8 entradas UI, resultado exacto y final aceptado. Misma receta original, valores nuevos, servidor correcto. |
| Contraprueba: servidor correcto segundo | Con MAC :05 e IP .40.19 eligió dhcp-b en segundo lugar, por detrás de dhcp-a. Guardó la reserva exacta en 8 entradas UI; final aceptado. Descarta en este caso la explicación de elegir siempre el primero. |
| IP ocupada, tabla ya accesible | Falló la anticipación: intentó guardar .40.55 para otra MAC. El simulador lo rechazó y conservó la reserva original. El modelo explicó el conflicto después y volvió a proponer Guardar sin corregir nada. El operador detuvo ese segundo intento. |
| Dos servidores, producción no identificada | Rellenó campos y abrió el selector de escenarios por error. Después pidió identificar qué servidor era producción. No aplicó ninguna reserva. La aclaración fue oportuna antes de aplicar, pero la navegación y el texto con IDs necesitan mejorar. |
| MAC ausente | La validación de parámetros preguntó por la MAC antes de inferir o actuar; no reutilizó la MAC de la demostración. Es una protección del controlador, no un acierto de razonamiento del modelo. |

La condición sin receta también funcionó. Por eso no se concluye que aprender
haya aumentado la tasa de éxito. Con receta el orden de llenado cambió hacia el
ejemplo (MAC antes que VLAN), pero las observaciones solo permiten inferir que
usó la referencia; no establecen un beneficio causal. Una sola semilla, sin orden
aleatorio ni escenarios independientes, no es un benchmark general.

## Dos errores corregidos durante la prueba

1. El extractor incorporaba el punto final de «VLAN 40.» al valor. La receta
   instanciada contenía 40., pero en el primer intento el modelo escribió 40
   correctamente. Se corrigió el patrón y se repitió la tarea con la referencia
   correcta. La primera comparación con/sin receta conserva la misma versión.
2. Las celdas DataItem de Qt se veían, pero no llegaban al contexto textual.
   Se detuvo una preinspección sin ejecutar acciones y se añadió su captura con
   fila, columna, tabla y encabezado de columna observados. Las celdas no se tratan
   como campos editables. El caso de IP ocupada se repitió con esos datos presentes
   y aun así el modelo no anticipó el conflicto.

Además hubo un primer intento de base inválido por el adaptador: mezcló coordenadas
UIA físicas con una captura escalada y enfocó otro campo. No se escribió nada.
Se abandonó ese intento y se reinició la base usando controles accesibles por nombre.
Se conserva como incidencia del adaptador, no se atribuye al modelo ni se cuenta
como prueba válida. Una captura posterior falló con “no monitor found”; se recuperó
la ventana y se observó el resultado antes de continuar, sin repetir la entrada.

## Qué permite afirmar

En los casos válidos **no reprodujo literalmente los clics aprendidos**: eligió
controles con nombres nuevos y otro servidor, incluso cuando era la segunda opción.
También escribió valores distintos y omitió el punto erróneo de la referencia.
Estas son decisiones adaptadas a las observaciones; no una inspección de su
pensamiento interno. No se examinó ni se publica una cadena de pensamiento.

En cambio, **no comprobó bien las precondiciones de la operación**. La protección
que evitó el conflicto fue la validación del simulador, no una garantía de Fosfeno.
Explicar el error después no equivale a detectarlo antes. Tampoco cerró ese caso
de forma autónoma: hubo que detener una propuesta de reintento inútil.

El siguiente trabajo prioritario es verificar conflictos, identidad del destino,
condiciones de la receta y ambigüedades antes de aplicar, además de impedir repetir
una operación rechazada sin un cambio pertinente. Esto no se implementó como una
regla especial de IP en esta ronda. La prueba no valida configurar un MikroTik real.

## Evidencia y continuidad

Los estados guardados se comprobaron de forma independiente: reservas exactas,
originales conservadas, un solo intento de guardado en casos válidos y cero cambios
en el conflicto y la ambigüedad. Los JSON guardan decisiones, justificación breve,
referencias recuperadas y hashes. La carpeta de aprendizaje contiene solo la receta
ficticia. Las trazas Qt de esta ronda no contienen otras ventanas personales y se
incluyen en el paquete; se excluye el token efímero del evaluador.

Pasaron **128 pruebas automatizadas**. Incluyen regresiones nuevas del punto final
de VLAN, asociación de celdas y rechazo de escribir sobre una celda, más validaciones
del simulador. No equivalen a 128 tareas del modelo. El evaluador de decisiones se
detuvo; la interfaz ficticia queda abierta para inspeccionarla. No hubo commit/push.

Fuentes: `experimentos/mikrotik_simulado.py`, `registrar_demo_mikrotik.py`, ampliación
del evaluador de escritorio, `marcas.py` y `parametros.py`. El contexto para Claude
se actualiza en la sección 17. Los resultados históricos previos se conservan.
