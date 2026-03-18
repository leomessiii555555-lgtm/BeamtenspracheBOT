import streamlit as st
from groq import Groq
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. SEITEN-EINSTELLUNGEN ---
st.set_page_config(
    page_title="Behörden-Dolmetscher",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. VERBINDUNG ZU DEN DIENSTEN ---
# Diese Daten holt sich die App aus den Streamlit "Secrets"
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Fehler: API-Keys fehlen in den Streamlit Secrets!")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 3. HILFSFUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 4. SEITENLEISTE (SIDEBAR) ---
with st.sidebar:
    st.title("🏢 Menü")
    st.write("Scanne deinen Brief und erhalte sofort eine einfache Erklärung.")
    
    st.markdown("---")
    
    # BILD-UPLOAD
    st.subheader("📸 Foto hochladen")
    uploaded_file = st.file_uploader("Brief fotografieren/scannen", type=["jpg", "jpeg", "png"])
    
    st.markdown("---")
    
    # MIKROFON (Fest in der Sidebar)
    st.subheader("🎙️ Sprach-Anweisung")
    audio_data = mic_recorder(
        start_prompt="🎤 Sprechen",
        stop_prompt="🛑 Senden",
        key='sidebar_mic'
    )
    
    st.markdown("---")
    if st.button("🗑️ Chat löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 5. HAUPT-INTERFACE ---
st.title("📑 Behörden-Dolmetscher")
st.info("Keine Angst mehr vor komplizierten Briefen. Ich übersetze Beamtendeutsch in klare Schritte.")

# Chat-Speicher initialisieren
if "messages" not in st.session_state:
    st.session_state.messages = []

# Bisherigen Chat anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 6. KI-ANWEISUNG (SYSTEM PROMPT) ---
system_instruction = (
    "Du bist ein Experte für deutsches Verwaltungsrecht und einfache Sprache. "
    "Deine Aufgabe ist es, Behördenbriefe zu analysieren. "
    "Struktur deiner Antwort:\n"
    "1. **Was ist das?** (Max. 2 Sätze in einfacher Sprache)\n"
    "2. **Wichtige Fristen** (Datum fettgedruckt hervorheben!)\n"
    "3. **Was musst du jetzt tun?** (Klare Schritt-für-Schritt-Liste)\n"
    "Sei höflich, nimm dem Nutzer die Angst und verwende KEIN Beamtendeutsch."
)

# --- 7. INPUT VERARBEITUNG (TEXT & AUDIO) ---
user_text = st.chat_input("Frage zum Brief stellen...")

# Audio zu Text wandeln (Whisper)
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

# Welcher Input wird genutzt?
final_input = user_text if user_text else audio_prompt

if final_input:
    # User Nachricht speichern
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user"):
        st.markdown(final_input)

    # KI Modell wählen (Vision für Bilder, Versatile für Text)
    model_name = "llama-3.2-11b-vision-preview" if uploaded_file else "llama-3.3-70b-versatile"
    
    # Payload bauen
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

    # KI Antwort generieren
    with st.spinner("Analysiere..."):
        try:
            chat_completion = client.chat.completions.create(model=model_name, messages=messages_payload)
            ai_response = chat_completion.choices[0].message.content
            
            # Disclaimer hinzufügen
            full_response = ai_response + "\n\n---\n*Hinweis: Dies ist eine KI-Analyse, keine Rechtsberatung.*"
            
            with st.chat_message("assistant"):
                st.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # In Supabase speichern (nur die Analyse)
            try:
                supabase.table("brief_summaries").insert({"summary_text": ai_response[:300]}).execute()
            except:
                pass
            
            if audio_prompt: st.rerun()
        except Exception as e:
            st.error(f"Fehler: {e}")
