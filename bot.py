#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║   بوت حلول كلمات كراش - النسخة النهائية v3.0    ║
║   Kalimat Krash Solutions Bot - Final Edition    ║
╚══════════════════════════════════════════════════╝
"""

import os
import sys
import fitz  # PyMuPDF
import io
import json
import gdown
import logging
import time
import signal
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Thread, Lock
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# ═══════════════════════════════════════════════════
# إعداد نظام التسجيل (Logging)
# ═══════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)
logger = logging.getLogger("KrashBot")

# ═══════════════════════════════════════════════════
# الإعدادات الأساسية
# ═══════════════════════════════════════════════════
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"
FILE_ID = "1ca7Qsgq5FKtPNpx8mAyUFMD6NCvSQ5g7"

# ✅ ضع الآيدي كرقم أو اضبطه من متغيرات البيئة
#ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
ADMIN_ID = 769848965
# ═══════════════════════════════════════════════════
# الثوابت
# ═══════════════════════════════════════════════════
USERS_DB_FILE = "users_db.json"
RATE_LIMIT_WINDOW = 60          # نافذة الحد (ثانية)
MAX_REQUESTS_PER_WINDOW = 20    # الحد الأقصى للطلبات
MAX_LEVEL = 6000                # أقصى مرحلة مدعومة
PAGE_CACHE_SIZE = 100           # عدد الصفحات المخزنة مؤقتاً
BOT_VERSION = "3.0"
START_TIME = datetime.now()


# ═══════════════════════════════════════════════════
# 1. قاعدة بيانات المستخدمين (JSON)
# ═══════════════════════════════════════════════════
class UserDatabase:
    """نظام بسيط لتخزين بيانات المستخدمين"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lock = Lock()
        self.data = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"خطأ تحميل قاعدة البيانات: {e}")
        return {"users": {}, "total_queries": 0}

    def _save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ حفظ قاعدة البيانات: {e}")

    def add_user(self, user) -> bool:
        """إضافة/تحديث مستخدم. يرجع True إذا كان جديداً"""
        with self.lock:
            uid = str(user.id)
            is_new = uid not in self.data["users"]

            self.data["users"][uid] = {
                "first_name": user.first_name or "",
                "username": user.username or "",
                "last_seen": datetime.now().isoformat(),
                "join_date": (
                    self.data["users"].get(uid, {}).get(
                        "join_date", datetime.now().isoformat()
                    )
                ),
                "queries": self.data["users"].get(uid, {}).get("queries", 0),
            }
            self._save()
            return is_new

    def increment_query(self, user_id: int):
        with self.lock:
            uid = str(user_id)
            if uid in self.data["users"]:
                self.data["users"][uid]["queries"] = (
                    self.data["users"][uid].get("queries", 0) + 1
                )
                self.data["total_queries"] = (
                    self.data.get("total_queries", 0) + 1
                )
                self._save()

    @property
    def total_users(self) -> int:
        return len(self.data.get("users", {}))

    @property
    def total_queries(self) -> int:
        return self.data.get("total_queries", 0)

    def get_all_user_ids(self) -> list:
        return [int(uid) for uid in self.data.get("users", {}).keys()]

    def get_top_users(self, limit=10) -> list:
        users = self.data.get("users", {})
        sorted_users = sorted(
            users.items(),
            key=lambda x: x[1].get("queries", 0),
            reverse=True
        )
        return sorted_users[:limit]

    def get_today_users(self) -> int:
        today = datetime.now().date().isoformat()
        count = 0
        for u in self.data.get("users", {}).values():
            if u.get("last_seen", "").startswith(today):
                count += 1
        return count


# ═══════════════════════════════════════════════════
# 2. نظام الحماية من السبام (Rate Limiter)
# ═══════════════════════════════════════════════════
class RateLimiter:
    """يمنع المستخدم من إرسال طلبات كثيرة في وقت قصير"""

    def __init__(self, window: int, max_requests: int):
        self.window = window
        self.max_requests = max_requests
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, user_id: int) -> bool:
        with self.lock:
            now = time.time()
            # تنظيف الطلبات القديمة
            self.requests[user_id] = [
                t for t in self.requests[user_id]
                if now - t < self.window
            ]
            if len(self.requests[user_id]) >= self.max_requests:
                return False
            self.requests[user_id].append(now)
            return True

    def remaining(self, user_id: int) -> int:
        now = time.time()
        active = [
            t for t in self.requests.get(user_id, [])
            if now - t < self.window
        ]
        return max(0, self.max_requests - len(active))


