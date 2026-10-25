"""Pruebas automatizadas: CE-01, CE-02, CE-03, RD-02, RF-03, RF-06."""
import time
from datetime import date, timedelta

import pytest

from sistema_rural.errores import CupoAgotado, DNIDuplicado, ErrorValidacion, NoEncontrado
from sistema_rural.servicio import ServicioClinica

NAC = date(1990, 5, 17)
MAÑANA = date.today() + timedelta(days=1)


def dni(n: int) -> str:
    return f"{n:08d}"


@pytest.fixture
def srv(tmp_path):
    s = ServicioClinica(tmp_path / "datos.enc", tmp_path / "clave.key", cupos_por_turno=3)
    s.registrar_medico("40000001", "Rosa", "Quispe", "CMP-1001", "Medicina General")
    return s


# ---------------------------------------------------------------- RD-02
def test_dni_no_queda_en_texto_plano(srv):
    p = srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    assert p.get_dni_enmascarado() == "****5678"
    assert "12345678" not in str(vars(p))          # ni cifrado ni hash lo contienen en claro
    assert p.coincide_dni("12345678") and not p.coincide_dni("87654321")


def test_archivo_de_datos_esta_cifrado(srv, tmp_path):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    srv.actualizar_historia("12345678", alergias="Penicilina")
    srv.registrar_atencion("12345678", "CMP-1001", "Fiebre", "J00")
    crudo = (tmp_path / "datos.enc").read_bytes()
    for secreto in (b"12345678", b"Penicilina", b"J00", b"Torres"):
        assert secreto not in crudo


def test_persistencia_ida_y_vuelta(srv, tmp_path):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    srv.registrar_atencion("12345678", "CMP-1001", "Tos", "J20")
    cita = srv.agendar_cita("12345678", "CMP-1001", MAÑANA, "MAÑANA")
    srv.emitir_ticket(cita.get_id())
    otro = ServicioClinica(tmp_path / "datos.enc", tmp_path / "clave.key", cupos_por_turno=3)
    assert otro.buscar_por_dni("12345678").get_historia().get_atenciones()[0].get_diagnostico() == "J20"
    assert [t.get_numero() for t in otro.listar_tickets()] == [1]
    nuevo = otro.emitir_ticket(otro.agendar_cita("12345678", "CMP-1001", MAÑANA, "TARDE").get_id())
    assert nuevo.get_numero() == 2   # el correlativo continúa tras reiniciar


# ---------------------------------------------------------------- validaciones
@pytest.mark.parametrize("malo", ["1234567", "123456789", "1234567a", "", "12 45678"])
def test_dni_invalido_se_rechaza(srv, malo):
    with pytest.raises(ErrorValidacion):
        srv.registrar_paciente(malo, "Ana", "Torres", NAC)


