"""Parámetros explícitos de una tarea y plantillas conservadoras de demostraciones."""
import ipaddress
import re
import unicodedata


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if not unicodedata.combining(c))


PATRONES = {
    'mac': r'(?<![\w:.-])(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}(?![\w:.-])',
    'ip': r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\w./])',
    'vlan': r'\bvlan\s*(?:id\s*)?(?:[:=]\s*)?[«"\']?([\w](?:[\w.-]*[\w-])?)',
}


def validar(nombre, valor):
    valor = str(valor).strip()
    if nombre == 'mac':
        if not re.fullmatch(PATRONES['mac'], valor):
            raise ValueError('MAC inválida: se requieren seis pares hexadecimales')
        return valor.replace('-', ':').upper()
    if nombre == 'ip':
        try:
            return str(ipaddress.ip_interface(valor) if '/' in valor else ipaddress.ip_address(valor))
        except ValueError as error:
            raise ValueError('Dirección IP o prefijo inválido') from error
    if nombre == 'vlan':
        if valor.isdigit():
            if not 1 <= int(valor) <= 4094:
                raise ValueError('El identificador VLAN debe estar entre 1 y 4094')
            return str(int(valor))
        if not re.fullmatch(r'[\w.-]{1,48}', valor) or normalizar(valor) in ('tal', 'una', 'la', 'existente', 'y', 'con'):
            raise ValueError('Falta identificar la VLAN')
        return valor
    raise ValueError('Tipo de parámetro no admitido')


def extraer(texto):
    """No adivina entre varias IP/MAC ni interpreta una dirección como gateway."""
    valores, ambiguos, errores, literales = {}, {}, [], {}
    for nombre, patron in PATRONES.items():
        encontrados = list(dict.fromkeys(re.findall(patron, texto, re.I)))
        validos = []
        for literal in encontrados:
            try:
                valor = validar(nombre, literal)
                if valor not in validos:
                    validos.append(valor)
                literales.setdefault(nombre, []).append(literal)
            except ValueError as error:
                errores.append(str(error))
        if len(validos) == 1:
            valores[nombre] = validos[0]
        elif len(validos) > 1:
            ambiguos[nombre] = validos
    return {'valores': valores, 'ambiguos': ambiguos, 'errores': errores, 'literales': literales}


def crear_plantilla(objetivo, pasos):
    datos = extraer(objetivo)
    if datos['ambiguos'] or datos['errores']:
        return None
    # Solo parametrizar valores que el usuario nombró y que efectivamente escribió.
    parametros, nuevos = {}, list(pasos)
    objetivo_plantilla = objetivo
    for nombre, valor in datos['valores'].items():
        literales = datos['literales'][nombre]
        usado = False
        for i, paso in enumerate(nuevos):
            if not paso.startswith('escribí «'):
                continue
            m = re.match(r'escribí «([^»]*)»(.*)', paso, re.S)
            if not m:
                continue
            contenido = m[1]
            for literal in literales:
                patron = r'(?<![\w.:/-])' + re.escape(literal) + r'(?![\w.:/-])'
                contenido, cuenta = re.subn(patron, '{{' + nombre + '}}', contenido, flags=re.I)
                usado = usado or bool(cuenta)
            nuevos[i] = 'escribí «' + contenido + '»' + m[2]
        if usado:
            parametros[nombre] = {'tipo': nombre, 'requerido': True}
            if nombre == 'vlan':
                objetivo_plantilla = re.sub(PATRONES['vlan'],
                    lambda m: m[0][:m.start(1) - m.start()] + '{{vlan}}', objetivo_plantilla, flags=re.I)
                continue
            for literal in literales:
                objetivo_plantilla = re.sub(r'(?<![\w.:/-])' + re.escape(literal) + r'(?![\w.:/-])',
                                           '{{' + nombre + '}}', objetivo_plantilla, flags=re.I)
    if not parametros:
        return None
    operacion = 'reserva_dhcp' if re.search(r'\b(dhcp|reserva|reservar|lease)\b', normalizar(objetivo)) else 'ip_interfaz' if re.search(r'\b(interfaz|gateway)\b', normalizar(objetivo)) else ''
    return {'version': 1, 'parametros': parametros, 'objetivo': objetivo_plantilla, 'pasos': nuevos, 'operacion': operacion,
            'alcance': 'Referencia de demostración; volver a observar controles y condiciones antes de actuar'}


def instanciar(plantilla, objetivo):
    datos = extraer(objetivo)
    requeridos = plantilla.get('parametros', {})
    pendientes = []
    operacion = plantilla.get('operacion')
    pedido = normalizar(objetivo)
    if operacion and not re.search(r'\b(como te ensene|mismo procedimiento|misma receta)\b', pedido):
        menciona_dhcp = bool(re.search(r'\b(dhcp|reserva|reservar|lease)\b', pedido))
        menciona_interfaz = bool(re.search(r'\b(interfaz|gateway)\b', pedido))
        if (operacion == 'reserva_dhcp' and (not menciona_dhcp or menciona_interfaz)
                or operacion == 'ip_interfaz' and (not menciona_interfaz or menciona_dhcp)):
            pendientes.append('si deseas una reserva DHCP para el dispositivo o una IP de la interfaz')
    for nombre in requeridos:
        if nombre not in datos['valores'] or nombre in datos['ambiguos']:
            pendientes.append(nombre)
    if datos['errores']:
        pendientes.extend(datos['errores'])
    if pendientes:
        return {'lista': False, 'pregunta': 'Para reutilizar este procedimiento necesito aclarar: ' + ', '.join(pendientes) + '.',
                'faltantes': pendientes, 'valores': datos['valores']}
    def reemplazar(texto):
        def poner(m):
            if m[1] not in requeridos:
                raise ValueError('Marcador de parámetro no declarado')
            return datos['valores'][m[1]]
        return re.sub(r'\{\{([a-z_]+)\}\}', poner, texto)
    return {'lista': True, 'valores': {n: datos['valores'][n] for n in requeridos},
            'objetivo': reemplazar(plantilla['objetivo']),
            'pasos': [reemplazar(p) for p in plantilla['pasos']]}
