from pygost.gost3410 import CURVES, public_key, pub_marshal, pub_unmarshal
from hashlib import sha256
import os

# Используем 256-битную кривую из ГОСТ Р 34.10-2012
curve = CURVES["id-tc26-gost-3410-2012-256-paramSetA"]

def generate_key_pair():
    """
    Генерирует пару ключей: приватный и публичный по ГОСТ.
    """
    # Генерация случайного приватного ключа
    private_key_bytes = os.urandom(32)
    private_key = int.from_bytes(private_key_bytes, byteorder="big") % curve.q
    # Получаем публичный ключ как точку и сериализуем в байты
    public_key_point = public_key(curve, private_key)
    public_key_bytes = pub_marshal(public_key_point)  # Используем pub_marshal для сериализации
    print(f'public_key_bytes: {str(public_key_bytes)}\nprivate_key: {private_key}')
    return private_key, public_key_bytes

def calculate_shared_secret(own_private_key, other_public_key_bytes):
    """
    Вычисляет общий секрет на основе своего приватного ключа и публичного ключа другой стороны.
    """
    # Десериализуем публичный ключ другой стороны для получения координат (x, y)
    other_public_key_point = pub_unmarshal(other_public_key_bytes)  # Используем pub_unmarshal
    other_public_key_x, other_public_key_y = other_public_key_point

    # Вычисление общего секрета через скалярное умножение на координаты публичного ключа
    shared_secret_point = curve.exp(own_private_key, x=other_public_key_x, y=other_public_key_y)

    # Хешируем X-координату для получения симметричного ключа
    shared_secret = sha256(shared_secret_point[0].to_bytes(32, byteorder='big')).digest()
    return shared_secret

# Пример использования:
def gen_sym():
    # Сторона A генерирует свою пару ключей
    private_key_A, public_key_A = generate_key_pair()

    # Сторона B генерирует свою пару ключей
    private_key_B, public_key_B = generate_key_pair()

    # Обмен публичными ключами и вычисление общего секрета
    shared_secret_A = calculate_shared_secret(private_key_A, public_key_B)
    shared_secret_B = calculate_shared_secret(private_key_B, public_key_A)

    # Проверка, что общий секрет одинаков у обеих сторон
    assert shared_secret_A == shared_secret_B, "Общий секрет должен совпадать у обеих сторон!"

    # Использование общего секрета в качестве симметричного ключа
    symmetric_key = shared_secret_A
    return symmetric_key

if __name__ == "__main__":
    key=gen_sym()
    print(key.hex())