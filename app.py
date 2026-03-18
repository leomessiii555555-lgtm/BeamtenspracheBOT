import streamlit as st
from groq import Groq
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. INITIALISIERUNG ---
st.set_page_config(page_title="Amtsschimmel-Zähmer v3", layout="wide")

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]
except:
    st.error("API Keys in Streamlit Secrets fehlen!")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(S_URL, S_KEY)

# --- 2. BILD-HELFER ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    st.info("Aktueller Status: Online 🟢")
    uploaded_file = st.file_uploader("📸 Brief hochladen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Fertig", key='sidebar_mic')
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 4. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. SYSTEM PROMPT ---
system_instruction = (
    "Du bist der 'Amtsschimmel-Zähmer'. Deine Aufgabe: Analysiere den Brief auf dem Bild VOLLSTÄNDIG. "
    "Gib klare Befehle. Struktur: 🎯 KLARTEXT, 💰 FAKTEN, ⚡ SCHLACHTPLAN."
)

# --- 6. INPUT-VERARBEITUNG ---
user_text = st.chat_input("Frag mich was...")

# Audio-Check (Whisper ist stabil)
audio_prompt = None
if audio_data:
    audio_bio = io.BytesIO(audio_data['bytes'])
    audio_bio.name = "input.wav"
    trans = client.audio.transcriptions.create(file=(audio_bio.name, audio_bio.read()), model="whisper-large-v3")
    audio_prompt = trans.text

final_input = user_text if user_text else audio_prompt

if final_input or uploaded_file:
    if not final_input:
        final_input = "Analysiere diesen Brief."

    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # --- MODEL CHECK (AKTUELLSTE VERSIONEN) ---
    # Wir probieren das stärkste verfügbare Vision Modell
    # Falls 'llama-3.2-90b-vision-preview' weg ist, ist 'llama-3.2-11b-vision-preview' meist noch da.
    # Als Backup nutzen wir das universelle 'llama-3.3-70b-versatile' für reinen Text.
    
    if uploaded_file:
        model_to_use = "llama-3.2-11b-vision-preview" # Das stabilste kleine Vision Modell
    else:
        model_to_use = "llama-3.3-70b-versatile" # Das aktuellste Text-Modell
    
    # Payload
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

    with st.spinner(f"🤖 Analysiere mit {model_to_use}..."):
        try:
            res = client.chat.completions.create(model=model_name, messages=messages_payload)
            ai_text = res.choices[0].message.content
            with st.chat_message("assistant"):
                st.markdown(ai_text)
            st.session_state.messages.append({"role": "assistant", "content": ai_text})
            
            # DB Speicher
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_text[:300]}).execute()
            except: pass
            
        except Exception as e:
            st.error(f"Modell-Fehler: {e}")
            st.info("Tipp: Wenn das Modell 'decommissioned' ist, muss der Name im Code kurz angepasst werden. Groq ändert die Namen oft minimal.")
