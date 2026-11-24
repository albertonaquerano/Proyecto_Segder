# SERVIDOR DE CONTENIDOS - Proyecto SEGDER, Partes I y II (puerto 6767)
# Parte II: las imagenes llevan una marca de agua visible con el nombre del usuario

import socket as s
import os
import sys
import io
import json
from PIL import Image, ImageDraw, ImageFont
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IP = '127.0.0.1'
PUERTO = 6767
DIRECTORIO_CONTENIDOS = "contenidos"
FICHERO_CLAVES = "claves.enc"             # lo crea el servidor de licencias
CLAVE_MAESTRA = b'MaestraSGDD2627!'
FUENTE_PATH = "dtmf_fuente.ttf"           # si no esta, se usa la fuente por defecto
FORMATOS_IMAGEN = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".bmp": "BMP"}
COLOR_MARCA = (255, 255, 255, 128)        # blanco semitransparente (cambiar si el fondo es claro)
DEBUG = True  # False para quitar los mensajes de depuracion

def debug(mensaje):
    if DEBUG:
        print(f"[DEBUG] {mensaje}")

def cargar_claves():
    # Lee el fichero de claves cifrado (AES-CTR, IV en los 16 primeros bytes)
    with open(FICHERO_CLAVES, 'rb') as f:
        datos = f.read()
    descifrador = Cipher(algorithms.AES(CLAVE_MAESTRA), modes.CTR(datos[:16])).decryptor()
    claves = json.loads(descifrador.update(datos[16:]) + descifrador.finalize())
    debug(f"Fichero de claves leido: {len(claves)} claves -> {list(claves.keys())}")
    return claves

def cargar_fuente(tamano):
    try:
        return ImageFont.truetype(FUENTE_PATH, tamano)
    except OSError:  # si da error, la de por defecto
        return ImageFont.load_default(size=tamano)

