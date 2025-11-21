import tkinter as tk
from tkinter import messagebox
from network import NetworkClient

HOST = "127.0.0.1"
PORT = 5000


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Parqués Online - Cliente")
        self.geometry("800x650")

        self.network = NetworkClient(HOST, PORT, self.procesar_mensaje)
        if not self.network.conectar():
            messagebox.showerror("Error", "No se pudo conectar al servidor")
            self.destroy()
            return

        self.mi_nombre = None
        self.salas_disponibles = []
        self.sala_actual_id = None

        self.frame_actual = None
        self.mostrar_login()

    # -------------------- gestión de frames --------------------

    def cambiar_frame(self, nuevo_frame):
        if self.frame_actual:
            self.frame_actual.destroy()
        self.frame_actual = nuevo_frame
        self.frame_actual.pack(fill="both", expand=True)

    def mostrar_login(self):
        self.cambiar_frame(FrameLogin(self))

    def mostrar_lobby(self):
        self.cambiar_frame(FrameLobby(self))

    # -------------------- procesamiento de mensajes --------------------

    def procesar_mensaje(self, msg):
        # esto lo llama el hilo de red
        tipo = msg.get("tipo")
        data = msg.get("data", {})

        if tipo == "LOGIN_OK":
            self.mi_nombre = data.get("nombre")
            # cambiar a lobby
            self.after(0, self.mostrar_lobby)

        elif tipo == "PARTIDAS_DISPONIBLES":
            self.salas_disponibles = data
            if isinstance(self.frame_actual, FrameLobby):
                self.after(0, self.frame_actual.actualizar_lista)

        elif tipo == "PARTIDA_CREADA":
            # el servidor devuelve info_publica de la sala
            messagebox.showinfo(
                "Sala creada",
                f"Sala {data['id']} creada, modo {data['modo']}"
            )

        elif tipo == "UNIDO_A_PARTIDA":
            # data: {id_sala, jugadores}
            id_sala = data.get("id_sala")
            jugadores = data.get("jugadores", [])

            self.sala_actual_id = id_sala

            def _go():
                frame = FrameSalaEspera(self, id_sala)
                self.cambiar_frame(frame)
                frame.actualizar_jugadores(jugadores, [False] * len(jugadores))

            self.after(0, _go)

        elif tipo == "ESTADO_SALA":
            jugadores = data.get("jugadores", [])
            listos = data.get("listos", [])
            if isinstance(self.frame_actual, FrameSalaEspera):
                self.after(0, lambda: self.frame_actual.actualizar_jugadores(jugadores, listos))

        elif tipo == "MENSAJE_GENERAL":
            autor = data.get("autor", "")
            texto = data.get("texto", "")

            # Si estamos en el lobby, lo mostramos
            if isinstance(self.frame_actual, FrameLobby):
                self.after(0, lambda: self.frame_actual.agregar_chat(autor, texto))
            # Si no estamos en lobby, ignoramos el mensaje ANTES de que llegue al final
            return

        elif tipo == "MENSAJE_SALA":
            if isinstance(self.frame_actual, FrameSalaEspera):
                autor = data.get("autor", "")
                texto = data.get("texto", "")
                self.after(0, lambda: self.frame_actual.agregar_chat(autor, texto))

        elif tipo == "INICIAR_PARTIDA":
            # por ahora solo mostramos popup y cambiamos al tablero
            mensaje = data.get("mensaje", "La partida va a comenzar")
            messagebox.showinfo("Partida", mensaje)

            def _go():
                frame = FrameTablero(self, self.sala_actual_id, self.mi_nombre)
                self.cambiar_frame(frame)

            self.after(0, _go)

        elif tipo == "ERROR":
            mensaje = data.get("mensaje", "Error desconocido")
            messagebox.showerror("Error", mensaje)
            return

# ============================================================
# Frames
# ============================================================

class FrameLogin(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text="Ingresa tu nombre", font=("Arial", 16)).pack(pady=20)
        self.entry_nombre = tk.Entry(self, font=("Arial", 14))
        self.entry_nombre.pack(pady=10)

        tk.Button(self, text="Entrar", font=("Arial", 12),
                  command=self.login).pack(pady=10)

    def login(self):
        nombre = self.entry_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Nombre inválido", "Ingresa un nombre")
            return

        msg = {"tipo": "LOGIN", "data": {"nombre": nombre}}
        self.app.network.enviar(msg)


