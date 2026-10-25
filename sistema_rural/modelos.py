"""Clases del dominio (DD-01): POO con atributos privados y getters/setters.

Convención: los atributos se escriben con guion bajo (-atributo en el UML) y
se acceden solo mediante get_/set_. Los datos sensibles se guardan cifrados.
"""
import re
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import date

from . import seguridad
from .errores import CupoAgotado, ErrorValidacion

TURNOS = ("MAÑANA", "TARDE")
ESTADOS_TICKET = ("RESERVADO", "EN_ATENCION", "COMPLETADO")
_CIE10 = re.compile(r"^[A-TV-Z]\d{2}(\.\d{1,2})?$")


def _texto_obligatorio(valor: str, campo: str) -> str:
    valor = str(valor).strip()
    if not valor:
        raise ErrorValidacion(f"El campo «{campo}» es obligatorio.")
    return valor


# ----------------------------------------------------------------- Personas
class Persona(ABC):
    """Datos comunes de pacientes y médicos. El DNI nunca queda en texto plano."""

    def __init__(self, dni, nombres, apellidos, telefono=""):
        dni = seguridad.validar_dni(dni)
        c = seguridad.cifrador()
        self._dni_cifrado = c.cifrar(dni)
        self._dni_hash = c.hash_dni(dni)
        self._nombres = _texto_obligatorio(nombres, "nombres")
        self._apellidos = _texto_obligatorio(apellidos, "apellidos")
        self._telefono = str(telefono).strip()

    # getters / setters
    def get_nombres(self): return self._nombres
    def set_nombres(self, v): self._nombres = _texto_obligatorio(v, "nombres")
    def get_apellidos(self): return self._apellidos
    def set_apellidos(self, v): self._apellidos = _texto_obligatorio(v, "apellidos")
    def get_telefono(self): return self._telefono
    def set_telefono(self, v): self._telefono = str(v).strip()
    def get_dni_hash(self): return self._dni_hash
    def nombre_completo(self): return f"{self._apellidos}, {self._nombres}"

    def _get_dni(self) -> str:
        """Uso interno (persistencia). La interfaz usa get_dni_enmascarado()."""
        return seguridad.cifrador().descifrar(self._dni_cifrado)

    def get_dni_enmascarado(self) -> str:
        return seguridad.enmascarar_dni(self._get_dni())

    def coincide_dni(self, dni: str) -> bool:
        """Compara por hash, sin exponer el número (DM-05)."""
        try:
            dni = seguridad.validar_dni(dni)
        except ErrorValidacion:
            return False
        return self._dni_hash == seguridad.cifrador().hash_dni(dni)

    @abstractmethod
    def rol(self) -> str: ...


class Medico(Persona):
    def __init__(self, dni, nombres, apellidos, cmp, especialidad, telefono=""):
        super().__init__(dni, nombres, apellidos, telefono)
        self._cmp = _texto_obligatorio(cmp, "CMP")
        self._especialidad = _texto_obligatorio(especialidad, "especialidad")

    def get_cmp(self): return self._cmp
    def get_especialidad(self): return self._especialidad
    def rol(self): return "Médico"

    def to_dict(self):
        return {"dni": self._get_dni(), "nombres": self._nombres, "apellidos": self._apellidos,
                "telefono": self._telefono, "cmp": self._cmp, "especialidad": self._especialidad}

    @classmethod
    def from_dict(cls, d):
        return cls(d["dni"], d["nombres"], d["apellidos"], d["cmp"], d["especialidad"], d.get("telefono", ""))


