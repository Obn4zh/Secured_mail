from os import urandom
from functools import reduce
from operator import xor
import os
import asimm_crypto

# Константы для ГОСТ Кузнечик
PI = [
    252, 238, 221, 17, 207, 110, 49, 22, 251, 196, 250, 218, 35, 197, 4, 77,
    233, 119, 240, 219, 147, 46, 153, 186, 23, 54, 241, 187, 20, 205, 95, 193,
    249, 24, 101, 90, 226, 92, 239, 33, 129, 28, 60, 66, 139, 1, 142, 79, 5,
    132, 2, 174, 227, 106, 143, 160, 6, 11, 237, 152, 127, 212, 211, 31, 235,
    52, 44, 81, 234, 200, 72, 171, 242, 42, 104, 162, 253, 58, 206, 204, 181,
    112, 14, 86, 8, 12, 118, 18, 191, 114, 19, 71, 156, 183, 93, 135, 21, 161,
    150, 41, 16, 123, 154, 199, 243, 145, 120, 111, 157, 158, 178, 177, 50, 117,
    25, 61, 255, 53, 138, 126, 109, 84, 198, 128, 195, 189, 13, 87, 223, 245,
    36, 169, 62, 168, 67, 201, 215, 121, 214, 246, 124, 34, 185, 3, 224, 15,
    236, 222, 122, 148, 176, 188, 220, 232, 40, 80, 78, 51, 10, 74, 167, 151,
    96, 115, 30, 0, 98, 68, 26, 184, 56, 130, 100, 159, 38, 65, 173, 69, 70,
    146, 39, 94, 85, 47, 140, 163, 165, 125, 105, 213, 149, 59, 7, 88, 179, 64,
    134, 172, 29, 247, 48, 55, 107, 228, 136, 217, 231, 137, 225, 27, 131, 73,
    76, 63, 248, 254, 141, 83, 170, 144, 202, 216, 133, 97, 32, 113, 103, 164,
    45, 43, 9, 91, 203, 155, 37, 208, 190, 229, 108, 82, 89, 166, 116, 210, 230,
    244, 180, 192, 209, 102, 175, 194, 57, 75, 99, 182
]

SIGMA = [
    6, 11, 3, 12, 7, 0, 5, 10, 1, 14, 15, 8, 4, 2, 13, 9
]

# Функции преобразования
def s_block(x):
    return reduce(xor, [PI[(x >> (4 * i)) & 0xF] for i in range(8)])

def p_layer(x):
    return reduce(lambda a, b: (a << 8) | b, [((x >> (8 * i)) & 0xFF) for i in SIGMA])

def f(x, k):
    return p_layer(s_block(x ^ k))

def gost_kuznechik_encrypt(block, key):
    k = [int.from_bytes(key[i * 32:(i + 1) * 32], 'big') for i in range(8)]
    x = int.from_bytes(block, 'big')
    for i in range(12):
        x = f(x, k[i % 8])
    return x.to_bytes(16, 'big')

def gost_kuznechik_decrypt(block, key):
    k = [int.from_bytes(key[i * 32:(i + 1) * 32], 'big') for i in range(8)]
    x = int.from_bytes(block, 'big')
    for i in range(11, -1, -1):
        x = f(x, k[i % 8])
    return x.to_bytes(16, 'big')

# Умножение в поле Галуа для генерации аутентификационного тега
def galois_mult(a, b):
    result = 0
    for i in range(8):
        if b & 1:
            result ^= a
        a = (a << 1) ^ (0xC3 if (a & 0x80) else 0)
        b >>= 1
    return result

# Генерация тега аутентификации
def generate_tag(data, key):
    tag = gost_kuznechik_encrypt(bytes(16), key)
    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        tag = bytes([a ^ b for a, b in zip(tag, block)])
        tag = gost_kuznechik_encrypt(tag, key)
    return tag

# Уникальный IV с отслеживанием использованных значений
used_ivs = set()

# Функция шифрования с GCM
def gost_kuznechik_gcm_encrypt(plaintext, key):
    iv = urandom(16)  # случайный IV для каждой сессии
    if iv in used_ivs:
        raise ValueError("Повторное использование IV! Генерация нового значения.")
    used_ivs.add(iv)  # сохраняем использованный IV
    ciphertext = bytearray()
    counter = int.from_bytes(iv, 'big')
    
    for i in range(0, len(plaintext), 16):
        block = plaintext[i:i + 16]
        keystream = gost_kuznechik_encrypt(counter.to_bytes(16, 'big'), key)
        ciphertext.extend(bytes([a ^ b for a, b in zip(block, keystream)]))
        counter += 1
    
    # Генерируем тег аутентификации
    tag = generate_tag(ciphertext, key)
    return iv + ciphertext + tag  # возвращаем IV, зашифрованный текст и тег

