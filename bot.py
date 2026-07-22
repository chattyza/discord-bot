import discord
from discord.ext import commands
import os
import re
import ast
import json
import operator
import asyncio
import functools
import urllib.parse
import aiohttp
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Translate ---
# !w en-th / th-en / th-cn <ข้อความ>  = แปลปกติ (ฟรี ผ่าน Google Translate)
# !w en-th! / th-en! / th-cn! <ข้อความ>  = แปลแบบ advance (ผ่าน Gemini, เป็นธรรมชาติกว่า, ต้องตั้งค่า GEMINI_API_KEY)
gemini_client = None
if GEMINI_API_KEY:
    from google import genai
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

TRANSLATE_LANGS = {
    "en": {"code": "en", "name": "อังกฤษ", "flag": "🇬🇧"},
    "th": {"code": "th", "name": "ไทย", "flag": "🇹🇭"},
    "cn": {"code": "zh-CN", "name": "จีน", "flag": "🇨🇳"},
}

TRANSLATE_CMD_RE = re.compile(
    r"^!w\s+(en-th|th-en|th-cn)(!)?\s+(.+)$", re.IGNORECASE | re.DOTALL
)


async def translate_basic(text: str, src_code: str, dst_code: str) -> str:
    """แปลแบบปกติ ฟรี ไม่ต้องมี API key (ผ่าน Google Translate แบบ unofficial)"""
    loop = asyncio.get_event_loop()
    fn = functools.partial(GoogleTranslator(source=src_code, target=dst_code).translate, text)
    return await loop.run_in_executor(None, fn)


async def translate_advanced(text: str, src_name: str, dst_name: str) -> str:
    """แปลแบบ advance ผ่าน Gemini ให้ได้ภาษาที่เป็นธรรมชาติกว่า"""
    if gemini_client is None:
        raise RuntimeError("ยังไม่ได้ตั้งค่า GEMINI_API_KEY บน server")

    prompt = (
        f"แปลข้อความต่อไปนี้จากภาษา{src_name}เป็นภาษา{dst_name} "
        "ให้เป็นธรรมชาติเหมือนเจ้าของภาษาพูดจริง ไม่แปลตรงตัวแบบแข็งๆ "
        "ตอบกลับมาแค่คำแปลอย่างเดียว ห้ามใส่คำอธิบาย ห้ามใส่เครื่องหมายคำพูดครอบ:\n\n"
        f"{text}"
    )
    loop = asyncio.get_event_loop()
    fn = functools.partial(
        gemini_client.models.generate_content,
        model="gemini-3.5-flash",
        contents=prompt,
    )
    response = await loop.run_in_executor(None, fn)
    return (response.text or "").strip()


async def handle_translate_command(message: discord.Message, pair: str, advanced: bool, text: str) -> None:
    src_key, dst_key = pair.lower().split("-")
    src = TRANSLATE_LANGS[src_key]
    dst = TRANSLATE_LANGS[dst_key]
    text = text.strip()
    if not text:
        cmd = pair + ("!" if advanced else "")
        await message.channel.send(f"⚠️ ใส่ข้อความที่จะแปลด้วย เช่น `!w {cmd} hello`", delete_after=8)
        return

    async with message.channel.typing():
        try:
            if advanced:
                result = await translate_advanced(text, src["name"], dst["name"])
            else:
                result = await translate_basic(text, src["code"], dst["code"])
        except Exception as e:
            await message.channel.send(f"❌ แปลไม่สำเร็จ: `{e}`", delete_after=10)
            return

    title = f"{src['flag']} {src['name']} → {dst['flag']} {dst['name']}"
    if advanced:
        title += " ✨ Advance"
    embed = discord.Embed(title=title, color=0x9B59B6 if advanced else 0x5865F2)
    embed.add_field(name="ต้นฉบับ", value=text[:1000], inline=False)
    embed.add_field(name="คำแปล", value=(result[:1000] if result else "-"), inline=False)
    await message.channel.send(embed=embed)


# --- Calculator ---
class CalcError(Exception):
    """ข้อผิดพลาดที่คาดไว้ตอนคำนวณ (ข้อความ error จะโชว์ให้ user เห็นได้ตรงๆ)"""


