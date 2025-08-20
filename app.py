"""
Streamlit app: Generate 10 similar physics/math problems using Google's Gemini

Setup:
  pip install streamlit google-generativeai pandas openpyxl python-docx

Run:
  export GOOGLE_API_KEY="your-key"   # or set in the app sidebar each run
  streamlit run app.py
"""

import os
import io
import re
import textwrap
from typing import Generator

import pandas as pd
import streamlit as st

try:
    import google.generativeai as genai
except Exception as e:
    genai = None

# ------------------------------
# Streamlit Page Config
# ------------------------------
st.set_page_config(
    page_title="Физик/Математик Бодлого Үүсгэгч (Gemini)",
    page_icon="🧮",
    layout="centered",
)

st.title("🧮 Физик/Математик Бодлого Үүсгэгч — Gemini")
st.caption(
    "Textarea дээр оруулсан бодлоготой төстэй **10** бодлого автоматаар үүсгэнэ. "
    "Google Gemini-г ашигладаг."
)

# ------------------------------
# Subject and subtopic definitions
# ------------------------------
PHYSICS_SUBTOPICS = {
    "Механик": ["Кинематик", "Динамик", "Статик", "Гравитаци", "Хөдөлгөөний хадгалалтын хууль", "Хүчний момент"],
    "Термодинамик": ["Хийн хууль", "Дулаан дамжуулалт", "Дулааны машин", "Энтропи", "Термодинамикийн хууль"],
    "Цахилгаан ба Соронз": ["Цахилгаан орон", "Цахилгаан гүйдэл", "Соронзон орон", "Цахилгаан соронзон индукц", "RC ба RL хэлхээ"],
    "Долгион ба Оптик": ["Долгионы шинж чанар", "Гэрлийн огилт", "Гэрлийн интерференц", "Гэрлийн туялзуур", "Хазайлт"],
    "Орчин үеийн физик": ["Квант механик", "Харьцангуй онол", "Атомын физик", "Цөмийн физик", "Элементар бөөмс"]
}

MATH_SUBTOPICS = {
    "Алгебр": ["Тэгшитгэл бодох", "Тэнцэтгэл биш", "Олон гишүүнт", "Комплекс тоо", "Матриц, тодорхойлогч"],
    "Геометр": ["Гурвалжин", "Дөрвөлжин", "Тойрог", "Геометр трансформац", "Стереометр"],
    "Тригонометр": ["Тригонометр функц", "Тригонометр тэгшитгэл", "Тригонометр тэнцэтгэл биш", "Инверс тригонометр функц"],
    "Математик анализ": ["Уламжлал", "Интеграл", "Дифференциал тэгшитгэл", "Функцийн судалгаа", "Ряд"],
    "Магадлал ба Статистик": ["Комбинаторик", "Магадлалын онол", "Санамсаргүй хэмжигдэхүүн", "Статистик дүн анализ", "Регрессийн анализ"]
}

