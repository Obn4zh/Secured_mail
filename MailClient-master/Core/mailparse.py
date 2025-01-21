from __future__ import unicode_literals
from six import BytesIO, binary_type
#BytesIO аналог файла в памяти, предназначенный для работы с байтовыми данными
# quopri кодирование\декодирование ASCII

import re
import email
import base64
import quopri
import time
from datetime import datetime
from email.header import decode_header


def str_encode(value=b'', encoding=None, errors='strict'):
    try:
        return value.decode(encoding, errors)
    except UnicodeDecodeError:
        return value.decode("koi8_r", errors)

def str_decode(value='', encoding=None, errors='strict'):
    if isinstance(value, str):
        return bytes(value, encoding, errors).decode('utf-8')
    elif isinstance(value, bytes):
        return value.decode(encoding or 'utf-8', errors=errors)
    else:
        raise TypeError( "Cannot decode '{}' object".format(value.__class__) )

def decode_mail_header(value, default_charset='us-ascii'):
    """
    Раскодировать значение заголовка в строку Unicode
    """
    try:
        headers = decode_header(value)
    except email.errors.HeaderParseError:
        return str_decode(str_encode(value, default_charset, 'replace'), default_charset)
    else:
        decoded_parts = []
        for text, charset in headers:
            if charset is None:
                if isinstance(text, bytes):
                    # Попытка декодировать байты как UTF-8
                    try:
                        decoded_parts.append(text.decode('utf-8'))
                    except UnicodeDecodeError:
                        decoded_parts.append(text.decode(default_charset, 'replace'))
                else:
                    # Если это строка, добавляем её без изменений
                    decoded_parts.append(text)
            else:
                try:
                    decoded_parts.append(str_decode(text, charset or default_charset, 'replace'))
                except LookupError:
                    decoded_parts.append(str_decode(text, default_charset, 'replace'))

        return ''.join(decoded_parts)





def get_mail_addresses(message, header_name):
    """
   Извлечь все адреса электронной почты из заголовка одного письма
    """
    headers = [h for h in message.get_all(header_name, [])]
    addresses = email.utils.getaddresses(headers)

    for index, (address_name, address_email) in enumerate(addresses):
        addresses[index] = {'name': decode_mail_header(address_name),
                            'email': address_email}
    return addresses


def decode_param(param):
    """
    Декодирование MIME-закодированных параметров, часто встречающихся в заголовках электронной почты
    """
    name, v = param.split('=', 1)
    values = v.split('\n')
    value_results = []
    for value in values:
        match = re.search(r'=\?((?:\w|-)+)\?(Q|B)\?(.+)\?=', value)
        if match:
            encoding, type_, code = match.groups()
            if type_ == 'Q':
                value = quopri.decodestring(code)
            elif type_ == 'B':
                value = base64.decodestring(code)
            value = str_encode(value, encoding)
            value_results.append(value)
            if value_results:
                v = ''.join(value_results)
    return name, v


def parse_attachment(message_part):
    content_disposition = message_part.get("Content-Disposition", None)
    if content_disposition is not None and not message_part.is_multipart():
        dispositions = content_disposition.strip().split(";")

        if dispositions[0].lower() in ["attachment", "inline"]:
            file_data = message_part.get_payload(decode=True)

            attachment = {
                'content-type': message_part.get_content_type(),
                'size': len(file_data),
                'content': BytesIO(file_data)
            }
            filename = message_part.get_param('name')
            if filename:
                attachment['filename'] = filename

            for param in dispositions[1:]:
                name, value = decode_param(param)

                if 'file' in name:
                    attachment['filename'] = value

                if 'create-date' in name:
                    attachment['create-date'] = value

            return attachment

    return None


def decode_content(message, isDecode=True):
    content = message.get_payload(decode=isDecode)
    charset = message.get_content_charset('utf-8')
    try:
        return content.decode(charset)
    except AttributeError:
        return content


