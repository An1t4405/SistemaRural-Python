"""Carga datos FICTICIOS para probar el sistema antes de tener la posta.
Uso: python cargar_demo.py   (crea datos.enc y clave.key; bórrelos antes de usar datos reales)"""
from datetime import date, timedelta

from sistema_rural.servicio import ServicioClinica

s = ServicioClinica("datos.enc", "clave.key")
if not s.listar_medicos():
    s.registrar_medico("40000001", "Rosa", "Quispe Vera", "CMP-1001", "Medicina General")
    s.registrar_medico("40000002", "Carlos", "Mendoza Ruiz", "CMP-1002", "Obstetricia")
    for i, (n, a) in enumerate([("Ana", "Torres Gil"), ("Luis", "Paredes Soto"), ("María", "Castillo Ríos"),
                                ("José", "Alva Núñez"), ("Elena", "Rojas León")]):
        s.registrar_paciente(f"7000000{i}", n, a, date(1985 + i, 3, 10 + i), "Moche, La Libertad", f"95000000{i}")
    for i, cie in enumerate(["J00", "J00", "E11.9", "I10", "J20"]):
        s.registrar_atencion(f"7000000{i}", "CMP-1001", "Consulta de rutina", cie, date.today() - timedelta(days=i))
    manana = date.today() + timedelta(days=1)
    for i in range(3):
        s.emitir_ticket(s.agendar_cita(f"7000000{i}", "CMP-1001", manana, "MAÑANA").get_id())
print("Datos de demostración cargados.")
