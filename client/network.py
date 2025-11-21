import socket
import threading
import json


class NetworkClient:
    def __init__(self, host, port, on_message_callback):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.on_message_callback = on_message_callback

    def conectar(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.connected = True

            hilo = threading.Thread(target=self.hilo_receptor, daemon=True)
            hilo.start()

            return True
        except Exception as e:
            print(f"Error conectando al servidor: {e}")
            return False

    def hilo_receptor(self):
        buffer = ""
        try:
            while self.connected:
                data = self.sock.recv(4096)
                if not data:
                    print("Servidor desconectado")
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    linea = linea.strip()
                    if linea:
                        try:
                            msg = json.loads(linea)
                            self.on_message_callback(msg)
                        except:
                            print("JSON inválido recibido")
        except:
            pass
        finally:
            self.connected = False

    def enviar(self, msg):
        if not self.connected:
            return
        try:
            data = json.dumps(msg) + "\n"
            self.sock.sendall(data.encode("utf-8"))
        except:
            self.connected = False
