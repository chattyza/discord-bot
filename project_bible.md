# Project Bible — Discord Bot (Blackfire Helper)

อัปเดตล่าสุด: 2026-07-19

## ภาพรวม

Discord bot (Python, `discord.py`) สำหรับช่วยเหลือผู้เล่นเกม **Blackfire** ในเซิร์ฟเวอร์ Discord ทำหน้าที่หลัก 6 อย่าง:

1. ค้นหาชื่อด่าน (TH/EN/CN) จาก `stages.json`
2. ค้นหาคำศัพท์เกม (TH/EN/CN) จาก `dictionary.json`
3. OCR แปลงรูปภาพเป็นข้อความ (ผ่าน ocr.space API) เมื่อมีคนกด reaction ✅ บนรูป
4. ค้นหารูปภาพด้วย Google Lens เมื่อมีคนกด reaction 🖕 บนรูป
5. แปลภาษา EN/TH/CN แบบปกติ (ฟรี) หรือแบบ advance (Gemini, เป็นธรรมชาติกว่า)
6. เครื่องมือ mod: ลบข้อความของ user (`clear`, `nuke`)

Repo: `https://github.com/chattyza/discord-bot`

## Tech Stack

| อะไร | เวอร์ชัน |
|---|---|
| Python | 3.14.6 (ทดสอบแล้วว่าใช้ได้กับ discord.py 2.7.1) |
| discord.py | >=2.3.0 (ติดตั้งจริง 2.7.1) |
| python-dotenv | >=1.0.0 |
| aiohttp | >=3.9.0 |
| deep-translator | >=1.11.4 — แปลภาษาแบบปกติ (ฟรี, wrap Google Translate แบบ unofficial ไม่ต้องมี API key) |
| google-genai | >=1.0.0 — แปลภาษาแบบ advance ผ่าน Gemini (ต้องมี `GEMINI_API_KEY`) |
| Git | ใช้ push ข้อมูล JSON ที่อัปเดตขึ้น GitHub |
| Hosting | Railway (service ชื่อ "worker", deploy อัตโนมัติจาก git push ผ่าน GitHub) |

## โครงสร้างไฟล์

- `bot.py` — โค้ดบอททั้งหมด (single file)
- `requirements.txt` — รายการ Python packages
- `stages.json` — ข้อมูลด่านทั้งหมด (โหลดจาก disk ตอนรันคำสั่ง `!w m`)
- `dictionary.json` — ข้อมูลคำศัพท์ (โหลดจาก disk ตอนรันคำสั่ง `!w d`)
- `.env` — เก็บ token/credentials (**ไม่ถูก commit เข้า git** — เช็คแล้วว่าไม่เคยอยู่ใน git history เลย ปลอดภัย)
- `.gitignore` — กัน `.env`, `__pycache__/`, `*.pyc`, ไฟล์ cookies ทุกชนิด (เผื่อไว้แม้ตอนนี้ไม่ได้ใช้ cookies แล้ว)
- `Procfile` — `worker: python bot.py` (สำหรับ deploy แบบ Heroku-style worker dyno)
- `run_bot.bat` — รันบอทบน Windows แบบดับเบิลคลิก
- `update_json.bat` — สคริปต์อัปเดตข้อมูล (ดูหัวข้อ Workflow ด้านล่าง)

## Environment Variables (.env)

ไฟล์ `.env` ต้องมี key ต่อไปนี้ (ค่าจริงเก็บในเครื่องเท่านั้น ห้าม commit หรือแชร์ใน chat/public ที่ไหนอีก):

