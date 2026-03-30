import os
import fitz  # مكتبة PyMuPDF
import io
import gdown  # مكتبة التحميل من درايف
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------------------------------------------------
# المتغيرات الأساسية (تم إضافة رابطك الخاص)
# ---------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"
FILE_ID = "1ca7Qsgq5FKtPNpx8mAyUFMD6NCvSQ5g7"

# ---------------------------------------------------------
# دالة التحميل من جوجل درايف
# ---------------------------------------------------------
def download_pdf_from_drive():
    """تحميل الملف من جوجل درايف إذا لم يكن موجوداً في الخادم"""
    if not os.path.exists(PDF_FILE_NAME):
        print("جاري تحميل ملف الحلول من Google Drive... الرجاء الانتظار.")
        url = f'https://drive.google.com/uc?id={FILE_ID}'
        gdown.download(url, PDF_FILE_NAME, quiet=False)
        print("✅ تم تحميل ملف الـ PDF بنجاح!")
    else:
        print("✅ ملف الـ PDF موجود بالفعل.")

# ---------------------------------------------------------
# دوال البوت
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة الرد على أمر /start للترحيب بالمستخدم"""
    welcome_message = (
        "مرحباً بك في بوت حلول كلمات كراش! 🧩\n\n"
        "أرسل لي **رقم المرحلة** (مثلاً: 150) وسأرسل لك صورتها فوراً."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة استقبال أرقام المراحل من المستخدمين والرد بالصور"""
    user_text = update.message.text.strip()

    # التحقق من أن المدخل عبارة عن أرقام فقط
    if not user_text.isdigit():
        await update.message.reply_text("❌ يرجى إرسال أرقام فقط. مثال: 150")
        return

    level_number = int(user_text)

    # التحقق من وجود ملف الـ PDF
    if not os.path.exists(PDF_FILE_NAME):
        await update.message.reply_text("❌ عذراً، النظام يقوم حالياً بتهيئة ملف الحلول. يرجى المحاولة بعد دقيقة.")
        return

    try:
        # إظهار حالة "جاري إرسال صورة..." للمستخدم
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')

        # فتح الملف
        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)

        # التحقق من أن رقم المرحلة يقع ضمن نطاق الصفحات المتاحة
        if level_number < 2 or level_number >= total_pages:
            await update.message.reply_text(f"❌ عذراً، المرحلة رقم {level_number} غير موجودة في قاعدة البيانات.")
            doc.close()
            return

        # تحميل الصفحة وتحويلها لصورة
        page = doc.load_page(level_number)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        photo_stream = io.BytesIO(img_bytes)
        
        # إرسال الصورة
        await update.message.reply_photo(
            photo=photo_stream, 
            caption=f"✅ حل المرحلة {level_number}"
        )
        doc.close()

    except Exception as e:
        print(f"Error processing level {level_number}: {e}")
        await update.message.reply_text("❌ حدث خطأ فني أثناء استخراج الصورة. يرجى المحاولة لاحقاً.")

# ---------------------------------------------------------
# التشغيل الأساسي
# ---------------------------------------------------------
def main():
    """تكوين وتشغيل البوت"""
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على TELEGRAM_BOT_TOKEN في متغيرات البيئة.")
        return

    # نقوم بتحميل الملف أولاً قبل تشغيل البوت
    download_pdf_from_drive()

    # بناء تطبيق البوت
    app = Application.builder().token(TOKEN).build()

    # إضافة موجهات الأوامر والرسائل
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء استقبال الرسائل
    print("🤖 البوت يعمل الآن وينتظر الرسائل...")
    app.run_polling()

if __name__ == "__main__":
    main()
