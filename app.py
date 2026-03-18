import streamlit as st
from openai import OpenAI
from supabase import create_client
import base64
from streamlit_mic_recorder import mic_recorder
import io
from streamlit.components.v1 import html

# --- 1. SETUP ---
st.set_page_config(page_title="Amtsschimmel-Zähmer STRENG", layout="wide")

# PayPal Client ID hier eintragen (aus deinem Dashboard kopiert)
PAYPAL_CLIENT_ID = "HIER_DEINE_CLIENT_ID_EINSETZEN"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort:", type="password")
    if pw == "Amt123":
        st.session_state.auth = True
        st.session_state.user_id = "standard_user" # Platzhalter für die DB
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("API-Key Fehler!")
    st.stop()

# --- 2. PAYWALL LOGIK ---
def get_user_stats(user_id):
    # Holt Daten aus Supabase oder erstellt neuen Eintrag
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        supabase.table("profiles").insert({"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}).execute()
        return {"text_count": 0, "image_count": 0, "is_premium": False}
    return res.data[0]

def show_paypal():
    st.error("🛑 Limit erreicht! Du hast 15 Nachrichten oder 3 Bilder verbraucht.")
    st.info("Schalte jetzt die unbegrenzte Nutzung für einmalig 5,00 € frei:")
    
    paypal_code = f"""
    <div id="paypal-button-container"></div>
    <script src="https://www.paypal.com/sdk/js?client-id={PAYPAL_CLIENT_ID}&currency=EUR"></script>
    <script>
      paypal.Buttons({{
        createOrder: function(data, actions) {{
          return actions.order.create({{
            purchase_units: [{{ amount: {{ value: '5.00' }} }}]
          }});
        }},
        onApprove: function(data, actions) {{
          return actions.order.capture().then(function(details) {{
            window.parent.postMessage({{type: 'payment_done'}}, '*');
            alert('Zahlung erfolgreich! Bitte lade die Seite neu.');
          }});
        }}
      }}).render('#paypal-button-container');
    </script>
    """
    html(paypal_code, height=350)

# Nutzerdaten laden
stats = get_user_stats(st.session_state.user_id)

# --- 3. FUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Amtsschimmel-Zähmer")
    if stats['is_premium']:
        st.success("💎 PREMIUM STATUS")
    else:
        st.info(f"📊 Verbrauch: {stats['text_count']}/15 Texte | {stats['image_count']}/3 Bilder")
    
    st.error("Modus: STRENG & EFFIZIENT 🛑")
    uploaded_file = st.file_uploader("📸 Brief-Foto", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 5. CHAT-LOGIK ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

system_instruction = (
    "IDENTITÄT: Du bist der 'Amtsschimmel-Zähmer'. Du bist ein Spezial-Werkzeug NUR für Behördenbriefe."
    "\n\nSTRIKTE VERBOTE: NIEMALS Mathe oder allgemeines Wissen."
    "\n\nANTWORT-LOGIK: Nutze Klartest, Details, Fristen, Schlachtplan."
)

# --- 6. INPUT & PAYWALL CHECK ---
user_input = st.chat_input("Nur Brief-Fragen...")
final_prompt = user_input

# Prüfen ob Paywall angezeigt werden muss
paywall_aktiv = not stats['is_premium'] and (stats['text_count'] >= 15 or stats['image_count'] >= 3)

if final_prompt or uploaded_file:
    if paywall_aktiv:
        show_paypal()
    else:
        # Normaler KI Ablauf
        query = final_prompt if final_prompt else "Analysiere diesen Brief."
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        payload = [{"role": "system", "content": system_instruction}]
        for m in st.session_state.messages[:-1]:
            payload.append({"role": m["role"], "content": m["content"]})
        
        if uploaded_file:
            img_b64 = encode_image(uploaded_file)
            payload.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "low"}}
                ]
            })
            # Bild-Zähler erhöhen
            supabase.table("profiles").update({"image_count": stats['image_count'] + 1}).eq("id", st.session_state.user_id).execute()
        else:
            payload.append({"role": "user", "content": query})
            # Text-Zähler erhöhen
            supabase.table("profiles").update({"text_count": stats['text_count'] + 1}).eq("id", st.session_state.user_id).execute()

        with st.spinner("🤖"):
            try:
                res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=payload,
                    max_tokens=450,
                    temperature=0.0
                )
                answer = res.choices[0].message.content
                with st.chat_message("assistant"):
                    st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Fehler: {e}") # --- DAS HIER GEHÖRT IN DIE app.py DATEI, NICHT IN SUPABASE ---
from streamlit_javascript import st_javascript

pay_signal = st_javascript("""
    window.addEventListener('message', function(event) {
        if (event.data.type === 'payment_done') {
            return true;
        }
    }, false);
""")

if pay_signal:
    supabase.table("profiles").update({"is_premium": True}).eq("id", st.session_state.user_id).execute()
    st.success("Zahlung empfangen! Du bist jetzt Premium-Nutzer. 🎉")
    st.balloons()
    st.rerun()
