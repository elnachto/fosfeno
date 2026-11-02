# Demostraciones visuales: implementación pendiente de pruebas

Esta primera implementación conecta el modo «Mírame» con evidencia visual y
referencias estructuradas. No incorpora procedimientos de una aplicación concreta.
Se escribió y revisó el código sin ejecutar pruebas, por petición del usuario.

## Grabación

Al iniciar «Mírame» se crea una carpeta única en `salidas/demostraciones/`.
`demostraciones.RegistroVisual` mantiene una muestra reciente de la ventana activa
y registra los clics, segmentos de escritura y atajos que reconoce el grabador.
Conserva nombre y rol UIA, tiempo, posición relativa del clic cuando es conocida,
y capturas previas/posteriores disponibles. El origen distingue usuario de la
opción experimental que admite entradas de automatización.

El muestreo se realiza en momentos sin eventos, como máximo cada 250 ms. No es
vídeo ni sincronización perfecta. Solo se acepta como previa una captura terminada
antes del evento. Si otra acción se adelanta a la captura posterior, se señala
la ambigüedad. Las capturas guardadas se limitan a 1440×1000 y a 120 pasos visuales.
El texto y los pasos originales se mantienen aunque falten imágenes.

Las entradas identificadas como contraseña no se guardan como valores ni reciben
capturas asociadas. No hay un detector general de contenido sensible de pantalla.
Los archivos son locales y están bajo la carpeta excluida de Git `salidas/`.

La limpieza del aprendizaje conserva clics sobre Group/Pane/Document y repeticiones.
No se infiere que sean errores únicamente por su rol o igualdad de texto.
Los arrastres y desplazamientos no están reconstruidos como trayectorias semánticas
en esta versión; se conserva el alcance del capturador anterior en esos casos.

## Interpretación y memoria

Después de grabar, el modelo configurado recibe como máximo 12 pares disponibles
de imágenes y sus eventos. Propone descripción, finalidad posible, cambio visible
e incertidumbre. Las interpretaciones se guardan como hipótesis no verificadas;
no acreditan que el procedimiento cumpla un objetivo ni que pueda reutilizarse.
Los pasos sin un par de capturas independiente se omiten del análisis visual.

Tras la decisión normal de guardar la demostración, la receta puede contener
`demostracion_visual` y `conocimiento_visual`. Se conserva el formato anterior
para las recetas que no tienen esos campos. Las imágenes y el manifiesto quedan
como evidencia local; los prompts ordinarios reciben extractos breves de hasta
cuatro interpretaciones y parte de los eventos, no la grabación entera.

La decisión de descartar una receta evita guardarla en la memoria. Las capturas
de la sesión permanecen en `salidas/` como material local de depuración; esta
versión no implementa limpieza automática de esas carpetas.

## Ayuda, guía y acciones

`marcas.responder` recupera hasta dos recetas pertinentes de la aplicación activa
para apoyar explicaciones y soporte. `marcas.decidir` incorpora esas referencias
al señalar un control. El planificador de acciones utiliza el mismo formato de
referencias de memoria que ya tenía. Se conserva la selección por app y objetivo.

Una explicación puede referirse a lo mostrado y a sus incertidumbres. Los pasos
de una demostración siguen siendo antecedentes, no permisos ni confirmación del
estado actual. Las posiciones grabadas son evidencia: el ejecutor sigue
localizando destinos actuales; no reproduce coordenadas históricas automáticamente.

## Pendiente antes de usarlo como capacidad validada

- Comprobar captura y orden temporal de eventos, incluidos clics rápidos y cambios de ventana.
- Verificar escritura por segmentos, tratamiento de contraseñas y fallos de captura/almacenamiento.
- Evaluar utilidad y precisión de las interpretaciones con el modelo local.
- Comparar sin demostración, texto y evidencia visual en distintas aplicaciones.
- Medir tareas completas y calidad de explicaciones, coste y falsos éxitos.

No se ejecutaron pruebas unitarias, llamadas al modelo ni recorridos GUI de esta
implementación. No se implementaron aún investigación autónoma en manuales/web,
aprendizaje de errores consolidado ni un sistema de validación de nuevas habilidades.