_CALC_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_CALC_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _calc_eval_node(node):
    """ประเมินค่า AST node แบบจำกัดชนิด (ไม่ใช้ eval()/exec() ตรงๆ เพื่อกัน code injection)"""
    if isinstance(node, ast.Expression):
        return _calc_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalcError("ค่าที่ไม่รองรับ")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _CALC_BIN_OPS:
            raise CalcError("ตัวดำเนินการที่ไม่รองรับ")
        left = _calc_eval_node(node.left)
        right = _calc_eval_node(node.right)
        if op_type is ast.Pow and (abs(right) > 20 or abs(left) > 1_000_000):
            raise CalcError("เลขยกกำลังใหญ่เกินไป")
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise CalcError("หารด้วยศูนย์ไม่ได้")
        return _CALC_BIN_OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _CALC_UNARY_OPS:
            raise CalcError("ตัวดำเนินการที่ไม่รองรับ")
        return _CALC_UNARY_OPS[op_type](_calc_eval_node(node.operand))
    raise CalcError("รูปแบบสมการไม่ถูกต้อง")


def calculate(expr: str) -> int | float:
    """คำนวณสมการคณิตศาสตร์แบบปลอดภัย รองรับ + - x(หรือ *) / ^ วงเล็บ"""
    if len(expr) > 200:
        raise CalcError("สมการยาวเกินไป (จำกัด 200 ตัวอักษร)")
    normalized = (
        expr.replace("x", "*")
        .replace("X", "*")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
        .replace(",", "")
    )
    if not re.fullmatch(r"[0-9.\+\-\*/()%\s]+", normalized):
        raise CalcError("มีอักขระที่ไม่รองรับในสมการ (รองรับแค่ตัวเลข + - x / ^ วงเล็บ)")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError:
        raise CalcError("รูปแบบสมการไม่ถูกต้อง")
    return _calc_eval_node(tree)


def format_calc_result(result: int | float) -> str:
    if isinstance(result, float):
        if result.is_integer():
            return str(int(result))
        return str(round(result, 10)).rstrip("0").rstrip(".")
    return str(result)


def load_json(filename: str) -> list | dict | None:
    """อ่านไฟล์ JSON จาก disk"""
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!w ", intents=intents)


def find_member(guild: discord.Guild, name: str) -> discord.Member | None:
    """ค้นหา member จาก username, display name, หรือ nickname (case-insensitive)"""
    name_lower = name.lower()
    for member in guild.members:
        if (
            member.name.lower() == name_lower
            or member.display_name.lower() == name_lower
            or (member.nick and member.nick.lower() == name_lower)
        ):
            return member
    return None


