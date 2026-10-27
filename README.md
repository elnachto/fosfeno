# Fosfeno

Un asistente de escritorio **100 % local** para Windows: mantienes un atajo, le hablas, él mira tu pantalla, te señala dónde está lo que buscas y, si se lo pides, hace clic y escribe por ti. Lo acompaña una pequeña bolita animada con sus propias expresiones.

> Estado: proyecto experimental, en desarrollo. Funciona, pero comete errores. Léete la sección de [seguridad](#seguridad-y-privacidad) antes de dejarlo actuar solo.

La idea nace de la fantasía del asistente tipo **Jarvis** (un compañero que ve lo que ves y te ayuda a usar el computador), con una inspiración ligera en **Clicky** y en el estilo de animación de dos librerías de [libraries.dev](https://libraries.dev) (ver [créditos](#créditos-e-inspiración)).

![Expresiones](docs/expresiones.gif)

## Qué hace

- **Pregunta:** "¿qué significa este error?" responde con lo que ve en pantalla.
- **Guía:** "¿cómo abro una pestaña nueva?" te señala el botón con una animación y te ofrece hacerlo por ti.
- **Hazlo:** "abre WhatsApp y dile hola a Mamá" hace clic, escribe y pulsa teclas, paso a paso, con cuenta atrás y cancelación con `Esc`.
- **Aprende por demostración:** "mírame cómo se crea un usuario" observa lo que haces, limpia los errores y guarda una receta.
- **Explora una app:** "explora esta app" escribe un mapa de la ventana para ayudarte mejor la próxima vez.
- **Se corrige con la voz:** "no, era el botón de arriba" o "recuerda que aquí se guarda con Ctrl+S".
- **Se marea** si das muchas vueltas con el mouse.

![Mareo](docs/mareo.gif)

## Cómo funciona

1. Windows **UI Automation** lista los elementos reales de la ventana activa (botones, campos, pestañas, barra de tareas).
2. Cada elemento se numera sobre la captura de pantalla y la lista se envía a un modelo de visión **local** (Nemotron 3.5 Bolt E4B vía `llama-server`).
3. El modelo elige una acción: `CLIC n`, `ESCRIBIR texto`, `TECLA x` o `LISTO`. Un clasificador previo decide si lo que dijiste es una pregunta, una guía o una orden.
4. La voz se transcribe con `faster-whisper` en la CPU.
5. Una capa transparente en PySide6 dibuja la bolita, las señales y los mensajes, con un efecto gooey (desenfoque + contraste) propio.

Todo corre en tu máquina. Nada sale a internet.

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior.
- GPU NVIDIA con **8 GB de VRAM** o más. El modelo cuantizado (Q4) ocupa unos 4,7 GB, el `mmproj` 0,9 GB y el contexto de 16K unos 1-2 GB más, así que en total usa entre 6 y 7 GB. Se probó con una RTX 5070 de 12 GB.
- 8 GB de RAM como mínimo (16 GB recomendados). La voz (`faster-whisper`, modelo `small`) corre en la CPU y usa cerca de 1 GB.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) con `llama-server` compilado con CUDA.
- Modelo y visión, en GGUF: `NVIDIA-Nemotron-3.5-Bolt-E4B-UD-Q4_K_XL.gguf` y `mmproj-F16.gguf` (o `mmproj-Q8_0.gguf`, que pesa la mitad).

Con menos de 8 GB de VRAM baja el contexto (`-c 8192`) y usa el `mmproj` Q8.

## Instalación

```
git clone https://github.com/elnachto/fosfeno.git
cd fosfeno
python -m pip install -r requirements.txt
copy config.ejemplo.json config.json
copy vocabulario.ejemplo.txt vocabulario.txt
copy correcciones.ejemplo.txt correcciones.txt
```

Arranca el servidor del modelo en otra ventana (ajusta las rutas):

```
llama-server -m RUTA\NVIDIA-Nemotron-3.5-Bolt-E4B-UD-Q4_K_XL.gguf --mmproj RUTA\mmproj-F16.gguf -ngl 99 -c 16384 -np 1 -fa on --jinja --host 127.0.0.1 --port 8095
```

Y luego:

```
python jarvis.py
```

## Uso

| Atajo | Acción |
|---|---|
| `Ctrl+Alt+J` | Empieza a escuchar; al pulsar otra vez termina y decide qué hacer |
| `Ctrl+Alt+K` | Fuerza el modo "hazlo"; también confirma una guía |
| `Esc` | Cancela antes de cada clic |

Otras formas de ejecutarlo:

- `python jarvis.py --texto` escribes la orden en la consola en vez de hablar.
- `python demo.py` solo muestra las animaciones, sin modelo ni micrófono.

Cosas para probar:

- "¿Qué es esto que veo?" / "Explícame esta página"
- "¿Cómo abro una pestaña nueva?"
- "Abre una pestaña nueva y busca el clima en La Paz"
- "Explora esta app" y luego pídele algo en esa app
- "Mírame cómo envío un mensaje aquí" y, después, "envía un mensaje que diga hola"
- "Olvida eso" / "¿Qué aprendiste aquí?"

## Configuración

`config.json` (no se sube al repositorio):

| Clave | Para qué sirve |
|---|---|
| `mic` | Micrófono elegido (se guarda solo) |
| `modelo` | Modelo de Whisper: `small` por defecto |
| `tecla`, `tecla_actuar` | Letras de los atajos |
| `buddy` | Muestra la bolita en reposo |
| `tema` | `claro` u `oscuro` |

## Seguridad y privacidad

- **Puede hacer clic y escribir como si fueras tú.** Úsalo en ventanas donde un error no cause daño. Todavía no pide confirmación antes de acciones sensibles (enviar, borrar, pagar); está en la lista de pendientes.
- El texto y los nombres de la pantalla se tratan como **datos, nunca como órdenes**; solo cuenta lo que dices tú. Aun así, un modelo pequeño puede equivocarse.
- Lo que aprende se guarda en `conocimiento/` (recetas y notas por app) y puede incluir texto que escribas o nombres que vea. **Está excluido de git** salvo la nota de ejemplo de Visual Studio Code. Revísalo antes de compartirlo.
- "Mírame" no guarda el contenido de campos de contraseña.
- `salidas/` guarda capturas y registros de cada paso para depurar; también está excluida.

## Estructura

| Archivo | Qué hace |
|---|---|
| `jarvis.py` | Programa principal: atajos, flujo y decisiones |
| `marcas.py` | Lee la pantalla, arma la lista numerada y habla con el modelo |
| `overlay.py` | La bolita, las expresiones y el efecto gooey |
| `acciones.py` | Clic, teclas y escritura con `SendInput` |
| `voz.py` | Micrófono y transcripción |
| `memoria.py` | Recetas, notas y correcciones |
| `mirame.py` | Grabación de demostraciones |
| `demo.py` | Muestra las animaciones |

## Créditos e inspiración

- **Jarvis**: la idea general del asistente que ve tu pantalla. Es un personaje de ficción de Marvel; este proyecto no tiene ninguna relación con Marvel.
- **Clicky** (Farza): inspiración ligera para el flujo de "mantén un atajo, habla y te señala dónde está". No se usó su código.
- **[liquid-gooey](https://libraries.dev/gooey)** (MIT): la técnica del efecto gooey (desenfoque gaussiano y contraste con un valor de corte) y los valores por defecto de desenfoque, contraste y resortes se tomaron de su código. Esta versión es una reimplementación propia en Python y Qt, no usa el paquete.
- **[thinking-orbs](https://libraries.dev/orbs)** (MIT): la bolita muestra una esfera de puntos al escuchar ("onda") y otra al pensar ("globo"), basadas en las animaciones de esa librería, reescritas en Python.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) para la transcripción y [llama.cpp](https://github.com/ggml-org/llama.cpp) para servir el modelo.
- El modelo de visión es NVIDIA Nemotron; revisa su licencia antes de usarlo o redistribuirlo.

## Licencia

MIT. Ver [LICENSE](LICENSE).
