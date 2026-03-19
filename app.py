import streamlit as st
import resend
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. SETUP (DIE BASIS) ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

# Wir laden alle Schlüssel direkt aus den Secrets
try:
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]
    O_KEY = st.secrets["OPENAI_API_KEY"]
    R_KEY = st.secrets["RESEND_API_KEY"]

    # Verbindungen aufbauen
    supabase: Client = create_client(S_URL, S_KEY)
    openai_client = OpenAI(api_key=O_KEY)
    resend.api_key = R_KEY
except Exception as e:
    st.error(f"Fehler beim Laden der Secrets: {e}")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(datei):
    """Wandelt ein Foto in Text für die KI um."""
    return base64.b64encode(datei.read()).decode('utf-8')

def email_senden(empfaenger, inhalt):
    """Verschickt die Analyse per Resend."""
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": empfaenger,
            "subject": "🛡️ Deine Beamten-Zähmer Analyse",
            "html": f"<h3>Ergebnis:</h3><p>{inhalt.replace(chr(10), '<br>')}</p>"
        })
        st.toast("E-Mail versendet!", icon="📧")
    except Exception as e:
        st.sidebar.warning(f"Mail-Fehler: {e}")

# --- 3. LOGIN & REGISTRIERUNG ---

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🛡️ Beamten-Zähmer: Login")
    
    t1, t2 = st.tabs(["Anmelden", "Konto erstellen"])
    
    with t2:
        r_email = st.text_input("E-Mail", key="r_mail")
        r_pw = st.text_input("Passwort (min. 6 Zeichen)", type="password", key="r_pw")
        if st.button("Jetzt Registrieren"):
            try:
                # User erstellen
                res = supabase.auth.sign_up({"email": r_email, "password": r_pw})
                if res.user:
                    st.success("✅ Konto erstellt! Du kannst dich jetzt anmelden.")
                    st.info("Hinweis: Wenn 'Confirm Email' in Supabase OFF ist, bist du sofort startklar.")
                else:
                    st.error("Fehler: User konnte nicht angelegt werden.")
            except Exception as e:
                st.error(f"Fehler: {e}")

    with t1:
        l_email = st.text_input("E-Mail", key="l_mail")
        l_pw = st.text_input("Passwort", type="password", key="l_pw")
        if st.button("Einloggen"):
            try:
                res = supabase.auth.sign_in_with_password({"email": l_email, "password": l_pw})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Login fehlgeschlagen: {e}")
    st.stop()

# --- 4. DIE HAUPT-APP (WENN EINGELOGGT) ---

with st.sidebar:
    st.header("📸 Foto-Upload")
    foto = st.file_uploader("Brief scannen", type=["jpg", "png", "jpeg"])
    if foto:
        st.image(foto)
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

st.title("🛡️ Der Beamten-Zähmer")
st.write(f"Eingeloggt als: **{st.session_state.user.email}**")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Chat anzeigen
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Chat-Eingabe (Mikrofon-freundlich ganz unten)
prompt = st.chat_input("Was steht in deinem Brief?")

if prompt or foto:
    # 1. User-Input
    with st.chat_message("user"):
        anzeige = prompt if prompt else "Hier ist mein Brief (Bild)."
        st.markdown(anzeige)
    st.session_state.messages.append({"role": "user", "content": anzeige})

    # 2. KI-Antwort
    with st.chat_message("assistant"):
        with st.spinner("Ich übersetze Beamten-Deutsch..."):
            system_prompt = "Du bist der Beamten-Zähmer. Nur Behörden-Themen! Erkläre einfach, markiere Fristen FETT."
            messages = [{"role": "system", "content": system_prompt}]
            
            if foto:
                b64 = bild_zu_base64(foto)
                messages.append({"role": "user", "content": [
                    {"type": "text", "text": prompt if prompt else "Analysiere das Bild."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
            else:
                messages.append({"role": "user", "content": prompt})

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=messages)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                
                # E-Mail schicken
                email_senden(st.session_state.user.email, antwort)
                
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
