# APLICACION, cliente del servidor de contenidos

import socket as s
import json

IP_SERVIDOR = '127.0.0.1'
PUERTO_SERVIDOR = 6767

comando = input("Introduce un comando (ej. LIST, o GET video_promo.mp4): ")

cliente = s.socket(s.AF_INET, s.SOCK_STREAM)
cliente.connect((IP_SERVIDOR, PUERTO_SERVIDOR))
cliente.send(comando.encode('utf-8'))

if comando.upper().startswith("GET"):
    # Recibimos todos los datos hasta que el servidor cierre la conexión
    datos_recibidos = b""
    while True:
        chunk = cliente.recv(4096)
        if not chunk:
            break
        datos_recibidos += chunk
    
    # Separamos el manifiesto del contenido binario del fichero
    separador = b"\n---FIN_MANIFIESTO---\n"
    if separador in datos_recibidos:
        manifiesto_bytes, contenido_fichero = datos_recibidos.split(separador, 1)
        manifiesto = json.loads(manifiesto_bytes.decode('utf-8'))
        
        print("\n--- Manifiesto Recibido ---")
        for clave, valor in manifiesto.items():
            print(f"{clave}: {valor}")
            
        # Guardamos el archivo
        nombre_archivo = "descargado_" + comando.split()[1]
        with open(nombre_archivo, 'wb') as f:
            f.write(contenido_fichero)
        print(f"\nArchivo guardado en el disco como: {nombre_archivo}")
    else:
        print(datos_recibidos.decode('utf-8', errors='ignore'))

else:
    # Comportamiento normal para LIST
    respuesta = cliente.recv(4096).decode('utf-8')
    print("\n--- Respuesta del Servidor ---")
    print(respuesta)

cliente.close()
s.close()