# Функция дешифрования с GCM и проверкой тега
def gost_kuznechik_gcm_decrypt(ciphertext, key):
    iv = ciphertext[:16]
    tag = ciphertext[-16:]
    encrypted_data = ciphertext[16:-16]
    counter = int.from_bytes(iv, 'big')
    
    plaintext = bytearray()
    for i in range(0, len(encrypted_data), 16):
        block = encrypted_data[i:i + 16]
        keystream = gost_kuznechik_encrypt(counter.to_bytes(16, 'big'), key)
        plaintext.extend(bytes([a ^ b for a, b in zip(block, keystream)]))
        counter += 1
    
    # Проверка аутентификационного тега
    calculated_tag = generate_tag(encrypted_data, key)
    if calculated_tag != tag:
        raise ValueError("Ошибка аутентификации! Тег не совпадает.")
    
    return bytes(plaintext)

# Функции для шифрования и дешифрования файлов с GCM
def gost_kuznechik_gcm_encrypt_file(input_file, output_file, key):
    with open(input_file, 'rb') as f_in:
        plaintext = f_in.read()
    file_extension = os.path.splitext(input_file)[1].encode('utf-8')
    encrypted_data = gost_kuznechik_gcm_encrypt(plaintext + b'::' + file_extension, key)
    with open(output_file, 'wb') as f_out:
        f_out.write(encrypted_data)
    print(f"Файл {input_file} успешно зашифрован и сохранен как {output_file}.")

def gost_kuznechik_gcm_decrypt_file(input_file, output_dir, key):
    with open(input_file, 'rb') as f_in:
        encrypted_data = f_in.read()
    try:
        decrypted_data = gost_kuznechik_gcm_decrypt(encrypted_data, key)
        plaintext, file_extension = decrypted_data.rsplit(b'::', 1)
        output_file = os.path.join(output_dir, f"decrypted{file_extension.decode('utf-8')}")
        
        # Создаем директорию, если она не существует
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'wb') as f_out:
            f_out.write(plaintext)
        print(f"Файл {input_file} успешно расшифрован и сохранен как {output_file}.")
    except ValueError as e:
        print("Ошибка расшифровки:", e)

def p_layer(state):
    """
    Перестановочный слой для алгоритма "Кузнечик" по ГОСТ Р 34.12-2018.
    Преобразует входные данные в массив байтов, если они передаются в виде целого числа.
    """
    # Convert integer input to list of bytes if needed
    if isinstance(state, int):
        state = state.to_bytes(16, 'big')
    
    # Permutation logic based on GOST standards
    perm = [
        0, 8, 16, 24, 32, 40, 48, 56, 1, 9, 17, 25, 33, 41, 49, 57, 
        2, 10, 18, 26, 34, 42, 50, 58, 3, 11, 19, 27, 35, 43, 51, 59,
        4, 12, 20, 28, 36, 44, 52, 60, 5, 13, 21, 29, 37, 45, 53, 61,
        6, 14, 22, 30, 38, 46, 54, 62, 7, 15, 23, 31, 39, 47, 55, 63
    ]
    return [state[p] for p in perm]


# Пример использования
if __name__ == "__main__":
    # Генерация ключа
    key = asimm_crypto.gen_sym()
    
    # Вывод ключа
    print(f"Ключ: {key.hex()}")
    
    mode = input("Выберите режим (текст или файл): ").strip().lower()
    
    if mode == "текст":
        # Ввод текста для шифрования
        plaintext = input("Введите сообщение для шифрования: ").encode('utf-8')
        
        # Шифруем данные
        encrypted_message = gost_kuznechik_gcm_encrypt(plaintext, key)
        print(f"Зашифрованное сообщение (HEX): {encrypted_message.hex()}")
        
        # Дешифруем данные
        try:
            decrypted_message = gost_kuznechik_gcm_decrypt(encrypted_message, key)
            print(f"Расшифрованное сообщение: {decrypted_message.decode('utf-8')}")
        except ValueError as e:
            print("Ошибка аутентификации:", e)
    
    elif mode == "файл":
        input_file = "C:/D/Диплом/Crypto/test_kuznechik/testhtml.py".strip()
        encrypted_file = "C:/D/Диплом/Crypto/test_kuznechik/encrypted".strip()
        output_dir = "C:/D/Диплом/Crypto/test_kuznechik/output".strip()

        # Шифрование файла
        gost_kuznechik_gcm_encrypt_file(input_file, encrypted_file, key)
        
        # Дешифрование файла
        gost_kuznechik_gcm_decrypt_file(encrypted_file, output_dir, key)
    else:
        print("Неверный выбор режима. Попробуйте снова.")



