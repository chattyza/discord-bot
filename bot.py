import discord
from discord.ext import commands
import os
import json
import asyncio
import functools
from collections import deque
import aiohttp
import yt_dlp
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")
FFMPEG_EXECUTABLE = os.getenv("FFMPEG_PATH", "ffmpeg")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Music ---
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

music_queues: dict[int, deque] = {}   # guild_id -> deque ของเพลงที่รอเล่น


def get_queue(guild_id: int) -> deque:
    return music_queues.setdefault(guild_id, deque())


async def extract_track(query: str) -> dict:
    """ค้นหา/แปลง query (ชื่อเพลงหรือ URL) เป็นข้อมูลเพลงที่เล่นได้ (รันแบบ blocking ใน executor)"""
    loop = asyncio.get_event_loop()
    partial = functools.partial(ytdl.extract_info, query, download=False)
    data = await loop.run_in_executor(None, partial)
    if "entries" in data:
        if not data["entries"]:
            raise ValueError("ไม่พบผลลัพธ์")
        data = data["entries"][0]
    return {
        "title": data.get("title", "ไม่ทราบชื่อเพลง"),
        "url": data["url"],
        "webpage_url": data.get("webpage_url", query),
    }


async def play_next(ctx: commands.Context):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    voice_client = ctx.voice_client
    if not queue or voice_client is None:
        return

    track = queue.popleft()
    source = discord.FFmpegPCMAudio(track["url"], executable=FFMPEG_EXECUTABLE, **FFMPEG_OPTIONS)

    def _after(error: Exception | None):
        if error:
            print(f"⚠️ Player error: {error}")
        fut = asyncio.run_coroutine_threadsafe(play_next(ctx), ctx.bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"⚠️ play_next error: {e}")

    voice_client.play(source, after=_after)
    await ctx.send(f"🎶 กำลังเล่น: **{track['title']}**")

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
        name="🎵 เพลง",
        value=(
            "`!w play <ชื่อเพลง/URL>` — เล่นเพลง (ต้องอยู่ในห้องเสียงก่อน)\n"
            "`!w pause` — หยุด/เล่นต่อ (toggle)\n"
            "`!w stop` — หยุดและออกจากห้องเสียง"
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


@bot.command(name="play")
async def play(ctx: commands.Context, *, query: str):
    """
    เล่นเพลง — !w play <ชื่อเพลง หรือ URL YouTube>

    ถ้ามีเพลงเล่นอยู่แล้ว จะเพิ่มเข้าคิวแทน
    """
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("⚠️ ต้องเข้าห้องเสียงก่อนถึงจะใช้คำสั่งนี้ได้", delete_after=8)
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.voice_client
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    async with ctx.typing():
        try:
            track = await extract_track(query)
        except Exception as e:
            await ctx.send(f"❌ หาเพลงไม่เจอ: `{e}`", delete_after=10)
            return

    get_queue(ctx.guild.id).append(track)

    if voice_client.is_playing() or voice_client.is_paused():
        await ctx.send(f"➕ เพิ่มเข้าคิว: **{track['title']}**")
    else:
        await play_next(ctx)


@play.error
async def play_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ระบุชื่อเพลงหรือ URL ด้วย เช่น `!w play imagine dragons believer`", delete_after=8)
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`", delete_after=10)
        raise error


@bot.command(name="pause")
async def pause(ctx: commands.Context):
    """หยุดเพลงชั่วคราว / เล่นต่อ — !w pause (toggle)"""
    voice_client = ctx.voice_client
    if voice_client is None or not (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send("⚠️ ไม่มีเพลงกำลังเล่นอยู่", delete_after=5)
        return

    if voice_client.is_playing():
        voice_client.pause()
        await ctx.send("⏸️ หยุดเพลงชั่วคราวแล้ว (พิมพ์ `!w pause` อีกครั้งเพื่อเล่นต่อ)")
    else:
        voice_client.resume()
        await ctx.send("▶️ เล่นเพลงต่อ")


@bot.command(name="stop")
async def stop(ctx: commands.Context):
    """หยุดเพลงและออกจากห้องเสียง — !w stop"""
    voice_client = ctx.voice_client
    if voice_client is None:
        await ctx.send("⚠️ บอทไม่ได้อยู่ในห้องเสียง", delete_after=5)
        return

    get_queue(ctx.guild.id).clear()
    voice_client.stop()
    await voice_client.disconnect()
    await ctx.send("⏹️ หยุดเพลงและออกจากห้องเสียงแล้ว")


@map_search.error
async def map_search_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ระบุชื่อด่านด้วย เช่น `!w m เขาไฟ`")
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`")
        raise error


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    # ข้ามถ้าเป็นบอทเอง หรือไม่ใช่ ✅
    if user.bot or str(reaction.emoji) != "✅":
        return

    message = reaction.message
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
