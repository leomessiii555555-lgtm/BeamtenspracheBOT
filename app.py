import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. SETUP & SECRETS ---
try:
    # Wir holen alles aus den Streamlit Secrets
    resend.api_key = st.secrets["RESEND_API_KEY"]
    openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    # Die URL deiner App (lokal 8501, später deine Streamlit-URL)
    APP_URL = "http://localhost:8501" 
except Exception as e:
    st.error("Konfigurationsfehler: Prüfe deine Secrets!")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(bild_datei):
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_ergebnis_email(ziel_email, inhalt):
    """Nutzt die offizielle Resend API für schicke HTML Mails."""
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ziel_email,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"""
            <div style="font-family: sans-serif; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2e7d32;">Hallo!</h2>
                <p>Hier ist die Analyse deines Schreibens in einfachem Deutsch:</p>
                <div style="background: #f9f9f9; padding: 15px; border-left: 5px solid #2e7d32;">
                    {inhalt.replace('\n', '<br>')}
                </div>
                <p style="margin-top: 20px; font-size: 0.8em; color: #666;">
                    Gesendet vom Beamten-Zähmer. Viel Erfolg beim Widerspruch!
                </p>
            </div>
            """
        })
        return True
    except:
        return False

# --- 3. LOGIN & REGISTRIERUNG ---
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛡️ Beamten-Zähmer")
    tab_login, tab_reg = st.tabs(["Anmelden", "Konto erstellen"])
    
    with tab_reg:
        r_mail = st.text_input("E-Mail", key="reg_mail")
        r_pw = st.text_input("Passwort", type="password", key="reg_pw", help="Min. 6 Zeichen")
        if st.button("Registrieren"):
            try:
                # FIX: Hier sagen wir Supabase, dass es auf Port 8501 zurückleiten soll!
                supabase.auth.sign_up({
                    "email": r_mail, 
                    "password": r_pw,
                    "options": {"email_redirect_to": APP_URL}
                })
                st.success(f"Bestätigungs-Link an {r_mail} gesendet!")
            except Exception as e:
                st.error(f"Fehler: {e}")

    with tab_login:
        l_mail = st.text_input("E-Mail", key="log_mail")
        l_pw = st.text_input("Passwort", type="password", key="log_pw")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_mail, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except:
                st.error("Login fehlgeschlagen. Passwort falsch oder Mail nicht bestätigt?")
    st.stop()

# --- 4. DAS CHAT-INTERFACE (MODERN) ---

# Sidebar für Uploads
with st.sidebar:
    st.title("📸 Scan")
    uploaded_file = st.file_uploader("Brief hochladen", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file, caption="Dein Dokument")
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Hauptfenster
st.title("🛡️ Der Beamten-Zähmer")
st.caption("Ich übersetze Behörden-Deutsch. (Kein Mathe, kein Fußball!)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat-Verlauf anzeigen
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Eingabe-Feld ganz unten (Standard-Streamlit Chat Input)
prompt = st.chat_input("Schreib mir oder nutze das Mikro deiner Tastatur...")

if prompt or uploaded_file:
    # User Input anzeigen
    with st.chat_message("user"):
        user_text = prompt if prompt else "Analysiere diesen Brief für mich."
        st.markdown(user_text)
    st.session_state.messages.append({"role": "user", "content": user_text})

    # KI Antwort
    with st.chat_message("assistant"):
        with st.spinner("Ich lese zwischen den Zeilen..."):
            rules = """Du bist der 'Beamten-Zähmer'. 
            1. Antworte NUR auf Behörden-Themen. 
            2. Wenn der User über Mathe, Fußball oder anderes redet, sag: 'Dafür bin ich zu schlau. Ich zähme lieber Beamte!'
            3. Nutze Bulletpoints, markiere Fristen FETT, erkläre es wie für ein Kind."""
            
            msgs = [{"role": "system", "content": rules}]
            
            if uploaded_file:
                b64 = bild_zu_base64(uploaded_file)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                msgs.append({"role": "user", "content": user_text})

            try:
                # OpenAI Abfrage
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                
                # E-Mail senden
                sende_ergebnis_email(st.session_state.user.email, antwort)
                
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
