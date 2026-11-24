# SERVIDOR DE LICENCIAS - Proyecto SEGDER, Partes I y II (puerto 6768)
# Canal seguro: RSA (pow) para acordar clave de sesion AES, y AES-CTR para la peticion/respuesta
# Parte II: se verifica la firma digital (RSA con pow) de la peticion de clave

import socket as s
import os
import json
import hashlib
import time
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IP = '127.0.0.1'
PUERTO = 6768
FICHERO_CLAVES = "claves.enc"
CLAVE_MAESTRA = b'MaestraSGDD2627!'  # 16 bytes = AES-128, protege el fichero de claves
DEBUG = True  # False para quitar los mensajes de depuracion

def debug(mensaje):
    if DEBUG:
        print(f"[DEBUG] {mensaje}")

# Funciones AES-CTR (el IV de 16 bytes va delante de los datos cifrados)
def cifrar(clave, datos):
    iv = os.urandom(16)
    cifrador = Cipher(algorithms.AES(clave), modes.CTR(iv)).encryptor()
    return iv + cifrador.update(datos) + cifrador.finalize()

def descifrar(clave, datos):
    iv, cifrado = datos[:16], datos[16:]
    descifrador = Cipher(algorithms.AES(clave), modes.CTR(iv)).decryptor()
    return descifrador.update(cifrado) + descifrador.finalize()

# Fichero de claves cifrado: si no existe, lo creamos con las claves de los contenidos
if not os.path.exists(FICHERO_CLAVES):
    debug(f"{FICHERO_CLAVES} no existe: se crea con las claves iniciales")
    claves_iniciales = {
        "KID_video_promo.mp4": b'1234567890123456'.hex(),
        "KID_imagen_miniatura.jpg": b'abcdefghijklmnop'.hex()
    }
    with open(FICHERO_CLAVES, 'wb') as f:
        f.write(cifrar(CLAVE_MAESTRA, json.dumps(claves_iniciales).encode('utf-8')))
else:
    debug(f"{FICHERO_CLAVES} ya existe: se carga")

with open(FICHERO_CLAVES, 'rb') as f:
    CLAVES = json.loads(descifrar(CLAVE_MAESTRA, f.read()))  # {key_id: clave en hex}
debug(f"Claves cargadas: {len(CLAVES)} -> {list(CLAVES.keys())}")

# Par de claves RSA (generacion con cryptography, cifrado/descifrado con pow)
clave_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
numeros = clave_privada.private_numbers()
n = numeros.public_numbers.n
e = numeros.public_numbers.e
d = numeros.d
debug(f"Par RSA generado: n de {n.bit_length()} bits, e = {e}")

s_servidor = s.socket(s.AF_INET, s.SOCK_STREAM)
s_servidor.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
s_servidor.bind((IP, PUERTO))
s_servidor.listen()

print(f"Servidor de licencias iniciado en {IP}:{PUERTO}...")

while True:
    cliente, direccion = s_servidor.accept()
    debug(f"Conexion aceptada de {direccion}")
    try:
        # 1. La app saluda y le enviamos la clave publica (n, e)
        saludo = cliente.recv(1024)
        debug(f"Paso 1: saludo recibido {saludo!r}")
        cliente.send(json.dumps({"n": n, "e": e}).encode('utf-8'))
        debug("Paso 1: clave publica (n, e) enviada")

        # 2. Recibimos la clave de sesion cifrada con RSA y la peticion cifrada con AES
        datos = cliente.recv(8192)
        debug(f"Paso 2: recibidos {len(datos)} bytes de la app")
        mensaje = json.loads(datos.decode('utf-8'))
        c = int(mensaje["clave_sesion"], 16)
        k_sesion = pow(c, d, n).to_bytes(16, 'big')   # x = y^d mod n
        debug("Paso 2: clave de sesion recuperada con RSA")

        peticion = json.loads(descifrar(k_sesion, bytes.fromhex(mensaje["peticion"])))
        debug(f"Paso 2: peticion descifrada con AES-CTR (key_id={peticion['key_id']})")
        key_id = peticion["key_id"]
        print(f"Solicitud de licencia para {key_id}")

        # Verificacion de la firma de la app (Parte II)
        n_app = int(peticion["n_app"], 16)
        e_app = peticion["e_app"]
        firma = int(peticion["firma"], 16)
        h = int.from_bytes(hashlib.sha256(f'{key_id}|{peticion["ts"]}'.encode('utf-8')).digest(), 'big')
        firma_valida = (pow(firma, e_app, n_app) == h)  # h = firma^e mod n
        peticion_reciente = abs(time.time() - peticion["ts"]) < 60
        print(f"Firma valida: {firma_valida} | peticion reciente: {peticion_reciente}")

        # 3. Respondemos con la clave del contenido, cifrada con la clave de sesion
        if not firma_valida or not peticion_reciente:
            debug("Paso 3: firma no valida o peticion caducada, se envia error")
            respuesta = {"ok": False, "error": "firma no valida o peticion caducada"}
        elif key_id in CLAVES:
            debug("Paso 3: key_id encontrado, se envia la clave del contenido")
            respuesta = {"ok": True, "clave": CLAVES[key_id]}
        else:
            debug("Paso 3: key_id NO encontrado, se envia error")
            respuesta = {"ok": False, "error": "key_id desconocido"}
        respuesta_cifrada = cifrar(k_sesion, json.dumps(respuesta).encode('utf-8')).hex().encode('utf-8')
        cliente.send(respuesta_cifrada)
        debug(f"Paso 3: respuesta cifrada enviada ({len(respuesta_cifrada)} bytes en hex)")

    except Exception as error:
        print(f"Error con un cliente: {error}")
        debug(f"Tipo de error: {type(error).__name__}")
    finally:
        cliente.close()
        debug("Conexion cerrada\n")