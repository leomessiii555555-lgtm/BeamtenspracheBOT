import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
import base64

# --- 1. SETUP ---
st.set_page_config(page_title="Beamten-Zähmer V3", layout="centered")

try:
    # Secrets laden
    S_URL = st.secrets["SUPABASE_URL"]
    S_KEY = st.secrets["SUPABASE_KEY"]
    O_KEY = st.secrets["OPENAI_API_KEY"]
    # Dein PayPal-Link aus den Secrets (z.B. https://www.paypal.me/deinname/2)
    PAYPAL_URL = st.secrets.get("PAYPAL_URL", "https://www.paypal.me")

    supabase: Client = create_client(S_URL, S_KEY)
    openai_client = OpenAI(api_key=O_KEY)
except Exception as e:
    st.error(f"Fehler beim Laden der Konfiguration: {e}")
    st.stop()

# --- 2. HILFSFUNKTIONEN ---

def bild_zu_base64(datei):
    """Wandelt ein Foto in Base64-Text um."""
    return base64.b64encode(datei.read()).decode('utf-8')

def get_or_create_user_stats(user_id):
    """Holt Stats aus Supabase oder erstellt Profil, falls es fehlt."""
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if len(res.data) == 0:
        # Falls kein Profil existiert, eines anlegen (verhindert 'not found' Fehler)
        new_profile = {"id": user_id, "messages_count": 0, "images_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_profile).execute()
        return new_profile
    return res.data[0]

def update_counter(user_id, column):
    """Erhöht den jeweiligen Zähler in der DB um +1."""
    stats = get_or_create_user_stats(user_id)
    new_val = stats[column] + 1
    supabase.table("profiles").update({column: new_val}).eq("id", user_id).execute()

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
                res = supabase.auth.sign_up({"email": r_email, "password": r_pw})
                if res.user:
                    # Profil sofort mit UPSERT anlegen (verhindert 'Already exists')
                    supabase.table("profiles").upsert({
                        "id": res.user.id, 
                        "messages_count": 0, 
                        "images_count": 0, 
                        "is_premium": False
                    }).execute()
                    st.success("✅ Konto erstellt! Du kannst dich jetzt anmelden.")
            except Exception as e:
                st.error(f"Registrierung fehlgeschlagen: {e}")

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

# --- 4. STATUS & LIMITS PRÜFEN ---

user_stats = get_or_create_user_stats(st.session_state.user.id)
is_premium = user_stats.get("is_premium", False)
m_count = user_stats.get("messages_count", 0)
i_count = user_stats.get("images_count", 0)

# Limit-Logik: 15 Texte ODER 3 Bilder
limit_erreicht = False
if not is_premium:
    if m_count >= 15 or i_count >= 3:
        limit_erreicht = True

# --- 5. HAUPT-APP ---

st.title("🛡️ Der Beamten-Zähmer")

with st.sidebar:
    st.header("Dein Status")
    if is_premium:
        st.success("💎 Premium (Unbegrenzt)")
    else:
        st.info(f"Texte: {m_count}/15\n\nBilder: {i_count}/3")
    
    st.divider()
    if st.button("Abmelden"):
        st.session_state.user = None
        st.rerun()

# Falls Limit erreicht -> Paywall anzeigen
if limit_erreicht:
    st.warning("⚠️ Gratis-Limit erreicht!")
    st.write("Um den Beamten-Zähmer weiter zu nutzen, schalte die Flatrate frei.")
    st.link_button("Jetzt für 2€ freischalten (PayPal)", PAYPAL_URL)
    st.stop()

# Foto-Upload in der Sidebar
foto = st.sidebar.file_uploader("Brief scannen (Bild)", type=["jpg", "png", "jpeg"])
if foto:
    st.sidebar.image(foto, caption="Dein Scan")

# Chat-Verlauf
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Eingabe
prompt = st.chat_input("Frage zum Brief stellen...")

if prompt or foto:
    # 1. User Nachricht
    with st.chat_message("user"):
        text = prompt if prompt else "Hier ist mein Brief."
        st.markdown(text)
    st.session_state.messages.append({"role": "user", "content": text})

    # 2. KI Antwort
    with st.chat_message("assistant"):
        with st.spinner("Zähme Beamten-Deutsch..."):
            system_msg = "Du bist der Beamten-Zähmer. Antworte einfach und markiere Fristen FETT."
            msgs = [{"role": "system", "content": system_msg}]
            
            if foto:
                b64 = bild_zu_base64(foto)
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": prompt if prompt else "Analysiere dieses Dokument."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]})
                update_counter(st.session_state.user.id, "images_count")
            else:
                msgs.append({"role": "user", "content": prompt})
                update_counter(st.session_state.user.id, "messages_count")

            try:
                response = openai_client.chat.completions.create(model="gpt-4o", messages=msgs)
                antwort = response.choices[0].message.content
                st.markdown(antwort)
                st.session_state.messages.append({"role": "assistant", "content": antwort})
            except Exception as e:
                st.error(f"Fehler: {e}")
