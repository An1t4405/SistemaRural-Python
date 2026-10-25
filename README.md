# SistemaRural-PE

Módulo de software de código abierto para digitalizar el registro de pacientes, historias clínicas,
citas, turnos y reportes de una posta médica rural (Python 3 + Tkinter).

## Instalación y uso
```
pip install -r requirements.txt
python cargar_demo.py     # (opcional) datos FICTICIOS para probar
python main.py            # abre la aplicación
python -m pytest -v       # pruebas automatizadas (CE-01, CE-02, CE-03, RD-02...)
python medir_recursos.py  # evidencia de CE-01 y RD-03
```
En Linux puede faltar Tkinter: `sudo apt install python3-tk`.
**Importante:** `clave.key` es la llave de cifrado. Sin ella `datos.enc` no se puede abrir; haga copia de ambos
y no suba `clave.key` ni `datos.enc` a GitHub (ya están en `.gitignore`).

## Estructura (trazabilidad con el informe)
| Archivo | Contenido | Requisito |
|---|---|---|
| `sistema_rural/seguridad.py` | Cifrado Fernet, hash HMAC del DNI, enmascarado | RD-02, DM-01, DM-05 |
| `sistema_rural/modelos.py` | Persona (abstracta), Paciente, Medico, HistoriaClinica, Atencion, AgendaMedica, Cita, Ticket, **GeneradorTurnos (Singleton)** | DD-01, RF-01 a RF-05 |
| `sistema_rural/reportes.py` | Reporte (abstracta), Diario/Semanal/Mensual, **ReporteFactory** (map/filter/reduce/lambda) | DD-02, RF-06 |
| `sistema_rural/servicio.py` | ServicioClinica: operaciones + persistencia cifrada | RF-01 a RF-06 |
| `sistema_rural/interfaz.py` | VentanaPrincipal: solo handlers de eventos que delegan al servicio | DD-03, RD-04 |
| `tests/test_sistema.py` | pytest | CE-01, CE-02, CE-03 |

## Paradigmas
- **POO**: entidades del dominio con atributos privados (`_x`) y getters/setters; herencia, composición, agregación.
- **Funcional**: reportes y búsquedas con `map`, `filter`, `reduce`, `lambda`, sin modificar las historias.
- **Eventos**: `Tkinter` con handlers (`_on_*`) y `try/except` central en `_ejecutar`.
- **Estructurado**: validaciones y secuencias dentro de los métodos (DD-04).

## Documentos de apoyo para el informe
- `docs/criterios_aceptacion_GUI.md`: componente → evento → criterio → prueba (Tema 5.3).
- `docs/calidad_codigo_y_SOLID.md`: SOLID, buenas prácticas, funciones de orden superior y reflexión sobre usuarios ([1.5]).
- `docs/resultado_pruebas.txt`: resultado de `pytest -v` (evidencia de pruebas automatizadas).

## Subir el repositorio a GitHub (debe ser público)
```
git remote add origin https://github.com/SU_USUARIO/SistemaRural-PE.git
git branch -M main
git push -u origin main
```
Los datos del sistema son **ficticios** (`cargar_demo.py`); no se usan datos reales de pacientes.
