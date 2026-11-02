# Comprobación de uso real

2 de noviembre de 2026. Rama `nucleo/uso-real`, creada desde `nucleo/rapidez` en `e1edbc5`. Sin commit. Nemotron E4-64, json_schema, runtime b11946 y semillas 42/99.

## Cambios

- **Bucles:** el registro nativo de Untitled-1 contiene siete propuestas de clic, pero ninguna línea EJECUTADO ni OBSERVADO. La revalidación rechazaba el documento raíz antes de registrarlo en la traza; por eso el detector no podía contarlas. Ahora registra los rechazos y corta después de dos intentos sobre el mismo destino. La firma excluye datos auxiliares de cursor, formato y coincidencia; conserva los valores operativos.
- **NADA:** sin acciones ejecutadas no consulta al verificador. Si hay efectos anteriores pendientes, conserva esa comprobación. Prueba de integración con Nemotron real y percepción sustituida: una consulta, 2,125 s, tarea incompleta; no se aceptó un éxito ficticio.
- **Abrir aplicaciones:** se acepta Win como tecla independiente. Sin control visible, una petición explícita de abrir una aplicación inicia una ruta controlada: Win, búsqueda observada y enfocada, nombre, Enter solo con resultado único y espera hasta observar la ventana. No acepta rutas, URLs ni pedidos de abrir menús o documentos. La espera tiene límite; no reinicia la búsqueda en bucle. Los nombres deben coincidir con el resultado observado.
- **Ayudas:** selectores de ventana y texto permitido en `ayudas_aplicacion/ventanas.json`; instrucciones en `escritorio.md` y `calculadora.md`. La calculadora admite entrada aritmética completa sin campo editable, ligada a su ventana y revalidada antes de escribir. No permite saltos de línea ni texto arbitrario. Word conserva su ayuda condicional. INSTRUCCION solo incorpora instrucciones generales.
- **GUIAR:** la oferta conserva control y ventana. Ctrl+Alt+K vuelve a observar e identificar ese control, ejecuta un clic y termina, sin reinterpretar la pregunta. Funciona también en modo texto. Se rechazan ofertas caducadas, ventanas cambiadas y controles ambiguos. DECIR idénticos no se repiten aunque haya otra acción entre medias.

## Arnés antes y después

Ocho tareas por semilla, 16 ejecuciones por fila. Mismo motor, pesos, muestreo y caché desactivada. Se midió antes de editar y se repitió con las fuentes finales; las huellas coinciden con su manifiesto.

| Versión | Semilla 42 | Semilla 99 | Pasos/tarea | Tokens/consulta | Segundos/tarea | Consultas |
|---|---:|---:|---:|---:|---:|---:|
| Antes: nucleo/rapidez | 8/8 | 8/8 | 4.5000 | 128.73 | 9.98 | 94 |
| Después: nucleo/uso-real | 8/8 | 8/8 | 4.5625 | 127.45 | 11.76 | 96 |

Cero falsos éxitos aceptados y cero tareas fallidas en ambas filas. El arnés no se aceleró: navegación (42) necesitó un paso y dos consultas más; los demás cambios de consultas se compensan. El ahorro se aplica a los caminos NADA inicial, apertura sin control y confirmación de GUIAR, no a todos los recorridos del arnés. No se controlaron cargas ni temperatura del equipo.

## Casos nativos y alcance

La referencia aportada por el usuario es 6/12 intentos. No se repitió una matriz nativa completa de doce; no se calcula una nueva tasa global.

| Caso | Antes | Comprobación posterior |
|---|---|---|
| Untitled-1 | Siete propuestas de enfoque rechazadas, sin registro útil para el detector | Reproducción en tests de unidad e integración: dos rechazos registrados y corte antes del tercero. No se afirma haber habilitado la escritura en ese editor. |
| Configuración | NADA inicial | Flujo simulado completo con Nemotron real: correcto, Win → ESCRIBIR → Enter → ESPERAR → LISTO; dos consultas, 3,453 s. La herramienta no expuso una ventana controlable de Inicio/Configuración; falta la prueba nativa completa, incluida Pantalla. |
| Carpeta en escritorio | NADA inicial | Manual en Explorador, carpeta Escritorio: Ctrl+Shift+N, nombre y Enter crearon la carpeta; existencia comprobada. La carpeta temporal vacía se retiró. No fue una ejecución completa de Fosfeno. |
| Calculadora | Introdujo 185 en vez de 125 antes de multiplicar | Manual en la ventana real: entrada 125*8 y Enter mostraron 1.000. La transferencia posterior a Bloc de notas no se repitió. El camino de entrada directa del controlador pasa sus tests. |
| Guía de Guardar | Reinterpretaba la pregunta, repetía DECIR y acababa en Guardar como | Tests: un clic, cero consultas nuevas y sin tarea completa. Manual: Archivo abrió solo el menú. No se hizo una prueba completa del atajo global con voz. |

## Reproducir

```powershell
python -B servidores_lfm3.py --motor nemotron
```

En otra consola, desde la raíz, con una carpeta de salida nueva:

```powershell
python -B -m unittest discover -s tests -v
$env:FOSFENO_GBNF_EXPERIMENTAL = "0"
$env:FOSFENO_TIEMPOS_CRUDO = "0"
$env:FOSFENO_TIEMPOS_LOG = "salidas/uso-real/repeticion/pasos.jsonl"
python -B evaluacion.py --motores nemotron --semillas 42,99 --salida salidas/uso-real/repeticion
```

Pasan 209 tests. Cubren el bucle reproducido, NADA sin verificación inicial, la ruta de apertura y su espera/ambigüedad, ayudas condicionales, entrada aritmética sin foco editable y pérdida de ventana, repetición de DECIR y confirmación de guía con/sin voz.

Resultados y manifiestos definitivos: `salidas/uso-real/antes/` y `salidas/uso-real/final-controlado/`. Diagnóstico y comprobaciones: `comparacion-final.json`, `comprobaciones-nativas.json`, `configuracion-flujo-controlado.json` y `nada-control/` dentro de `salidas/uso-real/`. Las corridas intermedias también se conservan allí. Todo ese directorio está excluido de Git. La salida inicial del servidor apagado se conserva en el registro, pero no cuenta como medición.

Tokens/consulta incluye todas las consultas, revisiones y reintentos. Las medias incluyen pasos sin generación. Estas simulaciones no miden voz ni captura e inyección nativas.
