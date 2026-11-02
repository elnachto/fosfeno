# Pruebas de escritorio de Fosfeno — 29 de octubre de 2026

Se mejoró el controlador general y se probaron tareas reales con Nemotron en Bloc de notas, Explorador y Word. Hay mejoras verificadas en edición y guardado de texto, selección y copia de archivos. El formato complejo en Word sigue fallando. No se implementó el plugin de ChatGPT ni se repitió la comparación contra LFM3.

## Método y alcance

El evaluador experimental observa ventanas propias registradas, consulta al mismo controlador de Fosfeno y espera confirmación de cada acción. Codex traduce las entradas propuestas mediante Sky, vuelve a observar y registra el resultado. El evaluador no inyecta entradas por sí mismo. Se usaron archivos ficticios en esta carpeta, semilla 42, caché de prompt desactivada y el alias comprobado `fosfeno-nemotron`, servidor de contexto 16384. Las trazas registran hashes por propuesta. Las peticiones pueden usar imagen en reparación/verificación; esta ronda no permite medir por separado el aporte de visión.

Esto prueba decisiones del controlador sobre aplicaciones reales y un adaptador de entradas. No prueba el recorrido completo de voz, micrófono, atajos globales, animación o inyección nativa de Fosfeno. Los controles de foco y acciones nativas sí tienen regresiones automatizadas. Las capturas y notas de la aplicación son referencias falibles, no instrucciones autorizadas.

Durante el desarrollo se corrigió código entre intentos y el operador descartó propuestas erróneas o detuvo ciclos. Se distingue ese trabajo de las pequeñas regresiones nuevas con código fijo durante cada caso. No se convierte esta ronda en una puntuación universal ni se cambian el 16/16 simulado y el 0/3 real históricos. Tampoco se atribuye a Nemotron solo el resultado de las adaptaciones del controlador.

## Resultados observados

| Caso | Resultado y evidencia |
|---|---|
| Bloc de notas: crear inventario A | Desarrollo: se corrigió la omisión del editor, la selección localizada y la comparación de saltos. Archivo inicial guardado; final aceptado después de correcciones. |
| Bloc de notas: modificar A | 3 acciones: Cuadernos 12→18, PENDIENTE→REVISADO, conserva Lápices 30 y título. Archivo exacto y final aceptado. |
| Bloc de notas: reabrir A y leer | 5 acciones confirmadas; abre y comunica 18 cuadernos, 30 lápices, REVISADO. Hubo intervención y corrección de controles homónimos. |
| Explorador A | Desarrollo: ciclos de selección, correcciones y propuestas descartadas; finalmente dos copias exactas y final aceptado. |
| Explorador B, código fijo | 6 acciones, nombres con tildes/ñ; copias exactas y originales presentes. El verificador rechazó erróneamente el final: éxito funcional, fallo de aceptación. |
| Explorador C, código fijo durante el caso | 6 acciones, nombres con espacios y extensiones distintas; dos copias SHA-256 idénticas, originales conservados, archivo excluido fuera del destino y LISTO aceptado. Participaron las adaptaciones de selección y apertura del destino. |
| Word: título centrado/negrita y cuerpo normal | Incompleto en dos intentos de desarrollo. Resolvió la escritura, pero confundió cursor y selección, repitió el diálogo de párrafo y no consiguió el formato. No se declaró éxito. |
| Word: solo guardar el documento de diagnóstico | 5 acciones y LISTO aceptado. El DOCX tiene dos párrafos, ambos normales y a la izquierda: es éxito de guardado, fallo de formato complejo. |
| Bloc de notas B | 5 acciones guardan texto exacto con sangría, emoji y LF final, pero intenta guardar otra vez. Al reanudar hubo una edición fuera de traza; se detuvo. No es éxito completo. |
| Bloc de notas C | 5 acciones guardan texto exacto, sin cambios de código durante esas entradas. Luego propone reescribir el mismo texto. Tras añadir el rechazo de reemplazo idéntico y reanudar, da LISTO aceptado sin nuevas entradas. Éxito funcional inicial; aceptación resuelta en desarrollo. |

