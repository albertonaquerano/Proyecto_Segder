# APLICACION - Proyecto SEGDER, Partes I y II (cliente de contenidos y de licencias)
# Parte II: la app manda su nombre de usuario (marca de agua) y firma la peticion de clave

import socket as s
import os
import json
import hashlib
import time
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IP_SERVIDOR = '127.0.0.1' # IP servidor
PUERTO_SERVIDOR = 6767 # Puerto Servidor Contenidos

# Par de claves RSA de la aplicacion (para firmar). Se generan con cryptography, se firma con pow
clave_privada_app = rsa.generate_private_key(public_exponent=65537, key_size=2048)
numeros_app = clave_privada_app.private_numbers()
n_app = numeros_app.public_numbers.n
e_app = numeros_app.public_numbers.e
d_app = numeros_app.d

def firmar(mensaje):
    h = int.from_bytes(hashlib.sha256(mensaje.encode('utf-8')).digest(), 'big')
    return pow(h, d_app, n_app)  # firma = h^d mod n

def cifrar(clave, datos): # Funcion de cifrado CTR
    iv = os.urandom(16) # IV de 16 bytes
    aesCipher = Cipher(algorithms.AES(clave), modes.CTR(iv))  # se selecciona el cifrado AES modo CTR
    aesEncryptor = aesCipher.encryptor()  # se crea el objeto que cifra
    msg_cifrado = aesEncryptor.update(datos) + aesEncryptor.finalize()  # se cifran los datos
    return iv + msg_cifrado  # el IV va delante para poder descifrar después

def descifrar(clave, datos):
    iv = datos[:16]  # los 16 primeros bytes son el IV
    msg_cifrado = datos[16:]  # el resto es el mensaje cifrado
    aesCipher = Cipher(algorithms.AES(clave), modes.CTR(iv))  # mismo AES, modo e IV que al cifrar
    aesDecryptor = aesCipher.decryptor()  # se crea el objeto que descifra
    return aesDecryptor.update(msg_cifrado) + aesDecryptor.finalize()  # se descifra y se devuelve el original

def pedir_clave(url_licencias, key_id):
    # Fase 2: canal seguro con el servidor de licencias
    ip, puerto = url_licencias.split(":")
    socket_licencias = s.socket(s.AF_INET, s.SOCK_STREAM)
    socket_licencias.connect((ip, int(puerto)))

    # 1. Pedimos la clave publica RSA (n, e)
    socket_licencias.send("HELLO".encode('utf-8'))
    publica = json.loads(socket_licencias.recv(4096).decode('utf-8'))
    n, e = publica["n"], publica["e"]

    # 2. Clave de sesion AES-128 aleatoria, cifrada con RSA usando pow: y = x^e mod n
    k_sesion = os.urandom(16)
    clave_sesion_rsa = pow(int.from_bytes(k_sesion, 'big'), e, n)

    # 3. Peticion FIRMADA y cifrada con la clave de sesion
    ts = int(time.time())
    firma = firmar(f"{key_id}|{ts}")  # se firma lo que se pide + la hora
    peticion = cifrar(k_sesion, json.dumps({
        "key_id": key_id,
        "ts": ts,
        "firma": hex(firma)[2:],
        "n_app": hex(n_app)[2:],
        "e_app": e_app
    }).encode('utf-8'))
    mensaje = {"clave_sesion": hex(clave_sesion_rsa)[2:], "peticion": peticion.hex()}
    socket_licencias.send(json.dumps(mensaje).encode('utf-8'))

    # 4. Respuesta cifrada con la clave de sesion
    respuesta = json.loads(descifrar(k_sesion, bytes.fromhex(socket_licencias.recv(4096).decode('utf-8'))))
    socket_licencias.close()

    if not respuesta["ok"]:
        raise Exception(respuesta["error"])
    return bytes.fromhex(respuesta["clave"])

def ejecutar_comando(comando):
    # Cada comando abre su propia conexion, porque el servidor la cierra al responder
    cliente = s.socket(s.AF_INET, s.SOCK_STREAM)
    try:
        cliente.connect((IP_SERVIDOR, PUERTO_SERVIDOR))

        if comando.upper().startswith("GET"):
            cliente.send(f"{comando} {usuario}".encode('utf-8'))  # se añade el usuario para la marca de agua
        else:
            cliente.send(comando.encode('utf-8'))

        if comando.upper().startswith("GET"):
            # Recibimos todos los datos hasta que el servidor cierre la conexión
            trozos = []
            while True:
                chunk = cliente.recv(65536)
                if not chunk:
                    break
                trozos.append(chunk)
            datos_recibidos = b"".join(trozos)

            # Separamos el manifiesto del contenido binario del fichero
            separador = b"\n---FIN_MANIFIESTO---\n"
            if separador in datos_recibidos:
                manifiesto_bytes, contenido_fichero = datos_recibidos.split(separador, 1)
                manifiesto = json.loads(manifiesto_bytes.decode('utf-8'))
                nombre = os.path.basename(comando.split()[1])

                print("\n--- Manifiesto Recibido ---")
                for clave, valor in manifiesto.items():
                    print(f"{clave}: {valor}")

                # el manifiesto se guarda una sola vez
                with open("manifiesto_" + nombre + ".json", 'w') as f:
                    json.dump(manifiesto, f, indent=2)

                if manifiesto["cifrado"]:
                    if manifiesto["modo_cifrado"] != "CTR-cenc":  # la app solo implementa CTR
                        raise Exception(f"Modo de cifrado no soportado: {manifiesto['modo_cifrado']}")

                    print("\nContenido cifrado: solicitando licencia...")
                    clave_contenido = pedir_clave(manifiesto["url_licencias"], manifiesto["key_id"])
                    descifrador = Cipher(algorithms.AES(clave_contenido), modes.CTR(bytes.fromhex(manifiesto["iv"]))).decryptor()
                    contenido_fichero = descifrador.update(contenido_fichero) + descifrador.finalize()
                    print("Contenido descifrado correctamente.")
                else:
                    print("\nEl contenido NO está cifrado.")

                nombre_archivo = "descargado_" + nombre
                with open(nombre_archivo, 'wb') as f:
                    f.write(contenido_fichero)
                print(f"Archivo guardado en el disco como: {nombre_archivo}")
            else:
                print(datos_recibidos.decode('utf-8', errors='ignore'))

        else:
            # Comportamiento normal para LIST
            respuesta = cliente.recv(4096).decode('utf-8')
            print("\n--- Respuesta del Servidor ---")
            print(respuesta)

    except ConnectionRefusedError:
        print("Error: no se pudo conectar con el servidor (¿está arrancado?)")
    except Exception as error:
        print(f"Error: {error}")  # el programa NO se cierra, vuelve a pedir otro comando
    finally:
        cliente.close()

# Usuario que saldra en la marca de agua de las imagenes
usuario = input("Nombre de usuario (saldrá en la marca de agua de las imágenes): ").strip() or "anonimo"

# Bucle principal: se piden comandos hasta que el usuario escriba 'salir'
while True:
    comando = input("\nIntroduce un comando (LIST, LIST mp4, GET video_promo.mp4, o 'salir'): ").strip()

    if comando.lower() == 'salir':
        print("Cerrando la aplicación...")
        break
    if not comando:
        continue  # si se pulsa Enter sin escribir nada, se vuelve a preguntar
    if comando.upper().startswith("GET") and len(comando.split()) < 2:
        print("Uso: GET nombre_fichero")  # evita el error por falta de nombre
        continue

    ejecutar_comando(comando)