| Key | ใช้ทำอะไร |
|---|---|
| `DISCORD_TOKEN` | Token ของบอทจาก Discord Developer Portal |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS` | ข้อมูลเชื่อมต่อฐานข้อมูล (หมายเหตุ: ปัจจุบัน `bot.py` ยังไม่ได้ใช้ค่านี้จริง — เป็น credential ที่เตรียมไว้เผื่ออนาคต หรือใช้กับระบบอื่น เช่นเว็บ export ข้อมูล) |
| `OCR_API_KEY` | API key ของ ocr.space สำหรับฟีเจอร์ OCR |
| `GEMINI_API_KEY` | *(ไม่บังคับ)* API key จาก Google AI Studio — จำเป็นเฉพาะคำสั่งแปลแบบ advance (`!w en-th!` ฯลฯ) ถ้าไม่ตั้งค่า คำสั่งแบบ advance จะตอบ error แต่คำสั่งแปลแบบปกติ (ไม่มี `!`) ยังใช้ได้ปกติ ฟรี ไม่ต้องผูกบัตร ดูวิธีขอที่ Google AI Studio (ai.google.dev) |

> ⚠️ ค่าจริงของ `.env` เคยถูกพิมพ์ตรงๆ ในแชทนี้ ถ้า credential ชุดนี้เคยหลุดไปที่อื่น (เช่นเคย commit ไว้ก่อนหน้า, แชร์ใน public channel) แนะนำให้ rotate token/password ใหม่เพื่อความปลอดภัย

## คำสั่งบอททั้งหมด (prefix `!w `)

| คำสั่ง | รายละเอียด |
|---|---|
| `!w` | แสดง help embed |
| `!w m <ชื่อด่าน>` | ค้นหาด่าน (TH/EN/CN), แสดงสูงสุด 5 ผลลัพธ์ |
| `!w d [คำ]` | ค้นหาคำศัพท์ (ไม่ใส่คำ = แสดงทั้งหมด, สูงสุด 100 รายการ) |
| `!w howto` | ลิงก์สมัคร/เติมเงิน/CN ID |
| `!w cal <สมการ>` | คำนวณสมการ รองรับ `+ - x(หรือ *) / ^` และวงเล็บ เช่น `!w cal ((3+5) x (4-2) / 2) x (2 + 5)` |
| กด ✅ บนรูปภาพ | OCR แปลงรูปเป็นข้อความ (ภาษาไทย, สูงสุด 3 รูปต่อครั้ง) |
| กด 🖕 บนรูปภาพ | ส่งลิงก์ค้นหารูปนั้นด้วย Google Lens (reverse image search, สูงสุด 3 รูปต่อครั้ง) |
| `!w en-th <ข้อความ>` | แปล EN→TH แบบปกติ (ฟรี, Google Translate) |
| `!w th-en <ข้อความ>` | แปล TH→EN แบบปกติ |
| `!w th-cn <ข้อความ>` | แปล TH→CN แบบปกติ |
| `!w en-th! <ข้อความ>` | แปล EN→TH แบบ advance (Gemini, เป็นธรรมชาติกว่า, ต้องมี `GEMINI_API_KEY`) |
| `!w th-en! <ข้อความ>` | แปล TH→EN แบบ advance |
| `!w th-cn! <ข้อความ>` | แปล TH→CN แบบ advance |
| `!w clear <user\|all> [n]` | ลบข้อความ (ต้องมีสิทธิ์ Manage Messages), default 100, สูงสุด 1000 |
| `!w nuke <user>` | ลบข้อความของ user คนนั้นทุก channel (สแกน 500 ข้อความล่าสุดต่อ channel) |

## โครงสร้างข้อมูล

**stages.json**
```json
{
  "generated_at": "...",
  "count": 8,
  "stages": [
    {
      "id": 8, "name_th": "...", "name_en": "...", "name_cn": "...",
      "description": "", "tags": "", "game": "Blackfire", "game_slug": "blackfire",
      "mode": "Assault", "slug": "...", "image_path": "...", "image_url": "https://chatty.site.je/uploads/stages/..."
    }
  ]
}
```

**dictionary.json**
```json
{
  "generated_at": "...",
  "count": 8,
  "terms": [
    { "id": 9, "thai": "...", "english": "...", "chinese": "...", "meaning": null, "notes": null, "category": null }
  ]
}
```

ข้อมูลทั้งสองไฟล์มาจากระบบเว็บแยก (`chatty.site.je`) แล้ว export ออกมาเป็น JSON

## Workflow: อัปเดตข้อมูล (`update_json.bat`)

1. หาไฟล์ `stages_export_*.json` และ `dictionary_export_*.json` ล่าสุดใน `Downloads`
2. copy ทับเป็น `stages.json` / `dictionary.json` ในโปรเจค
3. `git add` + `git commit` + `git push origin master`

บอทโหลด JSON จาก disk ทุกครั้งที่มีคำสั่ง (ไม่ cache ในหน่วยความจำ) ดังนั้น push เสร็จแล้วต้อง **restart บอท** (หรือถ้า deploy บน host ที่ pull auto ก็ให้ pull ก่อน) ค่าใหม่ถึงจะมีผล

## ฟีเจอร์ค้นหารูปภาพ (Google Lens)

กด reaction 🖕 บนข้อความที่มีรูปภาพ (ไฟล์แนบ หรือรูปใน embed/link preview) บอทจะตอบกลับเป็นลิงก์ `https://lens.google.com/uploadbyurl?url=<image_url>` ให้กดเข้าไปดูผลค้นหาบน Google Lens ได้เลย

