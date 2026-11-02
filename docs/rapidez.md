# Rapidez de Nemotron

Mediciones locales del 1–2 de noviembre de 2026 en Windows 11, Python 3.12.10 y llama.cpp b11946 (8ca4060b7), con Nemotron 3.5 Bolt E4B UD-Q4_K_XL y su proyector. Rama: `nucleo/rapidez`.

## Hallazgo y decisión

El razonamiento oculto suponía aproximadamente el 60–80 % de los tokens. Doce respuestas retokenizadas mediante `POST /tokenize` contenían 55–78 tokens de JSON, 107–306 de `reasoning_content` y 10 de control. Acortar solo los campos redujo el tiempo de 17,81 a 16,27 s/tarea (8,62 %).

La plantilla Gemma 4 reconoce `enable_thinking=false`, pero omitir `<|think|>` no impide el canal thought. `--no-reasoning-preserve` tampoco limita la generación actual. El presupuesto del servidor sí la limita; GBNF directa la evita, pero pierde aciertos.

Se adopta **E4-64**: `--reasoning-budget 64` en el arranque de Nemotron, junto a `--no-reasoning-preserve`; `json_schema` por defecto; propiedades y campos obligatorios de acciones en orden `evidencia, objetivo_pendiente, accion, n, texto, reemplazar`. Los límites son 80/60 caracteres; la verificación independiente conserva sus límites largos y su orden. El prompt y sus ejemplos conservan el texto medido durante el aislamiento.

Regresión conocida: navegación falla con semillas 7 y 11. GBNF requiere `FOSFENO_GBNF_EXPERIMENTAL=1` y solo afecta a Nemotron; LFM3 conserva json_schema y su orden original.

## Variantes finales

Ocho tareas por semilla: 42/99 suman 16 ejecuciones. E1–E4 usan json_schema; E5 usa GBNF sin presupuesto. E3 usa pensamiento vacío mediante prefill. Se conservaron prompt, límites, controlador, pesos, contexto 16384, muestreo y caché desactivada.

| Variante: presupuesto y orden | Semilla 42 | Semilla 99 | Pasos/tarea | Tokens/consulta | Segundos/tarea | Falsos éxitos |
|---|---:|---:|---:|---:|---:|---:|
| E1: 0, acción primero | 4/8 | 5/8 | 4.94 | 82.26 | 8.92 | 2 |
| E2: 0, observación primero | 6/8 | 8/8 | 4.50 | 70.57 | 7.02 | 1 |
| E3: prefill vacío, observación primero | 7/8 | 8/8 | 5.12 | 73.13 | 8.61 | 0 |
| E4-64: 64, observación primero | 8/8 | 8/8 | 4.50 | 128.73 | 10.00 | 0 |
| E4-128: 128, observación primero | 8/8 | 8/8 | 4.50 | 180.21 | 12.41 | 0 |
| E5: GBNF, observación primero | 7/8 | 8/8 | 5.19 | 43.62 | 6.59 | 0 |

Referencia original 42/99: 16/16, 4,50 pasos/tarea, 278,54 tokens/consulta y 17,81 s/tarea. Salida corta con razonamiento completo: 16/16, 4,50 pasos/tarea, 247,55 tokens/consulta y 16,27 s/tarea.

Fallos: E1, navegación (42), selector (42/99), chat (42/99), checkbox (42/99); E2, navegación y checkbox (42); E3, navegación (42); E5, navegación (42). En E5 el efecto real estaba logrado, pero la evidencia vacía impidió confirmar LISTO. E4-64 y E4-128 no fallaron en 42/99. No hubo truncamientos en esta matriz.

## Comprobación con nuevas semillas

Original (7) usó fuentes archivadas verificadas contra el manifiesto: esquema largo, máximo 1200 y razonamiento completo. E4-64 (11) usó la configuración adoptada real.

