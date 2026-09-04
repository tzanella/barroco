import os
import sys
import base64
import secrets
import random
import string
from cryptography.fernet import Fernet

token = os.environ.get("BOT_TOKEN")
if not token:
    sys.exit(1)

key_raw = secrets.token_bytes(32)
key_b64 = base64.urlsafe_b64encode(key_raw)
f = Fernet(key_b64)
ciphertext = f.encrypt(token.encode())

build_id = "".join(random.choices(string.ascii_letters + string.digits, k=4))

with open("bot.template.py", "r", encoding="utf-8") as file:
    content = file.read()

content = content.replace('b"__MARKER_TOKEN_ENC__"', repr(ciphertext))
content = content.replace('b"__MARKER_TOKEN_KEY__"', repr(key_b64))
content = content.replace('__MARKER_APP_BUILD__', build_id)

with open("bot.py", "w", encoding="utf-8") as file:
    file.write(content)
