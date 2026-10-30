# Órdenes MAC/IP/VLAN: prueba de comprensión

Se pidió al agente actual crear dos reservas DHCP en un formulario simulado,
con valores nuevos y servidores de nombres opacos. El servidor inicialmente
seleccionado era de otra VLAN. Las opciones visibles declaraban qué servidor
atendía cada VLAN y subred; no había un campo VLAN que el modelo solo copiara.
Los IDs de controles cambiaban durante la ejecución.

No se añadieron notas, recetas, ejemplos o reglas al controlador. Sí se conservaron
sus prompts existentes, que contienen conocimiento manual de redes. La simulación
no representa percepción de WinBox: entrega controles y valores textualmente,
como si fueran accesibles por UIA. No controla la PC ni modifica un router.

## Resultados de la muestra

- Dos reservas explícitas: 2/2 guardadas con MAC, IP y servidor correctos, ocho
  pasos cada una. Cero falsos éxitos aceptados en esas dos simulaciones.
- Orden ambigua sobre IP de VLAN y dispositivo fijo: propuso abrir direcciones
  de interfaces sin pedir aclaración. No se ejecutó esa propuesta. La distinción
  IP de interfaz frente a reserva de dispositivo sigue fallando con esa redacción.
- Conflicto de IP con otra MAC: el revisor detuvo la confirmación y preguntó,
  pero ofreció sobrescribir pese a la orden de conservar las reservas. El bloqueo
  es útil; la pregunta no respeta la restricción y no cuenta como éxito completo.

No se corrigieron los prompts después de observar esos fallos para hacer pasar
esta muestra. Los resultados completos, preguntas y ayudas se guardan por separado.

## Auditoría de conocimiento de aquella ronda

Esta sección describe el código usado en ese ensayo histórico. La limpieza de
[aprendizaje general](aprendizaje-general.md) retiró después esas reglas del
asistente y trasladó los validadores a `experimentos/parametros_red.py`. Ejecutar
de nuevo el experimento utiliza el controlador actual y no reproduce los prompts
ni las garantías de aquella versión.

En la memoria activa se encontraron notas de VS Code y WhatsApp y doce recetas,
sin notas ni recetas relacionadas con MikroTik/WinBox/RouterOS/DHCP/VLAN.
Eso no significa ausencia de conocimiento añadido a mano en el programa:

- `parametros.py` reconoce y valida MAC, IPv4 y VLAN y diferencia tipos de operación
  al reutilizar plantillas. En esta prueba la extracción se registró después de la
  ejecución, no se proporcionó como referencia al agente.
- `agente.py` pide aclarar operaciones ambiguas y no inferir un servidor DHCP de
  un identificador VLAN sin evidencia.
- `precondiciones.py` contiene ejemplos DHCP de conflicto, conservación y destino,
  afinados con ensayos anteriores. Este revisor intervino en la simulación.
- Hay documentación, simuladores y scripts específicos de MikroTik en el
  laboratorio. No se cargan automáticamente como recetas en esta prueba.

El modelo puede traer además conocimiento previo de redes por su entrenamiento;
este ensayo no permite separar esa contribución de las ayudas del programa.
No se afirma «conocimiento cero», «cero hardprompting» ni dominio general de WinBox.

## Reproducción

```powershell
cd D:\LOCALai\clicky
python experimentos/evaluar_orden_red.py --salida salidas\orden-red
```

La semilla de datos de esta ronda fue `1635450297`; para repetir sus valores,
añadir `--semilla-datos 1635450297`. Los valores esperados solo se usan en la
evaluación externa y se guardan antes de consultar al modelo, no se envían como
respuesta objetivo. Se utiliza Nemotron y semilla de generación 42.

Sigue faltando desambiguación fiable y respeto de restricciones en las preguntas
de recuperación. La escritura y el aprendizaje visual del piloto OCR permanecen
bloqueados; los guardados descritos aquí existen únicamente en memoria del simulador.
