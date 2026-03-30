import streamlit as st
import fitz  # مكتبة PyMuPDF للتعامل مع ملفات PDF
import os

# ---------------------------------------------------------
# إعدادات صفحة Streamlit
# ---------------------------------------------------------
st.set_page_config(
    page_title="حلول كلمات كراش", 
    page_icon="🧩", 
    layout="centered"
)

# ---------------------------------------------------------
# المتغيرات الأساسية
# ---------------------------------------------------------
# اسم ملف الـ PDF الذي يجب أن يكون في نفس مسار المشروع
PDF_FILE_NAME = "kalimat_krash_solutions.pdf"

# ---------------------------------------------------------
# واجهة المستخدم
# ---------------------------------------------------------
st.title("🧩 دليل حلول لعبة كلمات كراش")
st.markdown("أدخل رقم المرحلة أدناه، وسيقوم النظام باستخراج الحل مباشرة من الملف الأصلي وعرضه لك.")

# التحقق من وجود ملف الـ PDF في المستودع/الخادم
if os.path.exists(PDF_FILE_NAME):
    try:
        # فتح ملف الـ PDF
        doc = fitz.open(PDF_FILE_NAME)
        total_pages = len(doc)
        
        st.success("✅ النظام متصل بملف الحلول بنجاح.")
        st.info(f"إجمالي عدد الصفحات في الملف: {total_pages} صفحة.")
        
        # حقل إدخال رقم المرحلة
        # الحد الأدنى هو 2 (لأن الصفحات 0 و 1 هي أغلفة كما تفضلت)
        # الحد الأقصى هو عدد الصفحات ناقص 1
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
                # رقم المرحلة يطابق رقم الـ Index في ملف الـ PDF
                page_index = level_number
                
                # تحميل الصفحة المحددة فقط
                page = doc.load_page(page_index)
                
                # تحويل الصفحة إلى صورة بدقة عالية (DPI 150)
                pix = page.get_pixmap(dpi=150)
                
                # تحويل الصورة إلى بيانات بايت (Bytes) لعرضها دون حفظها في مجلد
                img_bytes = pix.tobytes("png")
                
                # عرض رسالة النجاح والصورة
                st.success(f"تم العثور على حل المرحلة رقم {level_number}!")
                st.image(img_bytes, caption=f"حل المرحلة {level_number}", use_column_width=True)
                
    except Exception as e:
        st.error(f"حدث خطأ غير متوقع أثناء قراءة الملف: {e}")
        
else:
    # رسالة خطأ في حال نسيان رفع ملف الـ PDF مع المشروع
    st.error(f"❌ ملف الـ PDF المسمى '{PDF_FILE_NAME}' غير موجود في النظام.")
    st.markdown("يرجى التأكد من رفع الملف إلى نفس المجلد الذي يحتوي على كود `app.py`.")
