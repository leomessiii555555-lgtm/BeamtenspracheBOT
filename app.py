import streamlit as st
from groq import Groq
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP & DESIGN ---
st.set_page_config(
    page_title="Amtsschimmel-Zähmer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für einen moderneren Look
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. KEYS LADEN ---
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("❌ Fehler: API-Keys fehlen in den Streamlit Secrets! Bitte dort eintragen.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 3. HILFSFUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 4. SIDEBAR (STEUERZENTRALE) ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.write("Lade ein Foto hoch. Ich sag dir, was Phase ist.")
    
    st.markdown("---")
    uploaded_file = st.file_uploader("📸 Brief fotografieren", type=["jpg", "jpeg", "png"])
    
    st.markdown("---")
    st.subheader("🎙️ Sprach-Befehl")
    audio_data = mic_recorder(
        start_prompt="🎤 Jetzt sprechen",
        stop_prompt="🛑 Fertig",
        key='sidebar_mic'
    )
    
    st.markdown("---")
    if st.button("🗑️ Chat-Verlauf löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 5. CHAT SYSTEM ---
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("📑 Dein Behörden-Dolmetscher")
st.caption("Ich lese das Beamtendeutsch für dich. Du machst nur die Action.")

# Chat-Historie anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 6. DER "HART-ABER-FAIR" PROMPT ---
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Dein Job: Den Nutzer vor Behörden-Irrsinn schützen. "
    "Regel Nr. 1: Verweise NIEMALS darauf, dass der Nutzer den Brief selbst lesen soll. Du liest ihn für ihn! "
    "Regel Nr. 2: Sei extrem direkt. Kein 'Vielleicht', keine Höflichkeitsfloskeln. "
    "\n\nAntworte IMMER in diesem Format:\n"
    "### 🎯 KLARTEXT\n(Was wollen die? In 1 Satz.)\n\n"
    "### 💰 FAKTEN-CHECK\n- **Betrag:** [X Euro oder 'Keiner']\n- **DEADLINE:** [Datum fett markieren!]\n- **Wichtige Nummer:** [Aktenzeichen/Kundennummer]\n\n"
    "### ⚡ DEIN SCHLACHTPLAN (Das tust du jetzt)\n1. [Schritt 1]\n2. [Schritt 2]\n\n"
    "### ⚠️ RISIKO\n(Was passiert, wenn du die Deadline verpennst?)"
)

# --- 7. INPUT HANDLING ---
user_text = st.chat_input("Was soll ich für dich checken?")

# Audio zu Text
audio_prompt = None
if audio_data:
    audio_id = hash(audio_data['bytes'])
    if st.session_state.get('last_audio_id') != audio_id:
        with st.spinner("Ich höre zu..."):
            audio_bio = io.BytesIO(audio_data['bytes'])
            audio_bio.name = "input.wav"
            trans = client.audio.transcriptions.create(file=(audio_bio.name, audio_bio.read()), model="whisper-large-v3")
            audio_prompt = trans.text
            st.session_state.last_audio_id = audio_id

final_input = user_text if user_text else audio_prompt

if final_input:
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # Modell-Logik: Vision für Bilder nutzen!
    model_name = "llama-3.2-11b-vision-preview" if uploaded_file else "llama-3.3-70b-versatile"
    
    messages_payload = [{"role": "system", "content": system_instruction}]
    for m in st.session_state.messages[:-1]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    
    if uploaded_file:
        img_b64 = encode_image(uploaded_file)
        messages_payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": final_input},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
            ]
        })
    else:
        messages_payload.append({"role": "user", "content": final_input})

    with st.spinner("🤖 Analysiere..."):
        try:
            res = client.chat.completions.create(model=model_name, messages=messages_payload)
            ai_text = res.choices[0].message.content
            
            full_res = ai_text + "\n\n---\n*Wichtig: KI-Analyse, keine Rechtsberatung.*"
            
            with st.chat_message("assistant"):
                st.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})
            
            # Log in Datenbank (optional)
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_text[:200]}).execute()
            except: pass
            
            if audio_prompt: st.rerun()
        except Exception as e:
            st.error(f"Fehler: {e}")
