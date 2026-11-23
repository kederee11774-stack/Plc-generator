import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
import streamlit.components.v1 as components

st.set_page_config(page_title="مُولّد برامج PLC و HMI الذكي V2", layout="wide")
st.title("🏭 المساعد الذكي المتكامل لأتمتة المصانع (V2.0)")

def map_addresses(brand):
    if "Siemens" in brand:
        return ["I0.0", "I0.1", "I0.2", "Q0.0", "Q0.1", "M0.0"]
    elif "Omron" in brand:
        return ["0.00", "0.01", "0.02", "100.00", "100.01", "W0.00"]
    elif "ABB" in brand:
        return ["%IX0.0", "%IX0.1", "%IX0.2", "%QX0.0", "%QX0.1", "%MX0.0"]
    else:
        return ["X0", "X1", "X2", "Y0", "Y1", "M0"]

with st.sidebar:
    st.header("⚙️ إعدادات المشروع")
    api_key = st.text_input("مفتاح Gemini API Key:", type="password")
    
    plc_brand = st.selectbox(
        "اختر ماركة الـ PLC (تتغير العناوين تلقائياً):",
        [
            "Delta (ISPSoft / WPLSoft)",
            "Mitsubishi (GX Works2/3)",
            "Xinje (XDPPro)",
            "Siemens (TIA Portal S7-1200/1500)",
            "Omron (Sysmac Studio / CX-Programmer)",
            "Panasonic (FPWIN Pro)",
            "ABB (Automation Builder)"
        ]
    )
    
    code_lang = st.selectbox(
        "لغة البرمجة المطلوبة:",
        ["Structured Text (ST)", "Instruction List (IL / Mnemonic)"]
    )

mapped_addr = map_addresses(plc_brand)

col1, col2 = st.columns(2)

with col1:
    st.subheader("1️⃣ جدول المداخل والمخارج (مُحوّل تلقائياً)")
    default_io = pd.DataFrame([
        {"Tag_Name": "Start_Btn", "Address": mapped_addr[0], "Type": "Input", "Description": "زر التشغيل"},
        {"Tag_Name": "Stop_Btn", "Address": mapped_addr[1], "Type": "Input", "Description": "زر الإيقاف"},
        {"Tag_Name": "Overload_Fault", "Address": mapped_addr[2], "Type": "Input", "Description": "عطل أوفرلود"},
        {"Tag_Name": "Motor_Contactor", "Address": mapped_addr[3], "Type": "Output", "Description": "كونتاكتور المحرك"},
        {"Tag_Name": "Fault_Lamp", "Address": mapped_addr[4], "Type": "Output", "Description": "لمبة العطل"},
        {"Tag_Name": "HMI_Start", "Address": mapped_addr[5], "Type": "Internal_Bit", "Description": "تشغيل من الشاشة"},
    ])
    edited_io = st.data_editor(default_io, num_rows="dynamic", use_container_width=True)

with col2:
    st.subheader("2️⃣ وصف منطق التشغيل وشكل الشاشة")
    logic_prompt = st.text_area(
        "صف العملية المطلوبة:",
        height=210,
        value="تشغيل المحرك عند الضغط على Start_Btn أو HMI_Start، وإيقافه عند Stop_Btn أو Overload_Fault مع إضاءة لمبة العطل."
    )

st.markdown("---")
if st.button("🚀 توليد كود الـ PLC وتصميم شاشة الـ HMI", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API في القائمة الجانبية (اضغط على السهم >> في أعلى اليسار).")
    else:
        with st.spinner("جاري هندسة الكود ورسم شاشة الـ HMI..."):
            try:
                client = genai.Client(api_key=api_key)
                io_text = edited_io.to_csv(index=False)
                
                plc_prompt = f"""
                اكتب كود PLC لماركة {plc_brand} بلغة {code_lang} بناءً على الجدول التالي:
                {io_text}
                الوصف: {logic_prompt}
                التزم بالعناوين بدقة واكتب الكود فقط مع تعليقات إنجليزية مختصرة.
                """
                
                plc_res = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=plc_prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                
                hmi_prompt = f"""
                صمم واجهة شاشة لمس صناعية (HMI Screen) احترافية بصيغة كود SVG فقط (أبعاد 600x350) تمثل العناصر الموجودة في هذا الجدول:
                {io_text}
                اجعل الخلفية داكنة (#1e293b)، وارسم أزراراً واضحة للمدخلات ولمبات دائرية للمخارج مع كتابة اسم كل عنصر وعنوانه (Address) تحته بوضوح. أرجع كود <svg>...</svg> فقط بدون أي نص إضافي أو علامات markdown.
                """
                
                hmi_res = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=hmi_prompt,
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                
                svg_code = hmi_res.text.replace("```svg", "").replace("```xml", "").replace("```", "").strip()
                
                st.success("✅ تم بناء المشروع بالكامل!")
                
                tab1, tab2, tab3 = st.tabs(["📄 كود الـ PLC", "🖥️ معاينة شاشة الـ HMI", "📊 ملف المتغيرات (CSV)"])
                
                with tab1:
                    st.code(plc_res.text, language="iecst")
                    st.download_button("📥 تحميل كود الـ PLC", plc_res.text, file_name="PLC_Program.txt")
                    
                with tab2:
                    st.markdown("**معاينة حية لتصميم شاشة الـ HMI المقترحة:**")
                    components.html(svg_code, height=380)
                    st.download_button("📥 تحميل تصميم الشاشة (SVG/XML)", svg_code, file_name="HMI_Screen.svg")
                    
                with tab3:
                    st.dataframe(edited_io, use_container_width=True)
                    csv_data = edited_io.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 تحميل جدول المتغيرات للشاشة (CSV)", csv_data, file_name="HMI_Tags.csv")
                    
            except Exception as e:
                st.error(f"حدث خطأ: {e}")


