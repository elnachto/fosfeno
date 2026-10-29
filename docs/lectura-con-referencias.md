# Lectura visual con referencias

Esta segunda ronda reemplaza la aprobación libre de una respuesta OCR por una
selección de fuentes y una reconstrucción literal. No cambia los pesos del modelo.
Está dentro del modo experimental, que sigue desactivado por defecto.

## Cómo funciona

1. OCR detecta texto y rectángulos en la captura actual.
2. `lectura_visual.py` agrupa filas por posición y crea hipótesis de tablas con
   contexto, encabezados y celdas. Comprueba alineación, columnas intermedias,
   referencias existentes y ausencia de reutilización. No es un detector infalible
   de paneles: un contexto cercano también puede ser una etiqueta ajena.
3. Prioriza contextos que comparten palabras con el pedido. Esa recuperación usa
   texto visible, sin un diccionario de aplicaciones ni de valores esperados.
4. Nemotron selecciona identificadores de esas hipótesis, o textos aislados cuando
   no puede establecer una relación. No escribe los valores finales.
5. El programa vuelve a validar las referencias y construye la respuesta con sus
   literales. Conserva puntos suspensivos y señala que el valor completo se desconoce.

Una frase propuesta por el modelo queda en la traza como no verificada y no se
entrega directamente. Un booleano de confianza ya no basta. Los fragmentos sin
tabla se presentan explícitamente como textos aislados; pueden ser irrelevantes
para la pregunta. No equivalen a una tarea completada.

La selección admite una tabla por respuesta, seis columnas y cuatro filas por
hipótesis. Suponen encabezados horizontales y un contexto cercano, por encima y
alineado hacia la izquierda. Pueden producir hipótesis falsas o rechazar tablas
válidas. No prueban por sí solas pertenencia a una ventana, semántica ni exactitud
de OCR, y no comprueban filas ocultas o fuera de la captura.

## Prompts, reglas y transparencia

Sí hay prompts y reglas. No sería correcto afirmar «cero hardprompting».
El agente ya tenía una regla para no inferir un servidor DHCP a partir de una VLAN;
`precondiciones.py` conserva ejemplos DHCP desarrollados con casos anteriores.
`parametros.py` reconoce operaciones de reserva e IP de interfaz. Son conocimientos
y validaciones específicos del dominio, no una prueba de generalización.

La nueva lectura no contiene nombres de WinBox/MikroTik, rutas de menús, IP, MAC,
nombres de servidores ni respuestas del laboratorio. Tampoco obliga a abrir
IP/Addresses/DHCP Server. Geometría, límites y formatos son reglas del programa.
Los valores del oráculo de evaluación se guardan aparte y no se pasan al modelo.

Los ensayos de esta ronda son lecturas de capturas fijas: una captura real de
WinBox ya conocida y dos interfaces sintéticas con valores nuevos, generadas
después de implementar el lector. Hubo ajustes durante el desarrollo y se guardan
las versiones fallidas. No son un benchmark ciego, apps nuevas reales ni pruebas
de voz o de acciones sobre el escritorio.

La versión final pasó 179 pruebas del programa y la regresión conocida de
nota/contacto/selector: 3/3. En la captura guardada de WinBox, tanto el lector
como el controlador devolvieron dhcp40/vlan40; la propuesta adversarial incorrecta
no sustituyó esos valores. Las dos tablas sintéticas conservaron sus cinco filas
y quince valores. Ante IPv4 no visible, el lector final se abstuvo. La tarea
compuesta completa no se volvió a ejecutar. Se conservan también tres rechazos
iniciales, una duplicación de contexto y un agotamiento de salida previo al
protocolo final de cuatro identificadores enteros.

La selección final usa `tabla`, `texto1`, `texto2`, `texto3`, con cero como ausencia.
Esto limita el formato de respuesta, no impone qué tabla ni qué valores elegir.

## Qué se puede probar

Con la vista de servidores DHCP visible, pedir «Lee el nombre del servidor DHCP y
su interfaz» es una prueba razonable de lectura. La navegación experimental de la
ronda anterior permanece disponible. Crear reservas, cambiar IP y aprender nuevos
procedimientos visuales siguen bloqueados. La tarea completa de IPv4 más DHCP aún
requiere navegar, tratar columnas cortadas y conservar datos entre vistas.

Activación en la PC del laboratorio:

```powershell
cd D:\LOCALai\clicky
$env:FOSFENO_VISION_EXPERIMENTAL = '1'
& 'D:\LOCALai\laboratorios\fosfeno-gns3\vision-env\Scripts\python.exe' .\jarvis.py --motor nemotron
```

El entorno privado ya tiene OCR y hereda las dependencias normales. Cerrar ese
proceso y abrir el lanzador habitual devuelve al modo normal; no se cambia la
configuración global. No abrir varias instancias que compitan por los atajos.

## Próximos problemas

- Separar paneles y distinguir encabezados, pestañas y botones con más evidencia.
- Leer celdas cortadas, recorrer tablas largas y manejar iconos sin texto.
- Verificar foco antes de habilitar escritura o edición visual.
- Conservar hechos entre vistas con procedencia comprobable y una respuesta final
  que no marque un pedido compuesto como completo por una lectura parcial.
