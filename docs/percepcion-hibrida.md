# Percepción visual experimental

UIA sigue siendo la vía habitual. Cuando solo expone el marco de Windows,
el modo opcional añade regiones de texto detectadas por OCR local. Son IDs
`VisualText`, no botones ni campos nativos. Las posiciones salen de la captura
actual; no hay un recorrido de menús de WinBox en el controlador.

## Flujo

1. Capturar la ventana y conservar sus controles UIA.
2. Si no hay contenido accesible, detectar texto con RapidOCR/ONNX en CPU.
3. Dar al planificador etiquetas, posiciones y procedencia OCR, sin enviarle
   las miniaturas internas de validación.
4. Revisar la región seleccionada en otra consulta: texto ampliado y contexto.
   Solo se admiten clics clasificados como navegación.
5. Justo antes del clic, comprobar ventana activa, monitor, tamaño, antigüedad
   y cambios en la zona de destino. Recapturar después y observar el resultado.

La revisión separada usa el mismo modelo. No es un verificador independiente
ni garantiza que una respuesta sea verdadera. La revisión de lectura mostró
falsas aceptaciones en el ensayo; las respuestas siguen siendo provisionales.
Un `respaldada=true` con un problema no vacío se rechaza.

El piloto bloquea escritura, teclado, desplazamiento, confirmaciones y cambios
de configuración. También bloquea RECORDAR, IMPORTAR_PLAN y SIGUIENTE para
evitar guardar como aprendizaje relaciones visuales que aún interpreta mal.
Con la opción experimental activa tampoco se guardan recetas automáticas de éxito.
Los campos OCR no se declaran editables y no acreditan foco nativo.

## Activación voluntaria

Está **desactivado por defecto** y no cambia los lanzadores habituales.
Preparar un entorno con las dependencias normales del proyecto y las opcionales:

```powershell
cd D:\LOCALai\clicky
python -m venv --system-site-packages .venv-vision
.\.venv-vision\Scripts\python.exe -m pip install -r requirements-vision.txt
$env:FOSFENO_VISION_EXPERIMENTAL = '1'
.\.venv-vision\Scripts\python.exe jarvis.py --motor nemotron
```

En la PC del ensayo se instaló únicamente en el entorno privado
`D:\LOCALai\laboratorios\fosfeno-gns3\vision-env`; también puede usarse su Python
con la variable anterior. No se instalaron estos paquetes en el Python global.
RapidOCR puede descargar sus pesos al preparar el motor; el OCR se ejecuta localmente.
Implementación y modelos: [RapidOCR oficial](https://github.com/RapidAI/RapidOCR).

## Métodos comparados en desarrollo

- UIA: cuatro controles del marco en la sesión conectada de WinBox 4.4.
- Win32: `EnumChildWindows` devolvió cero ventanas hijas. Se conserva como
  diagnóstico de solo lectura, sin usarlo para inventar controles.
- Rejilla visual: tres objetivos iniciales, tres primeras celdas incorrectas;
  los recortes posteriores se abstuvieron. Cero clics. **No se activa como fallback.**
- OCR: detectó las etiquetas IP, Interfaces y Bridge. La selección de texto
  con revisión de región permitió ejecutar navegación real en WinBox.

La cruz pequeña sobre la imagen completa y luego sobre un recorte resultó
inconsistente para Nemotron. El camino OCR revisa texto y contexto ampliados;
la geometría la calcula el detector. No depende de que el LLM invente coordenadas.

## Alcance del ensayo real

Se conservan todas las iteraciones, incluidas las fallidas. El operador ejecutó
las propuestas con Computer Use y comprobó cada resultado antes de confirmar.
Se ejercitaron el planificador y la validación del destino; **no fue una prueba
completa de voz ni del SendInput nativo de Fosfeno**.

La navegación logró abrir Interfaces y la tabla IP/Addresses. La tarea compuesta
de leer todas las IPv4 y el DHCP no quedó resuelta: una columna aparecía cortada
y el modelo confundió relaciones entre columnas y ventanas superpuestas. Incluso
el revisor aceptó una fila de Interfaces como si fuera un servidor DHCP.
El operador rechazó ese RECORDAR; no se guardó ni se ejecutó.

La prueba separada «abre la vista de servidores DHCP», iniciada con el submenú IP
ya abierto, eligió DHCP Server, abrió la vista real y terminó con verificación
positiva. No sustituye la tarea compuesta. Se ejecutaron cinco clics de navegación
en total entre las distintas iteraciones, todos revalidados antes de actuar.
La versión final pasa 164 pruebas del programa; nota/contacto/selector pasan 3/3
en la regresión conocida con semilla 42, sin falsos éxitos en esa muestra.

Son pruebas de desarrollo sobre un laboratorio conocido, con cambios entre
iteraciones y estados iniciales distintos. No constituyen un benchmark ciego,
una comparación nueva contra LFM3 ni evidencia de compatibilidad universal.
El informe local conserva los resultados de la apertura separada de DHCP,
las pruebas automáticas, la regresión y las condiciones finales.

## Reproducción de localización sin clics

`experimentos/evaluar_localizacion.py` captura solo la ventana esperada mediante
HWND/título, oculta el exterior y permite tapar una franja externa. Después puede
comparar `--metodo rejilla` y `--metodo ocr` sobre la misma imagen y lista de
objetivos JSON. Nunca pulsa ni escribe. Guarda las propuestas, imágenes revisadas,
hashes y metadatos del servidor local. Las recetas no intervienen en esa medición.

Lo siguiente es resolver tablas con columnas cortadas, paneles superpuestos,
iconos sin texto y foco visual verificable antes de habilitar edición o aprendizaje.
