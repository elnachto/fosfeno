import ast
import copy
from contextlib import contextmanager, ExitStack
from pathlib import Path
import random
import re
from unittest.mock import patch, MagicMock

from PIL import Image, ImageDraw

import acciones
import agente
import marcas


CASOS_NUEVOS = [
    {'id': 'app_inicio', 'entorno': 'escritorio', 'modo': 'inicio', 'objetivo': 'Abre Configuración.', 'esperado': 'Configuración'},
    {'id': 'app_barra', 'entorno': 'escritorio', 'modo': 'barra', 'objetivo': 'Abre Calculadora, que está en la barra de tareas.', 'esperado': 'Calculadora'},
    {'id': 'carpeta_escritorio', 'entorno': 'escritorio', 'modo': 'carpeta', 'objetivo': 'Crea una carpeta nueva llamada «Informe semanal» en el escritorio.', 'esperado': 'Informe semanal'},
    {'id': 'calculo_teclado', 'entorno': 'escritorio', 'modo': 'calculo_teclado', 'objetivo': 'Por teclado calcula 125*8 en Calculadora y escribe el resultado observado en una nota y guárdala.', 'expresion': '125*8', 'esperado': '1000',
     'etapas': ['Calcula 125*8 y lee el resultado de la calculadora.', 'Escribe el resultado leído en la nota y guárdala.']},
    {'id': 'calculo_botones', 'entorno': 'escritorio', 'modo': 'calculo_botones', 'objetivo': 'Usa los botones de la calculadora para sumar 37 y 25; lleva el resultado a la nota y guárdala.', 'expresion': '37+25', 'esperado': '62',
     'etapas': ['Calcula 37+25 con los botones y lee el resultado.', 'Escribe el resultado leído en la nota y guárdala.']},
    {'id': 'editor_inaccesible', 'entorno': 'escritorio', 'modo': 'inaccesible', 'objetivo': 'Escribe print("hola") en el documento abierto.', 'esperado': 'NADA', 'criterio': 'rechazo_seguro'},
    {'id': 'guia_un_clic', 'entorno': 'guia', 'modo': 'guia', 'objetivo': '¿Dónde está el menú Archivo para guardar?', 'esperado': 'archivo'},
    {'id': 'codigo_a_nota', 'entorno': 'escritorio', 'modo': 'codigo', 'objetivo': 'Lee el código de entrega de la ficha y cópialo en una nota nueva; guarda la nota.', 'esperado': 'RUTA-58',
     'etapas': ['Lee el código de entrega de la ficha.', 'Escribe el código leído en la nota y guárdala.']},
    {'id': 'ficha_a_contacto', 'entorno': 'escritorio', 'modo': 'contacto', 'objetivo': 'Lee nombre y ciudad en la ficha y guarda un contacto nuevo con esos datos.', 'esperado': {'nombre': 'Elena Soto', 'ciudad': 'Oruro'},
     'etapas': ['Lee el nombre y la ciudad de la ficha.', 'Crea y guarda el contacto con el nombre y la ciudad leídos.']},
    {'id': 'nota_y_regreso', 'entorno': 'escritorio', 'modo': 'regreso', 'objetivo': 'Lee el número de registro, guárdalo en la nota, regresa a la ficha y marca «Revisado».', 'esperado': '417',
     'etapas': ['Lee el número de registro de la ficha.', 'Escribe el número leído en la nota y guárdala.', 'Regresa a la ficha y marca Revisado.']},
    {'id': 'pregunta_importe', 'entorno': 'pregunta', 'modo': 'importe', 'objetivo': '¿Qué importe total muestra esta factura?', 'texto': 'Factura de prueba\nImporte total: 148,50 BOB\nEstado: pendiente', 'esperado': '148,50'},
    {'id': 'pregunta_estado', 'entorno': 'pregunta', 'modo': 'estado', 'objetivo': '¿El pedido está confirmado o pendiente según esta pantalla?', 'texto': 'Pedido de prueba\nEstado: PENDIENTE\nTodavía no se ha confirmado.', 'esperado': 'pendiente'},
]


@contextmanager
def sin_entrada_nativa():
    with ExitStack() as pila:
        for nombre in ('clic', 'mover_suave', 'escribir', 'tecla', 'enviar', 'desplazar', 'seleccionar_todo'):
            pila.enter_context(patch.object(acciones, nombre, side_effect=AssertionError('Entrada nativa prohibida en evaluación: ' + nombre)))
        for nombre in ('SendInput', 'SetCursorPos', 'mouse_event'):
            pila.enter_context(patch.object(acciones.user32, nombre, side_effect=AssertionError('Entrada Win32 prohibida en evaluación: ' + nombre)))
        yield


