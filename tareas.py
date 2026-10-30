"""Memoria de trabajo acotada, subtareas verificadas y cierre persistente.

No captura ni opera aplicaciones. Los hechos observados no conceden permisos.
"""
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from precondiciones import normalizar

MAX_ETAPAS = 6
MAX_HECHOS = 8
MAX_VALOR = 500
MAX_CONTEXTO = 6000  # caracteres serializados; no equivale a un contador de tokens


def literal(texto):
    return str(texto).replace('\r\n', '\n').replace('\r', '\n')


def fragmentos_observados(estado):
    foco = estado.get('foco') or {}
    if foco.get('secreto'):
        return []
    textos = [estado.get('texto_visible', ''), foco.get('valor', '')]
    for d in estado.get('detalles', {}).values():
        if not d.get('secreto'):
            textos.append(d.get('valor', ''))
    for a in estado.get('archivos_observados', []):
        if a.get('existe'):
            textos.append(a.get('texto', ''))
    return [literal(t) for t in textos if isinstance(t, str) and t]


def confirmado(v):
    return isinstance(v, dict) and v.get('cumplido') is True and bool(v.get('evidencia')) and not v.get('pendiente', '').strip()


class SesionTarea:
    def __init__(self, objetivo, partes=None):
        if not isinstance(objetivo, str) or not 1 <= len(objetivo) <= 6000:
            raise ValueError('La orden debe contener entre 1 y 6000 caracteres; divide los pedidos mayores')
        self.id = time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        self.objetivo = objetivo
        originales = partes or [objetivo]
        if len(originales) > MAX_ETAPAS or any(not isinstance(p, str) or not p.strip() or len(p) > 6000 for p in originales):
            raise ValueError('El plan excede el límite de subtareas')
        self.etapas = [{'objetivo': p.strip(), 'estado': 'pendiente', 'evidencia': ''} for p in originales]
        self.etapas[0]['estado'] = 'activa'
        self.hechos = {}
        self.importado = False
        self.fuente_plan = None
        self.respuestas = []
        self.estado = 'en_curso'
        self.motivo = ''

    @property
    def indice(self):
        return next((i for i, e in enumerate(self.etapas) if e['estado'] != 'comprobada'), len(self.etapas))

    @property
    def actual(self):
        return self.etapas[self.indice]['objetivo'] if self.indice < len(self.etapas) else ''

    def lectura_activa(self):
        return bool(re.match(r'^\s*(?:(?:primero|despues|luego|por favor)\s*[:,]?\s*)?(?:lee|leer|extrae|extraer)\b',
                             normalizar(self.actual)))

    def delega_instrucciones(self):
        pedido = normalizar(self.objetivo)
        refiere = bool(re.search(r'\b(hazlas|ejecutalas|siguelas|aplicalas)\b', pedido)
                       or re.search(r'\b(ejecuta|sigue|aplica|realiza|cumple)\s+(?:las |los |el )?(?:instrucciones|indicaciones|procedimiento|pasos)\b', pedido))
        negado = bool(re.search(r'\b(no|sin)\s+(?:las |los )?(?:ejecut\w*|aplic\w*|seguir|sig\w*|realiz\w*)\b', pedido))
        return bool(re.search(r'\b(lee|leer|revisa|revisar)\b', pedido)
                    and re.search(r'\b(instrucciones|indicaciones|procedimiento|pasos)\b', pedido)
                    and refiere and not negado)

    def plan_breve_observado(self, estado):
        """Ingreso determinista opcional de una nota corta; no infiere pasos ni destinos."""
        if not self.delega_instrucciones() or not self.lectura_activa() or self.importado:
            return None
        pedido = normalizar(self.objetivo)
        ventana = normalizar(str(estado.get('ventana', '')))
        clase = estado.get('clase_aplicacion') or estado.get('clase_ventana')
        fuente_correcta = ((re.search(r'\b(nota|bloc|notepad)\b', pedido)
                           and (clase == 'Notepad' or re.search(r'\b(nota|notas|bloc|notepad)\b', ventana)))
                          or (re.search(r'\b(word|documento)\b', pedido)
                              and (clase == 'OpusApp' or re.search(r'\bword\b', ventana))))
        foco = estado.get('foco') or {}
        if not fuente_correcta or foco.get('secreto') or foco.get('rol') not in ('Document', 'Edit') or foco.get('valor_truncado'):
            return None
        for nombre in re.findall(r'(?:archivo|nota|documento)\s+«([^»]+)»', self.objetivo, re.I):
            if normalizar(nombre) not in ventana:
                return None
        contenido = literal(foco.get('valor', ''))
        if not contenido or len(contenido) > 1000:
            return None
        pasos = [p.strip() for p in contenido.splitlines() if p.strip() and normalizar(p.strip()) != 'instrucciones:']
        verbo = r'^(?:[-*•]|\d+[.)])?\s*(escribe|guarda|abre|crea|cambia|selecciona|copia|pega|pulsa|introduce|rellena|activa|desactiva)\b'
        if not 1 <= len(pasos) <= 4 or not all(len(p) <= 240 and re.match(verbo, normalizar(p)) for p in pasos):
            return None
        return pasos

    def validar_accion(self, accion, elementos, estado):
        if not self.lectura_activa() or not fragmentos_observados(estado):
            return
        if len(self.etapas) == 1 and not self.delega_instrucciones():
            return
        if accion['tipo'] == 'escribir':
            n = accion.get('n') or (estado.get('foco') or {}).get('n')
            nombre = elementos[n - 1][1] if n and 1 <= n <= len(elementos) else ''
            if not re.search(r'\b(buscar|busqueda|search|filtrar|filtro)\b', normalizar(nombre)):
                raise ValueError('La etapa activa es leer: conserva los datos o importa el plan y solicita SIGUIENTE antes de escribir en el destino')
        if accion['tipo'] == 'clic':
            nombre = normalizar(elementos[accion['n'] - 1][1])
            palabras = lambda t: set(re.findall(r'[a-z0-9]{3,}', normalizar(t)))
            posteriores = palabras(self.objetivo) - palabras(self.actual) - {
                'luego', 'despues', 'hazlas', 'ejecutalas', 'instrucciones', 'prueba', 'actual',
                'abre', 'abrir', 'escribe', 'escribir', 'guarda', 'guardar', 'dime', 'resultado'}
            if palabras(nombre) & posteriores:
                raise ValueError('Ese destino pertenece al trabajo posterior a la lectura. Conserva los datos con RECORDAR o IMPORTAR_PLAN y solicita SIGUIENTE antes de salir de la fuente')

    def contexto(self):
        dato = {'etapa_activa': self.indice + 1 if self.actual else None,
                'etapas': [{'n': i + 1, 'objetivo': e['objetivo'][:260], 'estado': e['estado'],
                            **({'evidencia': e['evidencia'][:180]} if e['estado'] == 'comprobada' else {})}
                           for i, e in enumerate(self.etapas)],
                'hechos_observados': self.hechos, 'plan_importado': self.importado,
                'fuente_plan': self.fuente_plan, 'limite_memoria_hechos': MAX_HECHOS}
        if len(json.dumps(dato, ensure_ascii=False)) > MAX_CONTEXTO:
            raise ValueError('Memoria de tarea llena; utiliza menos datos o divide la tarea')
        return dato

    def recordar(self, texto, estado):
        try:
            dato = json.loads(texto)
        except (ValueError, TypeError) as error:
            # Compatibilidad con varios objetos JSON consecutivos: no se acepta prosa.
            if not isinstance(texto, str):
                raise ValueError('RECORDAR requiere JSON con clave y valor literales') from error
            dato, resto = [], texto.strip()
            try:
                while resto and len(dato) < 4:
                    objeto, fin = json.JSONDecoder().raw_decode(resto)
                    dato.append(objeto)
                    resto = resto[fin:].strip()
                if resto or not dato:
                    raise ValueError('Datos adicionales no admitidos')
            except ValueError as error:
                raise ValueError('RECORDAR requiere un objeto JSON o una lista de hasta cuatro objetos con clave y valor') from error
        if isinstance(dato, list):
            if not 1 <= len(dato) <= 4:
                raise ValueError('Solo se guardan entre uno y cuatro datos por acción')
            anterior = dict(self.hechos)
            try:
                for registro in dato:
                    self._recordar_uno(registro, estado)
            except (ValueError, TypeError):
                self.hechos = anterior
                raise
            return {'etapa': self.indice + 1, 'claves': [d['clave'] for d in dato]}
        return self._recordar_uno(dato, estado)

    def _recordar_uno(self, dato, estado):
        if not isinstance(dato, dict) or set(dato) != {'clave', 'valor'}:
            raise ValueError('RECORDAR requiere únicamente clave y valor')
        clave, valor = dato['clave'], dato['valor']
        if not isinstance(clave, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', clave):
            raise ValueError('La clave debe ser un nombre breve sin espacios')
        if not isinstance(valor, str) or not valor or len(valor) > MAX_VALOR:
            raise ValueError('El valor debe contener entre 1 y 500 caracteres')
        valor = literal(valor)
        if not any(valor in t for t in fragmentos_observados(estado)):
            raise ValueError('El dato no aparece literalmente en la observación actual; no se guarda una inferencia')
        if clave in self.hechos:
            if self.hechos[clave]['valor'] == valor:
                raise ValueError('Ese dato ya está guardado; avanza a la siguiente acción')
            raise ValueError('Ese nombre ya tiene otro valor; usa un nombre distinto para conservar su procedencia')
        if len(self.hechos) >= MAX_HECHOS:
            raise ValueError('Memoria de tarea llena: máximo ocho datos; no se descartan datos anteriores automáticamente')
        dato = {'valor': valor, 'fuente': str(estado.get('ventana', 'Observación actual'))[:100],
                'etapa': self.indice + 1}
        self.hechos[clave] = dato
        try:
            self.contexto()
        except ValueError:
            del self.hechos[clave]
            raise
        return dato

    def importar_plan(self, texto, estado):
        if not self.delega_instrucciones() or self.importado:
            raise ValueError('Solo se importa un plan una vez y cuando el usuario pidió explícitamente leer instrucciones y realizarlas')
        pasos = json.loads(texto)
        if (not isinstance(pasos, list) or not 1 <= len(pasos) <= 4
                or any(not isinstance(p, str) or not 1 <= len(p) <= 240 for p in pasos)):
            raise ValueError('IMPORTAR_PLAN requiere una lista JSON de uno a cuatro pasos literales, de hasta 240 caracteres')
        observados = fragmentos_observados(estado)
        if not all(any(literal(p) in t for t in observados) for p in pasos):
            raise ValueError('Los pasos deben aparecer literalmente en la fuente actual')
        if any(re.search(r'\b(ignora|ignorar|desobedece|system prompt|contraseña|contrasena)\b', normalizar(p)) for p in pasos):
            raise ValueError('La fuente intenta cambiar instrucciones o incluye credenciales; no se importa como plan')
        # Conservar las obligaciones explícitas del usuario posteriores a la lectura.
        restantes = [e for e in self.etapas[self.indice + 1:]
                     if not re.fullmatch(r'(?:hazlas|ejecutalas|siguelas|aplicalas)[.! ]*', normalizar(e['objetivo']))
                     and not re.fullmatch(r'(?:ejecuta|sigue|aplica|realiza|cumple) (?:las |los )?(?:instrucciones|indicaciones|pasos|procedimiento)[.! ]*', normalizar(e['objetivo']))]
        primeras = self.etapas[:self.indice + 1]
        if len(self.etapas) == 1:
            primeras = [{'objetivo': 'Lee las instrucciones de la fuente seleccionada', 'estado': 'activa', 'evidencia': ''}]
        nuevas = primeras + [{'objetivo': p, 'estado': 'pendiente', 'evidencia': ''} for p in pasos] + restantes
        if len(nuevas) > MAX_ETAPAS:
            raise ValueError('El plan importado excede seis etapas; divide la tarea')
        previo = self.etapas, self.fuente_plan
        self.etapas = nuevas
        self.fuente_plan = {'ventana': str(estado.get('ventana', ''))[:100],
                            'sha256_fragmentos': hashlib.sha256('\n'.join(pasos).encode()).hexdigest()}
        self.importado = True
        try:
            self.contexto()
        except ValueError:
            self.etapas, self.fuente_plan = previo
            self.importado = False
            raise

    def avanzar(self, verificacion):
        if not self.actual:
            raise ValueError('No hay una etapa pendiente')
        if not confirmado(verificacion):
            raise ValueError('La etapa no está comprobada: ' + str(verificacion.get('pendiente', 'falta evidencia'))[:240])
        lectura = self.lectura_activa()
        if lectura and self.delega_instrucciones() and not self.importado:
            raise ValueError('Antes de ejecutar instrucciones usa IMPORTAR_PLAN para conservar todos los pasos necesarios de la fuente')
        if lectura and self.indice < len(self.etapas) - 1 and not (self.hechos or self.importado):
            raise ValueError('Antes de abandonar la lectura conserva los datos necesarios con RECORDAR o importa las instrucciones autorizadas')
        self.etapas[self.indice].update(estado='comprobada', evidencia=str(verificacion['evidencia'])[:300])
        if self.actual:
            self.etapas[self.indice]['estado'] = 'activa'

    def registrar_respuesta(self, texto):
        if texto and texto not in self.respuestas:
            self.respuestas.append(texto[:1200])
            self.respuestas = self.respuestas[-3:]

    def terminar(self, estado, motivo=''):
        if estado == 'completada' and self.actual:
            raise ValueError('No se puede completar una tarea con etapas pendientes')
        self.estado, self.motivo = estado, str(motivo)[:500]

    def resultado(self):
        return {'id': self.id, 'objetivo': self.objetivo, 'estado': self.estado, 'etapas': self.etapas,
                'hechos': self.hechos, 'respuestas': self.respuestas,
                'motivo': self.motivo, 'plan_importado': self.importado, 'fuente_plan': self.fuente_plan}

    def respuesta_final(self):
        prefijo = 'Tarea comprobada.' if self.estado == 'completada' else 'Tarea interrumpida.' if self.estado == 'cancelada' else 'Tarea incompleta.'
        completadas = [e['objetivo'] for e in self.etapas if e['estado'] == 'comprobada']
        pendientes = [e['objetivo'] for e in self.etapas if e['estado'] != 'comprobada']
        partes = [prefijo]
        if self.respuestas:
            partes.append(self.respuestas[-1])
        elif self.hechos:
            partes.append('Datos leídos: ' + '; '.join(k + ': ' + d['valor'] for k, d in self.hechos.items())[:700])
        if completadas:
            partes.append('Comprobado: ' + '; '.join(completadas)[:500])
        if pendientes:
            partes.append('Pendiente: ' + '; '.join(pendientes)[:400])
        if self.motivo:
            partes.append(self.motivo)
        return '\n'.join(partes)

    def guardar(self, carpeta):
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / ('tarea-' + self.id + '.json')
        temporal = ruta.with_suffix('.tmp')
        temporal.write_text(json.dumps(self.resultado(), ensure_ascii=False, indent=2), encoding='utf-8')
        temporal.replace(ruta)
        ruta.with_suffix('.md').write_text(self.respuesta_final() + '\n', encoding='utf-8')
        return ruta
