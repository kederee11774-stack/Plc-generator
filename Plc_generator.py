import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
import streamlit.components.v1 as components

st.set_page_config(
    page_title="مُولّد برامج PLC و HMI الاحترافي V3",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 المساعد الهندسي لأتمتة المصانع (V3.0 Pro)")
st.caption("توليد أكواد PLC (Ladder / ST / IL) وتصميم شاشات HMI بضغطة زر")

def get_brand_addresses(brand, count=6):
    if "Siemens" in brand:
        base = ["I0.0", "I0.1", "I0.2", "Q0.0", "Q0.1", "M0.0"]
    elif "Omron" in brand:
        base = ["0.00", "0.01", "0.02", "100.00", "100.01", "W0.00"]
    elif "ABB" in brand:
        base = ["%IX0.0", "%IX0.1", "%IX0.2", "%QX0.0", "%QX0.1", "%MX0.0"]
    else:
        base = ["X0", "X1", "X2", "Y0", "Y1", "M0"]
    return base[:count]

TEMPLATES = {
    "🛠️ مشروع مخصص (تعديل حر)": {
        "io": [
            {"Tag_Name": "Start_Btn", "Type": "Input 🟢", "Description": "زر التشغيل"},
            {"Tag_Name": "Stop_Btn", "Type": "Input 🟢", "Description": "زر الإيقاف"},
            {"Tag_Name": "Overload_Fault", "Type": "Input 🟢", "Description": "حماية أوفرلود"},
            {"Tag_Name": "Motor_Main", "Type": "Output 🔴", "Description": "كونتاكتور المحرك"},
            {"Tag_Name": "Fault_Lamp", "Type": "Output 🔴", "Description": "لمبة بيان العطل"},
            {"Tag_Name": "HMI_Start", "Type": "Internal_Bit 🔵", "Description": "تشغيل من الشاشة"},
        ],
        "logic": "تشغيل المحرك عند الضغط على Start_Btn أو HMI_Start، وإيقافه فوراً عند Stop_Btn أو Overload_Fault مع إضاءة لمبة العطل."
    },
    "🔄 عكس حركة محرك (Forward / Reverse)": {
        "io": [
            {"Tag_Name": "Fwd_Btn", "Type": "Input 🟢", "Description": "تشغيل أمامي"},
            {"Tag_Name": "Rev_Btn", "Type": "Input 🟢", "Description": "تشغيل عكسي"},
            {"Tag_Name": "Stop_All", "Type": "Input 🟢", "Description": "إيقاف كلي"},
            {"Tag_Name": "KM_Forward", "Type": "Output 🔴", "Description": "كونتاكتور أمامي"},
            {"Tag_Name": "KM_Reverse", "Type": "Output 🔴", "Description": "كونتاكتور عكسي"},
            {"Tag_Name": "Interlock_Flag", "Type": "Internal_Bit 🔵", "Description": "حماية تداخل"},
        ],
        "logic": "تشغيل أمامي عند الضغط على Fwd_Btn وعكسي عند Rev_Btn بشرط وجود حماية تداخل برمجية (Interlock) وزمن أمان 2 ثانية بين الاتجاهين، وإيقاف الكل عند Stop_All."
    },
    "⚡ تشغيل ستار - دلتا (Star - Delta)": {
        "io": [
            {"Tag_Name": "Start_PB", "Type": "Input 🟢", "Description": "زر البدء"},
            {"Tag_Name": "Stop_PB", "Type": "Input 🟢", "Description": "زر الإيقاف"},
            {"Tag_Name": "Thermal_Trip", "Type": "Input 🟢", "Description": "أوفرلود حراري"},
            {"Tag_Name": "KM_Main", "Type": "Output 🔴", "Description": "الكونتاكتور الرئيسي"},
            {"Tag_Name": "KM_Star", "Type": "Output 🔴", "Description": "كونتاكتور ستار"},
            {"Tag_Name": "KM_Delta", "Type": "Output 🔴", "Description": "كونتاكتور دلتا"},
        ],
        "logic": "عند الضغط على Start_PB يعمل KM_Main و KM_Star معاً لمدة 5 ثوانٍ، ثم يفصل KM_Star ويعمل KM_Delta مع وجود حماية تداخل تمنع عمل ستار ودلتا معاً."
    },
    "💧 تحكم في مستوى خزان ومضختين": {
        "io": [
            {"Tag_Name": "Low_Level_Sw", "Type": "Input 🟢", "Description": "عوامة مستوى منخفض"},
            {"Tag_Name": "High_Level_Sw", "Type": "Input 🟢", "Description": "عوامة مستوى مرتفع"},
            {"Tag_Name": "Auto_Mode", "Type": "Input 🟢", "Description": "وضع أوتوماتيك"},
            {"Tag_Name": "Pump_1", "Type": "Output 🔴", "Description": "مضخة رقم 1"},
            {"Tag_Name": "Pump_2", "Type": "Output 🔴", "Description": "مضخة رقم 2"},
            {"Tag_Name": "Tank_Full_Ind", "Type": "Internal_Bit 🔵", "Description": "مؤشر امتلاء الخزان"},
        ],
        "logic": "في الوضع الأوتوماتيك Auto_Mode، عند انخفاض المستوى Low_Level_Sw تعمل المضخة الأولى، وإذا لم يرتفع المستوى خلال 10 ثوانٍ تدخل المضخة الثانية للمساعدة، وتتوقف المضختان عند الوصول للمستوى المرتفع High_Level_Sw."
    }
}

with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    api_key = st.text_input("🔑 مفتاح Gemini API Key:", type="password")
    
    st.markdown("---")
    st.subheader("🎛️ مواصفات الهاردوير")
    
    plc_brand = st.selectbox(
        "🏭 ماركة الـ PLC:",
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
        "💻 لغة البرمجة المطلوبة:",
        [
            "Ladder Diagram (رسم تخطيطي + Mnemonic/STL)",
            "Structured Text (ST)",
            "Instruction List (IL)"
        ]
    )
    
    selected_template = st.selectbox(
        "📋 اختر قالب مشروع جاهز:",
        list(TEMPLATES.keys())
    )

template_data = TEMPLATES[selected_template]
addresses = get_brand_addresses(plc_brand, len(template_data["io"]))

io_rows = []
for idx, item in enumerate(template_data["io"]):
    io_rows.append({
        "Tag_Name": item["Tag_Name"],
        "Address": addresses[idx],
        "Type": item["Type"],
        "Description": item["Description"]
    })

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("1️⃣ جدول المداخل والمخارج (قوائم تفاعلية)")
    df_io = pd.DataFrame(io_rows)
    
    edited_io = st.data_editor(
        df_io,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Tag_Name": st.column_config.TextColumn("🏷️ اسم المتغير", required=True),
            "Address": st.column_config.TextColumn("📍 العنوان", required=True),
            "Type": st.column_config.SelectboxColumn(
                "🔌 نوع الإشارة",
                options=[
                    "Input 🟢",
                    "Output 🔴",
                    "Internal_Bit 🔵",
                    "Timer ⏱️",
                    "Counter 🔢",
                    "Analog 📊"
                ],
                required=True
            ),
            "Description": st.column_config.TextColumn("📝 الوصف")
        }
    )

