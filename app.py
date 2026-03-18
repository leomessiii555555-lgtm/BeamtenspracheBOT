import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io
import uuid
from streamlit.components.v1 import html

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Amtsschimmel-Zähmer STRENG", layout="wide")

# WICHTIG: Trage hier deine echte App-URL ein, sobald sie online ist!
# Beispiel: "https://deine-app.streamlit.app"
APP_URL = "https://deine-app-url.streamlit.app"

# API Clients initialisieren (aus den Streamlit Secrets)
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    PAYPAL_CLIENT_ID = st.secrets["PAYPAL_CLIENT_ID"]
except Exception as e:
    st.error("Fehler bei den API-Keys oder Secrets! Bitte prüfen.")
    st.stop()

# --- 2. AUTHENTIFIZIERUNG ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort:", type="password")
    if pw == "Amt123":
        st.session_state.auth = True
        if "user_id" not in st.session_state:
            st.session_state.user_id = str(uuid.uuid4())
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

# --- 3. DATENBANK-FUNKTIONEN ---
def get_user_stats(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        new_user = {"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_user).execute()
        return new_user
    return res.data[0]

def update_count(user_id, column, current_value):
    supabase.table("profiles").update({column: current_value + 1}).eq("id", user_id).execute()

def set_premium(user_id):
    supabase.table("profiles").update({"is_premium": True}).eq("id", user_id).execute()

# --- 4. ZAHLUNGS-CHECK (RE-ENTRY) ---
# Wenn der User von PayPal mit ?payment=success zurückkommt
if st.query_params.get("payment") == "success":
    set_premium(st.session_state.user_id)
    st.balloons()
    st.success("Zahlung erfolgreich! Deine Flatrate wurde aktiviert.")
    st.query_params.clear()
    st.rerun()

# Aktuelle Stats laden
stats = get_user_stats(st.session_state.user_id)

# --- 5. PAYPAL-BUTTON KOMPONENTE ---
def show_paypal_button():
    st.error("🛑 Limit erreicht! Kostenlose Nutzung (15 Texte / 3 Bilder) verbraucht.")
    st.info("Schalte jetzt die unbegrenzte Flatrate für 2,00 € frei:")
    
    success_url = f"{APP_URL}?payment=success"
    
    paypal_html = f"""
    <div id="paypal-button-container"></div>
    <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&currency=EUR"></script>
    <script>
      paypal.Buttons({{
        createOrder: function(data, actions) {{
          return actions.order.create({{
            purchase_units: [{{ amount: {{ value: '2.00' }} }}]
          }});
        }},
        onApprove: function(data, actions) {{
          return actions.order.capture().then(function(details) {{
            window.top.location.href = "{success_url}";
          }});
        }}
      }}).render('#paypal-button-container');
    </script>
    """
    html(paypal_html, height=350)

# --- 6. HILFSFUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 7. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Amtsschimmel-Zähmer")
    if stats['is_premium']:
        st.success("💎 PREMIUM: Unbegrenzt aktiv")
    else:
        st.write(f"📊 Verbrauch: {stats['text_count']}/15 Texte | {stats['image_count']}/3 Bilder")
    
    st.warning("Modus: STRENG & EFFIZIENT 🛑")
    uploaded_file = st.file_uploader("📸 Brief-Foto", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.rerun()

# --- 8. CHAT-HISTORIE ANZEIGEN ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 9. KI-INSTRUKTIONEN ---
system_instruction = (
    "IDENTITÄT: Du bist der 'Amtsschimmel-Zähmer'. Du übersetzt Beamtendeutsch in einfaches Deutsch."
    "\n\nSTRIKTE VERBOTE:"
    "\n- Beantworte NIEMALS Mathe-Aufgaben oder allgemeine Fragen."
    "\n- Wenn kein Behördenbrief vorliegt, lehne höflich ab."
    "\n\nANTWORT-STRUKTUR: ## 🎯 KLARTEXT, ## 🔍 DETAILS, ## 💰 FRISTEN, ## ⚡ SCHLACHTPLAN."
)

# --- 10. INPUT-LOGIK & PAYWALL-CHECK ---
user_input = st.chat_input("Nur Brief-Fragen...")
final_prompt = user_input

# Audio-Verarbeitung
if audio_data and audio_data.get('bytes'):
    audio_bio = io.BytesIO(audio_data['bytes'])
    audio_bio.name = "input.wav"
    trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
    final_prompt = trans.text

if final_prompt or uploaded_file:
    # Check ob Limit erreicht
    limit_erreicht = not stats['is_premium'] and (stats['text_count'] >= 15 or stats['image_count'] >= 3)
    
    if limit_erreicht:
        show_paypal_button()
    else:
        query = final_prompt if final_prompt else "Analysiere diesen Brief."
        st.session_state.messages.append({"role": "user", "content": query})
        
        with st.chat_message("user"):
            st.markdown(query)

        # Payload für OpenAI vorbereiten
        payload = [{"role": "system", "content": system_instruction}]
        for m in st.session_state.messages:
            payload.append({"role": m["role"], "content": m["content"]})
        
        if uploaded_file:
            img_b64 = encode_image(uploaded_file)
            payload.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            })
            update_count(st.session_state.user_id, "image_count", stats['image_count'])
        else:
            update_count(st.session_state.user_id, "text_count", stats['text_count'])

        # API Call
        with st.spinner("🤖 Denkt nach..."):
            try:
                res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=payload,
                    max_tokens=500
                )
                answer = res.choices[0].message.content
                with st.chat_message("assistant"):
                    st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Fehler: {e}")
