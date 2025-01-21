from flask import Flask, request, jsonify
import sqlite3
import base64
import subprocess
import tempfile
import os
import logging
import time

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Подключение к основным базам данных
def connect_main_db():
    conn = sqlite3.connect('pubKey_storage.db')
    conn.row_factory = sqlite3.Row
    return conn

def connect_ca_db():
    conn = sqlite3.connect('ca_storage.db')
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация баз данных
def init_main_db():
    conn = connect_main_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            public_key_cert BLOB NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logging.info("Основная база данных инициализирована.")

def init_ca_db():
    conn = connect_ca_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ca_data (
            id INTEGER PRIMARY KEY,
            private_key BLOB NOT NULL,
            ca_cert BLOB NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logging.info("CA база данных инициализирована.")

# Эндпоинты для пользователей 
@app.route('/add_user_cert', methods=['POST'])
def add_user_cert():
    data = request.json
    email = data.get("email")
    public_key_cert_base64 = data.get("public_key_cert")

    if not email or not public_key_cert_base64:
        logging.error("Email и public_key_cert обязательны.")
        return jsonify({"error": "Email and public key certificate are required"}), 400

    try:
        public_key_cert = base64.b64decode(public_key_cert_base64)
    except Exception:
        logging.error("Неверный формат Base64 для public_key_cert.")
        return jsonify({"error": "Invalid Base64 format"}), 400

    conn = connect_main_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (email, public_key_cert) VALUES (?, ?)", (email, public_key_cert))
        logging.info(f"Добавлен новый пользователь: {email}")
    else:
        cursor.execute("UPDATE users SET public_key_cert = ? WHERE email = ?", (public_key_cert, email))
        logging.info(f"Обновлён сертификат пользователя: {email}")

    conn.commit()
    conn.close()

    return jsonify({"status": "success"}), 200

@app.route('/get_user_cert', methods=['GET'])
def get_user_cert():
    email = request.args.get("email")

    if not email:
        logging.error("Email обязателен для получения сертификата.")
        return jsonify({"error": "Email is required"}), 400

    conn = connect_main_db()
    cursor = conn.cursor()
    cursor.execute("SELECT public_key_cert FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        public_key_cert_base64 = base64.b64encode(row["public_key_cert"]).decode('utf-8')
        logging.info(f"Сертификат пользователя {email} успешно получен.")
        return jsonify({
            "email": email,
            "public_key_cert": public_key_cert_base64
        }), 200
    else:
        logging.error(f"Пользователь {email} не найден.")
        return jsonify({"error": "User not found"}), 404

# Эндпоинты для CA 
@app.route('/add_ca_data', methods=['POST'])
def add_ca_data():
    data = request.json
    private_key_base64 = data.get("private_key")
    ca_cert_base64 = data.get("ca_cert")

    if not private_key_base64 or not ca_cert_base64:
        logging.error("Private key и CA certificate обязательны.")
        return jsonify({"error": "Private key and CA certificate are required"}), 400

    try:
        private_key = base64.b64decode(private_key_base64)
        ca_cert = base64.b64decode(ca_cert_base64)
    except Exception:
        logging.error("Неверный формат Base64 для private_key или ca_cert.")
        return jsonify({"error": "Invalid Base64 format"}), 400

    conn = connect_ca_db()
    cursor = conn.cursor()

    # Проверяем, есть ли данные CA в таблице
    cursor.execute("SELECT id FROM ca_data WHERE id = 1")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO ca_data (id, private_key, ca_cert) VALUES (1, ?, ?)", (private_key, ca_cert))
        logging.info("Добавлены новые CA данные.")
    else:
        cursor.execute("UPDATE ca_data SET private_key = ?, ca_cert = ? WHERE id = 1", (private_key, ca_cert))
        logging.info("Обновлены CA данные.")

    conn.commit()
    conn.close()

    return jsonify({"status": "success"}), 200

@app.route('/get_ca_data', methods=['GET'])
def get_ca_data():
    conn = connect_ca_db()
    cursor = conn.cursor()
    cursor.execute("SELECT private_key, ca_cert FROM ca_data WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        private_key_base64 = base64.b64encode(row["private_key"]).decode('utf-8')
        ca_cert_base64 = base64.b64encode(row["ca_cert"]).decode('utf-8')
        logging.info("CA данные успешно получены.")
        return jsonify({
            "private_key": private_key_base64,
            "ca_cert": ca_cert_base64
        }), 200
    else:
        logging.error("CA данные не найдены.")
        return jsonify({"error": "CA data not found"}), 404



@app.route('/check_user', methods=['GET'])
def check_user():
    email = request.args.get("email")

    if not email:
        logging.error("Email обязателен для проверки.")
        return jsonify({"error": "Email is required"}), 400

    conn = connect_main_db()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        logging.info(f"Пользователь {email} найден.")
        return jsonify({"exists": True}), 200
    else:
        logging.info(f"Пользователь {email} не найден.")
        return jsonify({"exists": False}), 200


# Эндпоинт для подписания сертификатов
@app.route('/sign_certificate', methods=['POST'])
def sign_certificate():
    data = request.json
    csr_base64 = data.get("csr")

    if not csr_base64:
        logging.error("CSR не предоставлен.")
        return jsonify({"error": "CSR is required"}), 400

    try:
        csr = base64.b64decode(csr_base64)
    except Exception as e:
        logging.error(f"Ошибка декодирования CSR: {e}")
        return jsonify({"error": "Invalid Base64 format for CSR"}), 400

    # Получаем приватный ключ и CA сертификат из базы данных
    conn = connect_ca_db()
    cursor = conn.cursor()
    cursor.execute("SELECT private_key, ca_cert FROM ca_data WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        logging.error("CA данные не найдены.")
        return jsonify({"error": "CA data not found"}), 404

    private_key = row["private_key"]
    ca_cert = row["ca_cert"]

    # Сохраняем временные файлы
    with tempfile.NamedTemporaryFile(delete=False) as csr_file, \
         tempfile.NamedTemporaryFile(delete=False) as ca_cert_file, \
         tempfile.NamedTemporaryFile(delete=False) as ca_key_file, \
         tempfile.NamedTemporaryFile(delete=False) as cert_file:

        try:
            csr_file.write(csr)
            csr_file.flush()
            csr_file.close()  

            ca_cert_file.write(ca_cert)
            ca_cert_file.flush()
            ca_cert_file.close()  

            ca_key_file.write(private_key)
            ca_key_file.flush()
            ca_key_file.close() 

            cert_path = cert_file.name
            cert_file.close() 

            cert_command = [
                'openssl', 'x509', '-req', '-days', '365',
                '-in', csr_file.name,
                '-CA', ca_cert_file.name,
                '-CAkey', ca_key_file.name,
                '-out', cert_path,
                '-provider', 'gost',
            ]

            logging.info(f"Выполнение команды: {' '.join(cert_command)}")
            result = subprocess.run(cert_command, capture_output=True, text=True)

            logging.info(f"OpenSSL return code: {result.returncode}")
            logging.info(f"OpenSSL stdout: {result.stdout}")
            logging.info(f"OpenSSL stderr: {result.stderr}")

            if result.returncode != 0:
                # Проверяем, содержит ли stderr сообщение о самоподписи
                if "self-signature ok" in result.stderr:
                    logging.warning("OpenSSL вернул предупреждение о самоподписи, продолжаем обработку.")
                else:
                    logging.error(f"OpenSSL ошибка: {result.stderr}")
                    return jsonify({"error": "OpenSSL error", "details": result.stderr}), 500

            # Проверяем, создан ли сертификат
            if not os.path.exists(cert_path):
                logging.error("Сертификат не был создан OpenSSL.")
                return jsonify({"error": "Certificate not created"}), 500

            # Читаем подписанный сертификат
            with open(cert_path, 'rb') as f:
                signed_cert = f.read()

            signed_cert_base64 = base64.b64encode(signed_cert).decode('utf-8')

            logging.info("Сертификат успешно подписан.")
            return jsonify({"certificate": signed_cert_base64}), 200

        except Exception as e:
            logging.error(f"Ошибка при подписании сертификата: {e}")
            return jsonify({"error": "Internal server error"}), 500

        finally:
            for file_path in [csr_file.name, ca_cert_file.name, ca_key_file.name, cert_path]:
                try:
                    time.sleep(0.1)  
                    os.unlink(file_path)
                    logging.info(f"Временный файл {file_path} удалён.")
                except PermissionError as pe:
                    logging.warning(f"Не удалось удалить временный файл {file_path}: {pe}")
                except FileNotFoundError:
                    logging.warning(f"Временный файл {file_path} уже удалён.")
                except Exception as e:
                    logging.error(f"Ошибка при удалении временного файла {file_path}: {e}")

def add_files_to_ca_db(private_key_file, ca_cert_file):
    try:
        with open(private_key_file, 'rb') as pk_file:
            private_key = pk_file.read()
        with open(ca_cert_file, 'rb') as cert_file:
            ca_cert = cert_file.read()
    except FileNotFoundError:
        logging.error("Ошибка: Один или оба файла не найдены.")
        return

    conn = connect_ca_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM ca_data WHERE id = 1")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO ca_data (id, private_key, ca_cert) VALUES (1, ?, ?)", (private_key, ca_cert))
        logging.info("CA данные добавлены в базу данных.")
    else:
        cursor.execute("UPDATE ca_data SET private_key = ?, ca_cert = ? WHERE id = 1", (private_key, ca_cert))
        logging.info("CA данные обновлены в базе данных.")

    conn.commit()
    conn.close()
    logging.info("Файлы успешно добавлены в CA базу данных.")

# Инициализация баз данных перед запуском приложения
init_main_db()
init_ca_db()

if __name__ == '__main__':
    # path_to_private_key = './MailClient-master/CA/ca_private.key'
    # path_to_ca_cert = './MailClient-master/CA/ca_certificate.crt'
    # add_files_to_ca_db(path_to_private_key, path_to_ca_cert)
    app.run(host='0.0.0.0', port=5000)