def help_embed() -> discord.Embed:
    embed = discord.Embed(title="📋 คำสั่งทั้งหมด", color=0x5865F2)
    embed.add_field(
        name="🗺️ ค้นหาด่าน",
        value="`!w m <ชื่อด่าน>` — ค้นหาด่าน (TH/EN/CN)",
        inline=False,
    )
    embed.add_field(
        name="📖 พจนานุกรม",
        value="`!w d <คำ>` — ค้นหาคำศัพท์ EN/CN",
        inline=False,
    )
    embed.add_field(
        name="🔗 คู่มือ",
        value="`!w howto` — ลิงก์สมัคร / เติมเงิน / CN ID",
        inline=False,
    )
    embed.add_field(
        name="🖼️ OCR",
        value="กด ✅ ที่รูปภาพ — แปลงรูปเป็น text",
        inline=False,
    )
    embed.add_field(
        name="🔍 ค้นหารูปภาพ",
        value="กด 🖕 ที่รูปภาพ — ส่งลิงก์ค้นหารูปนั้นด้วย Google Lens",
        inline=False,
    )
    embed.add_field(
        name="🧮 คำนวณ",
        value="`!w cal <สมการ>` — คำนวณ +, -, x, /, ^, วงเล็บ เช่น `!w cal ((3+5) x (4-2) / 2) x (2 + 5)`",
        inline=False,
    )
    embed.add_field(
        name="🌐 แปลภาษา",
        value=(
            "`!w en-th <ข้อความ>` / `!w th-en <ข้อความ>` / `!w th-cn <ข้อความ>` — แปลปกติ (ฟรี)\n"
            "เติม `!` ต่อท้ายคำสั่ง (เช่น `!w en-th! hello`) — แปลแบบ advance ผ่าน Gemini เป็นธรรมชาติกว่า"
        ),
        inline=False,
    )
    embed.add_field(
        name="🗑️ ลบข้อความ (mod)",
        value=(
            "`!w clear <user> [n]` — ลบข้อความของ user ในช่องนี้\n"
            "`!w clear all [n]` — ลบทุกข้อความในช่องนี้\n"
            "`!w nuke <user>` — ลบข้อความของ user ทุก channel"
        ),
        inline=False,
    )
    embed.set_footer(text="[ ] = optional  |  n = จำนวนข้อความ (default 100)")
    return embed


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.content.strip() == "!w":
        await message.channel.send(embed=help_embed())
        return

    m = TRANSLATE_CMD_RE.match(message.content.strip())
    if m:
        pair, bang, text = m.group(1), m.group(2), m.group(3)
        await handle_translate_command(message, pair, bool(bang), text)
        return

    await bot.process_commands(message)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx: commands.Context, target: str, amount: int = 100):
    """
    ลบข้อความ

    รูปแบบ:
        !w clear all [n]          — ลบ n ข้อความล่าสุดในช่อง (default 100)
        !w clear <username> [n]   — ลบ n ข้อความของ user นั้นในช่อง (default 100)
    """
    await ctx.message.delete()  # ลบคำสั่งตัวเองออกก่อน

    if amount < 1 or amount > 1000:
        await ctx.send("⚠️ จำนวนต้องอยู่ระหว่าง 1–1000", delete_after=5)
        return

    # --- !w clear all ---
    if target.lower() == "all":
        deleted = await ctx.channel.purge(limit=amount)
        confirm = await ctx.send(
            f"🗑️ ลบข้อความทั้งหมด **{len(deleted)}** ข้อความในช่องนี้",
            delete_after=5,
        )
        return

    # --- !w clear <user> ---
    member = find_member(ctx.guild, target)
    if member is None:
        await ctx.send(f"❌ ไม่พบ user ชื่อ `{target}`", delete_after=5)
        return

    deleted = await ctx.channel.purge(
        limit=500,  # scan สูงสุด 500 ข้อความย้อนหลัง
        check=lambda m: m.author.id == member.id,
        before=ctx.message,
    )

    # ถ้าลบได้ไม่ครบตามที่ขอ ให้แจ้งด้วย
    note = ""
    if len(deleted) < amount:
        note = f" (พบแค่ {len(deleted)} ข้อความใน 500 ข้อความล่าสุด)"

    await ctx.send(
        f"🗑️ ลบข้อความของ **{member.display_name}** จำนวน **{len(deleted)}** ข้อความ{note}",
        delete_after=5,
    )


@bot.command(name="nuke")
@commands.has_permissions(manage_messages=True)
async def nuke(ctx: commands.Context, target: str):
    """
    ลบข้อความของ user ทุก channel ในเซิร์ฟเวอร์

    รูปแบบ:
        !w nuke <username>   — ลบข้อความของ user นั้นทุก channel (scan 500 ข้อความต่อ channel)
    """
    await ctx.message.delete()

    member = find_member(ctx.guild, target)
    if member is None:
        await ctx.send(f"❌ ไม่พบ user ชื่อ `{target}`", delete_after=5)
        return

    status_msg = await ctx.send(f"🔍 กำลังลบข้อความของ **{member.display_name}** ทุก channel...")

    total = 0
    for channel in ctx.guild.text_channels:
        # ข้ามช่องที่บอทไม่มีสิทธิ์
        if not channel.permissions_for(ctx.guild.me).manage_messages:
            continue
        try:
            deleted = await channel.purge(
                limit=500,
                check=lambda m: m.author.id == member.id,
            )
            total += len(deleted)
        except Exception:
            pass

    await status_msg.edit(content=f"✅ ลบข้อความของ **{member.display_name}** ทั้งหมด **{total}** ข้อความจากทุก channel")