class Atencion:
    """Una consulta registrada: fecha, motivo y diagnóstico CIE-10 (cifrado)."""

    def __init__(self, fecha: date, motivo: str, diagnostico_cie10: str, cmp_medico: str):
        diag = str(diagnostico_cie10).strip().upper()
        if not _CIE10.fullmatch(diag):
            raise ErrorValidacion("Diagnóstico inválido: use un código CIE-10 (ej. J00 o E11.9).")
        self._fecha = fecha
        self._motivo = _texto_obligatorio(motivo, "motivo")
        self._diagnostico = seguridad.cifrador().cifrar(diag)
        self._cmp_medico = cmp_medico

    def get_fecha(self): return self._fecha
    def get_motivo(self): return self._motivo
    def get_cmp_medico(self): return self._cmp_medico
    def get_diagnostico(self): return seguridad.cifrador().descifrar(self._diagnostico)

    def to_dict(self):
        return {"fecha": self._fecha.isoformat(), "motivo": self._motivo,
                "diagnostico": self.get_diagnostico(), "cmp_medico": self._cmp_medico}

    @classmethod
    def from_dict(cls, d):
        return cls(date.fromisoformat(d["fecha"]), d["motivo"], d["diagnostico"], d["cmp_medico"])


class HistoriaClinica:
    """Alergias, antecedentes (cifrados) y lista de atenciones. Vive dentro del Paciente."""

    def __init__(self, alergias="", antecedentes=""):
        self._alergias = ""
        self._antecedentes = ""
        self._atenciones: list[Atencion] = []
        self.set_alergias(alergias)
        self.set_antecedentes(antecedentes)

    def get_alergias(self): return seguridad.cifrador().descifrar(self._alergias)
    def set_alergias(self, v): self._alergias = seguridad.cifrador().cifrar(str(v).strip())
    def get_antecedentes(self): return seguridad.cifrador().descifrar(self._antecedentes)
    def set_antecedentes(self, v): self._antecedentes = seguridad.cifrador().cifrar(str(v).strip())
    def get_atenciones(self): return tuple(self._atenciones)
    def agregar_atencion(self, atencion: Atencion): self._atenciones.append(atencion)

    def to_dict(self):
        return {"alergias": self.get_alergias(), "antecedentes": self.get_antecedentes(),
                "atenciones": [a.to_dict() for a in self._atenciones]}

    @classmethod
    def from_dict(cls, d):
        h = cls(d.get("alergias", ""), d.get("antecedentes", ""))
        for a in d.get("atenciones", []):
            h.agregar_atencion(Atencion.from_dict(a))
        return h


class Paciente(Persona):
    def __init__(self, dni, nombres, apellidos, fecha_nacimiento: date, direccion="", telefono=""):
        super().__init__(dni, nombres, apellidos, telefono)
        if fecha_nacimiento > date.today():
            raise ErrorValidacion("La fecha de nacimiento no puede ser futura.")
        self._fecha_nacimiento = fecha_nacimiento
        self._direccion = str(direccion).strip()
        self._historia = HistoriaClinica()  # composición: nace y muere con el paciente

    def get_fecha_nacimiento(self): return self._fecha_nacimiento
    def get_direccion(self): return self._direccion
    def set_direccion(self, v): self._direccion = str(v).strip()
    def get_historia(self): return self._historia
    def rol(self): return "Paciente"

    def edad(self, hoy: date | None = None) -> int:
        hoy = hoy or date.today()
        n = self._fecha_nacimiento
        return hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day))

    def to_dict(self):
        return {"dni": self._get_dni(), "nombres": self._nombres, "apellidos": self._apellidos,
                "telefono": self._telefono, "fecha_nacimiento": self._fecha_nacimiento.isoformat(),
                "direccion": self._direccion, "historia": self._historia.to_dict()}

    @classmethod
    def from_dict(cls, d):
        p = cls(d["dni"], d["nombres"], d["apellidos"], date.fromisoformat(d["fecha_nacimiento"]),
                d.get("direccion", ""), d.get("telefono", ""))
        p._historia = HistoriaClinica.from_dict(d.get("historia", {}))
        return p


