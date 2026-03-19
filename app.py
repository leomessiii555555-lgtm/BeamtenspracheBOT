import streamlit as st
from openai import OpenAI
import base64
import io

# --- 1. SETUP & PASSWORT ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🛡️ Zugang zum Beamten-Zähmer")
        pwd_eingabe = st.text_input("Passwort eingeben", type="password")
        if st.button("Einloggen"):
            if pwd_eingabe == st.secrets["MASTER_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Falsches Passwort! 🚫")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. KI INITIALISIERUNG ---
try:
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Fehler: {e}")
    st.stop()

# --- 3. FUNKTIONEN ---
def bild_zu_base64(datei):
    return base64.b64encode(datei.read()).decode('utf-8')

def transcribe_audio(audio_file):
    try:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, response_format="text"
        )
        return response
    except:
        return None

# --- 4. DIE APP ---
st.title("🛡️ Der Beamten-Zähmer")

with st.sidebar:
    st.header("Brief-Upload & Sprache")
    foto = st.file_uploader("Foto vom Brief", type=["jpg", "png", "jpeg"])
    audio_upload = st.file_uploader("Sprachnachricht", type=["mp3", "wav", "m4a"])
    st.divider()
    if st.button("Abmelden"):
        st.session_state.authenticated = False
        st.rerun()
    if st.button("Neuer Brief / Chat löschen"):
        st.session_state.messages = []
        st.session_state.transcribed_text = None
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "transcribed_text" not in st.session_state:
    st.session_state.transcribed_text = None

if audio_upload and st.session_state.transcribed_text is None:
    audio_bytes = io.BytesIO(audio_upload.getvalue())
    audio_bytes.name = audio_upload.name
    st.session_state.transcribed_text = transcribe_audio(audio_bytes)

# Verlauf anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Was willst du wissen?", value=st.session_state.transcribed_text if st.session_state.transcribed_text else "")

if prompt and st.session_state.transcribed_text:
    st.session_state.transcribed_text = None

if prompt or (foto and "foto_verarbeitet" not in st.session_state):
    # SYSTEM PROMPT MIT DEINEN REGELN
    system_prompt = """
    Du bist der 'Beamten-Zähmer'. Ein menschlicher Ratgeber für Behörden-Kram.
    
    REGELN FÜR DIE ANALYSE:
    1. Wenn ein NEUES BILD oder ein langer Text zur Analyse kommt, antworte SOFORT mit Bulletpoints:
       - **Was ist los?** (Kurz erklären, worum es geht)
       - **Forderung:** (Was wollen die genau von mir?)
       - **Frist:** (Bis wann muss das erledigt sein? Datum **FETT** markieren)
    
    REGELN FÜR DEN CHAT DANACH:
    2. In der weiteren Unterhaltung verhältst du dich wie ein natürlicher Mensch.
    3. Antworte DIREKT auf Fragen. Wenn der User fragt 'Soll ich das machen?', sag ja/nein mit Begründung. 
    4. Wiederhole NICHT den Inhalt des Briefes, wenn nicht danach gefragt wurde.
    5. Keine Roboter-Floskeln. Bleib strikt beim Thema Behörden/Beamte.
    """

    with st.chat_message("user"):
        anzeige = prompt if prompt else "Hier ist ein Foto meines Briefes zur Analyse."
        st.markdown(anzeige)
    st.session_state.messages.append({"role": "user", "content": anzeige})

    with st.chat_message("assistant"):
        with st.spinner("Zähme Paragraphen..."):
            msgs = [{"role": "system", "content": system_prompt}] + st.session_state.messages
            
            # Falls ein Bild dabei ist, speziell aufbereiten
            if foto and "foto_verarbeitet" not in st.session_state:
                foto.seek(0)
                b64 = bild_zu_base64(foto)
                # Die letzte Nachricht im Verlauf durch Bild-Inhalt ersetzen/ergänzen
                msgs[-1] = {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief mit Bulletpoints."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
                st.session_state.foto_verarbeitet = True

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")

# Falls ein neues Foto hochgeladen wird, Reset für das nächste Mal
if not foto and "foto_verarbeitet" in st.session_state:
    del st.session_state.foto_verarbeitet
