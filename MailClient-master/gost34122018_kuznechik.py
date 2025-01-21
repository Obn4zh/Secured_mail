
from pygost.gost3412 import GOST3412Kuznechik
from pygost.gost3413 import ctr
import os
import asimm_crypto

def encrypt_message(plaintext, key):
    cipher = GOST3412Kuznechik(key)
    bs = cipher.blocksize  # Размер блока (16 байт для "Кузнечика")
    iv = os.urandom(bs // 2)  # IV размером половина блока (8 байт)
    ciphertext = ctr(cipher.encrypt, bs, plaintext.encode('utf-8'), iv)
    return iv + ciphertext

def decrypt_message(encrypted_message, key):
    cipher = GOST3412Kuznechik(key)
    bs = cipher.blocksize
    iv_length = bs // 2  # 8 байт для "Кузнечика"
    iv = encrypted_message[:iv_length]
    ciphertext = encrypted_message[iv_length:]
    plaintext = ctr(cipher.encrypt, bs, ciphertext, iv)
    return plaintext.decode('utf-8')  # Декодируем здесь

def encrypt_file(input_file_path, output_file_path, key):
    cipher = GOST3412Kuznechik(key)
    bs = cipher.blocksize
    iv = os.urandom(bs // 2)

    with open(input_file_path, 'rb') as f_in:
        plaintext = f_in.read()

    ciphertext = ctr(cipher.encrypt, bs, plaintext, iv)

    with open(output_file_path, 'wb') as f_out:
        f_out.write(iv + ciphertext)

def decrypt_file(input_file_path, output_file_path, key):
    cipher = GOST3412Kuznechik(key)
    bs = cipher.blocksize
    iv_length = bs // 2

    with open(input_file_path, 'rb') as f_in:
        encrypted_data = f_in.read()

    iv = encrypted_data[:iv_length]
    ciphertext = encrypted_data[iv_length:]

    plaintext = ctr(cipher.encrypt, bs, ciphertext, iv)

    with open(output_file_path, 'wb') as f_out:
        f_out.write(plaintext)


if __name__ == "__main__":
    # Генерация ключевых пар
    private_key_A, public_key_A_hex = asimm_crypto.generate_key_pair()
    private_key_B, public_key_B_hex = asimm_crypto.generate_key_pair()

    # Выработка симметричного ключа
    symmetric_key = asimm_crypto.gen_sym(private_key_A, public_key_B_hex)

    # Шифрование и расшифрование сообщения
    message = "Привет, это секретное сообщение."
    encrypted_message = encrypt_message(message, symmetric_key)
    decrypted_message = decrypt_message(encrypted_message, symmetric_key)

    print("Исходное сообщение:", message)
    print("Шифрованное сообщение:", encrypted_message)
    print("Расшифрованное сообщение:", decrypted_message)
