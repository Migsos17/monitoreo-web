import subprocess
import time
import json
import socket
import sqlite3
import os

# Configuración del archivo de base de datos
DB_NAME = "red_aesa.db"
# Ruta donde Apache lee los archivos en Ubuntu
JSON_OUTPUT_PATH = "/var/www/html/datos_red.json" 

def realizar_ping(hostname):
    """Hace un ping rápido compatible con Linux (Ubuntu)."""
    try:
        # En Linux se usa '-c' para la cantidad y '-w' es el tiempo de espera en segundos
        comando = ["ping", "-c", "1", "-w", "1", hostname]
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
        # En Linux 'ttl' viene en minúsculas
        return "verde" if "ttl=" in resultado.stdout.lower() else "rojo"
    except:
        return "rojo"

def obtener_ip(hostname):
    """Traduce el nombre (PCFxxx) a una IP real mediante resolución DNS."""
    try:
        return socket.gethostbyname(hostname)
    except:
        return "Sin IP"

def obtener_usuario_linux(hostname):
    """
    Consulta de forma remota el nombre del usuario activo en una máquina Windows 
    desde Linux utilizando comandos Net RPC de Samba.
    """
    try:
        # 🔐 LECTURA SEGURA DESDE VARIABLES DE ENTORNO
        USUARIO_RED = os.getenv("AESA_NET_USER", "usuario_defecto")
        PASSWORD_RED = os.getenv("AESA_NET_PASS", "clave_defecto")
        DOMINIO = "aesa" 

        # Comando Net RPC específico para extraer la sesión interactiva real
        comando = [
            "net", "rpc", "workstation", "user", "query",
            "-S", hostname,
            "-U", f"{DOMINIO}\\{USUARIO_RED}%{PASSWORD_RED}"
        ]
        
        # Ejecutamos con un tiempo límite de 3 segundos por equipo
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
        
        if resultado.returncode == 0 and resultado.stdout:
            lineas = resultado.stdout.strip().split('\n')
            for linea in lineas:
                # El output estándar de Windows reporta: "User logged in: NOMBRE"
                if "logged in:" in linea.lower():
                    partes = linea.split(":")
                    if len(partes) > 1:
                        usuario_real = partes[1].strip()
                        # Si devolvió un string válido y no está vacío o marcado como 'none'
                        if usuario_real and "none" not in usuario_real.lower():
                            return usuario_real
            
            # Respaldo si el puerto respondió pero la sesión interactiva está en transición
            return "Sesión Activa"
        
        return "Sin sesión activa"
    except Exception as e:
        return "No detectable"

def cargar_equipos_de_bd():
    """Conecta a SQLite y obtiene todos los equipos."""
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

print(f"📡 Iniciando monitoreo relacional en Linux: leyendo desde {DB_NAME}...")

while True:
    estado_general = []
    equipos = cargar_equipos_de_bd()
    
    if not equipos:
        print("⚠️ Tabla vacía o base de datos no encontrada.")
    else:
        for eq in equipos:
            id_equipo, tipo, ip_fija, edificio, piso, departamento, nombre_impresora = eq
            
            # Las impresoras usan su IP fija como objetivo, las PCs usan su hostname
            target = ip_fija if ip_fija else id_equipo
            
            # 💡 EL TRUCO PARA LAS IMPRESORAS USB 💡
            if target == 'USB':
                estado = 'verde'
            else:
                estado = realizar_ping(target)
            
            if tipo == 'PC':
                ip_detectada = obtener_ip(target) if estado == 'verde' else "Offline"
                usuario = obtener_usuario_linux(target) if estado == 'verde' else "DESCONECTADO"
                
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

        # Guardar el JSON directamente en la ruta pública de Apache
        try:
            with open(JSON_OUTPUT_PATH, 'w', encoding='utf-8') as f:
                json.dump(estado_general, f, indent=4)
        except Exception as e:
            print(f"❌ Error al guardar datos_red.json en Apache: {e}")
            
    print(f"✅ Ciclo terminado. Esperando 5 segundos...")
    time.sleep(5)