ทำงานแบบนี้เพราะ Google ไม่มี Lens API สาธารณะให้ใช้ตรงๆ (มีแต่บริการ third-party อย่าง SerpApi ที่คิดเงิน) แต่ endpoint `uploadbyurl` เป็นลิงก์เดียวกับที่ browser ใช้ตอนกด "Search image with Google Lens" อยู่แล้ว บอทแค่สร้างลิงก์นี้ให้ ไม่ได้ scrape หรือประมวลผลอะไรเอง จึงไม่มีค่าใช้จ่าย ไม่มี API key ต้องตั้งค่า และไม่เสี่ยงโดน rate limit/บล็อกแบบที่เจอกับ YouTube

## ฟีเจอร์แปลภาษา

คำสั่งแปลภาษา (`en-th`, `th-en`, `th-cn` และ version `!` ต่อท้าย) **ไม่ได้ผูกกับระบบ command ปกติของ discord.py** (ไม่ใช้ `@bot.command`) แต่ดักจับด้วย regex ใน `on_message` แทน เพราะชื่อคำสั่งมีเครื่องหมาย `!` ต่อท้ายได้ ซึ่งไม่ใช่ชื่อ command ที่ถูกต้องตามกติกาของ discord.py

- **แบบปกติ** ใช้ `deep-translator` (wrap Google Translate แบบ unofficial) ฟรี ไม่ต้องมี API key แต่แปลตรงตัว อาจแข็งกับสำนวน/คำแสลง
- **แบบ advance** ใช้ Gemini (`gemini-3.5-flash` ผ่าน `google-genai` SDK) ให้ prompt สั่งให้แปลแบบเป็นธรรมชาติ ไม่ใส่คำอธิบายเพิ่ม ต้องมี `GEMINI_API_KEY` ถ้าไม่ตั้งค่าไว้ คำสั่งจะตอบ error กลับมาเฉยๆ (ไม่กระทบคำสั่งแบบปกติ)

**ข้อควรระวังเรื่อง Gemini free tier:** ฟรี ไม่ต้องผูกบัตร แต่ถ้าวันไหน enable billing บน Google Cloud project เดียวกัน (เช่นอยากอัปเกรดไปใช้โมเดล Pro) ฟรีเทียร์จะหายไปทั้ง project ทันที ทุก request จะเริ่มเก็บเงินตั้งแต่ตัวแรก — ถ้าจะทดลองฟีเจอร์อื่นที่ต้องเสียเงินบน Google Cloud แนะนำสร้าง project แยกจากตัวที่ใช้กับ Gemini API key นี้

## ฟีเจอร์คำนวณ (`!w cal`)

รองรับ `+ - x(หรือ *) / ^ %` และวงเล็บซ้อนได้ไม่จำกัดชั้น เช่น `((3+5) x (4-2) / 2) x (2 + 5)`

**สำคัญ — ไม่ใช้ `eval()`/`exec()` โดยตรง** เพราะข้อความจาก user เป็น input ที่ไม่น่าเชื่อถือ ถ้าใช้ `eval()` ตรงๆ จะเปิดช่องให้รันโค้ด Python ใดๆ ก็ได้ผ่าน Discord message (code injection) วิธีที่ใช้จริงคือ parse ข้อความเป็น AST ด้วย `ast.parse(..., mode="eval")` แล้วเดินผ่าน node ทีละตัวโดยยอมรับเฉพาะตัวเลขกับ operator ทางคณิตศาสตร์เท่านั้น (`ast.BinOp`, `ast.UnaryOp`, `ast.Constant`) ปฏิเสธทุกอย่างที่ไม่ใช่กลุ่มนี้ (function call, import, ชื่อตัวแปร ฯลฯ) มี guard เพิ่มเติม: จำกัดความยาวสมการ 200 ตัวอักษร, เช็ค whitelist อักขระก่อน parse, จำกัดขนาดเลขยกกำลังกันคำนวณค้าง/หน่วยความจำระเบิด

