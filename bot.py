# -*- coding: utf-8 -*-
"""
Telegram Ko'p Tilli Tarjimon Boti
- Render.com, VPS va Kompyuterda 24/7 ishlashga moslashtirilgan.
- Matn va Rasmdagi yozuvlarni (OCR) tarjima qiladi.
- Admin ID: 7505810149 (barcha xabarlar faqat adminga keladi).
"""

import os
import json
import time
import base64
import logging
import threading
import urllib.request
import urllib.parse
from html import escape
from http.server import HTTPServer, BaseHTTPRequestHandler

# Log sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TranslatorBot")

# Bot ma'lumotlari
BOT_TOKEN = "9169461441:AAHSlO4BdY38FCmAGb1HzbkRs0mnnXM6RMs"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# SIZNING TELEGRAM ID RAQAMINGIZ
ADMIN_ID = 7505810149

# Qo'llab-quvvatlanadigan tillar ro'yxati
LANGUAGES = {
    "en": {"name": "Inglizcha", "flag": "🇺🇸"},
    "ru": {"name": "Ruscha", "flag": "🇷🇺"},
    "uz": {"name": "O'zbekcha", "flag": "🇺🇿"},
    "tr": {"name": "Turkcha", "flag": "🇹🇷"},
    "ar": {"name": "Arabcha", "flag": "🇸🇦"},
    "de": {"name": "Nemischa", "flag": "🇩🇪"},
    "fr": {"name": "Fransuzcha", "flag": "🇫🇷"},
    "zh-CN": {"name": "Xitoycha", "flag": "🇨🇳"},
    "ko": {"name": "Koreyscha", "flag": "🇰🇷"},
    "ja": {"name": "Yaponcha", "flag": "🇯🇵"},
    "es": {"name": "Ispancha", "flag": "🇪🇸"},
    "it": {"name": "Italyancha", "flag": "🇮🇹"},
}

user_settings = {}
user_last_text = {}


# --- Render.com Web Server (24/7 o'chib qolmasligi uchun) ---

class RenderHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Traduisbot serverda 24/7 faol ishlamoqda!")
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), RenderHealthHandler)
        logger.info(f"Render Web Server {port}-portda ishga tushdi.")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Web server xatosi: {e}")


# --- Telegram API bilan ishlash ---

def telegram_api_call(method: str, data: dict = None) -> dict:
    url = f"{API_URL}/{method}"
    headers = {"Content-Type": "application/json"}
    encoded_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Telegram API xatosi ({method}): {e}")
        return {"ok": False, "error": str(e)}


