# Tutor experimental de aplicaciones

`tutor_experimental.py` es un prototipo separado del asistente de voz. Genera
explicaciones en español y consulta manuales locales HTML, TXT o Markdown.
No controla la interfaz ni se activa desde los atajos de Fosfeno. No busca
en Internet, no lee PDF y no recorre subcarpetas del directorio indicado.

El modelo elige hasta cuatro archivos de un catálogo observado y hasta tres
consultas en inglés. La recuperación limita a seis fragmentos, dos por archivo,
con texto anterior para conservar el contexto. Los resultados incluyen las
fuentes, sus hashes, la configuración propuesta, el modelo que respondió y los
tiempos. Las referencias se tratan como datos, no como instrucciones.

## Uso

Con Nemotron disponible en el servidor configurado:

```powershell
python tutor_experimental.py --manuales "C:\Program Files\Cisco Packet Tracer 8.2.2\help\default" --app "Cisco Packet Tracer" --pregunta "Explícame cómo crear una LAN pequeña con dos PCs y un switch y cómo comprobarla" --salida salidas/leccion.json
```

`--sin-manuales` permite una explicación de control sin recuperación documental.
`--observaciones` recibe texto sobre el estado observado; el prototipo no lo
captura por sí mismo. `--restricciones archivo.json` recibe límites explícitos:

```json
{
  "equipos_permitidos": ["PC0", "PC1", "Switch0"],
  "configuracion_fija": {
    "PC0": {"ipv4": "192.168.1.1", "mascara": "255.255.255.0", "gateway": "0.0.0.0"}
  }
}
```

Las reglas rechazan referencias inexistentes, equipos fuera de la lista,
configuraciones duplicadas y cambios en campos fijos de la **tabla propuesta**.
Una tabla puede omitir equipos que no se propone cambiar. Los nombres deben
coincidir exactamente. En gateway, vacío y `0.0.0.0` equivalen a ausencia de
gateway para estos ejemplos. Estas reglas no interpretan toda la prosa.

Una respuesta bloqueada también se guarda y el programa termina con código 2.
`REGLAS_SUPERADAS_NO_VERIFICADA` solo significa que superó esas reglas: no
demuestra corrección técnica ni éxito en la aplicación. Toda lección conserva
`PROPUESTA_NO_PROBADA`.

`--revision-modelo` añade una segunda lectura crítica con el mismo modelo.
Es opcional porque produjo falsos rechazos y citas inválidas incluso al revisar
una corrección que funcionó. No constituye una verificación independiente.

## Experimento del 28 de octubre de 2026

Se usó Nemotron, semilla 42, contexto 16384 y solicitudes consecutivas. Los
guiones `experimentos/evaluar_tutor.py` y `evaluar_revision_tutor.py` conservan
condiciones y registros. La revisión fue retrospectiva sobre ejemplos conocidos
durante el desarrollo; no es una prueba independiente de generalización.

| Prueba | Resultado y alcance |
|---|---|
| Tres diagnósticos textuales, con/sin manuales | Ambas condiciones identificaron subredes distintas, IP duplicada y falta de evidencia. Las respuestas documentadas tuvieron errores de citas y detalles; no se califican como seis éxitos completos. |
| Red real en Packet Tracer 8.2.2 | Dos PCs y un 2960: PDU Successful; cambio de IP de PC1 a otra subred: Failed; corrección sugerida sin manuales: Successful. Después de guardar y reabrir, una PDU nueva volvió a Successful. |
| Diagnóstico documentado del fallo real | Propuso añadir router y cambiar PC0, incumpliendo la petición. Se rechazó sin aplicarlo. |
| Revisor del mismo modelo, dos versiones | Detectó la propuesta prohibida, pero ambas versiones bloquearon también la corrección válida. Se dejó opcional. |
| Nueva generación con límites explícitos | Superó reglas de la tabla, pero siguió afirmando en la prosa que hacía falta router. Demuestra que las reglas no garantizan una solución correcta. |

Las acciones nativas las ejecutó Codex mediante control de la PC, interpretando
las instrucciones y completando navegación que la lección omitía. Nemotron
recibió observaciones textuales; no eligió cada clic ni se evaluó aquí su visión.
No se evaluaron en esta ronda audio, atajos o autonomía completa de Fosfeno.

La lección inicial también recomendó cable cruzado PC-switch y citó un ejemplo
de otro tipo de conexión. La red construida funcionó con ese cable; esto no
valida su recomendación ni sus citas. La ayuda oficial distingue conexiones
PC-switch y PC-servidor. Ver [Connections / Links](https://tutorials.ptnetacad.net/help/default/connectionsLinks.htm),
[primer laboratorio](https://tutorials.ptnetacad.net/help/default/myFirstPTLab.htm)
y [modo simulación](https://tutorials.ptnetacad.net/help/default/mode_simulation.htm).

Este experimento muestra una corrección funcional concreta y fallos importantes
de explicación y recuperación documental. Antes de integrar el tutor al flujo
de voz hacen falta pruebas nuevas, mejores límites sobre la prosa y verificación
del resultado dentro de cada aplicación. No demuestra soporte para cualquier app.
