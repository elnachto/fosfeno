# Edición visual de laboratorio

Extensión experimental para aplicaciones que solo exponen su marco mediante UIA.
Permite escribir, usar teclas de formulario, desplazarse y confirmar cambios en
una ventana autorizada por HWND y título exacto, o sus diálogos propietarios.
No contiene recorridos de WinBox ni coordenadas fijas de sus formularios.

## Activación

Requiere el entorno con `requirements-vision.txt`, el servidor del modelo y estas
variables, limitadas al proceso que se lanza:

```powershell
$env:FOSFENO_VISION_EXPERIMENTAL = '1'
$env:FOSFENO_VISION_EDITAR = '1'
$env:FOSFENO_VENTANA_LAB = '<HWND actual de la ventana>'
$env:FOSFENO_TITULO_LAB = '<título exacto actual>'
python jarvis.py --motor nemotron
```

Un HWND inválido, un título distinto o cambiar de ventana impiden la escritura
visual. Reabrir la aplicación puede cambiar el HWND: hay que volver a vincularla.
Los lanzadores habituales y la configuración global no se modifican.

## Comprobaciones y límites

- Los textos OCR siguen siendo `VisualText`, con `editable=False`: no se inventan
  controles nativos ni confirmación UIA del foco.
- Una escritura dirigida a un ID visual se convierte en clic y escritura pendiente.
  El punto del clic debe ser clasificado como campo; una etiqueta cercana no basta.
- Tras el clic, una nueva consulta con la captura comprueba el foco visible dentro
  de la región solicitada. La escritura directa al foco también pasa por revisión.
- Se comprueban ventana vinculada, título, antigüedad de la captura y ventana activa.
  El guardado visual pasa por la revisión previa de formularios ya existente.
- En esta variante, el detector admite hasta 200 regiones OCR y el planificador
  recibe sus datos compactos. El límite anterior de 120 recortaba los botones
  inferiores de un formulario real. Sigue vigente el presupuesto de 24.000
  caracteres del prompt; no garantiza cobertura de interfaces arbitrariamente densas.
- Los clics sin escritura pueden conservar tipo visual desconocido dentro del
  laboratorio: permitir exploración no acredita que el control haga lo esperado.
- Las teclas se limitan a navegación/edición del formulario; no se habilitan
  consola, autenticación, seguridad, reinicio ni borrado por etiquetas.
- No se guardan recetas automáticas en este modo. La revisión usa el mismo modelo,
  puede aceptar un destino incorrecto y no garantiza compatibilidad universal.

Las pruebas reales se registran por separado de las simuladas. Las acciones que
un operador realiza para preparar un formulario no cuentan como autonomía del
agente. Los intentos fallidos se conservan junto a los resultados posteriores.

## Resultado de desarrollo del 29 de octubre de 2026

WinBox 4.4 conectado al CHR propio de GNS3 permitió dos escrituras literales
correctas: MAC e IP. El operador preparó el borrador tras un fallo de navegación,
enfocó IP y abrió el selector de servidor. Fosfeno no completó la reserva: eligió
etiquetas en vez de entradas, confundió una opción abierta con un valor seleccionado
y repitió preguntas sobre el servidor ya indicado. No se pulsó Apply/OK.

La comprobación independiente de RouterOS confirmó que la nueva reserva no existe,
las reservas anteriores y las IP de interfaces se conservaron y el laboratorio
sigue sin ruta predeterminada externa. No es evidencia de manejo autónomo completo,
de funcionamiento por voz ni de éxito del ejecutor SendInput nativo: el operador
ejecutó las propuestas permitidas mediante Computer Use y verificó cada resultado.

Se añadieron comprobaciones genéricas de foco y de opciones desplegadas. El revisor
visual también dio falsos permisos; comparte modelo con el planificador. La nueva
observación previa de foco no consiguió identificarlo en los casos anotados y
añade consultas: queda experimental, sin una mejora de precisión demostrada.
No se añadieron recetas de WinBox ni rutas de menú. Sí siguen existiendo los
validadores y ejemplos de red escritos a mano, declarados en
[órdenes simuladas](ordenes-red-simuladas.md).
