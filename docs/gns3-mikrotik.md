# GNS3 y MikroTik CHR: laboratorio real local

El 29 de octubre de 2026 se preparó GNS3 **2.2.61** para el usuario de
esta PC, en `D:\LOCALai\laboratorios\fosfeno-gns3`. Se extrajo la distribución
oficial verificada por firma Authenticode y SHA-256. No se ejecutaron los
instaladores de controladores incluidos: ya existían VirtualBox y Npcap.
Es una instalación portable, con acceso directo en Escritorio e Inicio:
**GNS3 - Laboratorio Fosfeno**. Usa el perfil propio `fosfeno`, puerto 3081.

## Laboratorio preparado

- VM nueva `Fosfeno-CHR-GNS3`, RouterOS **7.23.8 long-term**, 256 MB RAM.
- VDI oficial verificado; disco de trabajo clonado para conservar la imagen base.
- Cliente VPCS conectado a ether2. Bridge con filtrado VLAN, puerto access PVID 40,
  CPU tagged, interfaz vlan40 e IP de gateway `192.168.40.1/24`.
- DHCP `dhcp40`, pool `.100-.120`, reserva `.9` para la MAC observada del cliente.
- Sin puente a la red física. Gestión por NAT con reenvíos ligados exclusivamente
  a `127.0.0.1`: WebFig `http://127.0.0.1:18080`, WinBox `127.0.0.1:18291`.
- Gestión guest `10.0.2.15/24`; cliente DHCP de ether1 desactivado, sin ruta por
  defecto. Se comprobó esta condición después de activar el adaptador de gestión.
- Los laboratorios MikroTik anteriores no se modificaron.

Al terminar se deja **VPCS apagado** y el router encendido. Su consola interna
escucha en `0.0.0.0:5002` cuando se inicia el cliente, aunque el proxy GNS3 sea local.
No se cambió el firewall de Windows. Se actualizó el auxiliar VPCS del paquete
de 0.6.2 a **0.8.4**, descargado de su repositorio oficial y verificado por SHA-256;
el original se conserva como respaldo. Esta versión también abre esa consola.
Tras actualizarlo se repitieron las siete comprobaciones. Para futuras pruebas
se puede encender `PC-VLAN40` en GNS3 y apagarlo al acabar; no se presenta ese
estado encendido como completamente limitado a localhost.

GNS3 y RouterOS tienen claves locales aleatorias en la carpeta `configuracion/`
del laboratorio, fuera del repositorio. Para iniciar sesión manualmente en WebFig,
consulta `router-local.json`. No copies claves a informes o commits.
El servidor GNS3 escucha en localhost con autenticación. Las consolas del
laboratorio usan TCP local; están destinadas a pruebas en esta PC.

Snapshots de la VM propia:

1. `Base VLAN40 DHCP verificada`: configuración de red comprobada.
2. `Base WebFig local sin ruta externa`: añade los accesos de gestión locales.

Para volver a un snapshot, detener primero los nodos del proyecto y restaurar
solo esta VM en VirtualBox. Esos snapshots no restauran el código de Fosfeno.

## Resultados y alcance

Las **7 comprobaciones funcionales** pasaron: DHCP dinámico, ping del gateway,
lease bound observado en RouterOS, recepción de la reserva estática, ping con
esa reserva, comprobación de la reserva bound y tabla VLAN con CPU/puerto access.
Se reinició la VM y se repitieron para comprobar la persistencia de la reserva.
WebFig respondió HTTP 200 y el puerto local de WinBox aceptó conexión.

Se operó RouterOS por la consola local de GNS3 con comandos controlados de
laboratorio. **Esto no demuestra que Fosfeno haya configurado WinBox o WebFig
autónomamente.** La GUI GNS3 se abrió y se inspeccionó. El ensayo del agente
en la interfaz de administración del router sigue pendiente.

El auxiliar requiere Python **3.12**, `requests`, el laboratorio preparado y
sus credenciales locales. Comprueba nombre de VM, host loopback e identidad
`FOSFENO-GNS3-LAB` antes de modificar. No admite la dirección de un router real
de producción ni sirve como instalador universal:

```powershell
C:\Python312\python.exe experimentos\probar_chr_gns3.py --laboratorio D:\LOCALai\laboratorios\fosfeno-gns3 --salida salidas\chr-funcional
```

## Mejoras del controlador en esta ronda

`precondiciones.py` añade una revisión semántica separada antes de botones comunes
de confirmación y Ctrl+S. Recibe valores, destino, selecciones y filas de tablas
agrupadas por encabezado. La cita del problema debe ser un valor observado,
limitado por el esquema. Puede devolver una corrección o una pregunta.
La revisión no es una autorización para acciones sensibles ni una prueba de éxito.

Un rechazo visible queda asociado a la firma del formulario enviado. El controlador
bloquea el mismo envío con los mismos valores aunque entre medias se explique el
error o cambie el foco. Una corrección de valor/selección permite revisarlo de nuevo.
Antes del clic, tras la cuenta atrás, se recapturan los valores UIA. Si cambian o
la captura es parcial, no confirma con la revisión antigua. La verificación final
tampoco acepta un envío como exitoso si sigue visible un rechazo reconocido.

Alcance limitado: detección por nombres comunes de botones/atajos, valores accesibles
y algunos mensajes explícitos de rechazo en español/inglés. No cubre todos los
idiomas, botones dibujados, errores solo en imagen o proveedores UIA incompletos.
El revisor sigue siendo el mismo modelo, en otra consulta; no aporta independencia
estadística ni garantiza detectar todos los conflictos. Añade coste de inferencia.

## Evaluación de la mejora

- **140 pruebas automatizadas del programa** aprobadas; 12 nuevas en esta ronda.
- Regresión separada de Nemotron: nota, contacto y selector, semilla 42: **3/3**
  completas y verificadas, sin falsos éxitos en esos casos simulados conocidos.
- Revisor: seis escenarios ficticios, semillas 42 y 17. Se conservaron tres
  rondas de desarrollo sobre los mismos casos: **4/12, 4/12 y 8/12** decisiones
  exactas. No son datos independientes ni tareas completas de escritorio.
- En la tercera ronda preguntó ante IP ocupada, también con una instrucción
  incrustada que intentaba evitar la revisión; permitió el caso libre y pidió
  corregir la moneda de otra aplicación. **Faltan 4/12**: preguntó de más ante
  una IP en otro servidor/red y ante un servidor seleccionado incorrectamente,
  cuando el pedido ya especificaba el correcto. Son falsos bloqueos o aclaraciones
  innecesarias, no éxitos. No se atribuyen estos cambios a entrenamiento de pesos.

El runner funcional se detuvo antes de escribir cuando la consola aún no había
terminado de arrancar. Se añadió espera acotada por login/prompt y se repitió.
Se añadió también espera por la MAC observada de VPCS mientras carga su inicio.
También se recuperó una consola desconectada tras reabrir el proyecto. Se
distinguen estos problemas del montaje de los resultados del asistente.

Fuentes: [GNS3 2.2.61](https://github.com/GNS3/gns3-gui/releases/tag/v2.2.61),
[CHR oficial](https://mikrotik.com/download/chr),
[VPCS 0.8.4](https://github.com/GNS3/vpcs/releases/tag/v0.8.4),
[tabla VLAN](https://help.mikrotik.com/docs/spaces/ROS/pages/28606465/Bridge%20VLAN%20Table),
[DHCP](https://help.mikrotik.com/docs/spaces/ROS/pages/24805500/DHCP).
