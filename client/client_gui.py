import tkinter as tk
from tkinter import messagebox
from network import NetworkClient


HOST = "127.0.0.1"
PORT = 5000


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Parqués Online - Cliente")
        self.geometry("600x500")

        self.network = NetworkClient(HOST, PORT, self.procesar_mensaje)

        if not self.network.conectar():
            messagebox.showerror("Error", "No se pudo conectar al servidor")
            self.destroy()
            return

        self.mi_nombre = None
        self.salas_disponibles = []

        self.frame_actual = None
        self.mostrar_login()

    def cambiar_frame(self, nuevo_frame):
        if self.frame_actual:
            self.frame_actual.destroy()
        self.frame_actual = nuevo_frame
        self.frame_actual.pack(fill="both", expand=True)

    def mostrar_login(self):
        self.cambiar_frame(FrameLogin(self))

    def mostrar_lobby(self):
        self.cambiar_frame(FrameLobby(self))

    def procesar_mensaje(self, msg):
        tipo = msg.get("tipo")
        data = msg.get("data", {})

        if tipo == "LOGIN_OK":
            self.mi_nombre = data.get("nombre")
            self.mostrar_lobby()

        elif tipo == "PARTIDAS_DISPONIBLES":
            self.salas_disponibles = data
            if isinstance(self.frame_actual, FrameLobby):
                self.frame_actual.actualizar_lista()

        elif tipo == "PARTIDA_CREADA":
            messagebox.showinfo("Sala creada", f"La sala fue creada con ID {data['id_sala']}")

        elif tipo == "UNIDO_A_PARTIDA":
            jugadores = data.get("jugadores", [])
            messagebox.showinfo("Sala", f"Jugadores en sala: {jugadores}")

        elif tipo == "MENSAJE_GENERAL":
            if isinstance(self.frame_actual, FrameLobby):
                self.frame_actual.agregar_chat(data)


class FrameLogin(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text="Ingresa tu nombre:", font=("Arial", 12)).pack(pady=10)
        self.entry_nombre = tk.Entry(self, font=("Arial", 12))
        self.entry_nombre.pack()

        tk.Button(self, text="Entrar", command=self.login).pack(pady=10)

    def login(self):
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Error", "Ingresa un nombre válido")
            return

        msg = {"tipo": "LOGIN", "data": {"nombre": nombre}}
        self.app.network.enviar(msg)


class FrameLobby(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text=f"Bienvenido {app.mi_nombre}", font=("Arial", 16)).pack(pady=10)

        # Chat General
        self.chat = tk.Text(self, height=10, state="disabled")
        self.chat.pack(fill="x", pady=5)

        self.entry_chat = tk.Entry(self)
        self.entry_chat.pack(fill="x")
        self.entry_chat.bind("<Return>", self.enviar_chat)

        # Botones lobby
        tk.Button(self, text="Listar Partidas", width=20,
                  command=self.listar).pack(pady=5)

        tk.Button(self, text="Crear Partida", width=20,
                  command=self.crear).pack(pady=5)

        # Lista de partidas
        tk.Label(self, text="Partidas disponibles:", font=("Arial", 12)).pack(pady=5)
        self.lista = tk.Listbox(self, height=8)
        self.lista.pack(fill="both", expand=True)

        # Botón para unirse
        tk.Button(self, text="Unirse a partida", width=20,
                  command=self.unirse).pack(pady=10)

    def listar(self):
        msg = {"tipo": "LISTAR_PARTIDAS", "data": {}}
        self.app.network.enviar(msg)

    def crear(self):
        msg = {"tipo": "CREAR_PARTIDA", "data": {"modo": "1v1v1v1"}}
        self.app.network.enviar(msg)

    def unirse(self):
        seleccion = self.lista.curselection()
        if not seleccion:
            messagebox.showwarning("Error", "Debes seleccionar una sala")
            return

        sala = self.app.salas_disponibles[seleccion[0]]
        msg = {"tipo": "UNIR_PARTIDA", "data": {"id_sala": sala["id"]}}
        self.app.network.enviar(msg)

    def actualizar_lista(self):
        self.lista.delete(0, tk.END)
        for sala in self.app.salas_disponibles:
            texto = f"ID {sala['id']} | {sala['modo']} | {sala['jugadores']}/{sala['max']}"
            self.lista.insert(tk.END, texto)

    def agregar_chat(self, data):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, f"{data['autor']}: {data['texto']}\n")
        self.chat.config(state="disabled")
        self.chat.see(tk.END)

    def enviar_chat(self, event):
        texto = self.entry_chat.get().strip()
        if texto:
            msg = {"tipo": "CHAT_GENERAL", "data": {"texto": texto}}
            self.app.network.enviar(msg)
        self.entry_chat.delete(0, tk.END)


if __name__ == "__main__":
    app = App()
    app.mainloop()