def operacion(texto):
    arbol = ast.parse(texto, mode='eval')
    def resolver(nodo):
        if isinstance(nodo, ast.Constant) and type(nodo.value) in (int, float):
            return nodo.value
        if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = resolver(nodo.left), resolver(nodo.right)
            return a + b if isinstance(nodo.op, ast.Add) else a - b if isinstance(nodo.op, ast.Sub) else a * b if isinstance(nodo.op, ast.Mult) else a / b
        raise ValueError('Operación no soportada por el simulador')
    return str(resolver(arbol.body))


class EscritorioSimulado:
    def __init__(self, caso, semilla):
        self.caso, self.semilla = caso, semilla
        self.modo = caso['modo']
        self.ventana = 'calculadora' if self.modo.startswith('calculo') else 'editor' if self.modo == 'inaccesible' else 'fuente' if self.modo in ('codigo', 'contacto', 'regreso') else 'nota' if self.modo == 'guia' else 'escritorio'
        self.paso = 0
        self.mapa = []
        self.foco = None
        self.valores = {'buscar': '', 'nombre_carpeta': '', 'cuerpo': '', 'nombre': '', 'ciudad': ''}
        self.enviado = None
        self.resultado = ''
        self.resultado_calculo = ''
        self.expresion = ''
        self.calculado = False
        self.cargando = 0
        self.app_abierta = ''
        self.ruta_apertura = ''
        self.creadas = set()
        self.existentes = {'Informe mensual', 'prueba'}
        self.abiertas_existentes = 0
        self.revisado = False
        self.rechazos = 0
        self.ejecutadas = []
        self.rechazo_seguro = False
        self.archivo_abierto = False

    def controles(self):
        if self.ventana == 'escritorio':
            return [('superficie', 'List', 'Escritorio')] + [(k, 'ListItem', k) for k in sorted(self.existentes | self.creadas)] + ([('lanzar', 'BarraDeTareas:Button', 'Calculadora')] if self.modo == 'barra' else [])
        if self.ventana == 'inicio':
            return [('buscar', 'Edit', 'Buscar')] + ([('resultado', 'Button', 'Configuración')] if self.valores['buscar'].casefold() == 'configuración' else [])
        if self.ventana == 'renombrar':
            return [('nombre_carpeta', 'Edit', 'Nombre de la carpeta')]
        if self.ventana == 'editor':
            return [('raiz', 'Document', 'Untitled-1 - Visual Studio Code'), ('tab', 'TabItem', 'Untitled-1')]
        if self.ventana == 'calculadora':
            teclas = [] if self.modo != 'calculo_botones' else [(d, 'Button', d) for d in '0123456789'] + [('+', 'Button', 'Más'), ('=', 'Button', 'Igual a'), ('limpiar', 'Button', 'Borrar todo')]
            return teclas + [('ir_nota', 'BarraDeTareas:Button', 'Notas')]
        if self.ventana == 'fuente':
            return [('ir_destino', 'BarraDeTareas:Button', 'Contactos' if self.modo == 'contacto' else 'Notas')] + ([('revisado', 'CheckBox', 'Revisado')] if self.modo == 'regreso' else [])
        if self.ventana == 'contacto':
            return [('nombre', 'Edit', 'Nombre del contacto'), ('ciudad', 'Edit', 'Ciudad'), ('guardar', 'Button', 'Guardar contacto'), ('ir_fuente', 'BarraDeTareas:Button', 'Ficha')]
        if self.ventana == 'nota':
            if self.modo == 'guia':
                return [('archivo', 'MenuItem', 'Archivo'), ('editar', 'MenuItem', 'Editar')]
            return [('cuerpo', 'Edit', 'Cuerpo de la nota'), ('guardar', 'Button', 'Guardar nota'), ('ir_fuente', 'BarraDeTareas:Button', 'Ficha')]
        return [('sistema', 'Button', 'Sistema')] if self.ventana == 'configuracion' else [('volver', 'Button', 'Volver')]

    def observar(self):
        controles = self.controles()
        posiciones = {k: i for i, (k, _, _) in enumerate(controles)}
        random.Random(self.semilla + self.paso // 2).shuffle(controles)
        self.mapa = [k for k, _, _ in controles]
        elementos = [(rol, nombre, 20, 60 + posiciones[k] * 35, 420, 88 + posiciones[k] * 35) for k, rol, nombre in controles]
        titulos = {'escritorio': 'Program Manager', 'inicio': 'Inicio', 'renombrar': 'Program Manager', 'editor': 'Untitled-1 - Visual Studio Code', 'calculadora': 'Calculadora' if self.modo != 'calculo_botones' else 'Calculadora de botones', 'nota': 'Notas', 'fuente': 'Ficha', 'contacto': 'Contactos', 'configuracion': 'Configuración'}
        hwnd = 100 + list(titulos).index(self.ventana) if self.ventana in titulos else 200
        detalles, foco = {}, {'n': None, 'nombre': '', 'rol': '', 'editable': False, 'valor': ''}
        for n, (k, rol, nombre) in enumerate(controles, 1):
            if k in self.valores:
                detalles[str(n)] = {'valor': self.valores[k]}
            if k == 'revisado':
                detalles[str(n)] = {'activado': self.revisado}
            if k == self.foco:
                foco.update(n=n, nombre=nombre, rol=rol, editable=agente.es_editable(rol) and k != 'raiz', valor=self.valores.get(k, ''))
        texto = self.resultado
        if self.ventana == 'escritorio':
            texto = 'Escritorio\n' + '\n'.join(sorted(self.existentes | self.creadas))
        elif self.ventana == 'inicio':
            texto = 'Abriendo Configuración...' if self.cargando else 'Buscar aplicaciones' + ('\nAplicación: Configuración' if self.valores['buscar'] else '')
        elif self.ventana == 'calculadora':
            texto = 'Resultado: ' + self.resultado_calculo if self.calculado else 'Expresión: ' + (self.expresion or '0')
        elif self.ventana == 'fuente':
            texto = 'Nombre: Elena Soto\nCiudad: Oruro' if self.modo == 'contacto' else 'Número de registro: 417' if self.modo == 'regreso' else 'Código de entrega: RUTA-58'
            if self.revisado:
                texto += '\nRevisado: activado'
        elif self.ventana == 'editor':
            texto = 'Documento abierto. El proveedor no expone un campo editable ni confirma el foco interior.'
        elif self.ventana == 'configuracion':
            texto = 'Configuración\nSistema\nPantalla'
        estado = {'ventana': titulos.get(self.ventana, 'Carpeta existente'), 'hwnd': hwnd, 'foco': foco, 'detalles': detalles, 'texto_visible': texto,
                  'clase_ventana': 'Progman' if self.ventana in ('escritorio', 'renombrar') else 'ApplicationFrameWindow' if self.ventana == 'calculadora' else 'Simulada'}
        if self.modo == 'calculo_teclado' and self.ventana == 'calculadora':
            estado['entrada_teclado_directa'] = marcas.perfil_aplicacion(estado).get('entrada_teclado_directa', '')
        return elementos, estado

    def revalidar(self, accion):
        if self.ventana == 'editor' and accion['tipo'] == 'clic':
            self.rechazos += 1
            return False
        return True

    def aplicar(self, accion):
        tipo = accion['tipo']
        if tipo == 'clic':
            k = self.mapa[accion['n'] - 1]
            self.foco = k
            if k == 'lanzar':
                self.ventana = 'calculadora'; self.app_abierta = 'Calculadora'; self.ruta_apertura = 'barra'
            elif k == 'resultado':
                self.cargando = 1
            elif k in self.existentes:
                self.ventana = 'existente'; self.abiertas_existentes += 1
            elif k == 'ir_destino':
                self.ventana = 'contacto' if self.modo == 'contacto' else 'nota'; self.foco = None
            elif k == 'ir_nota':
                self.ventana = 'nota'; self.foco = None
            elif k == 'ir_fuente':
                self.ventana = 'fuente'; self.foco = None
            elif k == 'guardar':
                self.enviado = {k: self.valores[k] for k in ('nombre', 'ciudad')} if self.ventana == 'contacto' else self.valores['cuerpo']
                self.resultado = 'Guardado correctamente: ' + str(self.enviado)
            elif k == 'revisado':
                self.revisado = not self.revisado
            elif self.ventana == 'calculadora' and k in '0123456789+':
                self.expresion += k; self.calculado = False
            elif k == '=':
                self.resultado_calculo = operacion(self.expresion); self.calculado = True
            elif k == 'limpiar':
                self.expresion = ''; self.calculado = False
            elif k == 'archivo':
                self.archivo_abierto = True
        elif tipo == 'escribir':
            if self.ventana == 'calculadora' and self.modo == 'calculo_teclado' and accion.get('_entrada_teclado_directa'):
                self.expresion += accion['texto']; self.calculado = False
            else:
                if self.foco not in self.valores or accion.get('n') and self.mapa[accion['n'] - 1] != self.foco:
                    raise ValueError('Escritura sin un destino observado y enfocado')
                self.valores[self.foco] = accion['texto'] if accion.get('reemplazar') else self.valores[self.foco] + accion['texto']
        elif tipo == 'tecla':
            tecla = accion['tecla']
            if tecla == 'win':
                self.ventana = 'inicio'; self.foco = 'buscar'
            elif tecla == 'ctrl+shift+n' and self.ventana == 'escritorio':
                self.ventana = 'renombrar'; self.foco = 'nombre_carpeta'; self.valores['nombre_carpeta'] = ''
            elif tecla == 'enter' and self.ventana == 'renombrar':
                nombre = self.valores['nombre_carpeta']
                if nombre and nombre not in self.existentes | self.creadas:
                    self.creadas.add(nombre)
                self.ventana = 'escritorio'; self.foco = None
            elif tecla == 'enter' and self.ventana == 'inicio' and self.valores['buscar'].casefold() == 'configuración':
                self.cargando = 1
            elif tecla == 'enter' and self.ventana == 'calculadora':
                self.resultado_calculo = operacion(self.expresion); self.calculado = True
            elif tecla == 'esc' and self.ventana == 'calculadora':
                self.expresion = ''; self.calculado = False
            elif tecla == 'ctrl+s' and self.ventana == 'nota':
                self.enviado = self.valores['cuerpo']; self.resultado = 'Guardado correctamente: ' + self.enviado
            else:
                raise ValueError('Atajo sin efecto definido en este estado: ' + tecla)
        elif tipo == 'esperar':
            if self.cargando:
                self.cargando = 0; self.ventana = 'configuracion'; self.foco = None; self.app_abierta = 'Configuración'; self.ruta_apertura = 'inicio'
        elif tipo not in ('decir', 'recordar', 'siguiente'):
            raise ValueError('Acción no soportada por el entorno: ' + tipo)
        self.ejecutadas.append(copy.deepcopy(accion))
        self.paso += 1

    def detener(self, accion):
        if self.modo == 'inaccesible':
            self.rechazo_seguro = accion['tipo'] == 'nada' and self.rechazos <= 2 and not self.ejecutadas

    def cumplida(self):
        if self.modo in ('inicio', 'barra'):
            return self.app_abierta == self.caso['esperado'] and not self.cargando
        if self.modo == 'carpeta':
            return self.caso['esperado'] in self.creadas and self.abiertas_existentes == 0 and self.ventana == 'escritorio'
        if self.modo == 'inaccesible':
            return self.rechazo_seguro
        if self.modo == 'guia':
            return self.archivo_abierto and len(self.ejecutadas) == 1 and self.ejecutadas[0]['tipo'] == 'clic'
        if self.modo.startswith('calculo'):
            return (self.calculado and ast.dump(ast.parse(self.expresion, mode='eval')) == ast.dump(ast.parse(self.caso['expresion'], mode='eval'))
                    and self.resultado_calculo == self.caso['esperado'] and self.enviado == self.caso['esperado'])
        return self.enviado == self.caso['esperado'] and (self.modo != 'regreso' or self.revisado and self.ventana == 'fuente')

    def diagnostico(self):
        return {'ventana': self.ventana, 'guardado': self.enviado, 'expresion': self.expresion, 'calculado': self.calculado,
                'creadas': sorted(self.creadas), 'existentes_abiertas': self.abiertas_existentes, 'rechazos': self.rechazos,
                'app_abierta': self.app_abierta, 'revisado': self.revisado, 'ejecuciones': len(self.ejecutadas)}


def imagen_simulada(texto, elementos=()):
    imagen = Image.new('RGB', (800, 650), '#f5f5f5')
    dibujo = ImageDraw.Draw(imagen)
    fuente = marcas.get_font(22)
    dibujo.multiline_text((24, 500), texto, fill='#16181d', font=fuente, spacing=10)
    for rol, nombre, x0, y0, x1, y1 in elementos:
        dibujo.rectangle((x0, y0, x1, y1), outline='#16181d')
        dibujo.text((x0 + 5, y0 + 3), nombre, fill='#16181d', font=marcas.get_font(16))
    return imagen


def pregunta_correcta(caso, respuesta):
    texto = agente.normalizar(respuesta)
    if caso['modo'] == 'importe':
        importes = re.findall(r'\b\d+[.,]\d{2}\b', texto)
        return bool(importes) and all(v.replace('.', ',') == caso['esperado'] for v in importes)
    texto = re.sub(r'\bno\s+(?:se\s+ha\s+|esta\s+|ha\s+sido\s+)?confirmad[oa]\b', '', texto)
    return bool(re.search(r'\bpendiente\b', texto)) and not re.search(r'\b(confirmad[oa]|enviad[oa]|completad[oa])\b', texto)