def send_message(chat_id: int, text: str, reply_markup: dict = None, reply_to_message_id: int = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    return telegram_api_call("sendMessage", payload)


def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api_call("editMessageText", payload)


def answer_callback_query(callback_query_id: str, text: str = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return telegram_api_call("answerCallbackQuery", payload)


def notify_admin(text: str):
    """Adminga xabarnoma yuborish"""
    if ADMIN_ID:
        try:
            send_message(ADMIN_ID, text)
        except Exception as e:
            logger.error(f"Adminga yuborishda xatolik: {e}")


# --- Tarjima qilish funksiyasi ---

def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    try:
        query = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join([part[0] for part in data[0] if part and part[0]])
            return translated
    except Exception as e:
        logger.error(f"Tarjima xatosi: {e}")
        return f"Tarjima qilib bo'lmadi: {str(e)}"


# --- Rasmdan matnni o'qib olish (OCR texnologiyasi) ---

def extract_text_from_photo(file_id: str) -> str:
    try:
        file_info = telegram_api_call("getFile", {"file_id": file_id})
        if not file_info.get("ok"):
            return ""
        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        
        req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            img_bytes = res.read()
            
        b64 = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode()
        
        ocr_payload = urllib.parse.urlencode({
            "apikey": "helloworld",
            "OCREngine": "2",
            "detectOrientation": "true",
            "base64Image": b64
        }).encode()
        
        ocr_req = urllib.request.Request(
            "https://api.ocr.space/parse/image",
            data=ocr_payload,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(ocr_req, timeout=25) as ocr_res:
            data = json.loads(ocr_res.read().decode("utf-8"))
            parsed_results = data.get("ParsedResults", [])
            if parsed_results:
                text = parsed_results[0].get("ParsedText", "").strip()
                return text
        return ""
    except Exception as e:
        logger.error(f"OCR xatoligi: {e}")
        return ""


# --- Inline tugmalar ---

def get_language_keyboard(prefix: str = "tr") -> dict:
    keyboard = []
    row = []
    for code, info in LANGUAGES.items():
        button = {
            "text": f"{info['flag']} {info['name']}",
            "callback_data": f"{prefix}:{code}"
        }
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    if prefix == "set":
        keyboard.append([{"text": "🔄 Har safar so'rash (standart)", "callback_data": "set:ask"}])
        
    return {"inline_keyboard": keyboard}


# --- Xabarlarni boshqarish ---

def handle_start(chat_id: int, user_info: dict):
    first_name = user_info.get("first_name", "Foydalanuvchi")
    welcome_text = (
        f"Assalomu alaykum, <b>{escape(first_name)}</b>! 👋\n\n"
        f"🤖 Men ko'p tilli <b>Tarjimon Botman</b>.\n\n"
        f"<b>Mening imkoniyatlarim:</b>\n"
        f"✍️ <b>Matn yuboring:</b> Qaysi tilda bo'lishidan qat'i nazar darhol tarjima qilaman.\n"
        f"📸 <b>Rasm yuboring:</b> Kitob, hujjat yoki biror yozuvni rasmga olib tashlasangiz, ichidagi matnni o'qib, o'sha tilga o'girib beraman!\n\n"
        f"⚙️ <b>Qo'shimcha buyruqlar:</b>\n"
        f"/setlang - Avtomatik tarjima tilini belgilash\n"
        f"/help - Yordam"
    )
    send_message(chat_id, welcome_text)
    
    if chat_id != ADMIN_ID:
        u_name = user_info.get("first_name", "")
        u_user = f"@{user_info.get('username')}" if user_info.get("username") else "mavjud emas"
        notify_admin(
            f"👤 <b>Yangi foydalanuvchi botni boshladi!</b>\n\n"
            f"<b>Ismi:</b> {escape(u_name)}\n"
            f"<b>Username:</b> {u_user}\n"
            f"<b>ID:</b> <code>{chat_id}</code>"
        )


def handle_help(chat_id: int):
    help_text = (
        f"ℹ️ <b>Qanday foydalaniladi?</b>\n\n"
        f"1. <b>Matn orqali:</b> Shunchaki so'z yoki gap yozing va tilni tanlang.\n"
        f"2. <b>Rasm orqali:</b> Matnli rasmni botga yuboring, bot o'zi matnni ajratib olib tarjima qiladi.\n"
        f"3. <b>Doimiy til:</b> Har safar tugma bosmaslik uchun /setlang orqali asosiy tilingizni belgilang."
    )
    send_message(chat_id, help_text)


def handle_setlang(chat_id: int):
    text = (
        "⚙️ <b>Doimiy tarjima tilini tanlang:</b>\n\n"
        "Tanlangan tilga barcha matnlaringiz to'g'ridan-to'g'ri o'giriladi:"
    )
    send_message(chat_id, text, reply_markup=get_language_keyboard(prefix="set"))


def handle_user_text(chat_id: int, message_id: int, text: str, user_info: dict):
    user_last_text[chat_id] = text
    
    if chat_id != ADMIN_ID:
        u_name = user_info.get("first_name", "Foydalanuvchi")
        u_user = f"@{user_info.get('username')}" if user_info.get("username") else "mavjud emas"
        notify_admin(
            f"📩 <b>Yangi foydalanuvchi matni!</b>\n\n"
            f"👤 <b>Kimdan:</b> {escape(u_name)} ({u_user})\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"📝 <b>Matn:</b>\n<i>\"{escape(text)}\"</i>"
        )
    
    settings = user_settings.get(chat_id, {})
    default_lang = settings.get("default_lang")
    
    if default_lang and default_lang in LANGUAGES:
        lang_info = LANGUAGES[default_lang]
        translated = translate_text(text, default_lang)
        reply_text = (
            f"<b>Asl matn:</b>\n<i>{escape(text)}</i>\n\n"
            f"{lang_info['flag']} <b>Tarjima ({lang_info['name']}):</b>\n"
            f"<code>{escape(translated)}</code>\n\n"
            f"<i>Boshqa tilga o'girish uchun tugmani bosing:</i>"
        )
        send_message(chat_id, reply_text, reply_markup=get_language_keyboard(prefix="tr"), reply_to_message_id=message_id)
    else:
        preview = text[:150] + ("..." if len(text) > 150 else "")
        prompt_text = (
            f"📥 <b>Matn qabul qilindi:</b>\n"
            f"<i>\"{escape(preview)}\"</i>\n\n"
            f"Qaysi tilga tarjima qilamiz? Tugmani tanlang: 👇"
        )
        send_message(chat_id, prompt_text, reply_markup=get_language_keyboard(prefix="tr"), reply_to_message_id=message_id)


def handle_user_photo(chat_id: int, message_id: int, file_id: str, user_info: dict):
    status_msg = send_message(chat_id, "🔍 <i>Rasm tekshirilmoqda va matn o'qilmoqda...</i>", reply_to_message_id=message_id)
    status_msg_id = status_msg.get("result", {}).get("message_id")
    
    extracted_text = extract_text_from_photo(file_id)
    
    if not extracted_text:
        fail_text = "⚠️ <b>Rasmda matn topilmadi yoki u yetarlicha aniq emas.</b>\nIltimos, yozuv aniq va yorug' ko'ringan rasmni yuboring."
        if status_msg_id:
            edit_message_text(chat_id, status_msg_id, fail_text)
        else:
            send_message(chat_id, fail_text, reply_to_message_id=message_id)
        return

    user_last_text[chat_id] = extracted_text
    
    if chat_id != ADMIN_ID:
        u_name = user_info.get("first_name", "Foydalanuvchi")
        u_user = f"@{user_info.get('username')}" if user_info.get("username") else "mavjud emas"
        notify_admin(
            f"📸 <b>Yangi rasm yuborildi!</b>\n\n"
            f"👤 <b>Kimdan:</b> {escape(u_name)} ({u_user})\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"📝 <b>Rasmdan o'qilgan matn:</b>\n"
            f"<i>\"{escape(extracted_text[:400])}\"</i>"
        )
        
    settings = user_settings.get(chat_id, {})
    default_lang = settings.get("default_lang")
    
    if default_lang and default_lang in LANGUAGES:
        lang_info = LANGUAGES[default_lang]
        translated = translate_text(extracted_text, default_lang)
        reply_text = (
            f"📸 <b>Rasmdan o'qilgan matn:</b>\n<i>{escape(extracted_text)}</i>\n\n"
            f"{lang_info['flag']} <b>Tarjima ({lang_info['name']}):</b>\n"
            f"<code>{escape(translated)}</code>\n\n"
            f"<i>Boshqa tilga o'girish uchun tugmani bosing:</i>"
        )
        if status_msg_id:
            edit_message_text(chat_id, status_msg_id, reply_text, reply_markup=get_language_keyboard(prefix="tr"))
        else:
            send_message(chat_id, reply_text, reply_markup=get_language_keyboard(prefix="tr"), reply_to_message_id=message_id)
    else:
        preview = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
        prompt_text = (
            f"📸 <b>Rasmdan matn o'qildi:</b>\n"
            f"<i>\"{escape(preview)}\"</i>\n\n"
            f"Qaysi tilga tarjima qilamiz? Tugmani tanlang: 👇"
        )
        if status_msg_id:
            edit_message_text(chat_id, status_msg_id, prompt_text, reply_markup=get_language_keyboard(prefix="tr"))
        else:
            send_message(chat_id, prompt_text, reply_markup=get_language_keyboard(prefix="tr"), reply_to_message_id=message_id)


def handle_callback_query(callback_query: dict):
    cb_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    message_id = message.get("message_id")
    from_user = callback_query.get("from", {})
    u_id = from_user.get("id", chat_id)
    
    if not chat_id:
        return
        
    if data.startswith("set:"):
        code = data.split(":")[1]
        if code == "ask":
            user_settings.setdefault(chat_id, {})["default_lang"] = None
            answer_callback_query(cb_id, "Rejim: Har safar til so'raladi.")
            edit_message_text(chat_id, message_id, "✅ Endi har bir matn yuborganingizda til tanlash taklif etiladi.")
        elif code in LANGUAGES:
            user_settings.setdefault(chat_id, {})["default_lang"] = code
            lang_name = LANGUAGES[code]["name"]
            answer_callback_query(cb_id, f"Asosiy til: {lang_name}")
            edit_message_text(
                chat_id,
                message_id,
                f"✅ Matnlaringiz endi avtomatik <b>{lang_name}</b> ({LANGUAGES[code]['flag']}) tiliga o'giriladi.\n\n"
                f"O'zgartirish: /setlang"
            )
        return

    if data.startswith("tr:"):
        target_lang = data.split(":")[1]
        if target_lang not in LANGUAGES:
            answer_callback_query(cb_id, "Noma'lum til")
            return
            
        lang_info = LANGUAGES[target_lang]
        original_text = ""
        reply_to = message.get("reply_to_message")
        if reply_to and reply_to.get("text"):
            original_text = reply_to.get("text")
        elif chat_id in user_last_text:
            original_text = user_last_text[chat_id]
            
        if not original_text:
            answer_callback_query(cb_id, "Matn topilmadi. Qaytadan yuboring.")
            return

        answer_callback_query(cb_id, f"Tarjima: {lang_info['name']}...")
        translated = translate_text(original_text, target_lang)
        
        result_text = (
            f"<b>Asl matn:</b>\n<i>{escape(original_text)}</i>\n\n"
            f"{lang_info['flag']} <b>Tarjima ({lang_info['name']}):</b>\n"
            f"<code>{escape(translated)}</code>\n\n"
            f"<i>Boshqa tilga ham o'girish mumkin:</i>"
        )
        edit_message_text(chat_id, message_id, result_text, reply_markup=get_language_keyboard(prefix="tr"))
        
        if u_id != ADMIN_ID:
            u_name = from_user.get("first_name", "Foydalanuvchi")
            u_user = f"@{from_user.get('username')}" if from_user.get("username") else "mavjud emas"
            notify_admin(
                f"🔄 <b>Foydalanuvchi tarjima qildi:</b>\n\n"
                f"👤 <b>Kim:</b> {escape(u_name)} ({u_user})\n"
                f"🆔 <b>ID:</b> <code>{u_id}</code>\n"
                f"🌐 <b>Tanlagan tili:</b> {lang_info['flag']} {lang_info['name']}\n"
                f"📝 <b>Asl matn:</b>\n<i>\"{escape(original_text)}\"</i>\n\n"
                f"✅ <b>Natija:</b>\n<code>{escape(translated)}</code>"
            )


# --- Botni ishga tushirish (Long Polling) ---

def run_bot():
    logger.info("Bot ishga tushirilmoqda...")
    me = telegram_api_call("getMe")
    if not me.get("ok"):
        print("Xatolik: Bot tokeni noto'g'ri!")
        return
        
    bot_username = me.get("result", {}).get("username", "Noma'lum")
    print(f"==================================================")
    print(f" Bot faol! Telegramda yozishingiz mumkin: @{bot_username}")
    print(f" Funksiyalar: Matn + Rasm (OCR) tarjimasi + Render 24/7")
    print(f" Admin ID: {ADMIN_ID} (barcha xabarlar sizga keladi)")
    print(f"==================================================")

    # Render serverini orqa fonda yoqish
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    offset = 0
    while True:
        try:
            updates_res = telegram_api_call("getUpdates", {"offset": offset, "timeout": 20})
            if not updates_res.get("ok"):
                time.sleep(2)
                continue
                
            updates = updates_res.get("result", [])
            for update in updates:
                offset = update.get("update_id", 0) + 1
                
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg.get("chat", {}).get("id")
                    from_user = msg.get("from", {})
                    message_id = msg.get("message_id")
                    
                    if not chat_id:
                        continue
                    
                    if "photo" in msg:
                        file_id = msg["photo"][-1]["file_id"]
                        handle_user_photo(chat_id, message_id, file_id, from_user)
                    elif "text" in msg:
                        text = msg["text"]
                        if text == "/start":
                            handle_start(chat_id, from_user)
                        elif text == "/help":
                            handle_help(chat_id)
                        elif text == "/setlang":
                            handle_setlang(chat_id)
                        else:
                            handle_user_text(chat_id, message_id, text, from_user)
                        
                elif "callback_query" in update:
                    handle_callback_query(update["callback_query"])
                    
        except KeyboardInterrupt:
            print("Bot to'xtatildi.")
            break
        except Exception as e:
            time.sleep(2)


if __name__ == "__main__":
    run_bot()