Se comprobaron de nuevo los tres archivos de texto y las tres parejas de copias al cerrar. El estado abierto de una pestaña puede diferir del archivo guardado; la nota B tenía indicador de cambios sin guardar tras la edición fuera de traza. No se sobrescribió esa edición. Los resultados detallados, cantidades de propuestas/acciones y hashes están en `resultados-resumen.json`. Las incidencias contadas allí son un mínimo: las primeras ocurrieron antes de incorporar el registro específico.

## Cambios aplicados

- Captura de controles Document, foco real padre/hijo, campos de solo lectura, valores, selección, posición de párrafo, formato accesible, atajos observados y controles homónimos con geometrías distintas. Se declara incompleta una captura que agota el tiempo.
- Identidad de aplicación por clase y propietario real de los diálogos. La referencia de Word no se activa por un título que diga “Word”. Es una ayuda experimental escrita, no una habilidad aprendida ni validada.
- Escritura conserva sangría, tildes, emoji y salto final. Normaliza CR/LF. La selección completa usa Inicio y Fin con modificadores, evitando Ctrl+A, que abre archivos en este Bloc de notas en español. Se revalida el foco antes de escribir.
- Se bloquea el reemplazo que borraría texto exigido por el pedido o un documento del que solo se observó un fragmento. Se rechazan reemplazos idénticos y se pide replantear, sin convertirlos automáticamente en éxito.
- Detección de ciclos basada en el estado operativo; no depende de identificadores o barras de herramientas que cambian. Presupuesto compartido de 36 acciones, con cancelación y límites existentes.
- Memoria estructurada de selección al copiar y carpeta observada, sin leer el portapapeles. Extiende selección solo para dos archivos pedidos y adyacentes del mismo listado; abre la carpeta destino antes de pegar si sigue seleccionada en su carpeta padre. Estas son adaptaciones del controlador, con propuesta original registrada.
- Ruta local de Explorer mediante consulta de solo lectura a la ventana exacta. Evidencia acotada de archivos de salida explícitos y copias de la tarea, incluida comparación SHA-256. El planificador y el verificador reciben esa evidencia.
- Inspección de texto, negrita y alineación del DOCX guardado, incluidos estilos heredados y marcas de truncamiento. No verifica diseño, tablas o cuadros de texto ni formatos arbitrarios. TXT se lee hasta 256 KB y resume hasta 6000 caracteres; copias se comparan hasta 16 MB por archivo, máximo diez. No se recorren archivos privados generales.

## Comprobaciones y limitaciones

Pasaron **87 pruebas automatizadas**. Cubren foco, contraseñas y solo lectura, cancelación, continuidad, preservación de contenido, selección localizada, ciclos, copia y evidencia, normalización de texto, referencias por aplicación y lectura de formato real. No son 87 tareas completadas por el modelo.

Se ensayó además una única observación conocida de Word con/sin razonamiento solicitado, semilla 42 y máximo 4096 tokens. Ambas respuestas finales propusieron un siguiente paso inadecuado; activar razonamiento produjo contenido de razonamiento, pero no resolvió ese ejemplo. No se ejecutaron esas acciones ni se modificó la configuración predeterminada a partir de esta muestra. No es comparación estadística de calidad o velocidad.

Queda pendiente una ronda nueva completa con código final fijo, el recorrido nativo de voz/atajos/entradas y más aplicaciones. Word requiere resolver la selección y verificar el efecto de cada formato antes de ampliar tablas o documentos largos. No hay evidencia para prometer compatibilidad fiable con cualquier aplicación o petición.

## Entrega y continuidad

Cambios en `D:\LOCALai\clicky`, rama `experimental/agente-estado`, HEAD del usuario `94faaab`; esta ronda sigue sin commit ni push. El evaluador local se detuvo al terminar; Nemotron queda disponible. No se creó el plugin de ChatGPT.

`CONTEXTO_PARA_CLAUDE.md`, sección 15, y `contexto-fosfeno-para-claude.zip` incluyen el contexto y las fuentes. El ZIP incorpora este informe, resumen y condiciones de prueba seleccionadas. Las trazas crudas quedan locales: pueden contener nombres del panel lateral, historial o datos de la cuenta de Word. El token efímero `sesion-local.json`, esas trazas y el DOCX con metadatos no se incluyen en el paquete. El ZIP es un paquete de revisión, no un instalador completo.
