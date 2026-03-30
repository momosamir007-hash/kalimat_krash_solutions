import os
import fitz  # مكتبة PyMuPDF
import io
import gdown  # مكتبة التحميل من درايف
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

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
# 1. كود السيرفر الوهمي لـ Render (للباقة المجانية)
# ---------------------------------------------------------
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully on Render Free Tier!")

def run_dummy_server():
    # Render يعطينا بورت ديناميكي، إذا لم نجده نستخدم 10000
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def keep_alive():
    """تشغيل السيرفر في مسار (Thread) منفصل كي لا يوقف البوت"""
    t = Thread(target=run_dummy_server)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. دالة التحميل من جوجل درايف
# ---------------------------------------------------------
def download_pdf_from_drive():
    if not os.path.exists(PDF_FILE_NAME):
        print("جاري تحميل ملف الحلول من Google Drive... الرجاء الانتظار.")
        url = f'https://drive.google.com/uc?id={FILE_ID}'
        gdown.download(url, PDF_FILE_NAME, quiet=False)
        print("✅ تم تحميل ملف الـ PDF بنجاح!")
    else:
        print("✅ ملف الـ PDF موجود بالفعل.")

# ---------------------------------------------------------
# 3. دوال البوت
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "مرحباً بك في بوت حلول كلمات كراش! 🧩\n\n"
        "أرسل لي **رقم المرحلة** (مثلاً: 150) وسأرسل لك صورتها فوراً."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if not user_text.isdigit():
        await update.message.reply_text("❌ يرجى إرسال أرقام فقط. مثال: 150")
        return

    level_number = int(user_text)

    if not os.path.exists(PDF_FILE_NAME):
        await update.message.reply_text("❌ عذراً، النظام يقوم حالياً بتهيئة ملف الحلول. يرجى المحاولة بعد دقيقة.")
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')

        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)

        if level_number < 2 or level_number >= total_pages:
            await update.message.reply_text(f"❌ عذراً، المرحلة رقم {level_number} غير موجودة.")
            doc.close()
            return

        page = doc.load_page(level_number)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        photo_stream = io.BytesIO(img_bytes)
        
        await update.message.reply_photo(
            photo=photo_stream, 
            caption=f"✅ حل المرحلة {level_number}"
        )
        doc.close()

    except Exception as e:
        print(f"Error processing level {level_number}: {e}")
        await update.message.reply_text("❌ حدث خطأ فني أثناء استخراج الصورة. يرجى المحاولة لاحقاً.")

# ---------------------------------------------------------
# 4. التشغيل الأساسي
# ---------------------------------------------------------
def main():
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على TELEGRAM_BOT_TOKEN.")
        return

    # أ. تشغيل السيرفر الوهمي أولاً
    keep_alive()

    # ب. تحميل الملف من درايف
    download_pdf_from_drive()

    # ج. تشغيل البوت
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 البوت يعمل الآن وينتظر الرسائل...")
    app.run_polling()

if __name__ == "__main__":
    main()
