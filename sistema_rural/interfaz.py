"""Interfaz gráfica (DD-03): solo handlers de eventos que delegan en ServicioClinica.

Aquí no hay lógica de negocio ni se procesan datos sensibles: el DNI solo se
muestra enmascarado, salvo en el campo donde el personal lo digita.
"""
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .errores import ErrorSistema
from .modelos import ESTADOS_TICKET, TURNOS
from .reportes import ReporteFactory
from .servicio import ServicioClinica


def _fecha(texto: str, obligatoria: bool = False) -> date:
    texto = texto.strip()
    if not texto:
        if obligatoria:
            raise ErrorSistema("Ingrese la fecha en formato AAAA-MM-DD (ej. 1990-05-17).")
        return date.today()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ErrorSistema("Fecha inválida. Use el formato AAAA-MM-DD (ej. 2026-11-03).") from None


class VentanaPrincipal(tk.Tk):
    def __init__(self, servicio: ServicioClinica):
        super().__init__()
        self._srv = servicio
        self.title("SistemaRural-PE · Posta Médica Rural")
        self.geometry("980x640")
        self.minsize(860, 560)
        self._vars: dict[str, tk.StringVar] = {}
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for titulo, constructor in (("Pacientes", self._tab_pacientes), ("Historia clínica", self._tab_historia),
                                    ("Médicos", self._tab_medicos), ("Citas y turnos", self._tab_citas),
                                    ("Reportes", self._tab_reportes)):
            marco = ttk.Frame(nb, padding=10)
            nb.add(marco, text=titulo)
            constructor(marco)
        self._refrescar_todo()

    # ------------------------------------------------------------ utilidades
    def _var(self, nombre, inicial="") -> tk.StringVar:
        self._vars[nombre] = tk.StringVar(value=inicial)
        return self._vars[nombre]

    def _v(self, nombre) -> str:
        return self._vars[nombre].get().strip()

    def _campos(self, marco, etiquetas, fila0=0, columnas=2):
        """Crea pares etiqueta+entrada. etiquetas: [(clave, texto)]."""
        for i, (clave, texto) in enumerate(etiquetas):
            f, c = fila0 + i // columnas, (i % columnas) * 2
            ttk.Label(marco, text=texto).grid(row=f, column=c, sticky="e", padx=4, pady=3)
            ttk.Entry(marco, textvariable=self._var(clave), width=26).grid(row=f, column=c + 1, sticky="w", padx=4, pady=3)

    def _ejecutar(self, accion, exito=None):
        """Envuelve cada handler: errores controlados se muestran sin cerrar el programa."""
        try:
            resultado = accion()
            if exito:
                messagebox.showinfo("Listo", exito)
            return resultado
        except ErrorSistema as e:
            messagebox.showwarning("Revise los datos", str(e))
        except Exception as e:  # error inesperado: se informa, no se pierde el trabajo
            messagebox.showerror("Error inesperado", f"{type(e).__name__}: {e}")

    def _tabla(self, marco, columnas, alto=8):
        t = ttk.Treeview(marco, columns=[c for c, _ in columnas], show="headings", height=alto)
        for c, texto in columnas:
            t.heading(c, text=texto)
            t.column(c, width=120, anchor="w")
        t.pack(fill="both", expand=True, pady=6)
        return t

    @staticmethod
    def _llenar(tabla, filas):
        tabla.delete(*tabla.get_children())
        for f in filas:
            tabla.insert("", "end", values=f)

    # ------------------------------------------------------------ RF-01 pacientes
    def _tab_pacientes(self, m):
        form = ttk.LabelFrame(m, text="Datos del paciente", padding=8)
        form.pack(fill="x")
        self._campos(form, [("p_dni", "DNI (8 dígitos)"), ("p_nom", "Nombres"), ("p_ape", "Apellidos"),
                            ("p_nac", "Nacimiento (AAAA-MM-DD)"), ("p_dir", "Dirección"), ("p_tel", "Teléfono")])
        bt = ttk.Frame(m)
        bt.pack(fill="x", pady=6)
        ttk.Button(bt, text="Registrar", command=self._on_registrar_paciente).pack(side="left", padx=3)
        ttk.Button(bt, text="Actualizar", command=self._on_actualizar_paciente).pack(side="left", padx=3)
        ttk.Button(bt, text="Buscar por DNI", command=self._on_buscar_dni).pack(side="left", padx=3)
        ttk.Label(bt, text="  Buscar por nombre:").pack(side="left")
        ttk.Entry(bt, textvariable=self._var("p_busq"), width=20).pack(side="left", padx=3)
        ttk.Button(bt, text="Buscar", command=self._on_buscar_nombre).pack(side="left", padx=3)
        ttk.Button(bt, text="Ver todos", command=self._refrescar_pacientes).pack(side="left", padx=3)
        self._t_pac = self._tabla(m, [("dni", "DNI"), ("nombre", "Paciente"), ("edad", "Edad"),
                                      ("tel", "Teléfono"), ("dir", "Dirección")])

    def _on_registrar_paciente(self):
        def accion():
            self._srv.registrar_paciente(self._v("p_dni"), self._v("p_nom"), self._v("p_ape"),
                                         _fecha(self._v("p_nac"), obligatoria=True),
                                         self._v("p_dir"), self._v("p_tel"))
            self._refrescar_pacientes()
        self._ejecutar(accion, "Paciente registrado.")

    def _on_actualizar_paciente(self):
        def accion():
            self._srv.actualizar_paciente(self._v("p_dni"), self._v("p_nom") or None, self._v("p_ape") or None,
                                          self._v("p_dir"), self._v("p_tel"))
            self._refrescar_pacientes()
        self._ejecutar(accion, "Datos actualizados.")

    def _on_buscar_dni(self):
        def accion():
            p = self._srv.buscar_por_dni(self._v("p_dni"))
            self._mostrar_pacientes([p])
        self._ejecutar(accion)

    def _on_buscar_nombre(self):
        self._ejecutar(lambda: self._mostrar_pacientes(self._srv.buscar_por_nombre(self._v("p_busq"))))

    def _mostrar_pacientes(self, pacientes):
        self._llenar(self._t_pac, [(p.get_dni_enmascarado(), p.nombre_completo(), p.edad(),
                                    p.get_telefono(), p.get_direccion()) for p in pacientes])

    def _refrescar_pacientes(self):
        self._mostrar_pacientes(self._srv.listar_pacientes())

    # ------------------------------------------------------------ RF-02 historia
    def _tab_historia(self, m):
        top = ttk.LabelFrame(m, text="Paciente", padding=8)
        top.pack(fill="x")
        self._campos(top, [("h_dni", "DNI del paciente"), ("h_ale", "Alergias"), ("h_ant", "Antecedentes")], columnas=3)
        ttk.Button(top, text="Cargar historia", command=self._on_cargar_historia).grid(row=1, column=0, pady=4)
        ttk.Button(top, text="Guardar alergias/antecedentes", command=self._on_guardar_historia).grid(row=1, column=1, columnspan=2)
        nueva = ttk.LabelFrame(m, text="Nueva atención", padding=8)
        nueva.pack(fill="x", pady=6)
        self._campos(nueva, [("a_cmp", "CMP del médico"), ("a_mot", "Motivo"), ("a_cie", "Diagnóstico CIE-10")], columnas=3)
        ttk.Button(nueva, text="Registrar atención", command=self._on_registrar_atencion).grid(row=1, column=0, pady=4)
        self._t_aten = self._tabla(m, [("fecha", "Fecha"), ("motivo", "Motivo"), ("diag", "Diagnóstico"), ("medico", "CMP")])

    def _on_cargar_historia(self):
        def accion():
            h = self._srv.buscar_por_dni(self._v("h_dni")).get_historia()
            self._vars["h_ale"].set(h.get_alergias())
            self._vars["h_ant"].set(h.get_antecedentes())
            self._llenar(self._t_aten, [(a.get_fecha().isoformat(), a.get_motivo(), a.get_diagnostico(), a.get_cmp_medico())
                                        for a in h.get_atenciones()])
        self._ejecutar(accion)

    def _on_guardar_historia(self):
        self._ejecutar(lambda: self._srv.actualizar_historia(self._v("h_dni"), self._v("h_ale"), self._v("h_ant")),
                       "Historia clínica actualizada.")

    def _on_registrar_atencion(self):
        def accion():
            self._srv.registrar_atencion(self._v("h_dni"), self._v("a_cmp"), self._v("a_mot"), self._v("a_cie"))
            self._on_cargar_historia()
        self._ejecutar(accion, "Atención registrada.")

    # ------------------------------------------------------------ médicos
    def _tab_medicos(self, m):
        form = ttk.LabelFrame(m, text="Nuevo médico", padding=8)
        form.pack(fill="x")
        self._campos(form, [("m_dni", "DNI"), ("m_cmp", "CMP"), ("m_nom", "Nombres"), ("m_ape", "Apellidos"),
                            ("m_esp", "Especialidad"), ("m_tel", "Teléfono")])
        ttk.Button(m, text="Registrar médico", command=self._on_registrar_medico).pack(anchor="w", pady=6)
        self._t_med = self._tabla(m, [("cmp", "CMP"), ("nombre", "Médico"), ("esp", "Especialidad")])

    def _on_registrar_medico(self):
        def accion():
            self._srv.registrar_medico(self._v("m_dni"), self._v("m_nom"), self._v("m_ape"), self._v("m_cmp"),
                                       self._v("m_esp"), self._v("m_tel"))
            self._refrescar_medicos()
        self._ejecutar(accion, "Médico registrado.")

    def _refrescar_medicos(self):
        medicos = self._srv.listar_medicos()
        self._llenar(self._t_med, [(x.get_cmp(), x.nombre_completo(), x.get_especialidad()) for x in medicos])
        if hasattr(self, "_cb_medico"):
            self._cb_medico["values"] = [x.get_cmp() for x in medicos]

    # ------------------------------------------------------------ RF-03/04/05 citas y turnos
    def _tab_citas(self, m):
        form = ttk.LabelFrame(m, text="Agendar cita", padding=8)
        form.pack(fill="x")
        ttk.Label(form, text="DNI paciente").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(form, textvariable=self._var("c_dni"), width=14).grid(row=0, column=1, padx=4)
        ttk.Label(form, text="Médico (CMP)").grid(row=0, column=2, sticky="e", padx=4)
        self._cb_medico = ttk.Combobox(form, textvariable=self._var("c_cmp"), width=14, state="readonly")
        self._cb_medico.grid(row=0, column=3, padx=4)
        ttk.Label(form, text="Fecha (AAAA-MM-DD)").grid(row=0, column=4, sticky="e", padx=4)
        ttk.Entry(form, textvariable=self._var("c_fecha", date.today().isoformat()), width=12).grid(row=0, column=5, padx=4)
        ttk.Label(form, text="Turno").grid(row=0, column=6, sticky="e", padx=4)
        ttk.Combobox(form, textvariable=self._var("c_turno", TURNOS[0]), values=TURNOS, width=8,
                     state="readonly").grid(row=0, column=7, padx=4)
        bt = ttk.Frame(m)
        bt.pack(fill="x", pady=4)
        for texto, cmd in (("Agendar cita", self._on_agendar), ("Emitir ticket de la cita elegida", self._on_emitir),
                           ("Cancelar cita elegida", self._on_cancelar), ("Ver cupos", self._on_cupos),
                           ("Actualizar lista", self._refrescar_citas)):
            ttk.Button(bt, text=texto, command=cmd).pack(side="left", padx=3)
        self._lbl_cupos = ttk.Label(m, text="Cupos: —")
        self._lbl_cupos.pack(anchor="w")
        self._t_cit = self._tabla(m, [("id", "ID cita"), ("pac", "Paciente"), ("med", "Médico"), ("fecha", "Fecha"),
                                      ("turno", "Turno"), ("ticket", "N.º turno"), ("estado", "Estado")], alto=9)
        est = ttk.Frame(m)
        est.pack(fill="x")
        ttk.Label(est, text="Cambiar estado del turno elegido a:").pack(side="left")
        for e in ESTADOS_TICKET:
            ttk.Button(est, text=e.replace("_", " ").title(),
                       command=lambda e=e: self._on_estado(e)).pack(side="left", padx=3)

    def _cita_elegida(self):
        sel = self._t_cit.selection()
        if not sel:
            raise ErrorSistema("Seleccione primero una cita de la tabla.")
        return self._t_cit.item(sel[0], "values")

    def _on_agendar(self):
        def accion():
            self._srv.agendar_cita(self._v("c_dni"), self._v("c_cmp"), _fecha(self._v("c_fecha")), self._v("c_turno"))
            self._refrescar_citas()
            self._on_cupos()
        self._ejecutar(accion, "Cita agendada.")

    def _on_emitir(self):
        def accion():
            t = self._srv.emitir_ticket(self._cita_elegida()[0])
            self._refrescar_citas()
            messagebox.showinfo("Ticket emitido", f"Su número de turno es el {t.get_numero():03d}.")
        self._ejecutar(accion)

    def _on_cancelar(self):
        def accion():
            self._srv.cancelar_cita(self._cita_elegida()[0])
            self._refrescar_citas()
            self._on_cupos()
        self._ejecutar(accion, "Cita cancelada.")

    def _on_cupos(self):
        def accion():
            cupos = self._srv.consultar_cupos(self._v("c_cmp"), _fecha(self._v("c_fecha")))
            self._lbl_cupos.config(text="Cupos disponibles → " +
                                   "   ".join(f"{t}: {d}/{tot}" for t, (d, tot) in cupos.items()))
        self._ejecutar(accion)

    def _on_estado(self, estado):
        def accion():
            fila = self._cita_elegida()
            if not fila[5]:
                raise ErrorSistema("Esa cita aún no tiene ticket. Emítalo primero.")
            self._srv.cambiar_estado_ticket(date.fromisoformat(fila[3]), int(fila[5]), estado)
            self._refrescar_citas()
        self._ejecutar(accion)

    def _refrescar_citas(self):
        numeros = {t.get_cita().get_id(): t.get_numero() for t in self._srv.listar_tickets()}
        filas = [(c.get_id(), c.get_paciente().get_dni_enmascarado(), c.get_medico().get_cmp(),
                  c.get_fecha().isoformat(), c.get_turno(), numeros.get(c.get_id(), ""), c.get_estado())
                 for c in sorted(self._srv.listar_citas(), key=lambda c: (c.get_fecha(), c.get_turno()))]
        previa = self._t_cit.selection()
        id_previo = self._t_cit.item(previa[0], "values")[0] if previa else None
        self._llenar(self._t_cit, filas)
        for item in self._t_cit.get_children():          # conserva la cita elegida tras refrescar
            if self._t_cit.item(item, "values")[0] == id_previo:
                self._t_cit.selection_set(item)

    # ------------------------------------------------------------ RF-06 reportes
    def _tab_reportes(self, m):
        bar = ttk.Frame(m)
        bar.pack(fill="x")
        ttk.Label(bar, text="Tipo").pack(side="left", padx=4)
        ttk.Combobox(bar, textvariable=self._var("r_tipo", "diario"), values=ReporteFactory.tipos_disponibles(),
                     width=10, state="readonly").pack(side="left")
        ttk.Label(bar, text="Fecha de referencia (AAAA-MM-DD)").pack(side="left", padx=6)
        ttk.Entry(bar, textvariable=self._var("r_fecha", date.today().isoformat()), width=12).pack(side="left")
        ttk.Button(bar, text="Generar", command=self._on_reporte).pack(side="left", padx=8)
        self._txt = tk.Text(m, height=20, state="disabled", wrap="word")
        self._txt.pack(fill="both", expand=True, pady=8)

    def _on_reporte(self):
        def accion():
            r = self._srv.generar_reporte(self._v("r_tipo"), _fecha(self._v("r_fecha")))
            lineas = [f"Reporte {r['tipo']}: {r['desde']:%d/%m/%Y} al {r['hasta']:%d/%m/%Y}",
                      f"Atenciones realizadas: {r['total_atenciones']}", "", "Patologías más frecuentes (CIE-10):"]
            lineas += [f"  {i}. {cod}  —  {n} caso(s)" for i, (cod, n) in enumerate(r["patologias_frecuentes"], 1)] \
                or ["  (sin atenciones en el periodo)"]
            self._txt.config(state="normal")
            self._txt.delete("1.0", "end")
            self._txt.insert("1.0", "\n".join(lineas))
            self._txt.config(state="disabled")
        self._ejecutar(accion)

    # ------------------------------------------------------------
    def _refrescar_todo(self):
        self._refrescar_pacientes()
        self._refrescar_medicos()
        self._refrescar_citas()