# ═══════════════════════════════════════════════════
# 3. نظام كاش الصفحات (Page Cache)
# ═══════════════════════════════════════════════════
class PageCache:
    """تخزين مؤقت للصفحات لتسريع الاستجابة"""

    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.access_order = []
        self.lock = Lock()

    def get(self, page_idx: int) -> bytes | None:
        with self.lock:
            if page_idx in self.cache:
                # نقل للأعلى (LRU)
                if page_idx in self.access_order:
                    self.access_order.remove(page_idx)
                self.access_order.append(page_idx)
                return self.cache[page_idx]
        return None

    def put(self, page_idx: int, data: bytes):
        with self.lock:
            if len(self.cache) >= self.max_size:
                # حذف الأقدم استخداماً
                oldest = self.access_order.pop(0)
                del self.cache[oldest]
            self.cache[page_idx] = data
            self.access_order.append(page_idx)

    def clear(self):
        with self.lock:
            self.cache.clear()
            self.access_order.clear()


# ═══════════════════════════════════════════════════
# 4. تهيئة الأنظمة
# ═══════════════════════════════════════════════════
db = UserDatabase(USERS_DB_FILE)
limiter = RateLimiter(RATE_LIMIT_WINDOW, MAX_REQUESTS_PER_WINDOW)
cache = PageCache(PAGE_CACHE_SIZE)
TOTAL_PDF_PAGES = 0


# ═══════════════════════════════════════════════════
# 5. السيرفر الوهمي (Keep Alive for Render)
# ═══════════════════════════════════════════════════
class HealthHandler(BaseHTTPRequestHandler):
    """سيرفر صحة بسيط مع معلومات"""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        uptime = str(datetime.now() - START_TIME).split(".")[0]
        response = json.dumps({
            "status": "running",
            "bot": "Kalimat Krash Bot",
            "version": BOT_VERSION,
            "uptime": uptime,
            "users": db.total_users,
            "queries": db.total_queries,
        }, ensure_ascii=False)

        self.wfile.write(response.encode("utf-8"))

    def log_message(self, format, *args):
        # إخفاء سجلات HTTP لتنظيف الـ logs
        pass


def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"🌐 سيرفر الصحة يعمل على المنفذ {port}")
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()


# ═══════════════════════════════════════════════════
# 6. تحميل ملف PDF
# ═══════════════════════════════════════════════════
def download_pdf() -> bool:
    """تحميل PDF من Google Drive مع إعادة المحاولة"""
    global TOTAL_PDF_PAGES

    if os.path.exists(PDF_FILE_NAME):
        try:
            doc = fitz.open(PDF_FILE_NAME)
            TOTAL_PDF_PAGES = len(doc)
            doc.close()
            logger.info(
                f"📄 الملف موجود مسبقاً: {TOTAL_PDF_PAGES} صفحة"
            )
            return True
        except Exception:
            logger.warning("⚠️ الملف تالف، جاري إعادة التحميل...")
            os.remove(PDF_FILE_NAME)

    for attempt in range(3):
        try:
            logger.info(
                f"📥 محاولة تحميل #{attempt + 1}..."
            )
            url = f"https://drive.google.com/uc?id={FILE_ID}"
            gdown.download(url, PDF_FILE_NAME, quiet=False)

            doc = fitz.open(PDF_FILE_NAME)
            TOTAL_PDF_PAGES = len(doc)
            doc.close()
            logger.info(
                f"✅ تم التحميل بنجاح: {TOTAL_PDF_PAGES} صفحة"
            )
            return True

        except Exception as e:
            logger.error(f"❌ فشل التحميل #{attempt + 1}: {e}")
            if os.path.exists(PDF_FILE_NAME):
                os.remove(PDF_FILE_NAME)
            time.sleep(3)

    logger.critical("🚨 فشل تحميل الملف بعد 3 محاولات!")
    return False


