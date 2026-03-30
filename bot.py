import os
import fitz  # مكتبة PyMuPDF
import io
import gdown  # مكتبة التحميل من درايف
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- مكتبات السيرفر الوهمي ---
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------
# المتغيرات الأساسية
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"
FILE_ID = "1ca7Qsgq5FKtPNpx8mAyUFMD6NCvSQ5g7"

# ---------------------------------------------------------
# 1. كود السيرفر الوهمي
# ---------------------------------------------------------
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully on Render Free Tier!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run_dummy_server)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. دالة التحميل
# ---------------------------------------------------------
def download_pdf_from_drive():
    if not os.path.exists(PDF_FILE_NAME):
        print("جاري تحميل ملف الحلول من Google Drive...")
        url = f'https://drive.google.com/uc?id={FILE_ID}'
        gdown.download(url, PDF_FILE_NAME, quiet=False)

# ---------------------------------------------------------
# 3. دوال البوت التفاعلية
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك في بوت حلول كلمات كراش! 🧩\n\n"
        "أرسل لي **رقم المرحلة** (مثلاً: 150) وسأرسل لك صورتها.\n"
        "يمكنك استخدام الأزرار أسفل الصورة للتقليب إذا احتجت لذلك."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if not user_text.isdigit():
        await update.message.reply_text("❌ يرجى إرسال أرقام فقط. مثال: 150")
        return

    level_number = int(user_text)

    if not os.path.exists(PDF_FILE_NAME):
        await update.message.reply_text("❌ النظام يقوم حالياً بتهيئة الملف. جرب بعد دقيقة.")
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')

        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)

        # المعادلة الرياضية لتقريب الصفحة بناءً على الفروقات
        # كل 33 صفحة يوجد صفحة إضافية تقريباً
        estimated_page = level_number + int(level_number / 33)

        # التأكد من عدم تجاوز عدد صفحات الملف
        if estimated_page >= total_pages:
            estimated_page = total_pages - 1

        page = doc.load_page(estimated_page)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        photo_stream = io.BytesIO(img_bytes)
        
        # إنشاء أزرار التقليب التفاعلية
        keyboard = [
            [
                InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{estimated_page - 1}"),
                InlineKeyboardButton("التالي ➡️", callback_data=f"page_{estimated_page + 1}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_photo(
            photo=photo_stream, 
            caption=f"🔍 تقريب لنتيجة البحث عن المرحلة {level_number}\n(استخدم الأزرار للتقليب إذا لم تكن الصورة دقيقة)",
            reply_markup=reply_markup
        )
        doc.close()

    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ حدث خطأ فني أثناء استخراج الصورة.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغطات الأزرار لتحديث الصورة"""
    query = update.callback_query
    await query.answer()  # إخفاء دائرة التحميل في زر تليجرام
    
    # استخراج رقم الصفحة من الزر المكيوس عليه (مثال: page_52)
    data = query.data
    page_index = int(data.split("_")[1])

    try:
        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)
        
        # تجنب الأخطاء إذا تجاوزنا الصفحات
        if page_index < 0 or page_index >= total_pages:
            doc.close()
            return

        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        photo_stream = io.BytesIO(img_bytes)

        # تحديث الأزرار للصفحة الجديدة
        keyboard = [
            [
                InlineKeyboardButton("⬅️ السابق", callback_data=f"page_{page_index - 1}"),
                InlineKeyboardButton("التالي ➡️", callback_data=f"page_{page_index + 1}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # تغيير الصورة الحالية بدون إرسال رسالة جديدة
        await query.edit_message_media(
            media=InputMediaPhoto(media=photo_stream, caption="تم التقليب 🔄"),
            reply_markup=reply_markup
        )
        doc.close()
    except Exception as e:
        print(f"Button error: {e}")

# ---------------------------------------------------------
# 4. التشغيل الأساسي
# ---------------------------------------------------------
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على TELEGRAM_BOT_TOKEN.")
        return

    keep_alive()
    download_pdf_from_drive()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # إضافة معالج الأزرار (ضروري لعمل التقليب)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 البوت يعمل الآن وينتظر الرسائل...")
    app.run_polling()

if __name__ == "__main__":
    main()