class FrameLobby(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text=f"Bienvenido {app.mi_nombre}",
                 font=("Arial", 18)).pack(pady=10)

        # Chat general
        self.chat = tk.Text(self, height=8, state="disabled")
        self.chat.pack(fill="x", padx=10, pady=5)

        self.entry_chat = tk.Entry(self)
        self.entry_chat.pack(fill="x", padx=10)
        self.entry_chat.bind("<Return>", self.enviar_chat)

        # Controles lobby
        botones = tk.Frame(self)
        botones.pack(pady=10)

        tk.Button(botones, text="Listar partidas",
                  command=self.listar, width=15).grid(row=0, column=0, padx=5)
        tk.Button(botones, text="Crear partida",
                  command=self.crear, width=15).grid(row=0, column=1, padx=5)

        # Lista de partidas
        tk.Label(self, text="Partidas disponibles:",
                 font=("Arial", 12)).pack(pady=5)
        self.lista = tk.Listbox(self, height=8)
        self.lista.pack(fill="both", expand=True, padx=20)

        tk.Button(self, text="Unirse a partida",
                  command=self.unirse).pack(pady=10)

    def listar(self):
        msg = {"tipo": "LISTAR_PARTIDAS", "data": {}}
        self.app.network.enviar(msg)

    def crear(self):
        # por ahora solo modo 1v1v1v1
        msg = {"tipo": "CREAR_PARTIDA", "data": {"modo": "1v1v1v1"}}
        self.app.network.enviar(msg)

    def unirse(self):
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Error", "Selecciona una sala")
            return
        sala = self.app.salas_disponibles[sel[0]]
        msg = {"tipo": "UNIR_PARTIDA", "data": {"id_sala": sala["id"]}}
        self.app.network.enviar(msg)

    def actualizar_lista(self):
        self.lista.delete(0, tk.END)
        for sala in self.app.salas_disponibles:
            texto = f"ID {sala['id']} | {sala['modo']} | {sala['jugadores']}/{sala['max']}"
            self.lista.insert(tk.END, texto)

    def agregar_chat(self, autor, texto):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, f"{autor}: {texto}\n")
        self.chat.config(state="disabled")
        self.chat.see(tk.END)

    def enviar_chat(self, event):
        texto = self.entry_chat.get().strip()
        if texto:
            msg = {"tipo": "MENSAJE_GENERAL", "data": {"texto": texto}}
            self.app.network.enviar(msg)
        self.entry_chat.delete(0, tk.END)


class FrameSalaEspera(tk.Frame):
    def __init__(self, app, id_sala):
        super().__init__(app)
        self.app = app
        self.id_sala = id_sala

        tk.Label(self, text=f"Sala {id_sala}",
                 font=("Arial", 18)).pack(pady=10)

        self.lista = tk.Listbox(self, height=6)
        self.lista.pack(fill="x", padx=20, pady=5)

        self.boton_listo = tk.Button(self, text="Estoy listo",
                                     command=self.marcar_listo)
        self.boton_listo.pack(pady=5)

        tk.Label(self, text="Chat de sala:").pack()
        self.chat = tk.Text(self, height=10, state="disabled")
        self.chat.pack(fill="both", expand=True, padx=10, pady=5)

        self.entry_chat = tk.Entry(self)
        self.entry_chat.pack(fill="x", padx=10, pady=5)
        self.entry_chat.bind("<Return>", self.enviar_chat)

    def actualizar_jugadores(self, jugadores, listos):
        self.lista.delete(0, tk.END)
        for nombre, ready in zip(jugadores, listos):
            estado = "✔️ Listo" if ready else "❌ No listo"
            self.lista.insert(tk.END, f"{nombre} — {estado}")

    def marcar_listo(self):
        msg = {
            "tipo": "CAMBIAR_LISTO",
            "data": {"listo": True, "id_sala": self.id_sala}
        }
        self.app.network.enviar(msg)
        self.boton_listo.config(text="Esperando...", state="disabled")

    def enviar_chat(self, event):
        txt = self.entry_chat.get().strip()
        if txt:
            msg = {
                "tipo": "CHAT_SALA",
                "data": {"texto": txt, "id_sala": self.id_sala}
            }
            self.app.network.enviar(msg)
        self.entry_chat.delete(0, tk.END)

    def agregar_chat(self, autor, texto):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, f"{autor}: {texto}\n")
        self.chat.config(state="disabled")
        self.chat.see(tk.END)