def parse_email(raw_email):
    """
    Для обработки и разбора исходного письма в формате MIME (сырое письмо, загруженное из почтового сервера).
    """
    if isinstance(raw_email, binary_type):
        raw_email = str_encode(raw_email, 'utf-8')
    # Попытка создать объект email.message из сырого письма
    try:
        email_message = email.message_from_string(raw_email)
    except UnicodeEncodeError:
        email_message = email.message_from_string(raw_email.encode('utf-8'))
    maintype = email_message.get_content_maintype()
    parsed_email = {}

    parsed_email['raw_email'] = raw_email

    body = {
        "plain": [],
        "html": []
    }
    attachments = []

    if maintype in ('multipart', 'image'):
        for part in email_message.walk():
            content_type = part.get_content_type()
            part_maintype = part.get_content_maintype()
            content_disposition = part.get('Content-Disposition', None)
            if content_disposition or not part_maintype == "text":
                content = part.get_payload(decode=True)
            else:
                content = decode_content(part)

            is_inline = content_disposition is None \
                or content_disposition == "inline"
            if content_type == "text/plain" and is_inline:
                body['plain'].append(content)
            elif content_type == "text/html" and is_inline:
                body['html'].append(content)
            elif content_disposition:
                attachment = parse_attachment(part)
                if attachment:
                    attachments.append(attachment)

    elif maintype == 'text':
        payload = decode_content(email_message, False)
        body['plain'].append(payload)

    parsed_email['attachments'] = attachments

    parsed_email['body'] = body
    email_dict = dict(email_message.items())

    parsed_email['sent_from'] = get_mail_addresses(email_message, 'from')
    parsed_email['sent_to'] = get_mail_addresses(email_message, 'to')
    parsed_email['cc'] = get_mail_addresses(email_message, 'cc')
    parsed_email['bcc'] = get_mail_addresses(email_message, 'bcc')

    value_headers_keys = ['subject', 'date', 'message-id']
    key_value_header_keys = ['received-spf',
                             'mime-version',
                             'x-spam-status',
                             'x-spam-score',
                             'content-type']

    parsed_email['headers'] = []
    for key, value in email_dict.items():

        if key.lower() in value_headers_keys:
            valid_key_name = key.lower().replace('-', '_')
            parsed_email[valid_key_name] = decode_mail_header(value)

        if key.lower() in key_value_header_keys:
            parsed_email['headers'].append({'Name': key,
                                            'Value': value})

    if parsed_email.get('date'):
        timetuple = email.utils.parsedate(parsed_email['date'])
        parsed_date = datetime.fromtimestamp(time.mktime(timetuple)) \
            if timetuple else None
        parsed_email['parsed_date'] = parsed_date

    return dict(**parsed_email)


def parse_header(raw_email):
    if isinstance(raw_email, binary_type):
        raw_email = str_encode(raw_email, 'utf-8')
    try:
        email_message = email.message_from_string(raw_email)
    except UnicodeEncodeError:
        email_message = email.message_from_string(raw_email.encode('utf-8'))

    parsed_email = {}

    email_dict = dict(email_message.items())

    parsed_email['sent_from'] = get_mail_addresses(email_message, 'from')
    parsed_email['sent_to'] = get_mail_addresses(email_message, 'to')

    value_headers_keys = ['subject', 'date']

    for key, value in email_dict.items():
        if key.lower() in value_headers_keys:
            valid_key_name = key.lower().replace('-', '_')
            parsed_email[valid_key_name] = decode_mail_header(value)

    if parsed_email.get('date'):
        timetuple = email.utils.parsedate(parsed_email['date'])
        parsed_date = datetime.fromtimestamp(time.mktime(timetuple)) \
            if timetuple else None
        parsed_email['parsed_date'] = parsed_date

    return dict(**parsed_email) #** - распаковка словаря в переменные


def parse_body(raw_email):
    # Если входные данные представлены в виде байтов, преобразуем их в строку с кодировкой UTF-8
    if isinstance(raw_email, binary_type):
        raw_email = str_encode(raw_email, 'utf-8')
    
    try:
        # Парсим сырой email в email.message
        email_message = email.message_from_string(raw_email)
    except UnicodeEncodeError:
        email_message = email.message_from_string(raw_email.encode('utf-8'))

    # Определяем основной тип содержимого письма (например, text, multipart, image)
    maintype = email_message.get_content_maintype()

    # Создаем структуру для хранения результатов
    parsed_email = {}
    body = {"plain": [], "html": []}  

    if maintype in ('multipart', 'image'):
        # Обходим каждую часть сообщения
        for part in email_message.walk():
            content_type = part.get_content_type()  
            part_maintype = part.get_content_maintype()  
            content_disposition = part.get('Content-Disposition', None)  # Определяем наличие Content-Disposition

            if content_disposition or not part_maintype == "text":
                content = part.get_payload(decode=True)
            else:
                content = decode_content(part)

            is_inline = content_disposition is None or content_disposition == "inline"
            
            # Добавляем текстовые части в соответствующий список
            if content_type == "text/plain" and is_inline:
                body['plain'].append(content)  
            elif content_type == "text/html" and is_inline:
                body['html'].append(content)  

    elif maintype == 'text':
        payload = decode_content(email_message, False)  
        body['plain'].append(payload)

    parsed_email['body'] = body

    return dict(**parsed_email)