# ------------------------------
# Sidebar: API Key & Settings
# ------------------------------
with st.sidebar:
    st.header("Тохиргоо")

    existing_key = os.getenv("GOOGLE_API_KEY", "")
    api_key = st.text_input(
        "Google API Key",
        type="password",
        value=existing_key,
        help=(
            "Системийн орчинд түлхүүр тохируулаагүй бол энд түр зуур оруулж болно. "
            "Энэ түлхүүр зөвхөн локал дээр тань ашиглагдана."
        ),
    )

    # Subject selection
    subject = st.selectbox(
        "Хичээл",
        ["Физик", "Математик"],
        index=0,
        help="Бодлого үүсгэх хичээлээ сонгоно уу"
    )
    
    # Subtopic selection based on subject
    if subject == "Физик":
        main_topic = st.selectbox(
            "Гол сэдэв",
            list(PHYSICS_SUBTOPICS.keys()),
            index=0
        )
        subtopic = st.selectbox(
            "Дэд сэдэв",
            PHYSICS_SUBTOPICS[main_topic],
            index=0
        )
    else:  # Математик
        main_topic = st.selectbox(
            "Гол сэдэв",
            list(MATH_SUBTOPICS.keys()),
            index=0
        )
        subtopic = st.selectbox(
            "Дэд сэдэв",
            MATH_SUBTOPICS[main_topic],
            index=0
        )

    model_name = st.selectbox(
        "Gemini загвар",
        [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        index=0,
        help=(
            "flash нь хурдан бөгөөд бага өртөгтэй, pro нь илүү чадвартай боловч удаан/үнэтэй байж болно."
        ),
    )

    temperature = st.slider(
        "Санаачилгатай байдал (temperature)", 0.0, 1.0, 0.7, 0.05,
        help="Ихсэх тусам төрөлжилт нэмэгдэнэ."
    )

    include_solutions = st.checkbox(
        "Шийд (тайлбар)-ийг хамтад нь гаргах", value=False
    )

    st.markdown("---")
    st.subheader("Жишээ бодлого")
    
    # Example problems based on subject and subtopic
    if subject == "Физик":
        if main_topic == "Механик":
            if subtopic == "Кинематик":
                example_problem = "Машин 72 км/ц хурдтай явж байгаад 4 секундын дотор зогссон. Машины хурдатгал болон зогсох зам нь хэд вэ?"
            elif subtopic == "Динамик":
                example_problem = "15° налуу хавтгай дээр 2 кг масстай биетийг үрэлтгүй орчинд чирэхэд биед үйлчлэх татах хүч болон налуугийн дагуух хурдатгалыг ол. g=9.8 м/с²."
            else:
                example_problem = "5 кг масстай бие 10 м/с хурдтайгаар хөдөлж байгаад 2 кг масстай тайван байгаа биетэй мөргөлдөв. Мөргөлдөөн уян хатан бол угсарсан биеийн хурдыг ол."
        elif main_topic == "Цахилгаан ба Соронз":
            example_problem = "10 Ω эсэргүүцэлтэй дамжуулагчид 12 В хүчдэл залгахад гүйдэл хэд вэ? Дамжуулагчаар 5 минут явахад ялгарах дулааны хэмжээг ол."
        else:
            example_problem = "100 г масстай биеийн температур 20°C-аас 80°C хүртэл халаахад шаардагдах дулааны хэмжээг ол. Биеийн хувийн дулаан багтаамж 0.5 J/g°C байна."
    else:  # Математик
        if main_topic == "Алгебр":
            example_problem = "x² - 5x + 6 = 0 тэгшитгэлийн бодит шийдийг ол. Мөн язгууруудын нийлбэр ба үржвэрийг ол."
        elif main_topic == "Геометр":
            example_problem = "Гурвалжны талууд нь 6 см, 8 см, 10 см байна. Энэ гурвалжин тэгш өнцөгт эсэхийг шалгаад, талбайг нь ол."
        elif main_topic == "Математик анализ":
            example_problem = "y = 2x² - 4x + 1 функцийн уламжлалыг олж, экстремум цэгүүдийг тодорхойл."
        else:
            example_problem = "Нэг шоо шидэхэд: a) 4-өөс их тоо буух магадлал, b) тэгш тоо буух магадлалыг ол."
    
    if st.button("Жишээгээр дүүргэх"):
        st.session_state["problem_text"] = example_problem

# ------------------------------
# Main Input
# ------------------------------
problem_text = st.text_area(
    f"{subject} бодлогын жишээ оруулах ({main_topic} - {subtopic})",
    key="problem_text",
    height=180,
    placeholder=example_problem,
)

st.info(
    "Доорх товчийг дармагц, оруулсан бодлоготой төстэй **яг 10** бодлогыг үүсгэж, "
    "маркдаун хэлбэрээр шууд харагдуулна."
)

# ------------------------------
# Helpers
# ------------------------------
SYSTEM_HINT = """
Та бол {subject} багш.
Хэрэглэгчийн өгсөн бодлогын агуулга, сэдэв, түвшинд тулгуурлан төстэй шинэ бодлогууд зохионо.
Бодлогууд нь мэдээллийн хувьд логик, хэмжигдэхүүнүүд нь бодогдохоор,
бага зэрэг хувьсан өөрчлөгдсөн (тоо ба нөхцөл) байх ёстой.
""".strip()

def build_prompt(user_problem: str, n: int = 10, with_solutions: bool = False) -> str:
    subject_hint = SYSTEM_HINT.format(subject=subject)
    
    base = f"""
{subject_hint}

СЭДЭВ: {main_topic} - {subtopic}

Хэрэглэгчийн өгсөн бодлого:\n\n{user_problem}\n\n
ҮҮСГЭХ ДААЛГАВАР:
- Дээрх бодлоготой ижил сэдэв ({main_topic} - {subtopic}), нэг түвшний **{n}** шинэ бодлого зохионо.
- Хэмжигдэхүүн, нөхцөлийг өөрчилж төрөлжүүл.
- Бодлого бүр: 1-2 догол мөр, ойлгомжтой, нэг утгатай байг.
- {subject} хичээлийн стандарт нэгж, тэмдэглэгээг ашигла.
- Давхардсан нөхцөл, тоо бүү ашигла.
""".strip()

    if with_solutions:
        base += "\n- БҮР БОДЛОГОД бодолтын үндсэн алхам/хариуг богино тайлбартай хамт оруул."

    base += textwrap.dedent(
        f"""
\n\nГАРГАЛТЫН ХЭЛБЭР:
- Маркдаун жагсаалт хэлбэрээр.
- Бодлого бүрийг дугаарлаж, дараах маягаар бич:\n
{{n}}. **Бодлого:** ...\n   **Сэдэв:** {main_topic} - {subtopic}\n"""
    )

    if with_solutions:
        base += "   **Тайлбар/Шийд:** ...\n"

    base += "\nМонгол хэлээр бич."
    return base


def stream_gemini_text(prompt: str, model_name: str, temperature: float) -> Generator[str, None, None]:
    """Yield plain text chunks from a streaming Gemini response."""
    global genai
    if genai is None:
        yield "⚠️ google-generativeai сан суусан эсэхийг шалгана уу: `pip install google-generativeai`\n"
        return

    key = os.getenv("GOOGLE_API_KEY") or api_key
    if not key:
        yield "⚠️ API түлхүүр оруулаагүй байна. Sidebar-аас GOOGLE_API_KEY оруулна уу.\n"
        return

    genai.configure(api_key=key)

    generation_config = {
        "temperature": float(temperature),
        "max_output_tokens": 4096,
    }

    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(
            prompt,
            stream=True,
            generation_config=generation_config,
        )
        collected = []
        for chunk in response:
            if getattr(chunk, "text", None):
                collected.append(chunk.text)
                yield chunk.text
        st.session_state["last_generated"] = "".join(collected)
    except Exception as e:
        yield f"\n\n❌ Алдаа: {e}"


# ------------------------------
# Action Button
# ------------------------------
col1, col2 = st.columns([1, 2])
with col1:
    generate = st.button("🪄 10 бодлого үүсгэх", type="primary", use_container_width=True)
with col2:
    clear = st.button("🧹 Арилгах", use_container_width=True)

if clear:
    st.session_state["problem_text"] = ""
    st.session_state["last_generated"] = ""

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

# ------------------------------
# Generation
# ------------------------------
if generate:
    if not problem_text or problem_text.strip() == "":
        st.warning("Эх бодлогоо эхлээд бичнэ үү.")
    else:
        st.subheader(f"Үүсгэсэн {subject} бодлогууд ({main_topic} - {subtopic})")
        prompt = build_prompt(problem_text, n=10, with_solutions=include_solutions)
        st.write_stream(
            stream_gemini_text(prompt, model_name=model_name, temperature=temperature)
        )

# ------------------------------
# Download buttons (DOCX only, no topic header; only numbered problems)
# ------------------------------
if "last_generated" in st.session_state and st.session_state["last_generated"]:
    text = st.session_state["last_generated"]

    # Parse ONLY the problem statements from the markdown output.
    # We ignore lines like "**Сэдэв:** ..." and "**Тайлбар/Шийд:** ...".
    problems: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Capture lines that contain the problem marker
        if "**Бодлого:**" in line:
            # Remove leading numbering like "1. " if present, then split after marker
            line_no_num = re.sub(r"^\d+\.\s*", "", line)
            after_marker = line_no_num.split("**Бодлого:**", 1)[1].strip()
            # Remove leading punctuation like ':' just in case
            after_marker = after_marker.lstrip(":-–— ").strip()
            if after_marker:
                problems.append(after_marker)
            continue
        # Fallback: plain numbered line without bold markers
        if re.match(r"^\d+\.\s+", line) and "**" not in line and not line.lower().startswith("сэдэв"):
            problems.append(re.sub(r"^\d+\.\s+", "", line).strip())

    # If parsing found nothing (LLM deviated), fall back to non-empty lines that look like bullets
    if not problems:
        for raw in text.splitlines():
            line = raw.strip(" -*\t")
            if not line or line.lower().startswith("сэдэв") or line.lower().startswith("тайлбар"):
                continue
            problems.append(line)

    # Create DOCX with ONLY numbered problems, NO header/title.
    from docx import Document

    doc = Document()
    for i, prob in enumerate(problems, start=1):
        doc.add_paragraph(f"{i}. {prob}")

    doc_buffer = io.BytesIO()
    doc.save(doc_buffer)
    doc_buffer.seek(0)

    st.download_button(
        label="⬇️ DOCX татах",
        data=doc_buffer,
        file_name="problems.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

# ------------------------------
# Footer / Tips
# ------------------------------
st.markdown(
    """
---
**Зөвлөмжүүд**
- Оруулах бодлогоо тодорхой, бүрэн өгөгтэй бичих тусам чанартай гаралт гарна.
- Төстэй биш бол temperature-г багасгаж (0.3–0.6) туршаад үзээрэй.
- Шийд хэрэгтэй бол "Шийдийг хамтад нь гаргах" сонголтыг идэвхжүүлээрэй.
"""
)
