import os
import fitz  # مكتبة PyMuPDF
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ---------------------------------------------------------
# المتغيرات الأساسية
# ---------------------------------------------------------
# جلب الـ Token من متغيرات البيئة للأمان
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"

# ---------------------------------------------------------
# دوال البوت
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة الرد على أمر /start للترحيب بالمستخدم"""
    welcome_message = (
        "مرحباً بك في بوت حلول كلمات كراش! 🧩\n\n"
        "أنا متصل بقاعدة بيانات ضخمة تحتوي على كافة الحلول.\n"
        "فقط أرسل لي **رقم المرحلة** (مثلاً: 150) وسأرسل لك صورتها فوراً."
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
        await update.message.reply_text("❌ عذراً، ملف الحلول غير متوفر في الخادم حالياً. يرجى إبلاغ الإدارة.")
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

        # تحميل الصفحة المطلوبة (Index يطابق رقم المرحلة)
        page = doc.load_page(level_number)
        
        # تحويل الصفحة إلى صورة (DPI 150 لجودة واضحة)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        
        # استخدام io.BytesIO لتمرير البايتات كملف إلى واجهة تليجرام
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
        print("يرجى التأكد من إضافة الـ Token قبل تشغيل السكريبت.")
        return

    # بناء تطبيق البوت
    app = Application.builder().token(TOKEN).build()

    # إضافة موجهات الأوامر والرسائل (Handlers)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء استقبال الرسائل (Polling)
    print("🤖 البوت يعمل الآن وينتظر الرسائل...")
    app.run_polling()

if __name__ == "__main__":
    main()