# ------------------------------------------------------------ Citas y turnos
class Cita:
    """Cita con fecha, turno y estado. Asociada a un Paciente y un Médico."""

    def __init__(self, paciente: Paciente, medico: Medico, fecha: date, turno: str, id_cita=None, estado="RESERVADO"):
        if turno not in TURNOS:
            raise ErrorValidacion(f"Turno inválido. Opciones: {', '.join(TURNOS)}.")
        if estado not in ESTADOS_TICKET + ("CANCELADA",):
            raise ErrorValidacion("Estado de cita inválido.")
        self._id = id_cita or uuid.uuid4().hex[:8]
        self._paciente, self._medico = paciente, medico
        self._fecha, self._turno, self._estado = fecha, turno, estado

    def get_id(self): return self._id
    def get_paciente(self): return self._paciente
    def get_medico(self): return self._medico
    def get_fecha(self): return self._fecha
    def get_turno(self): return self._turno
    def get_estado(self): return self._estado
    def set_estado(self, estado):
        if estado not in ESTADOS_TICKET + ("CANCELADA",):
            raise ErrorValidacion("Estado de cita inválido.")
        self._estado = estado
    def ocupa_cupo(self): return self._estado != "CANCELADA"

    def to_dict(self):
        return {"id": self._id, "paciente": self._paciente.get_dni_hash(), "medico": self._medico.get_cmp(),
                "fecha": self._fecha.isoformat(), "turno": self._turno, "estado": self._estado}


class AgendaMedica:
    """Reúne las citas (agregación) y controla los cupos por turno (DM-04)."""

    def __init__(self, cupos_por_turno: int = 10):
        self._cupos = cupos_por_turno
        self._citas: dict[str, Cita] = {}

    def get_cupos_por_turno(self): return self._cupos
    def get_citas(self): return tuple(self._citas.values())
    def get_cita(self, id_cita): return self._citas.get(id_cita)

    def cupos_disponibles(self, medico: Medico, fecha: date, turno: str) -> int:
        usados = sum(1 for c in self._citas.values()
                     if c.ocupa_cupo() and c.get_medico() is medico and c.get_fecha() == fecha and c.get_turno() == turno)
        return self._cupos - usados

    def agendar(self, paciente: Paciente, medico: Medico, fecha: date, turno: str) -> Cita:
        if fecha < date.today():
            raise ErrorValidacion("No se puede agendar una cita en una fecha pasada.")
        if self.cupos_disponibles(medico, fecha, turno) <= 0:
            raise CupoAgotado(f"Sin cupos con {medico.nombre_completo()} el {fecha:%d/%m/%Y} ({turno}).")
        cita = Cita(paciente, medico, fecha, turno)
        self._citas[cita.get_id()] = cita
        return cita

    def agregar_existente(self, cita: Cita): self._citas[cita.get_id()] = cita


class GeneradorTurnos:
    """Singleton: una única fuente de números correlativos por día (CE-03)."""

    _instancia = None
    _candado = threading.Lock()

    def __new__(cls):
        with cls._candado:
            if cls._instancia is None:
                obj = super().__new__(cls)
                obj._contadores = {}
                cls._instancia = obj
            return cls._instancia

    def siguiente(self, fecha: date) -> int:
        with self._candado:
            clave = fecha.isoformat()
            self._contadores[clave] = self._contadores.get(clave, 0) + 1
            return self._contadores[clave]

    def exportar(self): return dict(self._contadores)

    def restaurar(self, contadores: dict):
        with self._candado:
            self._contadores = dict(contadores)


class Ticket:
    """Turno digital con número correlativo y estado (RF-04, RF-05)."""

    def __init__(self, cita: Cita, numero: int | None = None, fecha: date | None = None):
        self._cita = cita
        self._fecha = fecha or cita.get_fecha()
        self._numero = numero if numero is not None else GeneradorTurnos().siguiente(self._fecha)  # dependencia

    def get_numero(self): return self._numero
    def get_fecha(self): return self._fecha
    def get_cita(self): return self._cita
    def get_estado(self): return self._cita.get_estado()
    def cambiar_estado(self, estado):
        if estado not in ESTADOS_TICKET:
            raise ErrorValidacion(f"Estado inválido. Opciones: {', '.join(ESTADOS_TICKET)}.")
        self._cita.set_estado(estado)

    def to_dict(self):
        return {"numero": self._numero, "fecha": self._fecha.isoformat(), "cita": self._cita.get_id()}
