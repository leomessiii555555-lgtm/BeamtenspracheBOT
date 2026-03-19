import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. KONFIGURATION & SICHERHEIT ---
# Wir laden alles zentral. Wenn ein Key fehlt, bricht die App nicht lautlos ab.
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
    RESEND_API_KEY = st.secrets["RESEND_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    
    # WICHTIG: Die Adresse für den Bestätigungslink
    # Wenn du auf Streamlit Cloud gehst, ändere dies zu deiner .streamlit.app URL!
    APP_URL = "http://localhost:8501" 

    resend.api_key = RESEND_API_KEY
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ Konfigurationsfehler: {e}. Prüfe deine Secrets!")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(bild_datei):
    """Wandelt das Foto für die KI um."""
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Verschickt die Analyse via Resend API."""
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ziel_email,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"<h3>Analyse-Ergebnis:</h3><p>{inhalt.replace(chr(10), '<br>')}</p>"
        })
        return True
    except Exception as e:
        st.sidebar.warning(f"Mail-Versand hakt: {e}")
        return False

# --- 3. LOGIN & REGISTRIERUNG ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer")
    st.info("Bitte einloggen oder registrieren, um Briefe zu zähmen.")
    
    tab_login, tab_reg = st.tabs(["🔐 Login", "📝 Konto erstellen"])
    
    with tab_reg:
        r_mail = st.text_input("E-Mail Adresse", key="reg_m")
        r_pw = st.text_input("Passwort wählen", type="password", key="reg_p", help="Min. 6 Zeichen")
        if st.button("Konto jetzt erstellen"):
            try:
                # Hier schicken wir den User zur richtigen URL zurück (8501)
                res = supabase.auth.sign_up({
                    "email": r_mail, 
                    "password": r_pw,
                    "options": {"email_redirect_to": APP_URL}
                })
                st.success(f"📩 Bestätigungslink an {r_mail} gesendet! Bitte schau auch im Spam-Ordner nach.")
            except Exception as e:
                st.error(f"Fehler: {e}")

    with tab_login:
        l_mail = st.text_input("E-Mail Adresse", key="log_m")
        l_pw = st.text_input("Passwort", type="password", key="log_p")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_mail, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except:
                st.error("Login fehlgeschlagen. Passwort falsch oder E-Mail noch nicht bestätigt?")
    st.stop()

# --- 4. DAS CHAT-INTERFACE (MODERN & FIXIERT) ---

# Sidebar: Nur für das "Grobe" (Bild & Logout)
with st.sidebar:
    st.title("📸 Brief-Scan")
    uploaded_file = st.file_uploader("Dokument hochladen", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file, caption="Dein Brief")
    
    st.divider()
    if st.button("🚪 Abmelden"):
        st.session_state.user = None
        st.rerun()

# Hauptbereich: Das Gespräch
st.title("🛡️ Der Beamten-Zähmer")
st.markdown(f"Eingeloggt als: **{st.session_state.user.email}**")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Verlauf anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# DAS INPUT FELD (Ganz unten fixiert, gut für Handy-Mikrofon)
prompt = st.chat_input("Was hat das Amt geschrieben? Tippe hier...")

if prompt or uploaded_file:
    # 1. User Nachricht
    with st.chat_message("user"):
        anzeige = prompt if prompt else "Ich habe ein Bild hochgeladen."
        st.markdown(anzeige)
    st.session_state.messages.append({"role": "user", "content": anzeige})

    # 2. KI Antwort
    with st.chat_message("assistant"):
        with st.spinner("Ich übersetze Beamten-Deutsch..."):
            rules = """Du bist der 'Beamten-Zähmer'. 
            - Antworte NUR auf Behörden, Ämter, Briefe oder Gesetze.
            - Mathe, Fußball, Kochen etc. lehnst du ab: 'Dafür habe ich keine Zeit, ich muss Beamte zähmen!'
            - Nutze Bulletpoints, markiere Fristen FETT, erkläre einfach."""
            
            msgs = [{"role": "system", "content": rules}]
            
            if uploaded_file:
                b64 = bild_zu_base64(uploaded_file)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": prompt if prompt else "Analysiere diesen Brief."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                msgs.append({"role": "user", "content": prompt})

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                
                # Mail senden
                sende_ergebnis_email(st.session_state.user.email, antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI Fehler: {e}")