@nuke.error
async def nuke_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 คุณไม่มีสิทธิ์ลบข้อความ (ต้องมี Manage Messages)", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ระบุชื่อ user ด้วย เช่น `!w nuke mr.a`", delete_after=5)
    else:
        raise error


@clear.error
async def clear_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 คุณไม่มีสิทธิ์ลบข้อความ (ต้องมี Manage Messages)", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "⚠️ รูปแบบคำสั่งผิด\n"
            "```\n"
            "!w clear all [จำนวน]\n"
            "!w clear <username> [จำนวน]\n"
            "```",
            delete_after=8,
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ จำนวนต้องเป็นตัวเลข เช่น `!w clear mr.a 20`", delete_after=5)
    else:
        raise error


@bot.command(name="m")
async def map_search(ctx: commands.Context, *, query: str):
    """
    ค้นหาด่านจากชื่อ (TH/EN/CN)

    รูปแบบ:
        !w m <ชื่อด่าน>
    """
    data = load_json("stages.json")
    if data is None:
        await ctx.send("❌ โหลด stages.json ไม่ได้", delete_after=10)
        return

    q = query.lower()
    all_stages = data.get("stages", [])
    stages = [
        s for s in all_stages
        if q in (s.get("name_th") or "").lower()
        or q in (s.get("name_en") or "").lower()
        or q in (s.get("name_cn") or "").lower()
    ][:5]
    if not stages:
        await ctx.send(f"❌ ไม่พบด่านที่ตรงกับ `{query}`")
        return

    for stage in stages:
        title = stage.get("name_th") or stage.get("name_en") or "-"
        embed = discord.Embed(title=title, color=0x5865F2)
        embed.add_field(name="🇹🇭 TH", value=stage.get("name_th") or "-", inline=True)
        embed.add_field(name="🇬🇧 EN", value=stage.get("name_en") or "-", inline=True)
        cn = stage.get("name_cn")
        embed.add_field(
            name="🇨🇳 CN (copy ได้)",
            value=f"```{cn}```" if cn else "-",
            inline=False,
        )
        if stage.get("image_url"):
            embed.set_image(url=stage["image_url"])
        await ctx.send(embed=embed)


@bot.command(name="d")
async def dict_search(ctx: commands.Context, *, query: str = ""):
    """ค้นหาคำศัพท์ — !w d [คำ]"""
    data = load_json("dictionary.json")
    if data is None:
        await ctx.send("❌ โหลด dictionary.json ไม่ได้", delete_after=10)
        return

    entries = data if isinstance(data, list) else data.get("terms", data.get("dictionary", data.get("data", [])))

    if query:
        q = query.lower()
        results = [
            e for e in entries
            if q in (e.get("thai") or "").lower()
            or q in (e.get("english") or "").lower()
            or q in (e.get("chinese") or "").lower()
        ]
        title = f"📖 ผลค้นหา: {query}"
    else:
        results = entries
        title = "📖 คำศัพท์ทั้งหมด"

    if not results:
        await ctx.send(f"❌ ไม่พบคำที่ตรงกับ `{query}`")
        return

    # แบ่งส่งทีละ 20 รายการ ถ้ามีเยอะ
    chunk = 20
    for i in range(0, min(len(results), 100), chunk):
        lines = []
        for e in results[i:i+chunk]:
            en = e.get("english") or "-"
            cn = e.get("chinese") or "-"
            lines.append(f"**{en}** — `{cn}`")
        embed = discord.Embed(
            title=title if i == 0 else "",
            description="\n".join(lines),
            color=0xFEE75C,
        )
        if i == 0:
            embed.set_footer(text=f"ทั้งหมด {len(results)} คำ | copy ได้ที่ ` `")
        await ctx.send(embed=embed)