## Setup เครื่องใหม่

1. ติดตั้ง Python 3.x + pip + Git
2. `pip install -r requirements.txt`
3. สร้างไฟล์ `.env` ใส่ key ทั้งหมดด้านบนให้ครบ
4. รันบอทด้วย `run_bot.bat` หรือ `python bot.py`

## เคยลองทำ: ฟีเจอร์เพลง (play/pause/stop) — ทำไมถึงตัดทิ้ง

**อย่าลองเพิ่มฟีเจอร์นี้อีกโดยไม่อ่านหัวข้อนี้ก่อน** เคยพัฒนาเสร็จสมบูรณ์แล้ว (เชื่อมห้องเสียง, เล่นเพลงจาก YouTube ผ่าน `yt-dlp` + `ffmpeg`, คิวเพลง, auto-disconnect) แต่สุดท้ายต้องตัดทิ้งเพราะเจอข้อจำกัดที่แก้ไม่ได้ด้วยโค้ด:

**สาเหตุที่แท้จริง: Railway ไม่รองรับ inbound UDP**

Discord voice ต้องการให้บอท**รับ** UDP packet ตอบกลับจาก Discord voice server (ใช้ตอน IP discovery ตอนเริ่มเชื่อมต่อห้องเสียง) แต่ Railway (ตรวจสอบจากเอกสารทางการแล้ว) รองรับแค่ inbound HTTP domain กับ TCP proxy เท่านั้น **ไม่มี inbound UDP** เลย ผลคือทุกครั้งที่บอทพยายามต่อห้องเสียง จะค้างที่ขั้นตอน "voice handshake" จนครบ 30 วินาทีแล้ว timeout เสมอ (`discord.voice_state: Timed out connecting to voice`) — เป็นข้อจำกัดระดับ infrastructure ของ Railway เอง แก้ด้วยโค้ดยังไงก็ไม่มีทาง ระหว่างทางก่อนเจอสาเหตุนี้ ยังเจอปัญหาอื่นซ้อนด้วย (แก้ไปตามลำดับได้หมดแล้ว แต่สุดท้ายก็มาติดที่ UDP):

- discord.py 2.6+ ต้องมี package `davey` เพิ่ม (Discord's DAVE E2EE protocol) ไม่งั้น error `RuntimeError: davey library needed in order to use voice`
- YouTube บล็อกการดึงเสียงแบบไม่ login (`LOGIN_REQUIRED` / "Sign in to confirm you're not a bot") ต้องใช้ cookies จากบัญชีจริง — แต่ cookies จาก IP ของ cloud/datacenter อย่าง Railway หมดอายุไวมาก (เจอเคสหมดอายุใน ~30 นาที) เพราะ YouTube สงสัยว่า session ผิดปกติ
- ต่อให้ cookies ผ่าน ก็ยังเจอ YouTube's SABR streaming ที่ซ่อน format เสียงถ้าไม่มี PO token (ต้องเลี่ยงด้วย `extractor_args`)

**ถ้าจะกลับมาทำฟีเจอร์นี้อีกในอนาคต** ต้องย้าย hosting ไปที่รองรับ UDP แบบสองทาง (เช่น VPS จริงที่มี public IP ตรงๆ อย่าง DigitalOcean, Oracle Cloud, หรือเครื่อง/เซิร์ฟเวอร์ส่วนตัว) ไม่ใช่แค่แก้โค้ดฝั่งบอท — Railway ใช้ต่อได้ปกติสำหรับฟีเจอร์อื่นทั้งหมดที่ไม่ใช้เสียง (m, d, OCR, clear, nuke)

## Deploy

`Procfile` บ่งบอกว่าตั้งใจ deploy เป็น worker dyno (เช่น Heroku หรือ platform ที่รองรับ Procfile) — รันคำสั่งเดียวคือ `python bot.py` ไม่มี web process