class FrameTablero(tk.Frame):
    """
    Tablero detallado de Parqués (estilo Ludo 15x15).
    Por ahora solo dibujamos el tablero y fichas iniciales.
    """
    def __init__(self, app, id_sala, mi_nombre):
        super().__init__(app)
        self.app = app
        self.id_sala = id_sala
        self.mi_nombre = mi_nombre

        tk.Label(self, text=f"Tablero - Sala {id_sala} - Jugador: {mi_nombre}",
                 font=("Arial", 16)).pack(pady=10)

        self.canvas = tk.Canvas(self, width=600, height=600, bg="white")
        self.canvas.pack(pady=5)

        self.dibujar_tablero()
        self.dibujar_fichas_iniciales()

    def dibujar_tablero(self):
        cell = 40
        offset = 20  # margen

        # fondo
        self.canvas.create_rectangle(
            offset, offset,
            offset + 15 * cell, offset + 15 * cell,
            outline="black"
        )

        # casas de colores (4x4)
        # azul arriba izquierda
        self.canvas.create_rectangle(
            offset, offset,
            offset + 6 * cell, offset + 6 * cell,
            fill="#4A6FE3", outline="black"
        )
        # rojo arriba derecha
        self.canvas.create_rectangle(
            offset + 9 * cell, offset,
            offset + 15 * cell, offset + 6 * cell,
            fill="#E34A4A", outline="black"
        )
        # verde abajo izquierda
        self.canvas.create_rectangle(
            offset, offset + 9 * cell,
            offset + 6 * cell, offset + 15 * cell,
            fill="#4AE34A", outline="black"
        )
        # amarillo abajo derecha
        self.canvas.create_rectangle(
            offset + 9 * cell, offset + 9 * cell,
            offset + 15 * cell, offset + 15 * cell,
            fill="#E3E34A", outline="black"
        )

        # cruz central
        # brazo vertical
        self.canvas.create_rectangle(
            offset + 6 * cell, offset,
            offset + 9 * cell, offset + 15 * cell,
            fill="#F5F5F5", outline="black"
        )
        # brazo horizontal
        self.canvas.create_rectangle(
            offset, offset + 6 * cell,
            offset + 15 * cell, offset + 9 * cell,
            fill="#F5F5F5", outline="black"
        )

        # centro
        self.canvas.create_polygon(
            offset + 6 * cell, offset + 6 * cell,
            offset + 9 * cell, offset + 6 * cell,
            offset + 9 * cell, offset + 9 * cell,
            offset + 6 * cell, offset + 9 * cell,
            fill="#DDDDDD", outline="black"
        )

        # casillas del camino (simples cuadritos)
        for i in range(15):
            for j in range(15):
                x1 = offset + j * cell
                y1 = offset + i * cell
                x2 = x1 + cell
                y2 = y1 + cell

                # líneas de rejilla sobre la cruz
                if 6 <= j <= 8 or 6 <= i <= 8:
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline="gray90")

        # caminos de cada color (hacia el centro), estilizados
        # azul (desde arriba hacia el centro)
        for k in range(1, 6):
            self._cell_color(offset, cell, 6, k, "#2E46A8")
        # rojo (desde la derecha)
        for k in range(1, 6):
            self._cell_color(offset, cell, 14 - k, 8, "#A82E2E")
        # amarillo (desde abajo)
        for k in range(1, 6):
            self._cell_color(offset, cell, 8, 14 - k, "#A8A82E")
        # verde (desde la izquierda)
        for k in range(1, 6):
            self._cell_color(offset, cell, k, 6, "#2EA82E")

    def _cell_color(self, offset, cell, fila, col, color):
        x1 = offset + col * cell
        y1 = offset + fila * cell
        x2 = x1 + cell
        y2 = y1 + cell
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="black")

    def dibujar_fichas_iniciales(self):
        # fichas en las casas de colores (4 por color)
        cell = 40
        offset = 20
        r = cell * 0.3

        def draw_piece(cx, cy, color):
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=color, outline="black"
            )

        # azul (arriba izquierda)
        bases_azul = [
            (1, 1), (1, 3),
            (3, 1), (3, 3)
        ]
        for f, c in bases_azul:
            cx = offset + c * cell + cell / 2
            cy = offset + f * cell + cell / 2
            draw_piece(cx, cy, "#1B2F7F")

        # rojo (arriba derecha)
        bases_rojo = [
            (1, 11), (1, 13),
            (3, 11), (3, 13)
        ]
        for f, c in bases_rojo:
            cx = offset + c * cell + cell / 2
            cy = offset + f * cell + cell / 2
            draw_piece(cx, cy, "#7F1B1B")

        # verde (abajo izquierda)
        bases_verde = [
            (11, 1), (11, 3),
            (13, 1), (13, 3)
        ]
        for f, c in bases_verde:
            cx = offset + c * cell + cell / 2
            cy = offset + f * cell + cell / 2
            draw_piece(cx, cy, "#1B7F1B")

        # amarillo (abajo derecha)
        bases_amarillo = [
            (11, 11), (11, 13),
            (13, 11), (13, 13)
        ]
        for f, c in bases_amarillo:
            cx = offset + c * cell + cell / 2
            cy = offset + f * cell + cell / 2
            draw_piece(cx, cy, "#7F7F1B")


if __name__ == "__main__":
    app = App()
    app.mainloop()
