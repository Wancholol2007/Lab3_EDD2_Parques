import socket
import threading
import json
import uuid

HOST = "0.0.0.0"
PORT = 5000

# Lista de clientes conectados
clientes = []
clientes_lock = threading.Lock()

# Salas de juego
salas = {}  # id_sala -> GameRoom
salas_lock = threading.Lock()


class GameRoom:
    """
    Representa una sala de juego.
    Por ahora solo manejamos lobby, mas adelante aqui metemos el estado del Parques.
    """
    def __init__(self, modo):
        self.id = str(uuid.uuid4())[:8]   # ID corto y legible
        self.modo = modo                  # "1v1v1v1", "1v1v1v1_BOTS", "2v2"
        self.jugadores = []               # lista de cliente_info
        self.max_jugadores = 4

    def agregar_jugador(self, cliente_info):
        # Evitar duplicados por nombre
        for j in self.jugadores:
            if j["nombre"] == cliente_info["nombre"]:
                return False

        if len(self.jugadores) < self.max_jugadores:
            self.jugadores.append(cliente_info)
            cliente_info["sala_id"] = self.id
            return True

        return False




    def esta_llena(self):
        return len(self.jugadores) >= self.max_jugadores

    def info_publica(self):
        """
        Info para mostrar en el lobby.
        """
        return {
            "id": self.id,
            "modo": self.modo,
            "jugadores": len(self.jugadores),
            "max": self.max_jugadores
        }


def enviar_json(sock, mensaje):
    """
    Envia un diccionario como JSON seguido de salto de linea.
    """
    try:
        data = json.dumps(mensaje) + "\n"
        sock.sendall(data.encode("utf-8"))
    except Exception as e:
        print(f"Error enviando mensaje: {e}")


def broadcast_general(origen_sock, texto, nombre):
    """
    Envia un mensaje de chat general a todos los clientes.
    Mas adelante podemos limitarlo a la sala del jugador.
    """
    mensaje = {
        "tipo": "MENSAJE_GENERAL",
        "data": {
            "autor": nombre,
            "texto": texto
        }
    }
    with clientes_lock:
        for c in clientes:
            sock = c["sock"]
            try:
                enviar_json(sock, mensaje)
            except Exception as e:
                print(f"Error en broadcast: {e}")