# ═══════════════════════════════════════════════════
# 7. دوال مساعدة
# ═══════════════════════════════════════════════════
def get_page_image(page_idx: int) -> io.BytesIO | None:
    """جلب صورة صفحة مع الكاش"""
    global TOTAL_PDF_PAGES

    if page_idx < 0 or page_idx >= TOTAL_PDF_PAGES:
        return None

    # محاولة الجلب من الكاش
    cached = cache.get(page_idx)
    if cached:
        return io.BytesIO(cached)

    try:
        doc = fitz.open(PDF_FILE_NAME)
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        doc.close()

        # حفظ في الكاش
        cache.put(page_idx, img_bytes)
        return io.BytesIO(img_bytes)

    except Exception as e:
        logger.error(f"خطأ جلب الصفحة {page_idx}: {e}")
        return None


def level_to_page(level: int) -> int:
    """تحويل رقم المرحلة إلى رقم الصفحة"""
    # المعادلة المحسّنة: كل 34 مرحلة يوجد فاصل
    idx = level + (level // 34)
    return min(idx, TOTAL_PDF_PAGES - 1)


def build_nav_keyboard(
    current_idx: int,
    level: int | None = None
) -> InlineKeyboardMarkup:
    """بناء لوحة أزرار التنقل"""
    buttons = []

    # صف التنقل الأساسي
    nav_row = []
    if current_idx > 0:
        nav_row.append(
            InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"nav_{current_idx - 1}"
            )
        )

    nav_row.append(
        InlineKeyboardButton(
            f"📄 {current_idx + 1}/{TOTAL_PDF_PAGES}",
            callback_data="page_info"
        )
    )

    if current_idx < TOTAL_PDF_PAGES - 1:
        nav_row.append(
            InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"nav_{current_idx + 1}"
            )
        )
    buttons.append(nav_row)

    # صف القفز السريع
    jump_row = []
    if current_idx >= 10:
        jump_row.append(
            InlineKeyboardButton(
                "⏪ -10",
                callback_data=f"nav_{current_idx - 10}"
            )
        )
    if current_idx >= 5:
        jump_row.append(
            InlineKeyboardButton(
                "◀️ -5",
                callback_data=f"nav_{current_idx - 5}"
            )
        )
    if current_idx + 5 < TOTAL_PDF_PAGES:
        jump_row.append(
            InlineKeyboardButton(
                "+5 ▶️",
                callback_data=f"nav_{current_idx + 5}"
            )
        )
    if current_idx + 10 < TOTAL_PDF_PAGES:
        jump_row.append(
            InlineKeyboardButton(
                "+10 ⏩",
                callback_data=f"nav_{current_idx + 10}"
            )
        )

    if jump_row:
        buttons.append(jump_row)

    return InlineKeyboardMarkup(buttons)


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


# ═══════════════════════════════════════════════════
# 8. أوامر البوت الأساسية
# ═══════════════════════════════════════════════════
async def cmd_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """أمر البداية /start"""
    user = update.effective_user
    is_new = db.add_user(user)

    welcome = (
        f"مرحباً <b>{user.first_name}</b>! 🧩✨\n"
        f"{'🆕 أهلاً بك كمستخدم جديد!' if is_new else '👋 أهلاً بعودتك!'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>بوت حلول كلمات كراش</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>طريقة الاستخدام:</b>\n"
        "أرسل <b>رقم المرحلة</b> فقط وسيظهر لك الحل\n"
        "مثال: <code>150</code>\n\n"
        "🔧 <b>الأوامر المتاحة:</b>\n"
        "  /start  ➜ الصفحة الرئيسية\n"
        "  /help   ➜ المساعدة التفصيلية\n"
        "  /about  ➜ معلومات البوت\n\n"
        "🎮 <b>المميزات:</b>\n"
        "  • حلول لآلاف المراحل 📚\n"
        "  • أزرار تنقل ذكية ⬅️➡️\n"
        "  • قفز سريع ±5 و ±10 صفحات ⏩\n"
        "  • استجابة فورية ⚡\n\n"
        f"📊 عدد الصفحات المتاحة: <b>{TOTAL_PDF_PAGES}</b>"
    )

    await update.message.reply_text(welcome, parse_mode="HTML")

    # إشعار المدير بالمستخدم الجديد
    if is_new and is_admin(ADMIN_ID):
        try:
            notif = (
                "🔔 <b>مستخدم جديد!</b>\n"
                "━━━━━━━━━━━━━━\n"
                f"👤 الاسم: <b>{user.first_name}</b>\n"
                f"🆔 المعرف: @{user.username or 'بدون'}\n"
                f"🔢 الآيدي: <code>{user.id}</code>\n"
                f"📊 إجمالي المستخدمين: <b>{db.total_users}</b>"
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=notif,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"فشل إشعار المدير: {e}")


