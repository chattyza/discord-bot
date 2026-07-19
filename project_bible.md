# Project Bible — Discord Bot (Blackfire Helper)

อัปเดตล่าสุด: 2026-07-17

## ภาพรวม

Discord bot (Python, `discord.py`) สำหรับช่วยเหลือผู้เล่นเกม **Blackfire** ในเซิร์ฟเวอร์ Discord ทำหน้าที่หลัก 5 อย่าง:

1. ค้นหาชื่อด่าน (TH/EN/CN) จาก `stages.json`
2. ค้นหาคำศัพท์เกม (TH/EN/CN) จาก `dictionary.json`
3. OCR แปลงรูปภาพเป็นข้อความ (ผ่าน ocr.space API) เมื่อมีคนกด reaction ✅ บนรูป
4. เครื่องมือ mod: ลบข้อความของ user (`clear`, `nuke`)
5. เล่นเพลงในห้องเสียง (`play`, `pause`, `stop`) — ดึงเสียงผ่าน `yt-dlp` + `ffmpeg`

Repo: `https://github.com/chattyza/discord-bot`

## Tech Stack

| อะไร | เวอร์ชัน |
|---|---|
| Python | 3.14.6 (ทดสอบแล้วว่าใช้ได้กับ discord.py 2.7.1) |
| discord.py | >=2.3.0 (ติดตั้งจริง 2.7.1) |
| python-dotenv | >=1.0.0 |
| aiohttp | >=3.9.0 |
| PyNaCl | >=1.5.0 — จำเป็นสำหรับต่อเสียง (voice) ของ discord.py |
| davey | >=0.1.6 — จำเป็นสำหรับต่อเสียงของ discord.py 2.6+ (Discord's DAVE E2EE protocol) ไม่มีแล้วจะเจอ `RuntimeError: davey library needed in order to use voice` |
| yt-dlp | >=2024.1.0 — ดึงเสียงจาก YouTube/แหล่งอื่นสำหรับฟีเจอร์เพลง |
| ffmpeg | ต้องติดตั้งเองแยกจาก pip (ไม่ใช่ Python package) — ใช้แปลง/สตรีมเสียงตอนเล่นเพลง ดู "ติดตั้ง ffmpeg" ด้านล่าง |
| Git | ใช้ push ข้อมูล JSON ที่อัปเดตขึ้น GitHub |

## โครงสร้างไฟล์

- `bot.py` — โค้ดบอททั้งหมด (single file)
- `requirements.txt` — รายการ Python packages
- `stages.json` — ข้อมูลด่านทั้งหมด (โหลดจาก disk ตอนรันคำสั่ง `!w m`)
- `dictionary.json` — ข้อมูลคำศัพท์ (โหลดจาก disk ตอนรันคำสั่ง `!w d`)
- `.env` — เก็บ token/credentials (**ไม่ถูก commit เข้า git** — เช็คแล้วว่าไม่เคยอยู่ใน git history เลย ปลอดภัย)
- `.gitignore` — กัน `.env`, `__pycache__/`, `*.pyc`
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
| `FFMPEG_PATH` | *(ไม่บังคับ)* path เต็มไปยัง `ffmpeg.exe` — ใส่เฉพาะกรณี ffmpeg ไม่ได้อยู่ใน PATH ของระบบ ถ้าไม่ตั้งค่า บอทจะเรียก `ffmpeg` ตรงๆ (ต้องอยู่ใน PATH) |
| `YT_COOKIES` | *(ไม่บังคับ แต่จำเป็นถ้าเจอ error "Sign in to confirm you're not a bot")* เนื้อหาไฟล์ cookies.txt ทั้งหมด (Netscape cookie format) จากบัญชี YouTube จริง ดูวิธีทำในหัวข้อ "แก้ปัญหา YouTube bot detection" ด้านล่าง |

> ⚠️ ค่าจริงของ `.env` เคยถูกพิมพ์ตรงๆ ในแชทนี้ ถ้า credential ชุดนี้เคยหลุดไปที่อื่น (เช่นเคย commit ไว้ก่อนหน้า, แชร์ใน public channel) แนะนำให้ rotate token/password ใหม่เพื่อความปลอดภัย

## คำสั่งบอททั้งหมด (prefix `!w `)

| คำสั่ง | รายละเอียด |
|---|---|
| `!w` | แสดง help embed |
| `!w m <ชื่อด่าน>` | ค้นหาด่าน (TH/EN/CN), แสดงสูงสุด 5 ผลลัพธ์ |
| `!w d [คำ]` | ค้นหาคำศัพท์ (ไม่ใส่คำ = แสดงทั้งหมด, สูงสุด 100 รายการ) |
| `!w howto` | ลิงก์สมัคร/เติมเงิน/CN ID |
| กด ✅ บนรูปภาพ | OCR แปลงรูปเป็นข้อความ (ภาษาไทย, สูงสุด 3 รูปต่อครั้ง) |
| `!w clear <user\|all> [n]` | ลบข้อความ (ต้องมีสิทธิ์ Manage Messages), default 100, สูงสุด 1000 |
| `!w nuke <user>` | ลบข้อความของ user คนนั้นทุก channel (สแกน 500 ข้อความล่าสุดต่อ channel) |
| `!w play <ชื่อเพลง\|URL>` | เล่นเพลง (ต้องอยู่ในห้องเสียงก่อน) ถ้ามีเพลงเล่นอยู่แล้วจะเข้าคิวต่อท้าย |
| `!w pause` | toggle หยุดชั่วคราว/เล่นต่อ |
| `!w stop` | หยุดเพลง, ล้างคิว, ออกจากห้องเสียง |
| _(อัตโนมัติ)_ | บอทออกจากห้องเสียงเองถ้าทุกคนออกจากห้องหมด (เหลือบอทคนเดียว) |

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

## Setup เครื่องใหม่ (สรุปจากที่ทำไปแล้ว)

1. ติดตั้ง Python 3.x + pip + Git ✅ (มีอยู่แล้วบนเครื่องนี้: Python 3.14.6, Git 2.55.0)
2. `pip install -r requirements.txt` ✅ (รวม PyNaCl, yt-dlp สำหรับฟีเจอร์เพลง)
3. สร้างไฟล์ `.env` ใส่ key ทั้งหมดด้านบนให้ครบ
4. ติดตั้ง ffmpeg (ดูหัวข้อถัดไป) — ถ้าไม่ลง ฟีเจอร์เพลงจะใช้ไม่ได้ แต่คำสั่งอื่นยังทำงานปกติ
5. รันบอทด้วย `run_bot.bat` หรือ `python bot.py`

## ติดตั้ง ffmpeg (จำเป็นสำหรับฟีเจอร์เพลง)

ffmpeg ไม่ใช่ Python package เลยลงผ่าน `pip` ไม่ได้ ต้องดาวน์โหลด binary เอง:

1. โหลดจาก https://www.gyan.dev/ffmpeg/builds/ (เลือก "release essentials")
2. แตกไฟล์ zip แล้ว copy โฟลเดอร์ไปไว้ที่ไหนก็ได้ เช่น `C:\ffmpeg`
3. เพิ่ม `C:\ffmpeg\bin` เข้า PATH ของ Windows (Environment Variables) แล้วเปิด terminal ใหม่ ทดสอบด้วย `ffmpeg -version`
4. ถ้าไม่อยากยุ่งกับ PATH ระบบ ให้ตั้ง `FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe` ใน `.env` แทน — บอทจะเรียกใช้ path นี้ตรงๆ

## แก้ปัญหา YouTube bot detection ("Sign in to confirm you're not a bot")

ตั้งแต่ต้นปี 2026 YouTube เข้มงวดเรื่องบล็อกการดึงข้อมูลแบบไม่ login มากขึ้นมาก ทุก client ของ yt-dlp (web, android, tv, ios) มักโดน `LOGIN_REQUIRED` เหมือนกันหมด โดยเฉพาะจาก IP ของ cloud/datacenter อย่าง Railway วิธีแก้ที่ยังได้ผลตอนนี้คือใช้ **cookies จากบัญชี YouTube ที่ login จริง** (บัญชีที่มี YouTube Premium จะน่าเชื่อถือกว่าบัญชีฟรีในสายตาระบบตรวจจับของ YouTube)

**ขั้นตอน:**

1. เปิด Chrome/Edge (ใช้ browser ปกติ ไม่ใช่ incognito) แล้ว login เข้าบัญชี YouTube ที่จะใช้
2. ติดตั้ง extension "Get cookies.txt LOCALLY" (หรือชื่อใกล้เคียง) จาก Chrome Web Store
3. เข้า youtube.com แล้วกด export cookies ผ่าน extension จะได้ไฟล์ `cookies.txt`
4. **ในเครื่อง (dev):** copy ไฟล์ไปวางที่ `D:\Discord_Bot\cookies.txt` ตรงๆ (มีอยู่ใน `.gitignore` แล้ว จะไม่ถูก commit ขึ้น GitHub เด็ดขาด)
5. **บน Railway:** เปิดไฟล์ `cookies.txt` ด้วย Notepad คัดลอกเนื้อหาทั้งหมด ไปวางเป็นค่าของ env var ใหม่ชื่อ `YT_COOKIES` ใน Railway Variables (รองรับข้อความหลายบรรทัด) — บอทจะเขียนไฟล์ `cookies.txt` ให้เองตอน start จากค่านี้

**ข้อควรระวัง:**

- cookies.txt เทียบเท่ารหัสผ่านของบัญชีนั้น ห้าม commit เข้า git หรือแชร์ให้ใครเด็ดขาด
- cookies จะหมดอายุเป็นระยะ (สัปดาห์ถึงเดือน) ถ้าบอทเริ่ม error `Sign in to confirm` อีก ให้ export ใหม่แล้วอัปเดตค่าใน `YT_COOKIES`
- การใช้ cookies บัญชีจริงแบบอัตโนมัติแบบนี้ไม่ตรงกับ YouTube ToS เสี่ยงเล็กน้อยที่บัญชีจะถูกจำกัด แม้จะเป็นบัญชี Premium ก็ตาม แนะนำใช้บัญชีสำรอง ไม่ใช่บัญชีหลักที่ใช้ประจำ ถ้ากังวลเรื่องนี้

## Hosting note: ผลกระทบต่อ Railway (usage-based billing)

ฟีเจอร์เพลงเพิ่มการใช้ **network egress** (สตรีมเสียงออกไปตอนเล่น) เป็นตัวที่กระทบบิลชัดสุด ราวๆ 45–60MB/ชม. ของการเล่นเพลง ส่วน CPU/RAM เพิ่มขึ้นเฉพาะตอนมีเพลงเล่นอยู่ (ffmpeg transcode) ไม่ใช่ตลอดเวลาเหมือนโปรเซสหลัก ถ้าใช้งานเปิดเพลงไม่ต่อเนื่องทั้งวัน ผลกระทบต่อ credit ที่มีอยู่ใน plan จะไม่มาก

## Deploy

`Procfile` บ่งบอกว่าตั้งใจ deploy เป็น worker dyno (เช่น Heroku หรือ platform ที่รองรับ Procfile) — รันคำสั่งเดียวคือ `python bot.py` ไม่มี web process