def aplicar_marca_agua(contenido, texto, formato):
    # Trabaja con bytes en memoria, sin guardar ficheros intermedios
    img = Image.open(io.BytesIO(contenido)).convert("RGBA")
    capa = Image.new("RGBA", img.size, (255, 255, 255, 0))  # capa invisible para el texto
    dibujo = ImageDraw.Draw(capa)

    tamano = max(15, img.width // 19)
    fuente = cargar_fuente(tamano)
    while tamano > 15 and dibujo.textlength(texto, font=fuente) > img.width - 40:
        tamano -= 2  # si el nombre es largo y no cabe, se reduce el tamaño
        fuente = cargar_fuente(tamano)

    dibujo.text((20, 20), texto, fill=COLOR_MARCA, font=fuente)
    resultado = Image.alpha_composite(img, capa).convert("RGB")

    salida = io.BytesIO()
    if formato == "JPEG":
        resultado.save(salida, format=formato, quality=95)
    else:
        resultado.save(salida, format=formato)
    return salida.getvalue()

if not os.path.exists(FICHERO_CLAVES):
    print(f"Error: no existe {FICHERO_CLAVES}. Arranca primero el servidor de licencias.")
    sys.exit()

if not os.path.exists(DIRECTORIO_CONTENIDOS):
    debug(f"El directorio '{DIRECTORIO_CONTENIDOS}' no existe: se crea")
    os.makedirs(DIRECTORIO_CONTENIDOS)

s_servidor = s.socket(s.AF_INET, s.SOCK_STREAM)
s_servidor.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
s_servidor.bind((IP, PUERTO))
s_servidor.listen()

print(f"Servidor de contenidos iniciado en {IP}:{PUERTO}...")

while True:
    cliente, direccion = s_servidor.accept()
    debug(f"Conexion aceptada de {direccion}")
    try:
        peticion = cliente.recv(1024).decode('utf-8').strip()
        debug(f"Peticion recibida: {peticion!r}")
        partes = peticion.split()
        if not partes:
            debug("Peticion vacia: se ignora")
            continue
        comando_base = partes[0].upper()

        if comando_base == "LIST":
            archivos = os.listdir(DIRECTORIO_CONTENIDOS)
            debug(f"LIST: {len(archivos)} ficheros en '{DIRECTORIO_CONTENIDOS}'")
            if len(partes) > 1:
                extension = partes[1].lower()
                archivos = [f for f in archivos if f.lower().endswith(f".{extension}")]
                debug(f"LIST: filtro '.{extension}' -> {len(archivos)} ficheros")
            respuesta = "\n".join(archivos) if archivos else "No hay ficheros."
            cliente.send(respuesta.encode('utf-8'))
            debug(f"LIST: respuesta enviada ({len(respuesta)} bytes)")

        elif comando_base == "GET" and len(partes) > 1:
            nombre_archivo = os.path.basename(partes[1])   # evita rutas tipo ../
            usuario = " ".join(partes[2:]) if len(partes) > 2 else "anonimo"  # lo manda la app
            ruta_archivo = os.path.join(DIRECTORIO_CONTENIDOS, nombre_archivo)
            debug(f"GET: fichero pedido '{partes[1]}' por el usuario '{usuario}' -> ruta '{ruta_archivo}'")

            if os.path.isfile(ruta_archivo):
                with open(ruta_archivo, 'rb') as f:
                    contenido = f.read()
                debug(f"GET: fichero leido ({len(contenido)} bytes)")

                # Parte II: marca de agua visible solo en imagenes (antes de cifrar)
                extension = os.path.splitext(nombre_archivo)[1].lower()
                if extension in FORMATOS_IMAGEN:
                    contenido = aplicar_marca_agua(contenido, usuario, FORMATOS_IMAGEN[extension])
                    print(f"Marca de agua '{usuario}' aplicada a {nombre_archivo}")

                key_id = f"KID_{nombre_archivo}"
                claves = cargar_claves()

                if key_id in claves:
                    # Contenido protegido: AES-128 en modo CTR
                    iv = os.urandom(16)
                    debug(f"GET: contenido protegido, key_id={key_id}, IV={iv.hex()}")
                    cifrador = Cipher(algorithms.AES(bytes.fromhex(claves[key_id])), modes.CTR(iv)).encryptor()
                    contenido = cifrador.update(contenido) + cifrador.finalize()
                    debug(f"GET: contenido cifrado con AES-CTR ({len(contenido)} bytes)")
                    manifiesto = {
                        "cifrado": True,
                        "modo_cifrado": "CTR-cenc",
                        "url_licencias": "127.0.0.1:6768",
                        "key_id": key_id,
                        "iv": iv.hex()
                    }
                else:
                    # Sin clave registrada: se envia en claro
                    debug(f"GET: {key_id} sin clave registrada, se envia EN CLARO")
                    manifiesto = {
                        "cifrado": False,
                        "modo_cifrado": "NONE",
                        "url_licencias": "127.0.0.1:6768",
                        "key_id": "NONE",
                        "iv": "NONE"
                    }
                debug(f"GET: manifiesto -> {manifiesto}")

                # Manifiesto + separador + fichero (cifrado o no)
                separador = b"\n---FIN_MANIFIESTO---\n"
                cliente.send(json.dumps(manifiesto).encode('utf-8') + separador)
                cliente.sendall(contenido)
                debug(f"GET: enviados manifiesto + {len(contenido)} bytes de contenido")
            else:
                debug(f"GET: '{ruta_archivo}' no existe")
                cliente.send("Error: Archivo no encontrado".encode('utf-8'))
        else:
            debug(f"Comando no reconocido o incompleto: {peticion!r}")
    except Exception as error:
        print(f"Error con un cliente: {error}")
        debug(f"Tipo de error: {type(error).__name__}")
    finally:
        cliente.close()
        debug("Conexion cerrada\n")