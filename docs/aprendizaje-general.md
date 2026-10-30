# Aprendizaje general por demostración

El conocimiento sobre una aplicación se incorpora mediante las demostraciones,
correcciones y exploraciones del usuario. El controlador conserva instrucciones
generales de manejo de interfaces, lectura, memoria breve y verificación.

## Limpieza respecto a las rondas de red

La base `1ddc59e` y la primera ronda `94faaab` no contenían los criterios de red
añadidos posteriormente. Se retiraron del asistente habitual:

- Ejemplos DHCP, conflictos IP/MAC y relaciones entre servidor y VLAN en los prompts.
- Clasificación fija de tipos de operación de red al reutilizar demostraciones.
- Extracción y duplicación automática de MAC/IP/VLAN en cada memoria de tarea.
- Generación y ejecución de plantillas reservadas para esos tipos de dato.

`experimentos/parametros_red.py` conserva las utilidades de los ensayos históricos.
Solo los experimentos y sus pruebas las importan. Los simuladores, documentos y
el tutor experimental separado pueden contener conocimiento específico: no se
cargan como instrucciones del asistente de voz.

## Qué se conserva

«Mírame» sigue grabando y guardando el objetivo, los pasos, la aplicación, la
procedencia y la fecha. Las correcciones y mapas siguen en `conocimiento/`.
La limpieza no reescribe ni borra esos archivos.

Al ejecutar una orden simple se recuperan las recetas pertinentes de la aplicación
activa. Si cambia la aplicación, se refrescan las referencias. Los ejemplos de
otras aplicaciones no se recuperan por compartir palabras con la orden.
Sin una aplicación identificada no se entrega una lista global de recetas.
Las órdenes que el controlador divide en varias etapas mantienen su recorrido
previo de memoria de tarea y no recuperan recetas de demostración en ese flujo.

Una receta es una demostración histórica. El modelo adapta sus pasos a los
controles actuales y usa los valores del nuevo pedido o de su fuente solicitada.
Debe pedir los valores necesarios que falten. Esta es una capacidad del modelo,
no una garantía de adaptación correcta ni una sustitución determinista de campos.

Los metadatos `plantilla` guardados por versiones anteriores se dejan intactos
pero se ignoran al recuperar el ejemplo. Se usan su objetivo y pasos originales.
No se mantiene la validación automática de formatos de red en el asistente.

No se restauró todo el proyecto a la base: se conservan los motores, la percepción
UIA/OCR, la edición experimental, la memoria breve y las comprobaciones generales.
El modelo conserva además lo que aprendió durante su entrenamiento original.

## Verificación

Las pruebas de memoria comprueban persistencia de demostraciones, aislamiento por
aplicación, compatibilidad de recetas antiguas y ausencia de criterios de red en
los prompts generales. El ensayo `experimentos/evaluar_aprendizaje_general.py`
usa demostraciones ficticias, memoria temporal y Nemotron real en formularios
simulados de agenda, inventario y biblioteca. Verifica que se guarden los valores
nuevos y no los de los ejemplos. No usa el grabador «Mírame», voz ni GUI real.

Los resultados de desarrollo y los límites se conservan en el reporte de contexto;
estas comprobaciones no prueban manejo autónomo de cualquier aplicación.
