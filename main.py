"""Punto de entrada: python main.py"""
from sistema_rural.interfaz import VentanaPrincipal
from sistema_rural.servicio import ServicioClinica

if __name__ == "__main__":
    VentanaPrincipal(ServicioClinica("datos.enc", "clave.key")).mainloop()
