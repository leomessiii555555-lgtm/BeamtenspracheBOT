import streamlit as st
from groq import Groq
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer", layout="wide")

# Sicheres Laden der Keys
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception:
    st.error("Fehler: API-Keys fehlen in den Secrets!")
    st.stop()

# --- 2. BILD-HELFER ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Behörden-Killer")
    uploaded_file = st.file_uploader("📸 Brief hochladen", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Senden", key='mic')
    if st.button("🗑️ Chat löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 4. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. SYSTEM PROMPT ---
sys_prompt = "Du bist der 'Amtsschimmel-Zähmer'. Analysiere den Brief. Struktur: 🎯 KLARTEXT, 💰 FAKTEN, ⚡ SCHLACHTPLAN."

# --- 6. INPUT-VERARBEITUNG ---
user_text = st.chat_input("Frag mich was...")

final_input = user_text
if audio_data and "bytes" in audio_data:
    try:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=(audio_bio.name, audio_bio.read()), model="whisper-large-v3")
        final_input = trans.text
    except:
        pass

if final_input or uploaded_file:
    if not final_input:
        final_input = "Bitte analysiere diesen Brief für mich."

    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # --- DIREKTE MODELL-AUSWAHL (Keine Variablen-Fehler mehr möglich) ---
    aktuelles_modell = "llama-3.2-11b-vision-preview" if uploaded_file else "llama-3.3-70b-versatile"
    
    payload = [{"role": "system", "content": sys_prompt}]
    for m in st.session_state.messages[:-1]:
        payload.append(m)
    
    if uploaded_file:
        img_64 = encode_image(uploaded_file)
        payload.append({
            "role": "user",
            "content": [
                {"type": "text", "text": final_input},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_64}"}}
            ]
        })
    else:
        payload.append({"role": "user", "content": final_input})

    with st.spinner("🤖 Analysiere..."):
        try:
            res = client.chat.completions.create(model=aktuelles_modell, messages=payload)
            antwort = res.choices[0].message.content
            
            with st.chat_message("assistant"):
                st.markdown(antwort)
            st.session_state.messages.append({"role": "assistant", "content": antwort})
            
            try:
                supabase.table("brief_summaries").insert({"summary_text": antwort[:300]}).execute()
            except: 
                pass
                
        except Exception as e:
            st.error(f"Fehler von der KI: {e}")
