import socket
import threading
import json
import sys

HOST = "127.0.0.1"
PORT = 5000


def enviar_json(sock, mensaje):
    try:
        data = json.dumps(mensaje) + "\n"
        sock.sendall(data.encode("utf-8"))
    except Exception as e:
        print(f"Error enviando mensaje: {e}")


def hilo_receptor(sock):
    """
    Hilo que recibe mensajes del servidor y los imprime.
    """
    buffer = ""
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                print("Servidor cerro la conexion")
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
                    print(f"JSON invalido desde servidor: {e}")
                    continue

                manejar_mensaje_servidor(msg)

    except ConnectionResetError:
        print("Conexion reseteada por el servidor")
    finally:
        sock.close()
        print("Hilo receptor terminado")


def manejar_mensaje_servidor(msg):
    tipo = msg.get("tipo")
    data = msg.get("data", {})

    if tipo == "LOGIN_OK":
        print(f"[SERVIDOR] Login exitoso como: {data.get('nombre')}")

    elif tipo == "MENSAJE_GENERAL":
        autor = data.get("autor", "desconocido")
        texto = data.get("texto", "")
        print(f"[GENERAL] {autor}: {texto}")

    elif tipo == "ERROR":
        print(f"[ERROR] {data.get('mensaje')}")

    else:
        print(f"[DESCONOCIDO] {msg}")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except Exception as e:
        print(f"No se pudo conectar al servidor: {e}")
        sys.exit(1)

    print(f"Conectado a {HOST}:{PORT}")

    # Lanzar hilo receptor
    t = threading.Thread(target=hilo_receptor, args=(sock,), daemon=True)
    t.start()

    # Login inicial
    nombre = input("Ingresa tu nombre: ").strip()
    login_msg = {
        "tipo": "LOGIN",
        "data": {"nombre": nombre}
    }
    enviar_json(sock, login_msg)

    print("Escribe mensajes para el chat general. Escribe '/salir' para terminar.")

    try:
        while True:
            texto = input()
            if texto.strip().lower() == "/salir":
                break

            msg = {
                "tipo": "MENSAJE_GENERAL",
                "data": {"texto": texto}
            }
            enviar_json(sock, msg)

    except KeyboardInterrupt:
        print("Saliendo por teclado")
    finally:
        sock.close()
        print("Cliente cerrado")


if __name__ == "__main__":
    main()
