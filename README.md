# Proyecto Segder

## Segunda Sesión: Cifrado y Comunicaciones

### Objetivos y Temario
1. Cifrado de contenido con **AES**.
2. Cifrado de ficheros con claves.
3. Cifrado de comunicaciones (sobre todo `app -> server` para licencias y contenidos usando **AES CTR** + **RSA [OAEP]**).

---

### Fórmulas: Cifrado Asimétrico (RSA)

Las operaciones criptográficas se basan en aritmética modular:

$$ y = x^e \pmod n $$
$$ x = y^d \pmod n $$

* **Clave pública ($K_{pub}$):** $(n, e)$
* **Clave privada ($K_{pr}$):** $d$

---

### Implementación en Python

* **Generación de claves:** Uso de la biblioteca `cryptography` para crear las claves RSA.
* **Operaciones matemáticas:** Cifrado y descifrado aprovechando la función nativa `pow(base, exponente, modulo)` para realizar la exponenciación modular rápida utilizando sus 3 parámetros.