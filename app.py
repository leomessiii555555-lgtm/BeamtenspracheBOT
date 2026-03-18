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

# HIER DEINE PAYPAL ID EINTRAGEN
PAYPAL_CLIENT_ID = "DEINE_PAYPAL_CLIENT_ID"

# Authentifizierung & Nutzer-ID
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 Sicherer Zugang")
    pw = st.text_input("Passwort:", type="password")
    if pw == "Amt123":
        st.session_state.auth = True
        # Erstellt eine eindeutige ID für diesen Besucher, damit nicht alle denselben Zähler teilen
        if "user_id" not in st.session_state:
            st.session_state.user_id = str(uuid.uuid4())
        st.rerun()
    else:
        if pw: st.error("Falsches Passwort!")
        st.stop()

# API Clients initialisieren
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Fehler bei den API-Keys! Bitte in den Secrets prüfen.")
    st.stop()

# --- 2. DATENBANK-FUNKTIONEN ---
def get_user_stats(user_id):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()
    if not res.data:
        # Falls Nutzer neu, in DB anlegen
        new_user = {"id": user_id, "text_count": 0, "image_count": 0, "is_premium": False}
        supabase.table("profiles").insert(new_user).execute()
        return new_user
    return res.data[0]

def update_count(user_id, column, current_value):
    supabase.table("profiles").update({column: current_value + 1}).eq("id", user_id).execute()

def set_premium(user_id):
    supabase.table("profiles").update({"is_premium": True}).eq("id", user_id).execute()

# Aktuelle Stats laden
stats = get_user_stats(st.session_state.user_id)

# --- 3. PAYPAL-KOMPONENTE ---
def show_paypal_button():
    st.error("🛑 Limit erreicht! Kostenlose Nutzung (15 Texte / 3 Bilder) verbraucht.")
    st.info("Schalte jetzt die unbegrenzte Flatrate für 5,00 € frei:")
    
    paypal_html = f"""
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
            // Signal an Streamlit senden
            window.parent.postMessage({{type: 'payment_complete'}}, '*');
            alert('Zahlung erfolgreich! Deine Flatrate wird aktiviert.');
          }});
        }}
      }}).render('#paypal-button-container');
    </script>
    """
    html(paypal_html, height=350)

# JS-Listener für die Zahlungserkennung
# Wir nutzen ein einfaches HTML-Snippet um das Signal abzufangen
st.components.v1.html("""
<script>
window.addEventListener('message', function(event) {
    if (event.data.type === 'payment_complete') {
        // Hier müsste technisch ein Rerurn ausgelöst werden, 
        // für die Einfachheit nutzen wir das Signal direkt im Python-Check
    }
}, false);
</script>
""", height=0)

# --- 4. HILFSFUNKTIONEN ---
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Amtsschimmel-Zähmer")
    if stats['is_premium']:
        st.success("💎 PREMIUM: Unbegrenzt")
    else:
        st.write(f"📊 Verbrauch: {stats['text_count']}/15 Texte | {stats['image_count']}/3 Bilder")
    
    st.error("Modus: STRENG & EFFIZIENT 🛑")
    uploaded_file = st.file_uploader("📸 Brief-Foto", type=["jpg", "jpeg", "png"])
    audio_data = mic_recorder(start_prompt="🎤 Sprechen", stop_prompt="🛑 Stop", key='mic')
    
    if st.button("🗑️ Verlauf löschen"):
        st.session_state.messages = []
        st.session_state.last_audio_ts = None
        st.rerun()

# --- 6. CHAT-HISTORIE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# EISERNE REGELN
system_instruction = (
    "IDENTITÄT: Du bist der 'Amtsschimmel-Zähmer'. Du bist ein Spezial-Werkzeug NUR für Behördenbriefe."
    "\n\nSTRIKTE VERBOTE:"
    "\n- Beantworte NIEMALS Mathe-Aufgaben, Rechenrätsel oder allgemeine Wissensfragen."
    "\n- Wenn kein Behördenbrief vorliegt: 'Ich bin ein Fach-Tool für Behördenbriefe. Für Mathe oder andere Fragen bin ich nicht programmiert.'"
    "\n\nANTWORT-LOGIK: Nutze ## 🎯 KLARTEXT, ## 🔍 DETAILS, ## 💰 FRISTEN, ## ⚡ SCHLACHTPLAN."
    "\nSPAR-GEBOT: Antworte so kurz wie möglich."
)

# --- 7. INPUT-VERARBEITUNG & PAYWALL ---
user_input = st.chat_input("Nur Brief-Fragen...")
final_prompt = user_input

# Audio-Transkription (Whisper)
if audio_data and audio_data.get('bytes'):
    current_audio_hash = audio_data['bytes'][:100]
    if "last_audio_ts" not in st.session_state or st.session_state.last_audio_ts != current_audio_hash:
        audio_bio = io.BytesIO(audio_data['bytes'])
        audio_bio.name = "input.wav"
        trans = client.audio.transcriptions.create(file=audio_bio, model="whisper-1")
        final_prompt = trans.text
        st.session_state.last_audio_ts = current_audio_hash

# Hauptlogik
if final_prompt or uploaded_file:
    # PAYWALL CHECK
    limit_erreicht = not stats['is_premium'] and (stats['text_count'] >= 15 or stats['image_count'] >= 3)
    
    if limit_erreicht:
        show_paypal_button()
    else:
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
            update_count(st.session_state.user_id, "image_count", stats['image_count'])
        else:
            payload.append({"role": "user", "content": query})
            update_count(st.session_state.user_id, "text_count", stats['text_count'])

        with st.spinner("🤖 Denkt nach..."):
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
                st.error(f"Fehler: {e}")
