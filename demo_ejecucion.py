"""Demostración de SistemaRural-PE con datos FICTICIOS (carpeta temporal; no toca datos/).
Uso: python demo_ejecucion.py   (desde la raíz del proyecto)"""
import sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path
from sistema_rural.servicio import ServicioClinica
from sistema_rural.acceso import ServicioProtegido
from sistema_rural.errores import ErrorSistema

def titulo(t): print(f"\n=== {t} ===")
def intentar(f, *a, **k):
    try: return f(*a, **k)
    except ErrorSistema as e: print(f"  [{type(e).__name__}] {e}")

carpeta = Path(tempfile.mkdtemp())
s = ServicioClinica(carpeta / "datos.enc", carpeta / "clave.key")
s.crear_primer_administrador("admin", "Ana", "Administradora", "Posta2026")
s.registrar_medico("40000001", "Rosa", "Quispe Vera", "CMP-1001", "Medicina General")
s.crear_usuario("admision", "Eva", "Ríos Cano", "ADMISION", "Posta2026", debe_cambiar_clave=False)
s.crear_usuario("medico", "Rosa", "Quispe Vera", "MEDICO", "Posta2026", "CMP-1001", debe_cambiar_clave=False)
s.crear_usuario("tecnica", "Rita", "Gómez Lino", "TEC_ENFERMERIA", "Posta2026", debe_cambiar_clave=False)

titulo("1. Inicio de sesión y control de acceso por rol (Proxy)")
print("  clave incorrecta ->", end=" "); intentar(s.autenticar, "admision", "mala")
adm = ServicioProtegido(s, s.autenticar("admision", "Posta2026"))
med = ServicioProtegido(s, s.autenticar("medico", "Posta2026"))
tec = ServicioProtegido(s, s.autenticar("tecnica", "Posta2026"))

titulo("2. Registro de pacientes (documento enmascarado)")
for i, (n, a) in enumerate([("Ana", "Torres Gil"), ("Luis", "Paredes Soto"), ("María", "Castillo Ríos")]):
    p = adm.registrar_paciente(f"7000000{i}", n, a, date(1985 + i, 3, 10 + i), "Moche, La Libertad", f"95000000{i}")
    print(f"  {p.nombre_completo():<22} documento: {p.get_tipo_documento()} {p.get_dni_enmascarado()}")
print("  DNI repetido  ->", end=" "); intentar(adm.registrar_paciente, "70000000", "Otra", "Persona", date(1990, 1, 1))
print("  DNI de 7 dígitos ->", end=" "); intentar(adm.registrar_paciente, "1234567", "X", "Y", date(1990, 1, 1))

titulo("3. Permisos: lo que cada rol puede y no puede hacer")
print("  Admisión ve historia clínica ->", end=" "); intentar(lambda: adm.obtener_historia("70000000"))
print("  Técnica registra paciente    ->", end=" "); intentar(lambda: tec.registrar_paciente("70000009", "A", "B", date(1990, 1, 1)))
print("  Médico registra atención     ->", end=" ")
a = med.registrar_atencion("70000000", "Consulta de rutina", "J00"); print(f"OK (CMP {a.get_cmp_medico()}, CIE-10 {a.get_diagnostico()})")
med.registrar_atencion("70000001", "Control", "J00"); med.registrar_atencion("70000002", "Control", "E11.9")

titulo("4. Citas y tickets correlativos (Singleton)")
dia = date.today() + timedelta(days=1)
while dia.weekday() == 6: dia += timedelta(days=1)
horas = s.horas_disponibles("CMP-1001", dia)
print(f"  Cupo libre el {dia:%d/%m/%Y} con CMP-1001: {len(horas)} horas de 30 min disponibles")
nums = []
for i in range(3):
    c = adm.agendar_cita(f"7000000{i}", "CMP-1001", dia, "MAÑANA")
    nums.append(adm.emitir_ticket(c.get_id()).get_numero())
print("  Tickets emitidos:", nums)

titulo("5. Reporte con funciones de orden superior (filter / map / reduce)")
r = med.generar_reporte("diario", date.today())
print(f"  {r['tipo']}: {r['desde']:%d/%m/%Y} a {r['hasta']:%d/%m/%Y} | atenciones: {r['total_atenciones']} | CIE-10 frecuentes: {r['patologias_frecuentes']}")
print("  tipo desconocido ->", end=" "); intentar(lambda: med.generar_reporte("anual"))

titulo("6. Archivo de datos cifrado (Ley N.º 29733)")
crudo = (carpeta / "datos.enc").read_bytes()
for dato in (b"70000000", b"Torres", b"J00", b"E11.9"):
    print(f"  '{dato.decode()}' aparece en texto plano en datos.enc: {'SÍ' if dato in crudo else 'NO'}")
print(f"  Primeros bytes del archivo: {crudo[:34].decode('ascii', 'replace')}...")

titulo("7. Rendimiento de búsqueda por DNI")
t0 = time.perf_counter(); s.buscar_por_dni("70000001"); print(f"  Búsqueda: {(time.perf_counter()-t0)*1000:.3f} ms (meta CE-01: < 3 s)")