@dict_search.error
async def dict_search_error(ctx: commands.Context, error):
    await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`", delete_after=10)


@bot.command(name="howto")
async def howto(ctx: commands.Context):
    embed = discord.Embed(title="📖 How To", color=0x5865F2)
    embed.add_field(name="📥 Registration & Download", value="https://chatty.site.je/howto.php", inline=False)
    embed.add_field(name="💳 Topup", value="https://chatty.site.je/topup.php", inline=False)
    embed.add_field(name="🆔 CN ID", value="https://shorturl.at/zO1Yu", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="cal")
async def calc_cmd(ctx: commands.Context, *, expression: str):
    """
    คำนวณสมการคณิตศาสตร์ — !w cal <สมการ>

    รองรับ + - x (หรือ *) / ^ วงเล็บ เช่น:
        !w cal ((3+5) x (4-2) / 2) x (2 + 5)
    """
    try:
        result = calculate(expression)
    except CalcError as e:
        await ctx.send(f"❌ {e}", delete_after=10)
        return
    except Exception:
        await ctx.send("❌ คำนวณไม่ได้ ตรวจสอบรูปแบบสมการอีกครั้ง", delete_after=10)
        return

    await ctx.send(f"🧮 `{expression.strip()}` = **{format_calc_result(result)}**")


@calc_cmd.error
async def calc_cmd_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ใส่สมการด้วย เช่น `!w cal ((3+5) x (4-2) / 2) x (2 + 5)`", delete_after=8)
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`", delete_after=10)
        raise error


@map_search.error
async def map_search_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ระบุชื่อด่านด้วย เช่น `!w m เขาไฟ`")
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`")
        raise error


def find_message_image_urls(message: discord.Message) -> list[str]:
    """หา URL รูปภาพทั้งหมดในข้อความ (ทั้งไฟล์แนบ และรูปใน embed/link preview)"""
    urls = []
    for a in message.attachments:
        if a.content_type and a.content_type.startswith("image/"):
            urls.append(a.url)
    for e in message.embeds:
        if e.image and e.image.url:
            urls.append(e.image.url)
        elif e.thumbnail and e.thumbnail.url:
            urls.append(e.thumbnail.url)
    return urls


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return

    emoji = str(reaction.emoji)
    message = reaction.message

    # --- 🖕 : ค้นหารูปด้วย Google Lens (reverse image search) ---
    if emoji == "🖕":
        urls = find_message_image_urls(message)
        if not urls:
            return
        for url in urls[:3]:
            lens_url = "https://lens.google.com/uploadbyurl?url=" + urllib.parse.quote(url, safe="")
            await message.channel.send(f"🔍 ค้นหารูปนี้ด้วย Google Lens: {lens_url}")
        return

    # --- ✅ : OCR แปลงรูปเป็นข้อความ ---
    if emoji != "✅":
        return

    # หา attachment ที่เป็นรูปภาพ
    images = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]
    if not images:
        return

    async with aiohttp.ClientSession() as session:
        for img in images[:3]:
            # ดาวน์โหลดรูปก่อน แล้วส่งเป็นไฟล์
            async with session.get(img.url) as r:
                img_bytes = await r.read()

            form = aiohttp.FormData()
            form.add_field("apikey", OCR_API_KEY)
            form.add_field("language", "tha")
            form.add_field("isOverlayRequired", "false")
            form.add_field("OCREngine", "2")
            form.add_field("file", img_bytes, filename=img.filename, content_type=img.content_type)

            async with session.post("https://api.ocr.space/parse/image", data=form) as resp:
                data = await resp.json()

            results = data.get("ParsedResults", [])
            if not results or data.get("IsErroredOnProcessing"):
                err = data.get("ErrorMessage") or data.get("ErrorDetails") or "unknown"
                await message.channel.send(f"❌ OCR ล้มเหลว: `{err}`", delete_after=10)
                continue

            text = results[0].get("ParsedText", "").strip()
            if not text:
                await message.channel.send("⚠️ ไม่พบข้อความในรูป", delete_after=10)
                continue

            embed = discord.Embed(title="📝 ข้อความจากรูป", color=0x57F287)
            embed.description = f"```{text[:3900]}```"
            embed.set_footer(text=f"จาก: {img.filename}")
            await message.channel.send(embed=embed)


bot.run(TOKEN)
