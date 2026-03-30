import os
import fitz  # PyMuPDF
import io
import gdown
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- مكتبات السيرفر الوهمي لإبقاء البوت حياً على Render ---
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------
# الإعدادات الأساسية
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"
FILE_ID = "1ca7Qsgq5FKtPNpx8mAyUFMD6NCvSQ5g7"

# ---------------------------------------------------------
# 1. السيرفر الوهمي (Keep Alive)
# ---------------------------------------------------------
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run_dummy_server)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. تحميل الملف
# ---------------------------------------------------------
def download_pdf():
    if not os.path.exists(PDF_FILE_NAME):
        url = f'https://drive.google.com/uc?id={FILE_ID}'
        gdown.download(url, PDF_FILE_NAME, quiet=False)

# ---------------------------------------------------------
# 3. منطق البوت التفاعلي
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً بك! أرسل رقم المرحلة (مثال: 150) وسأعطيك الحل.\n"
        "استخدم الأزرار ⬅️ ➡️ للتصحيح إذا كان هناك فرق في الصفحات."
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("الرجاء إرسال أرقام فقط.")
        return

    lvl = int(text)
    try:
        doc = fitz.open(PDF_FILE_NAME)
        # المعادلة التقريبية لتعويض النقص (صفحة إضافية كل 34 مرحلة)
        idx = lvl + int(lvl / 34)
        
        if idx >= len(doc): idx = len(doc) - 1

        page = doc.load_page(idx)
        pix = page.get_pixmap(dpi=150)
        img = io.BytesIO(pix.tobytes("png"))

        # أزرار التحكم
        kb = [[
            InlineKeyboardButton("⬅️ السابق", callback_data=f"p_{idx-1}"),
            InlineKeyboardButton("التالي ➡️", callback_data=f"p_{idx+1}")
        ]]
        
        await update.message.reply_photo(
            photo=img, 
            caption=f"حل تقريبي للمرحلة {lvl}\n(استخدم الأزرار للتنقل الدقيق)",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        doc.close()
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    idx = int(query.data.split("_")[1])
    try:
        doc = fitz.open(PDF_FILE_NAME)
        if idx < 0 or idx >= len(doc): return

        page = doc.load_page(idx)
        pix = page.get_pixmap(dpi=150)
        img = io.BytesIO(pix.tobytes("png"))

        kb = [[
            InlineKeyboardButton("⬅️ السابق", callback_data=f"p_{idx-1}"),
            InlineKeyboardButton("التالي ➡️", callback_data=f"p_{idx+1}")
        ]]

        await query.edit_message_media(
            media=InputMediaPhoto(media=img, caption=f"الصفحة الحالية: {idx}"),
            reply_markup=InlineKeyboardMarkup(kb)
        )
        doc.close()
    except: pass

# ---------------------------------------------------------
# 4. التشغيل
# ---------------------------------------------------------
def main():
    if not TOKEN: return
    keep_alive()
    download_pdf()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(button))
    
    app.run_polling()

if __name__ == "__main__":
    main()
