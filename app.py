import streamlit as st
import fitz  # مكتبة PyMuPDF للتعامل مع ملفات PDF
import os
import gdown  # مكتبة التحميل من جوجل درايف

# ---------------------------------------------------------
# إعدادات صفحة Streamlit
# ---------------------------------------------------------
st.set_page_config(
    page_title="حلول كلمات كراش", 
    page_icon="🧩", 
    layout="centered"
)

# ---------------------------------------------------------
# المتغيرات الأساسية (تم إضافة رابطك الخاص)
# ---------------------------------------------------------
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"
FILE_ID = "1ca7Qsgq5FKtPNpx8mAyUFMD6NCvSQ5g7"

# ---------------------------------------------------------
# دالة التحميل من Google Drive
# ---------------------------------------------------------
@st.cache_resource
def download_pdf_from_drive():
    if not os.path.exists(PDF_FILE_NAME):
        url = f'https://drive.google.com/uc?id={FILE_ID}'
        # جلب الملف وتسميته بالاسم المطلوب
        gdown.download(url, PDF_FILE_NAME, quiet=False)
    return True

# ---------------------------------------------------------
# واجهة المستخدم
# ---------------------------------------------------------
st.title("🧩 دليل حلول لعبة كلمات كراش")
st.markdown("أدخل رقم المرحلة أدناه، وسيقوم النظام باستخراج الحل مباشرة.")

# تشغيل دالة التحميل مع إظهار رسالة للمستخدم أثناء التحميل الأول
with st.spinner("جاري تهيئة ملف الحلول... (قد يستغرق هذا ثوانٍ معدودة في المرة الأولى فقط)"):
    download_pdf_from_drive()

# بعد انتهاء التحميل، نتحقق من وجود الملف
if os.path.exists(PDF_FILE_NAME):
    try:
        # فتح ملف الـ PDF
        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)
        
        st.success("✅ النظام متصل بملف الحلول بنجاح.")
        
        # حقل إدخال رقم المرحلة
        level_number = st.number_input(
            "رقم المرحلة المطلوبة:", 
            min_value=2, 
            max_value=total_pages - 1, 
            step=1,
            format="%d"
        )
        
        # زر استخراج وعرض الحل
        if st.button("ابحث عن الحل 🔍"):
            with st.spinner('جاري معالجة الملف واستخراج الصورة...'):
                page_index = level_number
                
                # تحميل الصفحة المحددة فقط وتحويلها لصورة
                page = doc.load_page(page_index)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                
                # عرض الصورة
                st.success(f"تم العثور على حل المرحلة رقم {level_number}!")
                st.image(img_bytes, caption=f"حل المرحلة {level_number}", use_column_width=True)
                
    except Exception as e:
        st.error(f"حدث خطأ غير متوقع أثناء قراءة الملف: {e}")
else:
    st.error("❌ فشل في تحميل الملف من Google Drive. يرجى التأكد من صلاحيات الملف (أي شخص لديه الرابط).")
