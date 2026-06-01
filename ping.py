import subprocess
import time
import json
import socket
import sqlite3

# Configuración del archivo de base de datos
DB_NAME = "red_aesa.db"

def realizar_ping(hostname):
    """Hace un ping rápido al nombre o IP del equipo."""
    try:
        comando = ["ping", "-n", "1", "-w", "1000", hostname]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return "verde" if "TTL=" in resultado.stdout else "rojo"
    except:
        return "rojo"

def obtener_ip(hostname):
    """Traduce el nombre (PCFxxx) a una IP real mediante resolución DNS."""
    try:
        return socket.gethostbyname(hostname)
    except:
        return "Sin IP"

def obtener_usuario(hostname):
    """Intenta detectar el usuario activo en la máquina remota."""
    try:
        comando = ["query", "user", "/server:" + hostname]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        lineas = resultado.stdout.strip().split('\n')
        if len(lineas) > 1:
            datos = lineas[1].split()
            return datos[0].replace(">", "") if datos else "Sin sesión"
        return "Sin sesión activa"
    except:
        return "No detectable"

def cargar_equipos_de_bd():
    """Conecta a SQLite y obtiene todos los equipos con su información de ubicación."""
    equipos = []
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id_equipo, tipo, ip_fija, edificio, piso, departamento, nombre_impresora FROM equipos")
        equipos = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"❌ Error al conectar con {DB_NAME}: {e}")
    return equipos

# =========================================================
# MOTOR PRINCIPAL
# =========================================================

print(f"📡 Iniciando monitoreo relacional: leyendo equipos desde {DB_NAME}...")

while True:
    estado_general = []
    equipos = cargar_equipos_de_bd()
    
    if not equipos:
        print("⚠️ Tabla vacía. Asegúrate de haber ejecutado los INSERT en DBeaver.")
    else:
        for eq in equipos:
            id_equipo, tipo, ip_fija, edificio, piso, departamento, nombre_impresora = eq
            
            # Las impresoras usan su IP fija como objetivo, las PCs usan su hostname
            target = ip_fija if ip_fija else id_equipo
            
            # 💡 EL TRUCO PARA LAS IMPRESORAS USB 💡
            if target == 'USB':
                estado = 'verde' # Forzamos la luz verde sin hacer ping
            else:
                estado = realizar_ping(target)
            
            if tipo == 'PC':
                ip_detectada = obtener_ip(target) if estado == 'verde' else "Offline"
                usuario = obtener_usuario(target) if estado == 'verde' else "DESCONECTADO"
                
                estado_general.append({
                    "id": id_equipo, 
                    "tipo": tipo,
                    "edificio": edificio,
                    "piso": piso,
                    "departamento": departamento,
                    "estado": estado, 
                    "usuario": usuario, 
                    "ip": ip_detectada
                })
                print(f"🖥️ {id_equipo} ({departamento}) | {estado} | {usuario}")
            
            else: # Si es Impresora
                # Si detecta que es la impresora USB, le pone el texto personalizado
                if target == 'USB':
                    estado_imp = "CONECTADA (USB)"
                else:
                    estado_imp = "CONECTADA" if estado == 'verde' else "DESCONECTADA"
                    
                estado_general.append({
                    "id": id_equipo, 
                    "tipo": tipo,
                    "edificio": edificio,
                    "piso": piso,
                    "departamento": departamento,
                    "estado": estado, 
                    "usuario": estado_imp,
                    "nombre_impresora": nombre_impresora,
                    "ip_fija": ip_fija
                })
                print(f"🖨️ {id_equipo} ({edificio}) | {estado}")

        try:
            with open('datos_red.json', 'w', encoding='utf-8') as f:
                json.dump(estado_general, f, indent=4)
        except Exception as e:
            print(f"❌ Error al guardar datos_red.json: {e}")
            
    print(f"✅ Ciclo terminado. Esperando 5 segundos...")
    time.sleep(5)