def test_cie10_invalido_se_rechaza(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    with pytest.raises(ErrorValidacion):
        srv.registrar_atencion("12345678", "CMP-1001", "Dolor", "XYZ")


def test_paciente_inexistente(srv):
    with pytest.raises(NoEncontrado):
        srv.buscar_por_dni("99999999")


# ---------------------------------------------------------------- CE-02
def test_ce02_dni_repetido_es_rechazado(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    with pytest.raises(DNIDuplicado):
        srv.registrar_paciente("12345678", "Otra", "Persona", NAC)
    assert len(srv.listar_pacientes()) == 1


# ---------------------------------------------------------------- RF-03 / RF-05
def test_cupos_se_agotan_y_se_liberan(srv):
    for i in range(1, 5):
        srv.registrar_paciente(dni(i), f"P{i}", "Prueba", NAC)
    citas = [srv.agendar_cita(dni(i), "CMP-1001", MAÑANA, "MAÑANA") for i in range(1, 4)]
    assert srv.consultar_cupos("CMP-1001", MAÑANA)["MAÑANA"] == (0, 3)
    with pytest.raises(CupoAgotado):
        srv.agendar_cita(dni(4), "CMP-1001", MAÑANA, "MAÑANA")
    srv.cancelar_cita(citas[0].get_id())
    srv.agendar_cita(dni(4), "CMP-1001", MAÑANA, "MAÑANA")   # el cupo liberado se puede reusar


def test_no_se_agenda_en_el_pasado(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    with pytest.raises(ErrorValidacion):
        srv.agendar_cita("12345678", "CMP-1001", date.today() - timedelta(days=1), "MAÑANA")


# ---------------------------------------------------------------- CE-03
def test_ce03_cien_tickets_correlativos_y_unicos(tmp_path):
    s = ServicioClinica(tmp_path / "d.enc", tmp_path / "k.key", cupos_por_turno=100)
    s.registrar_medico("40000001", "Rosa", "Quispe", "CMP-1001", "Medicina General")
    for i in range(100):
        s.registrar_paciente(dni(10_000_000 + i), f"P{i}", "Prueba", NAC)
        s.emitir_ticket(s.agendar_cita(dni(10_000_000 + i), "CMP-1001", MAÑANA, "MAÑANA").get_id())
    numeros = [t.get_numero() for t in s.listar_tickets(MAÑANA)]
    assert numeros == list(range(1, 101))
    assert len(set(numeros)) == 100


def test_ticket_cambia_de_estado(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    t = srv.emitir_ticket(srv.agendar_cita("12345678", "CMP-1001", MAÑANA, "MAÑANA").get_id())
    srv.cambiar_estado_ticket(MAÑANA, t.get_numero(), "EN_ATENCION")
    assert t.get_estado() == "EN_ATENCION"
    with pytest.raises(ErrorValidacion):
        srv.cambiar_estado_ticket(MAÑANA, t.get_numero(), "INVENTADO")


# ---------------------------------------------------------------- CE-01
def test_ce01_busqueda_menor_a_3_segundos(tmp_path):
    s = ServicioClinica(tmp_path / "d.enc", tmp_path / "k.key")
    # 1000 pacientes (muy por encima de lo que atiende la posta); se guarda una vez al final
    from sistema_rural.modelos import Paciente
    for i in range(1000):
        p = Paciente(dni(20_000_000 + i), f"Nombre{i}", f"Apellido{i}", NAC)
        s._pacientes[p.get_dni_hash()] = p
    tiempos = []
    for i in range(0, 1000, 50):   # 20 búsquedas
        t0 = time.perf_counter()
        s.buscar_por_dni(dni(20_000_000 + i))
        tiempos.append(time.perf_counter() - t0)
    assert len(tiempos) == 20 and max(tiempos) < 3.0


# ---------------------------------------------------------------- RF-06
def test_reportes_diario_semanal_mensual(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    hoy = date(2026, 10, 14)  # miércoles
    for dias, cie in [(0, "J00"), (0, "J00"), (1, "E11.9"), (-5, "J00"), (-20, "I10")]:
        srv.registrar_atencion("12345678", "CMP-1001", "Consulta", cie, fecha=hoy + timedelta(days=dias))
    d, s, m = (srv.generar_reporte(t, hoy) for t in ("diario", "semanal", "mensual"))
    assert d["total_atenciones"] == 2
    assert s["total_atenciones"] == 3       # lunes 12 al domingo 18
    assert m["total_atenciones"] == 4       # octubre 2026 (la de -20 cae en septiembre)
    assert m["patologias_frecuentes"][0] == ("J00", 3)
    with pytest.raises(ErrorValidacion):
        srv.generar_reporte("anual", hoy)


def test_busqueda_por_nombre(srv):
    srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    srv.registrar_paciente("12345679", "Luis", "Torres", NAC)
    assert len(srv.buscar_por_nombre("torres")) == 2
    assert len(srv.buscar_por_nombre("luis")) == 1


# ---------------------------------------------------------------- patrones y encapsulamiento (rúbrica EF)
def test_singleton_generador_turnos_es_una_sola_instancia():
    from sistema_rural.modelos import GeneradorTurnos
    assert GeneradorTurnos() is GeneradorTurnos()


def test_factory_crea_el_reporte_correcto():
    from sistema_rural.reportes import ReporteDiario, ReporteFactory, ReporteMensual, ReporteSemanal
    assert isinstance(ReporteFactory.crear("diario", []), ReporteDiario)
    assert isinstance(ReporteFactory.crear("Semanal", []), ReporteSemanal)
    assert isinstance(ReporteFactory.crear("MENSUAL", []), ReporteMensual)


def test_persona_es_abstracta():
    from sistema_rural.modelos import Persona
    with pytest.raises(TypeError):
        Persona("12345678", "Ana", "Torres")


def test_setters_validan_los_datos(srv):
    p = srv.registrar_paciente("12345678", "Ana", "Torres", NAC)
    with pytest.raises(ErrorValidacion):
        p.set_nombres("   ")
    p.set_telefono(" 955123456 ")
    assert p.get_telefono() == "955123456"