def manejar_mensaje(cliente_info, msg):
    """
    Procesa un mensaje ya decodificado desde un cliente.
    msg es un dict con llaves 'tipo' y 'data'.
    """
    sock = cliente_info["sock"]
    nombre = cliente_info["nombre"]

    tipo = msg.get("tipo")
    data = msg.get("data", {})

    if tipo == "LOGIN":
        nuevo_nombre = data.get("nombre", "").strip()
        if not nuevo_nombre:
            respuesta = {
                "tipo": "ERROR",
                "data": {"mensaje": "Nombre no valido"}
            }
            enviar_json(sock, respuesta)
            return

        cliente_info["nombre"] = nuevo_nombre
        print(f"Cliente {sock.getpeername()} ahora se llama {nuevo_nombre}")

        respuesta = {
            "tipo": "LOGIN_OK",
            "data": {"nombre": nuevo_nombre}
        }
        enviar_json(sock, respuesta)

    elif tipo == "CHAT_GENERAL":
        if not nombre:
            respuesta = {
                "tipo": "ERROR",
                "data": {"mensaje": "Debes hacer LOGIN antes de chatear"}
            }
            enviar_json(sock, respuesta)
            return

        texto = data.get("texto", "").strip()
        if texto:
            print(f"[CHAT_GENERAL] {nombre}: {texto}")
            broadcast_general(sock, texto, nombre)

    elif tipo == "CREAR_PARTIDA":
        # Cliente debe estar logueado
        if not nombre:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Debes hacer LOGIN antes de crear partida"}
            })
            return

        modo = data.get("modo", "1v1v1v1")
        nueva_sala = GameRoom(modo)

        with salas_lock:
            salas[nueva_sala.id] = nueva_sala
            nueva_sala.agregar_jugador(cliente_info)

        print(f"Sala creada {nueva_sala.id} modo {modo} por {nombre}")

        respuesta = {
            "tipo": "PARTIDA_CREADA",
            "data": {
                "id_sala": nueva_sala.id,
                "modo": nueva_sala.modo
            }
        }
        enviar_json(sock, respuesta)

        # Enviamos tambien el estado basico del lobby de esa sala
        enviar_json(sock, {
            "tipo": "UNIDO_A_PARTIDA",
            "data": {
                "id_sala": nueva_sala.id,
                "jugadores": [j["nombre"] for j in nueva_sala.jugadores]
            }
        })

    elif tipo == "LISTAR_PARTIDAS":
        with salas_lock:
            lista = [sala.info_publica()
                     for sala in salas.values()
                     if not sala.esta_llena()]

        respuesta = {
            "tipo": "PARTIDAS_DISPONIBLES",
            "data": lista
        }
        enviar_json(sock, respuesta)

    elif tipo == "UNIR_PARTIDA":
        # Si ya está en una sala, no permitir unirse de nuevo
        if cliente_info.get("sala_id") == id_sala:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Ya estás en esta sala"}
            })
            return

        # Evitar cambio de sala sin salir
        if cliente_info.get("sala_id") is not None:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Ya estás en una sala"}
            })
            return

        if not nombre:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Debes hacer LOGIN antes de unirte a una partida"}
            })
            return

        id_sala = data.get("id_sala")
        if not id_sala:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "id_sala requerido"}
            })
            return

        # EVITAR MULTICUENTA: si ya está en una sala, no permitir volver a unirse
        if cliente_info.get("sala_id") is not None:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Ya estás en una sala"}
            })
            return

        with salas_lock:
            sala = salas.get(id_sala)

        if sala is None:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Sala inexistente"}
            })
            return

        if sala.esta_llena():
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "Sala llena"}
            })
            return

        # AGREGAR JUGADOR, PERO SOLO UNA VEZ
        agregado = sala.agregar_jugador(cliente_info)
        if not agregado:
            enviar_json(sock, {
                "tipo": "ERROR",
                "data": {"mensaje": "No se pudo unir a la sala"}
            })
            return

        print(f"{nombre} se unio a la sala {sala.id}")

        data_sala = {
            "id_sala": sala.id,
            "jugadores": [j["nombre"] for j in sala.jugadores]
        }

        # Notificar a todos en la sala (sin duplicados)
        with salas_lock:
            for p in sala.jugadores:
                enviar_json(p["sock"], {
                    "tipo": "UNIDO_A_PARTIDA",
                    "data": data_sala
                })


    else:
        respuesta = {
            "tipo": "ERROR",
            "data": {"mensaje": f"Tipo de mensaje desconocido: {tipo}"}
        }
        enviar_json(sock, respuesta)


def hilo_cliente(cliente_info):
    """
    Hilo encargado de recibir datos del socket de un cliente,
    reconstruir mensajes JSON por lineas y llamar a manejar_mensaje.
    """
    sock = cliente_info["sock"]
    addr = cliente_info["addr"]
    buffer = ""

    print(f"Nuevo cliente conectado desde {addr}")

    try:
        while True:
            data = sock.recv(4096)
            if not data:
                print(f"Cliente {addr} desconectado")
                break

            buffer += data.decode("utf-8")

            # Procesar linea por linea
            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    msg = json.loads(linea)
                except json.JSONDecodeError as e:
                    print(f"JSON invalido de {addr}: {e}")
                    continue

                manejar_mensaje(cliente_info, msg)

    except ConnectionResetError:
        print(f"Conexion reseteada por el cliente {addr}")
    finally:
        with clientes_lock:
            if cliente_info in clientes:
                clientes.remove(cliente_info)

        # Eliminarlo de una sala si estaba en alguna
        sala_id = cliente_info.get("sala_id")
        if sala_id:
            with salas_lock:
                sala = salas.get(sala_id)
                if sala and cliente_info in sala.jugadores:
                    sala.jugadores.remove(cliente_info)
                    # Si la sala queda vacia la podemos borrar
                    if not sala.jugadores:
                        print(f"Sala {sala.id} vacia, se elimina")
                        del salas[sala.id]

        sock.close()
        print(f"Socket con {addr} cerrado")


def iniciar_servidor():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((HOST, PORT))
    servidor.listen()

    print(f"Servidor escuchando en {HOST}:{PORT}")

    try:
        while True:
            sock_cliente, addr = servidor.accept()
            cliente_info = {
                "sock": sock_cliente,
                "addr": addr,
                "nombre": None,
                "sala_id": None
            }

            with clientes_lock:
                clientes.append(cliente_info)

            hilo = threading.Thread(
                target=hilo_cliente,
                args=(cliente_info,),
                daemon=True
            )
            hilo.start()
    except KeyboardInterrupt:
        print("Servidor detenido por el usuario")
    finally:
        servidor.close()


if __name__ == "__main__":
    iniciar_servidor()
