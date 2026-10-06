import socket as s
import os
import json

IP = '127.0.0.1'
PUERTO = 6767
DIRECTORIO_CONTENIDOS = "contenidos"

# Bloque de preparación (se mantiene igual)
if not os.path.exists(DIRECTORIO_CONTENIDOS):
    os.makedirs(DIRECTORIO_CONTENIDOS)
    open(os.path.join(DIRECTORIO_CONTENIDOS, "video_promo.mp4"), 'w').close()
    open(os.path.join(DIRECTORIO_CONTENIDOS, "imagen_miniatura.jpg"), 'w').close()

s_servidor = s.socket(s.AF_INET, s.SOCK_STREAM)
s_servidor.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
s_servidor.bind((IP, PUERTO))
s_servidor.listen()

print(f"Servidor de contenidos iniciado en {IP}:{PUERTO}...")

while True:
    cliente, direccion = s_servidor.accept()
    peticion = cliente.recv(1024).decode('utf-8').strip()
    partes = peticion.split()
    comando_base = partes[0].upper()
    
    if comando_base == "LIST":
        archivos = os.listdir(DIRECTORIO_CONTENIDOS)
        if len(partes) > 1:
            extension = partes[1].lower()
            archivos = [f for f in archivos if f.lower().endswith(f".{extension}")]
            
        respuesta = "\n".join(archivos) if archivos else "No hay ficheros."
        cliente.send(respuesta.encode('utf-8'))
        
    elif comando_base == "GET" and len(partes) > 1:
        nombre_archivo = partes[1]
        ruta_archivo = os.path.join(DIRECTORIO_CONTENIDOS, nombre_archivo)
        
        if os.path.exists(ruta_archivo):
            # 1. Generamos el manifiesto con los 5 requisitos del proyecto
            manifiesto = {
                "cifrado": False,               # Cambiará a True en la siguiente fase
                "modo_cifrado": "NONE",         # Será CTR-cenc o CBC-cbcs
                "url_licencias": "127.0.0.1:6768", # Puerto reservado para el servidor de licencias
                "key_id": "NONE",
                "iv": "NONE"
            }
            manifiesto_json = json.dumps(manifiesto)
            
            # 2. Enviamos el manifiesto y un separador claro
            separador = b"\n---FIN_MANIFIESTO---\n"
            cliente.send(manifiesto_json.encode('utf-8') + separador)
            
            # 3. Leemos y enviamos los bytes en crudo del archivo
            with open(ruta_archivo, 'rb') as f:
                cliente.sendall(f.read())
        else:
            cliente.send("Error: Archivo no encontrado".encode('utf-8'))
            
    cliente.close()