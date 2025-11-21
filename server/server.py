import socket
import threading
import json
import uuid

HOST = "0.0.0.0"
PORT = 5000

salas = {}
salas_lock = threading.Lock()
clientes = []


def enviar_json(sock, data):
    try:
        msg = json.dumps(data) + "\n"
        sock.sendall(msg.encode("utf-8"))
    except Exception as e:
        print("Error enviando:", e)


class GameRoom:
    def __init__(self, modo, creador_info):
        self.id = uuid.uuid4().hex[:8]
        self.modo = modo
        self.jugadores = []        # lista de dicts cliente_info
        self.listos = []           # paralela a jugadores
        self.max_jugadores = 4
        self.agregar_jugador(creador_info)

    def agregar_jugador(self, cliente_info):
        # evitar duplicados por nombre
        for j in self.jugadores:
            if j["nombre"] == cliente_info["nombre"]:
                return False

        if len(self.jugadores) < self.max_jugadores:
            self.jugadores.append(cliente_info)
            self.listos.append(False)
            cliente_info["sala_id"] = self.id
            return True
        return False

    def eliminar_jugador(self, cliente_info):
        if cliente_info in self.jugadores:
            idx = self.jugadores.index(cliente_info)
            self.jugadores.pop(idx)
            self.listos.pop(idx)

    def enviar_estado_sala(self):
        data = {
            "id_sala": self.id,
            "jugadores": [j["nombre"] for j in self.jugadores],
            "listos": self.listos,
            "faltan": self.listos.count(False)
        }
        for p in self.jugadores:
            enviar_json(p["sock"], {"tipo": "ESTADO_SALA", "data": data})

    def info_publica(self):
        return {
            "id": self.id,
            "modo": self.modo,
            "jugadores": len(self.jugadores),
            "max": self.max_jugadores
        }


def manejar_mensaje(cliente_info, msg, sock):
    tipo = msg.get("tipo")
    data = msg.get("data", {})
    nombre = cliente_info.get("nombre")

    # CHAT GENERAL
    if tipo == "MENSAJE_GENERAL":
        texto = data.get("texto", "")
        if not nombre:
            # ignoramos mensajes si todavía no hizo login
            return
        respuesta = {
            "tipo": "MENSAJE_GENERAL",
            "data": {"autor": nombre, "texto": texto}
        }
        for c in clientes:
            enviar_json(c["sock"], respuesta)

    # CREAR SALA
    elif tipo == "CREAR_PARTIDA":
        modo = data.get("modo", "1v1v1v1")
        sala = GameRoom(modo, cliente_info)
        with salas_lock:
            salas[sala.id] = sala

        enviar_json(sock, {
            "tipo": "PARTIDA_CREADA",
            "data": sala.info_publica()
        })

    # LISTAR SALAS
    elif tipo == "LISTAR_PARTIDAS":
        with salas_lock:
            lista = [s.info_publica() for s in salas.values()]
        enviar_json(sock, {"tipo": "PARTIDAS_DISPONIBLES", "data": lista})

    # UNIR SALA
    elif tipo == "UNIR_PARTIDA":
        id_sala = data.get("id_sala")
        with salas_lock:
            sala = salas.get(id_sala)

        if sala is None:
            enviar_json(sock, {"tipo": "ERROR",
                               "data": {"mensaje": "Sala no existe"}})
            return

        if sala.agregar_jugador(cliente_info):
            data_sala = {
                "id_sala": sala.id,
                "jugadores": [j["nombre"] for j in sala.jugadores]
            }
            for p in sala.jugadores:
                enviar_json(p["sock"],
                            {"tipo": "UNIDO_A_PARTIDA", "data": data_sala})
            sala.enviar_estado_sala()
        else:
            enviar_json(sock, {"tipo": "ERROR",
                               "data": {"mensaje": "Sala llena"}})

    # CAMBIAR ESTADO LISTO
    elif tipo == "CAMBIAR_LISTO":
        id_sala = data.get("id_sala")
        listo = data.get("listo", False)

        with salas_lock:
            sala = salas.get(id_sala)

        if sala is None:
            return

        for idx, info in enumerate(sala.jugadores):
            if info["sock"] == sock:
                sala.listos[idx] = listo
                break

        sala.enviar_estado_sala()

        if sala.listos.count(True) == len(sala.jugadores) and len(sala.jugadores) == 4:
            for p in sala.jugadores:
                enviar_json(p["sock"], {
                    "tipo": "INICIAR_PARTIDA",
                    "data": {"mensaje": "La partida va a comenzar"}
                })

    # CHAT DE SALA
    elif tipo == "CHAT_SALA":
        texto = data.get("texto", "")
        id_sala = data.get("id_sala")

        with salas_lock:
            sala = salas.get(id_sala)

        if sala is None:
            return

        for p in sala.jugadores:
            enviar_json(p["sock"], {
                "tipo": "MENSAJE_SALA",
                "data": {"autor": nombre, "texto": texto}
            })

    else:
        # cualquier tipo que no conozcamos
        enviar_json(sock, {
            "tipo": "ERROR",
            "data": {"mensaje": f"Tipo de mensaje desconocido: {tipo}"}
        })


def hilo_cliente(sock, addr):
    cliente_info = {"sock": sock, "nombre": None, "sala_id": None}
    buffer = ""

    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break

            buffer += data.decode("utf-8")

            while "\n" in buffer:
                linea, buffer = buffer.split("\n", 1)
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    msg = json.loads(linea)
                except json.JSONDecodeError as e:
                    print("JSON inválido:", e)
                    continue

                if msg.get("tipo") == "LOGIN":
                    nombre = msg.get("data", {}).get("nombre", "").strip()
                    if not nombre:
                        enviar_json(sock, {"tipo": "ERROR",
                                           "data": {"mensaje": "Nombre inválido"}})
                        continue
                    cliente_info["nombre"] = nombre
                    enviar_json(sock, {"tipo": "LOGIN_OK",
                                       "data": {"nombre": nombre}})
                else:
                    manejar_mensaje(cliente_info, msg, sock)

    except ConnectionResetError:
        print("Conexion reseteada", addr)
    finally:
        # salir de sala si estaba dentro
        if cliente_info["sala_id"]:
            with salas_lock:
                sala = salas.get(cliente_info["sala_id"])
                if sala:
                    sala.eliminar_jugador(cliente_info)
                    sala.enviar_estado_sala()
                    if len(sala.jugadores) == 0:
                        del salas[sala.id]

        sock.close()
        print("Cliente desconectado", addr)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(20)
    print(f"Servidor escuchando en {HOST}:{PORT}")

    try:
        while True:
            sock, addr = server.accept()
            print("Nuevo cliente", addr)
            clientes.append({"sock": sock})
            threading.Thread(target=hilo_cliente,
                             args=(sock, addr),
                             daemon=True).start()
    finally:
        server.close()


if __name__ == "__main__":
    main()