async def cmd_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """أمر المساعدة /help"""
    help_text = (
        "📖 <b>دليل الاستخدام الشامل</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ <b>البحث عن حل مرحلة:</b>\n"
        "   أرسل رقم المرحلة مباشرة\n"
        "   مثال: <code>250</code>\n\n"
        "2️⃣ <b>التنقل بين الصفحات:</b>\n"
        "   ⬅️➡️  للتنقل صفحة بصفحة\n"
        "   ◀️▶️  للقفز 5 صفحات\n"
        "   ⏪⏩  للقفز 10 صفحات\n\n"
        "3️⃣ <b>نصائح مهمة:</b>\n"
        "   • إذا لم يكن الحل دقيقاً، استخدم\n"
        "     أزرار التنقل للوصول للصفحة الصحيحة\n"
        "   • الأرقام فقط مقبولة (بدون حروف)\n"
        f"   • المراحل المدعومة: 1 إلى {MAX_LEVEL}\n\n"
        "❓ <b>مشكلة؟</b>\n"
        "   تواصل مع المطور عبر أمر /about"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def cmd_about(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """أمر معلومات البوت /about"""
    uptime = str(datetime.now() - START_TIME).split(".")[0]

    about = (
        "🤖 <b>معلومات البوت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 الاسم: بوت حلول كلمات كراش\n"
        f"📦 الإصدار: v{BOT_VERSION}\n"
        f"⏱ مدة التشغيل: {uptime}\n"
        f"👥 المستخدمون: {db.total_users}\n"
        f"🔍 إجمالي الاستعلامات: {db.total_queries}\n"
        f"📄 عدد الصفحات: {TOTAL_PDF_PAGES}\n\n"
        "⚙️ مبني بـ Python + PyMuPDF\n"
        "🏠 مستضاف على Render"
    )
    await update.message.reply_text(about, parse_mode="HTML")


# ═══════════════════════════════════════════════════
# 9. معالجة رسائل المستخدم (طلب المراحل)
# ═══════════════════════════════════════════════════
async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """معالجة الرسائل النصية (أرقام المراحل)"""
    user = update.effective_user
    text = update.message.text.strip()

    # تسجيل المستخدم
    db.add_user(user)

    # ── التحقق من السبام ──
    if not limiter.is_allowed(user.id):
        remaining = limiter.remaining(user.id)
        await update.message.reply_text(
            "⏳ أنت ترسل طلبات بسرعة كبيرة!\n"
            f"انتظر قليلاً ثم حاول مجدداً.\n"
            f"المتبقي: {remaining}/{MAX_REQUESTS_PER_WINDOW}"
        )
        logger.warning(f"⚠️ سبام من [{user.first_name}] ({user.id})")
        return

    # ── التحقق من الرقم ──
    if not text.isdigit():
        await update.message.reply_text(
            "❌ <b>أرسل رقماً فقط!</b>\n"
            "مثال: <code>150</code>\n\n"
            "💡 للمساعدة أرسل /help",
            parse_mode="HTML"
        )
        return

    level = int(text)

    if level < 1:
        await update.message.reply_text(
            "❌ رقم المرحلة يجب أن يكون <b>1</b> أو أكثر.",
            parse_mode="HTML"
        )
        return

    if level > MAX_LEVEL:
        await update.message.reply_text(
            f"❌ أقصى مرحلة مدعومة: <b>{MAX_LEVEL}</b>",
            parse_mode="HTML"
        )
        return

    # ── التحقق من وجود الملف ──
    if not os.path.exists(PDF_FILE_NAME):
        await update.message.reply_text(
            "⚠️ ملف الحلول غير متوفر حالياً.\n"
            "جاري إعادة التحميل... حاول بعد دقيقة."
        )
        download_pdf()
        return

    # ── حساب رقم الصفحة ──
    page_idx = level_to_page(level)

    logger.info(
        f"🔍 [{user.first_name}] ({user.id}) "
        f"→ مرحلة {level} → صفحة {page_idx}"
    )

    # ── إرسال رسالة انتظار ──
    wait_msg = await update.message.reply_text("⏳ جاري جلب الحل...")

    # ── جلب الصورة ──
    img = get_page_image(page_idx)
    if img is None:
        await wait_msg.edit_text(
            "❌ تعذر جلب الصفحة. الرقم قد يكون خارج النطاق."
        )
        return

    # ── تسجيل الاستعلام ──
    db.increment_query(user.id)

    # ── بناء لوحة الأزرار ──
    keyboard = build_nav_keyboard(page_idx, level)

    # ── إرسال الصورة ──
    caption = (
        f"🧩 <b>المرحلة {level}</b>\n"
        f"📄 الصفحة: {page_idx + 1} / {TOTAL_PDF_PAGES}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💡 إذا لم يكن الحل دقيقاً، استخدم\n"
        f"أزرار التنقل ⬅️➡️ للتعديل"
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    await update.message.reply_photo(
        photo=img,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ═══════════════════════════════════════════════════
# 10. معالجة أزرار التنقل
# ═══════════════════════════════════════════════════
async def handle_navigation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """معالجة ضغطات أزرار التنقل"""
    query = update.callback_query
    await query.answer()

    data = query.data

    # زر معلومات الصفحة (لا يفعل شيئاً)
    if data == "page_info":
        await query.answer(
            f"📄 الصفحة الحالية من أصل {TOTAL_PDF_PAGES}",
            show_alert=False
        )
        return

    if not data.startswith("nav_"):
        return

    try:
        page_idx = int(data.split("_")[1])
    except (ValueError, IndexError):
        return

    # التحقق من الحدود
    if page_idx < 0 or page_idx >= TOTAL_PDF_PAGES:
        await query.answer("🚫 لا توجد صفحة في هذا الاتجاه!", show_alert=True)
        return

    # جلب الصورة
    img = get_page_image(page_idx)
    if img is None:
        await query.answer("❌ خطأ في جلب الصفحة", show_alert=True)
        return

    # بناء الأزرار الجديدة
    keyboard = build_nav_keyboard(page_idx)

    caption = (
        f"📄 <b>الصفحة {page_idx + 1}</b> / {TOTAL_PDF_PAGES}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💡 استخدم الأزرار للتنقل"
    )

    try:
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=img,
                caption=caption,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"خطأ تعديل الرسالة: {e}")


# ═══════════════════════════════════════════════════
# 11. أوامر المدير (Admin Commands)
# ═══════════════════════════════════════════════════
async def cmd_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """إحصائيات البوت (للمدير فقط) /stats"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر للمدير فقط.")
        return

    uptime = str(datetime.now() - START_TIME).split(".")[0]
    today_users = db.get_today_users()
    top = db.get_top_users(5)

    # قائمة أنشط المستخدمين
    top_text = ""
    for i, (uid, info) in enumerate(top, 1):
        name = info.get("first_name", "مجهول")
        queries = info.get("queries", 0)
        top_text += f"  {i}. {name} — {queries} طلب\n"

    stats = (
        "📊 <b>إحصائيات البوت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 إجمالي المستخدمين: <b>{db.total_users}</b>\n"
        f"📅 نشطون اليوم: <b>{today_users}</b>\n"
        f"🔍 إجمالي الاستعلامات: <b>{db.total_queries}</b>\n"
        f"📄 صفحات PDF: <b>{TOTAL_PDF_PAGES}</b>\n"
        f"⏱ مدة التشغيل: <b>{uptime}</b>\n"
        f"💾 حجم الكاش: <b>{len(cache.cache)}</b> صفحة\n\n"
        f"🏆 <b>أنشط المستخدمين:</b>\n{top_text}"
    )

    await update.message.reply_text(stats, parse_mode="HTML")


async def cmd_broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """إذاعة رسالة لجميع المستخدمين /broadcast"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 هذا الأمر للمدير فقط.")
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>الاستخدام:</b>\n"
            "<code>/broadcast نص الرسالة</code>",
            parse_mode="HTML"
        )
        return

    message = " ".join(context.args)
    user_ids = db.get_all_user_ids()

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(
        f"📤 جاري الإرسال لـ {len(user_ids)} مستخدم..."
    )

    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 <b>رسالة من الإدارة:</b>\n\n{message}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

        # تأخير لتجنب حدود تيليجرام
        if sent % 25 == 0:
            await status_msg.edit_text(
                f"📤 جاري الإرسال... ({sent}/{len(user_ids)})"
            )
            time.sleep(1)

    await status_msg.edit_text(
        f"✅ <b>اكتملت الإذاعة!</b>\n"
        f"📨 نجح: {sent}\n"
        f"❌ فشل: {failed}",
        parse_mode="HTML"
    )


async def cmd_clearcache(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """مسح الكاش /clearcache"""
    if not is_admin(update.effective_user.id):
        return

    old_size = len(cache.cache)
    cache.clear()
    await update.message.reply_text(
        f"🗑 تم مسح الكاش ({old_size} صفحة)"
    )


async def cmd_reload(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """إعادة تحميل PDF /reload"""
    if not is_admin(update.effective_user.id):
        return

    msg = await update.message.reply_text("🔄 جاري إعادة تحميل الملف...")

    if os.path.exists(PDF_FILE_NAME):
        os.remove(PDF_FILE_NAME)
    cache.clear()

    success = download_pdf()
    if success:
        await msg.edit_text(
            f"✅ تم إعادة التحميل! ({TOTAL_PDF_PAGES} صفحة)"
        )
    else:
        await msg.edit_text("❌ فشل إعادة التحميل!")


# ═══════════════════════════════════════════════════
# 12. معالجة الأخطاء العامة
# ═══════════════════════════════════════════════════
async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    """معالج الأخطاء العام"""
    logger.error(f"❌ خطأ: {context.error}", exc_info=context.error)

    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ غير متوقع.\nحاول مرة أخرى لاحقاً."
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════
# 13. إعداد قائمة الأوامر
# ═══════════════════════════════════════════════════
async def setup_commands(app: Application):
    """تعيين قائمة الأوامر في واجهة تيليجرام"""
    commands = [
        BotCommand("start", "🏠 الصفحة الرئيسية"),
        BotCommand("help", "📖 المساعدة"),
        BotCommand("about", "ℹ️ معلومات البوت"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ تم تعيين قائمة الأوامر")


# ═══════════════════════════════════════════════════
# 14. التشغيل الرئيسي
# ═══════════════════════════════════════════════════
def main():
    # ── التحقق من التوكن ──
    if not TOKEN:
        logger.critical("🚨 لم يتم تعيين TELEGRAM_BOT_TOKEN!")
        sys.exit(1)

    if ADMIN_ID == 0:
        logger.warning(
            "⚠️ لم يتم تعيين ADMIN_ID - "
            "لن تعمل أوامر المدير والإشعارات"
        )

    # ── تشغيل سيرفر الصحة ──
    keep_alive()

    # ── تحميل PDF ──
    if not download_pdf():
        logger.critical("🚨 فشل تحميل ملف PDF!")
        sys.exit(1)

    # ── بناء التطبيق ──
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    # ── تسجيل المعالجات ──
    # أوامر المستخدم
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("about", cmd_about))

    # أوامر المدير
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("clearcache", cmd_clearcache))
    app.add_handler(CommandHandler("reload", cmd_reload))

    # الرسائل النصية (أرقام المراحل)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    # أزرار التنقل
    app.add_handler(CallbackQueryHandler(handle_navigation))

    # معالج الأخطاء
    app.add_error_handler(error_handler)

    # ── إعداد الأوامر بعد التشغيل ──
    app.post_init = setup_commands

    # ── الانطلاق! ──
    logger.info("=" * 50)
    logger.info("🚀 بوت كلمات كراش يعمل الآن!")
    logger.info(f"📦 الإصدار: v{BOT_VERSION}")
    logger.info(f"📄 الصفحات: {TOTAL_PDF_PAGES}")
    logger.info(f"👑 المدير: {ADMIN_ID or 'غير محدد'}")
    logger.info("=" * 50)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