with col2:
    st.subheader("2️⃣ وصف منطق التشغيل (Sequence)")
    logic_prompt = st.text_area(
        "✍️ عدّل الوصف أو اكتب طلبك بحرية:",
        height=230,
        value=template_data["logic"]
    )

st.markdown("---")
if st.button("🚀 توليد البرنامج وشاشة الـ HMI الآن", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API في القائمة الجانبية (اضغط على السهم >> في أعلى اليسار).")
    else:
        with st.spinner(f"جاري بناء الكود لماركة {plc_brand} وتصميم شاشة التحكم..."):
            try:
                client = genai.Client(api_key=api_key)
                io_text = edited_io.to_csv(index=False)
                
                ladder_instruction = ""
                if "Ladder" in code_lang:
                    ladder_instruction = f"""
                    بما أن المستخدم طلب Ladder Diagram:
                    1. ارسم أولاً كل Network/Rung بشكل تخطيطي واضح باستخدام الرموز النصية (ASCII Ladder) مثل: --| |-- و --|/|-- و --( )-- مع كتابة العناوين وأسماء المتغيرات فوق كل عنصر.
                    2. اكتب أسفل الرسم مباشرة كود التعليمات المقابل له (Mnemonic / Instruction List / STL) الخاص بماركة {plc_brand} لكي يتمكن المهندس من نسخه ولصقه مباشرة في البرنامج ليتحول إلى Ladder.
                    """
                
                plc_prompt = f"""
                أنت مهندس أتمتة صناعية خبير. اكتب كود PLC احترافي لماركة {plc_brand} باستخدام {code_lang}.
                جدول المداخل والمخارج:
                {io_text}
                
                منطق التشغيل المطلوب:
                {logic_prompt}
                
                {ladder_instruction}
                
                التزم بالعناوين بدقة، وراعِ شروط الأمان الصناعي (Interlocks & Stop Priority)، واكتب تعليقات واضحة.
                """
                
                plc_res = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=plc_prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                
                hmi_prompt = f"""
                صمم واجهة شاشة لمس صناعية (HMI Screen) احترافية بصيغة كود SVG فقط (أبعاد 650x380) تمثل العناصر الموجودة في هذا الجدول:
                {io_text}
                اجعل التصميم يشبه شاشات الصناعة الحديثة (خلفية داكنة #0f172a، إطار معدني، أزرار ثلاثية الأبعاد للمدخلات باللون الأخضر والأحمر، ولمبات بيان دائرية متوهجة للمخارج) مع كتابة اسم كل عنصر وعنوانه (Address) بوضوح. أرجع كود <svg>...</svg> فقط بدون أي نص إضافي أو علامات markdown.
                """
                
                hmi_res = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=hmi_prompt,
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                
                svg_code = hmi_res.text.replace("```svg", "").replace("```xml", "").replace("```", "").strip()
                
                st.success("✅ تم توليد الكود وتصميم شاشة الـ HMI بنجاح!")
                
                tab1, tab2, tab3 = st.tabs(["⚡ كود الـ PLC (Ladder/Code)", "🖥️ شاشة الـ HMI المرئية", "📊 جدول المتغيرات (CSV)"])
                
                with tab1:
                    st.code(plc_res.text, language="text" if "Ladder" in code_lang else "iecst")
                    st.download_button("📥 تحميل ملف الكود (.txt)", plc_res.text, file_name="PLC_Code.txt", use_container_width=True)
                    
                with tab2:
                    st.markdown("**معاينة تصميم شاشة الـ HMI:**")
                    components.html(svg_code, height=400)
