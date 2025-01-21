
from pygost.gost3410 import CURVES
from pygost.gost34112012 import GOST34112012
import os
import subprocess
import requests
import base64
from configparser import ConfigParser

# Используем 256-битную кривую из ГОСТ Р 34.10-2012
curve = CURVES["id-tc26-gost-3410-2012-256-paramSetB"]

def hash_text(text):
    data = text.encode('utf-8')
    hash_digest = GOST34112012(data=data, digest_size=32).digest()
    return hash_digest.hex()

def gen_private_key(private_key_path):
    subprocess.run([
        'openssl', 'genpkey',
        '-provider', 'gost',
        '-algorithm', 'gost2012_256',
        '-pkeyopt', 'paramset:A',
        '-out', private_key_path
    ], check=True)

def sign_certificate_on_server(csr_path, server_url, output_cert_path):
    # Чтение CSR из файла
    try:
        with open(csr_path, 'rb') as f:
            csr = f.read()
    except FileNotFoundError:
        print(f"Ошибка: Файл CSR по пути {csr_path} не найден.")
        return

    # Кодирование CSR в Base64
    csr_base64 = base64.b64encode(csr).decode('utf-8')

    # Отправка POST-запроса на сервер
    try:
        response = requests.post(f"{server_url}/sign_certificate", json={"csr": csr_base64})
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке запроса: {e}")
        return

    # Обработка ответа
    if response.status_code == 200:
        signed_cert_base64 = response.json().get("certificate")
        if signed_cert_base64:
            # Декодирование Base64 в байты
            signed_cert = base64.b64decode(signed_cert_base64)
            # Сохранение сертификата в файл
            try:
                with open(output_cert_path, "wb") as f:
                    f.write(signed_cert)
                print(f"Сертификат успешно подписан и сохранён по пути {output_cert_path}.")
            except IOError as e:
                print(f"Ошибка при сохранении сертификата: {e}")
        else:
            print("Ошибка: Сертификат не найден в ответе сервера.")
    else:
        # Вывод ошибки из ответа сервера
        error_message = response.json().get("error", "Неизвестная ошибка")
        details = response.json().get("details", "")
        print(f"Ошибка подписания сертификата: {error_message}")
        if details:
            print(f"Детали: {details}")

def gen_cert(priv_key_path,csr_path,cert_data,user_dir):
    config_parser = ConfigParser()
    config_file_path = './MailClient-master/settings.ini'
    config_parser.read(config_file_path)
    server_url = config_parser.get("MAILSERVER", "ca_server")

    csr_command = [
    'openssl', 'req', '-new',
    '-key', priv_key_path,
    '-out', csr_path,
    '-provider', 'gost',
    '-subj', f"/emailAddress={cert_data['emailAddress']}/CN={cert_data['CN']}/OU={cert_data['OU']}/O={cert_data['O']}/L={cert_data['L']}/ST={cert_data['ST']}/C={cert_data['C']}"
    ]
    subprocess.run(csr_command, check=True)


    cert_dir = os.path.join(user_dir, 'certificate.crt')
    signed_certificate = sign_certificate_on_server(csr_path, server_url, cert_dir)



def extract_private_key_openssl_text(private_key_path):

    cmd = [
        "openssl", "pkey",
        "-in", private_key_path,
        "-noout", "-text",
        "-provider", "gost"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = result.stdout

    private_key_hex = None
    for line in output.splitlines():
        line_stripped = line.strip()
        lower_line = line_stripped.lower()
        
        # Ищем "private key:" в нижнем регистре
        if lower_line.startswith("private key:"):
            # Теперь split тоже нужно делать по нижнему регистру:
            parts = lower_line.split("private key:")
            
            private_key_hex = parts[1].strip()
            d = int(private_key_hex, 16)
            return d

def parse_public_key_data(public_key_data: str) -> tuple[int, int]:

    cmd = [
        "openssl", "pkey",
        "-pubin",
        "-noout", "-text",
        "-provider", "gost"
    ]

    # Передаём содержимое ключа (public_key_data) в stdin openssl
    result = subprocess.run(
        cmd,
        input=public_key_data, # Ключ, подаваемый на стандартный ввод
        capture_output=True,
        text=True,
        check=True
    )
    output = result.stdout

    # Ищем строки X и Y
    x_hex = None
    y_hex = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("X:"):
            x_hex = line.split("X:", 1)[1].strip()
        elif line.startswith("Y:"):
            y_hex = line.split("Y:", 1)[1].strip()

    if not x_hex or not y_hex:
        raise ValueError("Не найдены строки 'X:' и 'Y:'")

    x = int(x_hex, 16)
    y = int(y_hex, 16)
    return x, y


def generate_key_pair(priv_key_path,csr_path,cert_data,user_dir):
    gen_private_key(priv_key_path)
    gen_cert(priv_key_path,csr_path,cert_data,user_dir)

def calculate_shared_secret(own_private_key, other_public_key_point):
    # Используем метод exp для скалярного умножения
    shared_point = curve.exp(own_private_key, other_public_key_point[0], other_public_key_point[1])
    shared_secret = shared_point[0].to_bytes(32, 'big')
  # Используем x-координату
    return shared_secret

def derive_symmetric_key(shared_secret):
    return GOST34112012(shared_secret, digest_size=32).digest()

def gen_sym(private_key, other_public_key):
    shared_secret = calculate_shared_secret(private_key, other_public_key)
    symmetric_key = derive_symmetric_key(shared_secret)
    return symmetric_key

if __name__ == "__main__":
    private_key_A, public_key_A_hex = generate_key_pair()
    private_key_B, public_key_B_hex = generate_key_pair()
    symmetric_key_A = gen_sym(private_key_A, public_key_B_hex)
    symmetric_key_B = gen_sym(private_key_B, public_key_A_hex)
    assert symmetric_key_A == symmetric_key_B
    print("Симметричный ключ успешно выработан и совпадает у обеих сторон.")
