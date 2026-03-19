import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. SETUP ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

try:
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]
    O_KEY = st.secrets["OPENAI_API_KEY"]
    # Deine PayPal-Link Vorlage aus den Secrets (z.B. https://www.paypal.me/deinname/2)
    PAYPAL_URL = st.secrets.get("PAYPAL_URL", "https://www.paypal.me")

    supabase: Client = create_client(S_URL, S_KEY)
    openai_client = OpenAI(api_key=O_KEY)
except Exception as e:
    st.error(f"Fehler beim Laden der Secrets: {e}")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(datei):
    """Wandelt ein Foto in Text für die KI um."""
    return base64.b64encode(datei.read()).decode('utf-8')

def get_user_stats(user_id):
    """Holt die aktuellen Zählerstände des Nutzers aus Supabase."""
    res = supabase.table("profiles").select("messages_count, images_count, is_premium").eq("id", user_id).single().execute()
    return res.data

def update_user_stats(user_id, col):
    """Erhöht den Zähler in der Datenbank um 1."""
    # Aktuellen Wert holen
    current = get_user_stats(user_id)
    new_val = current[col] + 1
    supabase.table("profiles").update({col: new_val}).eq("id", user_id).execute()

# --- 3. LOGIN & REGISTRIERUNG ---

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🛡️ Beamten-Zähmer: Login")
    t1, t2 = st.tabs(["Anmelden", "Konto erstellen"])
    
    with t2:
        r_email = st.text_input("E-Mail", key="r_mail")
        r_pw = st.text_input("Passwort", type="password", key="r_pw")
        if st.button("Jetzt Registrieren"):
            try:
                res = supabase.auth.sign_up({"email": r_email, "password": r_pw})
                if res.user:
                    # Initialen Eintrag in der Profile-Tabelle erstellen
                    supabase.table("profiles").insert({
                        "id": res.user.id, 
                        "messages_count": 0, 
                        "images_count": 0, 
                        "is_premium": False
                    }).execute()
                    st.success("✅ Konto erstellt! Du kannst dich jetzt anmelden.")
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

# --- 4. PRÜFUNG DER LIMITS ---

user_data = get_user_stats(st.session_state.user.id)
is_premium = user_data.get("is_premium", False)
m_count = user_data.get("messages_count", 0)
i_count = user_data.get("images_count", 0)

limit_erreicht = False
if not is_premium:
    if m_count >= 15 or i_count >= 3:
        limit_erreicht = True

# --- 5. HAUPT-APP ---

with st.sidebar:
    st.header("Konto-Status")
    if is_premium:
        st.success("💎 Premium Account")
    else:
        st.info(f"Nutzung: {m_count}/15 Texte, {i_count}/3 Bilder")
    
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

st.title("🛡️ Der Beamten-Zähmer")

if limit_erreicht:
    st.warning("⚠️ Dein Gratis-Limit ist erreicht!")
    st.write("Um den Beamten-Zähmer weiter zu nutzen, schalte die Flatrate für einmalig 2€ frei.")
    st.link_button("Jetzt 2€ per PayPal zahlen", PAYPAL_URL)
    st.info("Hinweis: Nach der Zahlung kann es einen Moment dauern, bis dein Status auf 'Premium' springt.")
    st.stop()

# Foto-Upload
foto = st.sidebar.file_uploader("Brief scannen", type=["jpg", "png", "jpeg"])
if foto:
    st.sidebar.image(foto)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Was steht in deinem Brief?")

if prompt or foto:
    # 1. User-Input anzeigen
    with st.chat_message("user"):
        anzeige = prompt if prompt else "Hier ist mein Brief (Bild)."
        st.markdown(anzeige)
    st.session_state.messages.append({"role": "user", "content": anzeige})

    # 2. KI-Antwort generieren
    with st.chat_message("assistant"):
        with st.spinner("Ich übersetze..."):
            system_prompt = "Du bist der Beamten-Zähmer. Nur Behörden-Themen! Erkläre einfach, markiere Fristen FETT."
            msgs = [{"role": "system", "content": system_prompt}]
            
            if foto:
                b64 = bild_zu_base64(foto)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": prompt if prompt else "Analysiere das Bild."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
                update_user_stats(st.session_state.user.id, "images_count")
            else:
                msgs.append({"role": "user", "content": prompt})
                update_user_stats(st.session_state.user.id, "messages_count")

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"KI-Fehler: {e}")