| Configuración, semilla | Aciertos | Pasos/tarea | Tokens/consulta | Segundos/tarea |
|---|---:|---:|---:|---:|
| Original, 7 | 8/8 | 4.50 | 276.74 | 18.60 |
| Original, 42 | 8/8 | 4.50 | 288.40 | 18.60 |
| Original, 99 | 8/8 | 4.50 | 268.24 | 17.02 |
| E4-64, 7 | 7/8 | 4.75 | 130.66 | 10.65 |
| E4-64, 11 | 7/8 | 5.75 | 130.92 | 14.36 |
| E4-64, 42 | 8/8 | 4.50 | 129.00 | 10.01 |
| E4-64, 99 | 8/8 | 4.50 | 128.47 | 9.98 |
| Original, acumulado | 24/24 | 4.50 | 277.94 | 18.07 |
| E4-64, acumulado | 30/32 | 4.88 | 129.88 | 11.25 |

Navegación (7) pasa en el original. E4-64 escribe antes de crear el destino nuevo y pierde ese valor; con semilla 11 repite LISTO hasta agotar pasos. La verificación rechaza ambos fallos: cero falsos éxitos aceptados en las cuatro semillas. Los acumulados tienen distintos conjuntos de semillas.

## Ensayo del prompt general

Se añadieron únicamente tres instrucciones generales: preparar el destino y volver a observar foco/valores tras cambiar de contexto; cerrar con LISTO cuando todos los efectos estén observados; identificar evidencia concreta no vacía antes del veredicto. No se añadieron reglas por aplicación ni se cambió el esquema del verificador.

| E4-64, semillas 42/99 | Aciertos | Pasos/tarea | Tokens/consulta | Segundos/tarea |
|---|---:|---:|---:|---:|
| Prompt anterior | 16/16 | 4.50 | 128.73 | 10.00 |
| Candidato general | 16/16 | 4.50 | 122.38 | 10.29 |

Se revirtió el candidato por no mejorar aciertos ni tiempo; el agente quedó idéntico al anterior. Validación final: 191 tests pasan.

## Reproducir

Desde la raíz del repositorio, en una consola para el servidor y otra para las pruebas:

```powershell
python -B servidores_lfm3.py --motor nemotron
```

Cerrar un servidor antiguo en 8095 antes de iniciar: el lanzador reutiliza servidores activos. El cliente avisa si detecta más de 66 tokens de razonamiento o no puede comprobarlo. Prueba real: 134 tokens con aviso; 63 sin aviso.

```powershell
python -B -m unittest discover -s tests -v
$env:FOSFENO_GBNF_EXPERIMENTAL = "0"
$env:FOSFENO_TIEMPOS_CRUDO = "0"
$env:FOSFENO_TIEMPOS_LOG = "salidas/rapidez/repeticion/pasos.jsonl"
python -B evaluacion.py --motores nemotron --semillas 42,99,7,11 --salida salidas/rapidez/repeticion
```

Usar una carpeta de salida nueva. El arnés imprime métricas por tarea y guarda resultados y manifiesto. Para repetir la matriz completa:

```powershell
python -B experimentos/evaluar_rapidez_variantes.py --salida salidas/rapidez/aislamiento-repeticion
```

El ejecutor separa variantes, impide sobrescrituras y restaura E4-64 y la plantilla original. Añade semilla 7 a variantes con 16/16 y menos de 11 s/tarea. LFM3 (8096) no recibe el presupuesto: su comprobación previa fue 3/3 JSON válidos, sin repetir su matriz completa.

`FOSFENO_TIEMPOS_CRUDO=1` guarda las primeras doce respuestas de acción completas del proceso y sus conteos en `salidas/rapidez/crudo/`. Dejarlo en 0 al medir. Los registros por paso contienen captura/percepción, preparación local, prompt/generación del servidor, tokens, acción y consultas.

Datos locales en `salidas/rapidez/`, carpetas `linea-base/`, `diagnostico/`, `aislamiento/` y `adopcion-e4/`: fuentes, manifiestos, respuestas y resultados, fuera de Git. Para repetir exactamente el original se necesitan sus fuentes archivadas; el código actual usa E4-64.

Tokens/consulta incluye revisión, verificación y reintentos. Las medias incluyen fallos. Son ocho objetivos simulados: las semillas cambian orden e identificadores, no objetivos. No se miden voz, captura real ni entrada nativa; tampoco se controlaron cargas y temperatura. Las corridas nuevas incluyen la comprobación del presupuesto en el cliente.
