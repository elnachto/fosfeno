import json


def compacta(esquema):
    permitidas = {"type", "properties", "required", "additionalProperties"}
    propiedades = esquema.get("properties", {})
    if (set(esquema) - permitidas or esquema.get("type") != "object"
            or esquema.get("additionalProperties") is not False
            or set(esquema.get("required", [])) != set(propiedades)):
        return None
    reglas = [r'char ::= [^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})']
    literal = lambda texto: json.dumps(texto, ensure_ascii=False)
    piezas = [literal("{")]
    for i, (clave, nodo) in enumerate(propiedades.items()):
        tipo = nodo.get("type")
        permitidas = {
            "string": {"type", "enum", "minLength", "maxLength"},
            "integer": {"type", "enum", "minimum", "maximum"},
            "boolean": {"type", "enum"},
        }.get(tipo)
        if permitidas is None or set(nodo) - permitidas:
            return None
        if i:
            piezas.append(literal(","))
        piezas.append(literal(json.dumps(clave, ensure_ascii=False) + ":"))
        nombre = "campo-" + str(i)
        if "enum" in nodo:
            opciones = []
            for valor in nodo["enum"]:
                if tipo == "string":
                    valido = (isinstance(valor, str)
                              and nodo.get("minLength", 0) <= len(valor) <= nodo.get("maxLength", float("inf")))
                elif tipo == "integer":
                    valido = (type(valor) is int
                              and nodo.get("minimum", float("-inf")) <= valor <= nodo.get("maximum", float("inf")))
                else:
                    valido = type(valor) is bool
                if valido:
                    opciones.append(literal(json.dumps(valor, ensure_ascii=False, separators=(",", ":"))))
            if not opciones:
                return None
            valor = " | ".join(opciones)
        elif tipo == "string":
            minimo = nodo.get("minLength", 0)
            maximo = nodo.get("maxLength")
            if not isinstance(maximo, int) or not isinstance(minimo, int) or not 0 <= minimo <= maximo <= 12000:
                return None
            valor = literal('"') + f" char{{{minimo},{maximo}}} " + literal('"')
        elif tipo == "boolean":
            valor = '"true" | "false"'
        else:
            minimo = nodo.get("minimum")
            maximo = nodo.get("maximum")
            if not isinstance(minimo, int) or not isinstance(maximo, int) or not 0 <= maximo - minimo <= 2048:
                return None
            valor = " | ".join(literal(str(v)) for v in range(minimo, maximo + 1))
        reglas.append(nombre + " ::= " + valor)
        piezas.append(nombre)
    piezas.append(literal("}"))
    return "root ::= " + " ".join(piezas) + "\n" + "\n".join(reglas) + "\n"
