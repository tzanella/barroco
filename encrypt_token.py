import os
import sys
import base64
import secrets
import random
import string
from cryptography.fernet import Fernet

token = None
build_id = None

if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
        if arg.upper() == "DEBUG":
            build_id = "DEBUG"
        elif not token and not arg.startswith("-"):
            token = arg

if not token:
    token = os.environ.get("BOT_TOKEN", "")

if not build_id:
    build_id = os.environ.get("APP_BUILD", "".join(random.choices(string.ascii_letters + string.digits, k=4)))

if token:
    key_raw = secrets.token_bytes(32)
    key_b64 = base64.urlsafe_b64encode(key_raw)
    f = Fernet(key_b64)
    ciphertext = f.encrypt(token.encode())
    key_repr = repr(key_b64)
    cipher_repr = repr(ciphertext)
else:
    print("[!] Warning: BOT_TOKEN environment variable or parameter not set.")
    print("[!] Generating bot.py without pre-embedded token. (Token must be passed at runtime via CLI).")
    key_repr = 'b""'
    cipher_repr = 'b""'

if not os.path.exists("bot.template.py"):
    print("[!] Error: bot.template.py file not found.")
    sys.exit(1)

with open("bot.template.py", "r", encoding="utf-8") as file:
    content = file.read()

content = content.replace('b"__MARKER_TOKEN_ENC__"', cipher_repr)
content = content.replace('b"__MARKER_TOKEN_KEY__"', key_repr)
content = content.replace('__MARKER_APP_BUILD__', build_id)

with open("bot.py", "w", encoding="utf-8") as file:
    file.write(content)

print(f"[+] Successfully generated bot.py (Build ID: {build_id})")


