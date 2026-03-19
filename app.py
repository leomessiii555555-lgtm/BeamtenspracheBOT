import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. KONFIGURATION (GEHIRN DER APP) ---
# Wir laden die Schlüssel sicher aus den Secrets
try:
    # API Keys
    RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    
    # Die Adresse, an die der Bestätigungslink schicken soll
    # Lokal ist das 8501. Wenn du online gehst, änderst du das in den Secrets.
    APP_URL = "http://localhost:8501"

    # Clients initialisieren
    resend.api_key = RESEND_API_KEY
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Fehler: Secrets fehlen oder sind falsch benannt! ({e})")
    st.stop()

# --- 2. FUNKTIONEN (DIE WERKZEUGE) ---

def bild_zu_base64(bild_datei):
    """Wandelt ein Foto so um, dass die KI es lesen kann."""
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die Analyse per E-Mail."""
    try:
        r = resend.Emails.send({
            "from": "onboarding@resend.dev", # Standard bei Resend Test-Accounts
            "to": ziel_email,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"""
            <div style="font-family: Arial; padding: 20px; border: 1px solid #eee;">
                <h2 style="color: #1E88E5;">Hier ist deine Analyse:</h2>
                <p style="white-space: pre-wrap;">{inhalt}</p>
                <hr>
                <p style="font-size: 0.8em; color: #777;">Gesendet vom Beamten-Zähmer Bot.</p>
            </div>
            """
        })
        st.toast("📧 E-Mail wurde versendet!", icon="✅")
        return True
    except Exception as e:
        st.sidebar.error(f"E-Mail Fehler: {e}")
        return False

# --- 3. LOGIN-SYSTEM (DER TÜRSTEHER) ---

if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer Login")
    tab_login, tab_register = st.tabs(["Anmelden", "Konto erstellen"])
    
    with tab_register:
        reg_email = st.text_input("E-Mail", key="reg_e")
        reg_pw = st.text_input("Passwort", type="password", key="reg_p")
        if st.button("Konto erstellen"):
            try:
                # Hier erzwingen wir den Rücksprung auf Port 8501
                supabase.auth.sign_up({
                    "email": reg_email, 
                    "password": reg_pw,
                    "options": {"email_redirect_to": APP_URL}
                })
                st.success("📩 Bestätigungslink gesendet! Schau in dein Postfach (und Spam).")
            except Exception as e:
                st.error(f"Registrierung fehlgeschlagen: {e}")

    with tab_login:
        log_email = st.text_input("E-Mail", key="log_e")
        log_pw = st.text_input("Passwort", type="password", key="log_p")
        if st.button("Einloggen"):
            try:
                auth_res = supabase.auth.sign_in_with_password({"email": log_email, "password": log_pw})
                st.session_state.user = auth_res.user
                st.rerun()
            except:
                st.error("Login fehlgeschlagen. Mail nicht bestätigt oder Passwort falsch.")
    st.stop()

# --- 4. HAUPT-APP (WENN EINGELOGGT) ---

# Sidebar für Bildupload
with st.sidebar:
    st.title("📸 Dokument scannen")
    foto = st.file_uploader("Brief fotografieren", type=["jpg", "png", "jpeg"])
    if foto:
        st.image(foto, caption="Dein Brief")
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Haupt-Chat Fenster
st.title("🛡️ Der Beamten-Zähmer")
st.write(f"Hallo **{st.session_state.user.email}**! Wie kann ich helfen?")

if "chat_verlauf" not in st.session_state:
    st.session_state.chat_verlauf = []

# Verlauf anzeigen
for msg in st.session_state.chat_verlauf:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Eingabe unten
user_input = st.chat_input("Schreib mir oder nutze das Mikro...")

if user_input or foto:
    # Nachricht anzeigen
    with st.chat_message("user"):
        text = user_input if user_input else "Analysiere diesen Brief für mich."
        st.markdown(text)
    st.session_state.chat_verlauf.append({"role": "user", "content": text})

    # KI-Antwort generieren
    with st.chat_message("assistant"):
        with st.spinner("Ich bändige das Behörden-Deutsch..."):
            instruktion = """Du bist der 'Beamten-Zähmer'. 
            - Antworte NUR auf Behörden, Ämter, Briefe.
            - Andere Themen lehnst du humorvoll ab.
            - Markiere Fristen FETT. Nutze einfache Sprache."""
            
            nachrichten = [{"role": "system", "content": instruktion}]
            
            if foto:
                b64 = bild_zu_base64(foto)
                nachrichten.append({"role": "user", "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                nachrichten.append({"role": "user", "content": text})

            try:
                ergebnis = openai_client.chat.completions.create(model="gpt-4o", messages=nachrichten)
                ki_antwort = ergebnis.choices[0].message.content
                st.markdown(ki_antwort)
                
                # E-Mail im Hintergrund senden
                sende_ergebnis_email(st.session_state.user.email, ki_antwort)
                
                st.session_state.chat_verlauf.append({"role": "assistant", "content": ki_antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
