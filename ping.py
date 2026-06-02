import subprocess
import time
import json
import socket
import sqlite3
import os

# =========================================================
# CONFIGURACIÓN
# =========================================================
DB_NAME = "red_aesa.db"

# 🚀 LA NUEVA LÍNEA: Guarda el JSON directo en el servidor Ubuntu por la red
JSON_OUTPUT_PATH = r"\\192.168.0.194\PanelWeb\datos_red.json" 

# =========================================================
# FUNCIONES
# =========================================================

def realizar_ping(hostname):
    """Hace un ping rápido usando la consola nativa de Windows."""
    try:
        # En Windows se usa '-n' para la cantidad y '-w' para los milisegundos
        comando = ["ping", "-n", "1", "-w", "1000", hostname]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        # Si responde, el texto incluye "TTL="
        return "verde" if "TTL=" in resultado.stdout.upper() else "rojo"
    except:
        return "rojo"

def obtener_ip(hostname):
    """Traduce el nombre (PCFxxx) a una IP real mediante resolución DNS."""
    try:
        return socket.gethostbyname(hostname)
    except:
        return "Sin IP"

def obtener_usuario_windows(hostname):
    """
    Usa el comando nativo de Windows 'query user' para consultar la PC remota.
    Como se ejecuta desde otra PC con Windows de la misma red, no lo bloquean.
    """
    try:
        comando = ["query", "user", f"/server:{hostname}"]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        
        if resultado.returncode == 0:
            lineas = resultado.stdout.strip().split('\n')
            if len(lineas) > 1:
                linea_datos = lineas[1].strip()
                # Limpiamos el '>' que Windows le pone al usuario activo
                if linea_datos.startswith('>'):
                    linea_datos = linea_datos[1:]
                
                # Agarramos la primera palabra (el nombre de usuario)
                usuario_real = linea_datos.split()[0]
                return usuario_real
                
            return "Sesión Activa"
        return "Sin sesión activa"
    except Exception:
        return "No detectable"

def cargar_equipos_de_bd():
    """Conecta a SQLite y obtiene todos los equipos."""
    equipos = []
    try:
        # Asegurate de que red_aesa.db esté en la misma carpeta que este script
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

print(f"📡 Iniciando motor híbrido en Windows... Enviando datos a {JSON_OUTPUT_PATH}")

while True:
    estado_general = []
    equipos = cargar_equipos_de_bd()
    
    if not equipos:
        print("⚠️ Tabla vacía o base de datos no encontrada.")
    else:
        for eq in equipos:
            id_equipo, tipo, ip_fija, edificio, piso, departamento, nombre_impresora = eq
            
            target = ip_fija if ip_fija else id_equipo
            
            # 💡 EL TRUCO PARA LAS IMPRESORAS USB 💡
            if target == 'USB':
                estado = 'verde'
            else:
                estado = realizar_ping(target)
            
            if tipo == 'PC':
                ip_detectada = obtener_ip(target) if estado == 'verde' else "Offline"
                usuario = obtener_usuario_windows(target) if estado == 'verde' else "DESCONECTADO"
                
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

        # Guardar el JSON directamente en el servidor Ubuntu por red
        try:
            with open(JSON_OUTPUT_PATH, 'w', encoding='utf-8') as f:
                json.dump(estado_general, f, indent=4)
        except Exception as e:
            print(f"❌ Error de red al guardar en Ubuntu: {e}\n(Verificá que la IP sea correcta y la carpeta esté compartida)")
            
    print(f"✅ Ciclo terminado. Esperando 5 segundos...")
    time.sleep(5)