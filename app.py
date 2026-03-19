import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. INITIALISIERUNG & SICHERHEIT ---
st.set_page_config(page_title="Der Beamten-Zähmer", layout="centered")

def get_secrets():
    try:
        return {
            "S_URL": st.secrets["SUPABASE_URL"],
            "S_KEY": st.secrets["SUPABASE_KEY"],
            "O_KEY": st.secrets["OPENAI_API_KEY"],
            "R_KEY": st.secrets["RESEND_API_KEY"],
            "APP_URL": "http://localhost:8501"
        }
    except Exception as e:
        st.error(f"❌ Secrets Fehler: {e}. Prüfe deine secrets.toml!")
        st.stop()

sec = get_secrets()
supabase: Client = create_client(sec["S_URL"], sec["S_KEY"])
openai_client = OpenAI(api_key=sec["O_KEY"])
resend.api_key = sec["R_KEY"]

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(bild_datei):
    return base64.b64encode(bild_datei.read()).decode('utf-8')

def sende_email(ziel, inhalt):
    try:
        # Hinweis: onboarding@resend.dev sendet nur an DICH selbst (Sandbox)
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": ziel,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"<div style='font-family:sans-serif;'><h3>Analyse-Ergebnis:</h3><p>{inhalt}</p></div>"
        })
        st.toast("📧 Analyse wurde per E-Mail gesendet!", icon="✅")
    except Exception as e:
        st.sidebar.error(f"Mail-Fehler: {e}")

# --- 3. AUTHENTIFIZIERUNG (LOGIN / REGISTRIERUNG) ---

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🛡️ Willkommen beim Beamten-Zähmer")
    st.info("Logge dich ein, um loszulegen.")
    
    t1, t2 = st.tabs(["Anmelden", "Konto erstellen"])
    
    with t2:
        reg_mail = st.text_input("E-Mail Adresse", key="reg_m")
        reg_pw = st.text_input("Passwort (min. 6 Zeichen)", type="password", key="reg_p")
        if st.button("🚀 Jetzt Registrieren"):
            try:
                # Hier schicken wir die Info an Supabase
                res = supabase.auth.sign_up({
                    "email": reg_mail,
                    "password": reg_pw,
                    "options": {"email_redirect_to": sec["APP_URL"]}
                })
                if res.user:
                    st.success(f"✅ Konto für {reg_mail} angelegt!")
                    st.warning("⚠️ WICHTIG: Prüfe jetzt dein Postfach und klicke auf den Bestätigungslink!")
                else:
                    st.error("Konto konnte nicht erstellt werden. User-Limit erreicht?")
            except Exception as e:
                st.error(f"Fehler: {e}")

    with t1:
        log_mail = st.text_input("E-Mail", key="log_m")
        log_pw = st.text_input("Passwort", type="password", key="log_p")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": log_mail, "password": log_pw})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Login fehlgeschlagen. Mail bestätigt? Fehler: {e}")
    st.stop()

# --- 4. HAUPT-APP (WENN EINGELOGGT) ---

with st.sidebar:
    st.title("📸 Dokument")
    u_file = st.file_uploader("Brief hochladen", type=["jpg", "png", "jpeg"])
    if u_file:
        st.image(u_file, caption="Scan bereit")
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

st.title("🛡️ Der Beamten-Zähmer")
st.write(f"Hallo **{st.session_state.user.email}**, was hat das Amt geschrieben?")

if "chat" not in st.session_state:
    st.session_state.chat = []

# Chatverlauf anzeigen
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Eingabefeld unten
prompt = st.chat_input("Tippe hier deine Frage oder nutze das Mikro...")

if prompt or u_file:
    # User Nachricht
    with st.chat_message("user"):
        txt = prompt if prompt else "Analysiere diesen Brief."
        st.markdown(txt)
    st.session_state.chat.append({"role": "user", "content": txt})

    # KI Antwort
    with st.chat_message("assistant"):
        with st.spinner("Ich zähme den Beamten..."):
            instruktion = "Du bist der 'Beamten-Zähmer'. Antworte nur auf Behörden-Themen. Erkläre es einfach, markiere Fristen FETT."
            msgs = [{"role": "system", "content": instruktion}]
            
            if u_file:
                b64 = bild_zu_base64(u_file)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": txt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                msgs.append({"role": "user", "content": txt})

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                
                # E-Mail versenden
                sende_email(st.session_state.user.email, antwort)
                
                st.session_state.chat.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI Fehler: {e}")
