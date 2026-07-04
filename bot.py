import discord
from discord.ext import commands
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
STAGES_API = "https://raw.githubusercontent.com/chattyza/discord-bot/master/stages.json"
OCR_API_KEY = os.getenv("OCR_API_KEY")

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
        name="📖 คู่มือ",
        value="`!w howto` — ลิงก์สมัคร / เติมเงิน / CN ID",
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
    async with aiohttp.ClientSession() as session:
        async with session.get(STAGES_API) as resp:
            if resp.status != 200:
                await ctx.send(f"❌ API error: HTTP {resp.status}", delete_after=10)
                return
            try:
                data = await resp.json(content_type=None)
            except Exception:
                raw = await resp.text()
                await ctx.send(f"❌ API ส่ง response ผิดปกติ:\n```{raw[:500]}```", delete_after=30)
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


@bot.command(name="howto")
async def howto(ctx: commands.Context):
    embed = discord.Embed(title="📖 How To", color=0x5865F2)
    embed.add_field(name="📥 Registration & Download", value="https://chatty.site.je/howto.php", inline=False)
    embed.add_field(name="💳 Topup", value="https://chatty.site.je/topup.php", inline=False)
    embed.add_field(name="🆔 CN ID", value="https://shorturl.at/zO1Yu", inline=False)
    await ctx.send(embed=embed)


@map_search.error
async def map_search_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ ระบุชื่อด่านด้วย เช่น `!w m เขาไฟ`", delete_after=5)
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: `{error}`", delete_after=10)


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
