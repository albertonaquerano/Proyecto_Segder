import socket as s
import os
import json
import binascii
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IP = '127.0.0.1'
PUERTO = 6767
DIRECTORIO_CONTENIDOS = "contenidos"

# Base de datos simulada de claves AES (128 bits = 16 caracteres/bytes)
CLAVES_CONTENIDOS = {
    "video_promo.mp4": b'1234567890123456', 
    "imagen_miniatura.jpg": b'abcdefghijklmnop'
}

if not os.path.exists(DIRECTORIO_CONTENIDOS):
    os.makedirs(DIRECTORIO_CONTENIDOS)
    # Creamos un archivo de prueba con texto para verificar fácilmente el cifrado
    with open(os.path.join(DIRECTORIO_CONTENIDOS, "video_promo.mp4"), 'w') as f:
        f.write("Este es el contenido secreto del video promocional.")

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
            # 1. Recuperamos la clave AES de 128 bits y generamos el IV de 16 bytes
            clave = CLAVES_CONTENIDOS.get(nombre_archivo, b'0000000000000000')
            key_id = f"KID_{nombre_archivo}"
            iv = os.urandom(16)
            
            # 2. Ciframos el archivo usando AES en modo CTR
            cipher = Cipher(algorithms.AES(clave), modes.CTR(iv))
            encryptor = cipher.encryptor()
            
            with open(ruta_archivo, 'rb') as f:
                contenido_original = f.read()
                
            contenido_cifrado = encryptor.update(contenido_original) + encryptor.finalize()
            
            # 3. Actualizamos el manifiesto con los requisitos del proyecto
            manifiesto = {
                "cifrado": True,
                "modo_cifrado": "CTR-cenc",
                "url_licencias": "127.0.0.1:6768",
                "key_id": key_id,
                "iv": binascii.hexlify(iv).decode('utf-8') # Convertimos bytes a texto para enviarlo en JSON
            }
            manifiesto_json = json.dumps(manifiesto)
            
            # 4. Enviamos manifiesto y fichero cifrado
            separador = b"\n---FIN_MANIFIESTO---\n"
            cliente.send(manifiesto_json.encode('utf-8') + separador)
            cliente.sendall(contenido_cifrado)
        else:
            cliente.send("Error: Archivo no encontrado".encode('utf-8'))
            
    cliente.close()