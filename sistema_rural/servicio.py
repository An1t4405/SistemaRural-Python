"""ServicioClinica: concentra las operaciones del sistema (RF-01 a RF-06).

La interfaz solo llama a este servicio (DD-03). Todo el archivo de datos se
guarda cifrado (RD-02).
"""
import json
import os
from datetime import date
from itertools import chain
from pathlib import Path

from . import seguridad
from .errores import DNIDuplicado, ErrorValidacion, NoEncontrado
from .modelos import (AgendaMedica, Atencion, Cita, GeneradorTurnos, Medico, Paciente, Ticket)
from .reportes import ReporteFactory


class ServicioClinica:
    def __init__(self, ruta_datos="datos.enc", ruta_clave="clave.key", cupos_por_turno=10):
        self._cif = seguridad.configurar(ruta_clave)
        self._ruta = Path(ruta_datos)
        self._pacientes: dict[str, Paciente] = {}   # clave: hash del DNI (búsqueda O(1))
        self._medicos: dict[str, Medico] = {}       # clave: CMP
        self._agenda = AgendaMedica(cupos_por_turno)
        self._tickets: list[Ticket] = []
        GeneradorTurnos().restaurar({})
        if self._ruta.exists():
            self.cargar()

    # ------------------------------------------------ RF-01 pacientes
    def registrar_paciente(self, dni, nombres, apellidos, fecha_nacimiento, direccion="", telefono="") -> Paciente:
        nuevo = Paciente(dni, nombres, apellidos, fecha_nacimiento, direccion, telefono)
        if nuevo.get_dni_hash() in self._pacientes:
            raise DNIDuplicado("Ya existe un paciente registrado con ese DNI.")  # CE-02
        self._pacientes[nuevo.get_dni_hash()] = nuevo
        self.guardar()
        return nuevo

    def actualizar_paciente(self, dni, nombres=None, apellidos=None, direccion=None, telefono=None) -> Paciente:
        p = self.buscar_por_dni(dni)
        if nombres is not None: p.set_nombres(nombres)
        if apellidos is not None: p.set_apellidos(apellidos)
        if direccion is not None: p.set_direccion(direccion)
        if telefono is not None: p.set_telefono(telefono)
        self.guardar()
        return p

    def buscar_por_dni(self, dni) -> Paciente:
        dni = seguridad.validar_dni(dni)
        p = self._pacientes.get(self._cif.hash_dni(dni))
        if p is None:
            raise NoEncontrado("No existe un paciente con ese DNI.")
        return p

    def buscar_por_nombre(self, texto: str) -> list[Paciente]:
        t = texto.strip().lower()
        return sorted(filter(lambda p: t in p.nombre_completo().lower(), self._pacientes.values()),
                      key=lambda p: p.nombre_completo())

    def listar_pacientes(self): return sorted(self._pacientes.values(), key=lambda p: p.nombre_completo())

    # ------------------------------------------------ médicos
    def registrar_medico(self, dni, nombres, apellidos, cmp, especialidad, telefono="") -> Medico:
        if cmp.strip() in self._medicos:
            raise ErrorValidacion("Ya existe un médico con ese CMP.")
        m = Medico(dni, nombres, apellidos, cmp, especialidad, telefono)
        self._medicos[m.get_cmp()] = m
        self.guardar()
        return m

    def obtener_medico(self, cmp) -> Medico:
        try:
            return self._medicos[str(cmp).strip()]
        except KeyError:
            raise NoEncontrado("No existe un médico con ese CMP.") from None

    def listar_medicos(self): return sorted(self._medicos.values(), key=lambda m: m.nombre_completo())

    # ------------------------------------------------ RF-02 historia clínica
    def actualizar_historia(self, dni, alergias=None, antecedentes=None):
        h = self.buscar_por_dni(dni).get_historia()
        if alergias is not None: h.set_alergias(alergias)
        if antecedentes is not None: h.set_antecedentes(antecedentes)
        self.guardar()

    def registrar_atencion(self, dni, cmp, motivo, diagnostico_cie10, fecha: date | None = None) -> Atencion:
        p, m = self.buscar_por_dni(dni), self.obtener_medico(cmp)
        a = Atencion(fecha or date.today(), motivo, diagnostico_cie10, m.get_cmp())
        p.get_historia().agregar_atencion(a)
        self.guardar()
        return a

    def todas_las_atenciones(self):
        return chain.from_iterable(p.get_historia().get_atenciones() for p in self._pacientes.values())

    # ------------------------------------------------ RF-03 citas
    def agendar_cita(self, dni, cmp, fecha: date, turno: str) -> Cita:
        cita = self._agenda.agendar(self.buscar_por_dni(dni), self.obtener_medico(cmp), fecha, turno)
        self.guardar()
        return cita

    def cancelar_cita(self, id_cita):
        cita = self._agenda.get_cita(id_cita)
        if cita is None:
            raise NoEncontrado("No existe esa cita.")
        cita.set_estado("CANCELADA")
        self.guardar()

    def listar_citas(self, fecha: date | None = None):
        return [c for c in self._agenda.get_citas() if fecha is None or c.get_fecha() == fecha]

    # ------------------------------------------------ RF-04 tickets
    def emitir_ticket(self, id_cita) -> Ticket:
        cita = self._agenda.get_cita(id_cita)
        if cita is None or not cita.ocupa_cupo():
            raise NoEncontrado("La cita no existe o está cancelada.")
        if any(t.get_cita() is cita for t in self._tickets):
            raise ErrorValidacion("Esa cita ya tiene un ticket emitido.")
        t = Ticket(cita)
        self._tickets.append(t)
        self.guardar()
        return t

    def cambiar_estado_ticket(self, fecha: date, numero: int, estado: str):
        for t in self._tickets:
            if t.get_fecha() == fecha and t.get_numero() == numero:
                t.cambiar_estado(estado)
                self.guardar()
                return t
        raise NoEncontrado("No existe ese ticket.")

    def listar_tickets(self, fecha: date | None = None):
        return sorted(filter(lambda t: fecha is None or t.get_fecha() == fecha, self._tickets),
                      key=lambda t: (t.get_fecha(), t.get_numero()))

    # ------------------------------------------------ RF-05 disponibilidad
    def consultar_cupos(self, cmp, fecha: date) -> dict:
        """{turno: (disponibles, total)} para un médico y fecha."""
        m = self.obtener_medico(cmp)
        total = self._agenda.get_cupos_por_turno()
        return {t: (self._agenda.cupos_disponibles(m, fecha, t), total) for t in ("MAÑANA", "TARDE")}

    # ------------------------------------------------ RF-06 reportes
    def generar_reporte(self, tipo: str, fecha: date | None = None) -> dict:
        return ReporteFactory.crear(tipo, self.todas_las_atenciones()).generar(fecha or date.today())

    # ------------------------------------------------ persistencia cifrada
    def guardar(self):
        datos = {
            "pacientes": [p.to_dict() for p in self._pacientes.values()],
            "medicos": [m.to_dict() for m in self._medicos.values()],
            "cupos_por_turno": self._agenda.get_cupos_por_turno(),
            "citas": [c.to_dict() for c in self._agenda.get_citas()],
            "tickets": [t.to_dict() for t in self._tickets],
            "contadores": GeneradorTurnos().exportar(),
        }
        crudo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        tmp = self._ruta.with_suffix(".tmp")
        tmp.write_bytes(self._cif.cifrar_bytes(crudo))
        os.replace(tmp, self._ruta)  # escritura atómica: no deja el archivo a medias

    def cargar(self):
        datos = json.loads(self._cif.descifrar_bytes(self._ruta.read_bytes()))
        self._pacientes = {p.get_dni_hash(): p for p in map(Paciente.from_dict, datos["pacientes"])}
        self._medicos = {m.get_cmp(): m for m in map(Medico.from_dict, datos["medicos"])}
        self._agenda = AgendaMedica(datos.get("cupos_por_turno", 10))
        for c in datos["citas"]:
            self._agenda.agregar_existente(Cita(self._pacientes[c["paciente"]], self._medicos[c["medico"]],
                                                date.fromisoformat(c["fecha"]), c["turno"], c["id"], c["estado"]))
        self._tickets = [Ticket(self._agenda.get_cita(t["cita"]), t["numero"], date.fromisoformat(t["fecha"]))
                         for t in datos["tickets"]]
        GeneradorTurnos().restaurar(datos.get("contadores", {}))
