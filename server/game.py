
CAMINO_LEN = 52
FIN_LEN = 6

# offsets del camino según el color
OFFSET_COLOR = {
    "azul": 0,
    "rojo": 13,
    "amarillo": 26,
    "verde": 39
}

def puede_salir_de_base(pasos):
    return pasos in (1, 6)

def mover_en_camino(pos_actual, pasos):
    return (pos_actual + pasos) % CAMINO_LEN

def mover_en_meta(pos_actual, pasos):
    nuevo = pos_actual + pasos
    return nuevo if nuevo <= FIN_LEN else None

def calcular_nueva_posicion(pos_actual, pasos, color):
    # sale de base
    if pos_actual is None:
        if puede_salir_de_base(pasos):
            return OFFSET_COLOR[color]
        return None

    # camino normal
    if isinstance(pos_actual, int):
        return mover_en_camino(pos_actual, pasos)

    # meta
    if isinstance(pos_actual, tuple) and pos_actual[0] == "fin":
        nuevo = mover_en_meta(pos_actual[1], pasos)
        if nuevo is None:
            return None
        return ("fin", nuevo)

    return None
