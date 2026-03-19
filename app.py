import streamlit as st
from openai import OpenAI
import base64

# --- 1. SETUP & PASSWORT ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

def check_password():
    """Ein einfacher Passwort-Schutz ohne Datenbank."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🛡️ Zugang zum Beamten-Zähmer")
        # Das Passwort muss in den Streamlit Secrets als MASTER_PASSWORD stehen
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
    st.error(f"Fehler beim Laden des API-Keys: {e}")
    st.stop()

# --- 3. FUNKTIONEN ---
def bild_zu_base64(datei):
    """Wandelt das Bild in Text für die KI um."""
    return base64.b64encode(datei.read()).decode('utf-8')

# --- 4. DIE APP ---
st.title("🛡️ Der Beamten-Zähmer")
st.info("Lade ein Foto hoch oder schreibe den Text deines Briefes hier rein.")

with st.sidebar:
    st.header("Brief-Upload")
    foto = st.file_uploader("Foto vom Brief", type=["jpg", "png", "jpeg"])
    if foto:
        st.image(foto, caption="Dein Scan")
    
    st.divider()
    if st.button("Abmelden"):
        st.session_state.authenticated = False
        st.rerun()

# Chat-Speicher
if "messages" not in st.session_state:
    st.session_state.messages = []

# Verlauf anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Eingabe-Feld
prompt = st.chat_input("Was willst du wissen?")

if prompt or foto:
    # 1. User-Input anzeigen
    with st.chat_message("user"):
        anzeige_text = prompt if prompt else "Hier ist ein Foto meines Briefes."
        st.markdown(anzeige_text)
    
    # Nachricht im Verlauf speichern (Bilder schicken wir nicht in den Verlaufsspeicher, um Tokens zu sparen)
    st.session_state.messages.append({"role": "user", "content": anzeige_text})

    # 2. KI-Antwort
    with st.chat_message("assistant"):
        with st.spinner("Zähme den Paragraphen-Dschungel..."):
            system_prompt = "Du bist der Beamten-Zähmer. Übersetze Behörden-Deutsch in einfaches Deutsch. Markiere Fristen FETT."
            msgs = [{"role": "system", "content": system_prompt}]
            
            if foto:
                # Bild-Analyse vorbereiten
                # Wir setzen den Dateizeiger zurück, falls das Bild oben schon angezeigt wurde
                foto.seek(0)
                b64_image = bild_zu_base64(foto)
                msgs.append({
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]
                })
            else:
                msgs.append({"role": "user", "content": prompt})

            try:
                # API Call
                response = openai_client.chat.completions.create(
                    model="gpt-4o", 
                    messages=msgs
                )
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
