import json

import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text

from main import ReservationAssistant


st.set_page_config(
    page_title="TableTalk Reservations",
    page_icon="🎙️",
    layout="wide"
)


# ---------------------------------------------------------
# Session initialization
# ---------------------------------------------------------

if "assistant" not in st.session_state:
    st.session_state.assistant = ReservationAssistant()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": st.session_state.assistant.last_reply
        }
    ]

if "turn_key" not in st.session_state:
    st.session_state.turn_key = 0

if "speak_text" not in st.session_state:
    st.session_state.speak_text = (
        st.session_state.assistant.last_reply
    )


assistant = st.session_state.assistant


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("🎙️ TableTalk")
st.subheader("Rule-Based Voice Assistant for Restaurant Reservations")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Physical Tables", "8")

with col2:
    st.metric("Booking Duration", "30 minutes")

with col3:
    st.metric("Opening Hours", "12 PM – 12 AM")

st.caption(
    "Bookings start every 30 minutes from 12:00 PM to 11:30 PM. "
    "Each reservation is assigned a physical table from T1 to T8."
)

st.info(
    "Demo application: reservation data is stored in memory. "
    "Bookings remain during this app session but are cleared "
    "when the Python app process restarts."
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

with st.sidebar:
    st.header("How to use")

    st.write("1. Choose a date.")
    st.write("2. Tell TableTalk how many people are coming.")
    st.write("3. Choose a time.")
    st.write("4. Provide your name after availability is checked.")
    st.write("5. Use your reservation reference to cancel or update.")

    st.divider()

    st.write("**Cancel:** Say `cancel booking`.")
    st.write("**Update:** Say `change time`, `change date`, or `change number of people`.")
    st.write("**New booking:** Say `book another`.")

    st.divider()

    if st.button(
        "Start a new conversation",
        use_container_width=True
    ):
        assistant.reset()

        st.session_state.messages = [
            {
                "role": "assistant",
                "content": assistant.last_reply
            }
        ]

        st.session_state.speak_text = assistant.last_reply
        st.session_state.turn_key += 1
        st.rerun()


# ---------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------

def submit_message(text):
    text = text.strip()

    if not text:
        return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": text
        }
    )

    response = st.session_state.assistant.handle(text)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response
        }
    )

    st.session_state.speak_text = response
    st.session_state.turn_key += 1


# ---------------------------------------------------------
# Conversation history
# ---------------------------------------------------------

st.header("Conversation")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])


# ---------------------------------------------------------
# Voice output
# ---------------------------------------------------------

pending_speech = st.session_state.get("speak_text")

if pending_speech:
    speech_json = json.dumps(pending_speech)

    components.html(
        """
        <div style="font-family: Arial, sans-serif; padding: 2px;">
            <button
                id="voiceButton"
                style="
                    padding: 8px 14px;
                    border-radius: 8px;
                    border: 1px solid #888;
                    cursor: pointer;
                    background: #f4f4f4;
                    color: #111;
                "
            >
                🔊 Enable voice / Repeat latest response
            </button>
        </div>

        <script>
            const message = %s;

            function speakMessage() {
                if (!("speechSynthesis" in window)) {
                    return;
                }

                window.speechSynthesis.cancel();

                const utterance =
                    new SpeechSynthesisUtterance(message);

                utterance.lang = "en-US";
                utterance.rate = 1;
                utterance.pitch = 1;

                window.speechSynthesis.speak(utterance);
            }

            window.addEventListener("load", function () {
                speakMessage();
            });

            document.getElementById("voiceButton").addEventListener(
                "click",
                speakMessage
            );
        </script>
        """ % speech_json,
        height=55
    )

    st.session_state.speak_text = None

elif st.button("🔊 Repeat latest assistant response"):
    latest_response = assistant.last_reply
    st.session_state.speak_text = latest_response
    st.rerun()


# ---------------------------------------------------------
# User input: microphone or typing
# ---------------------------------------------------------

st.divider()
st.header("Talk to TableTalk")

st.caption(
    "Use the microphone to speak in English, or type your message below."
)

spoken_text = speech_to_text(
    language="en",
    use_container_width=True,
    just_once=True,
    key="speech_%s" % st.session_state.turn_key
)

if spoken_text:
    submit_message(spoken_text)
    st.rerun()


with st.form("message_form", clear_on_submit=True):
    typed_text = st.text_input(
        "Your message",
        placeholder=(
            "Examples: 26 October, four people, 5 PM, "
            "cancel booking, change time"
        )
    )

    submitted = st.form_submit_button(
        "Send",
        use_container_width=True
    )

if submitted and typed_text:
    submit_message(typed_text)
    st.rerun()


# ---------------------------------------------------------
# Available time slots
# ---------------------------------------------------------

if assistant.screen_notice:
    st.divider()
    st.subheader("Availability")
    st.info(assistant.screen_notice)


# ---------------------------------------------------------
# Live reservation records
# ---------------------------------------------------------

st.divider()
st.header("Reservation Records")

st.caption(
    "Confirmed reservations only. Cancelled bookings are removed; "
    "updated bookings appear with their latest details."
)

if assistant.reservations:
    rows = []

    for booking in assistant.reservations:
        rows.append(
            {
                "Reservation Reference": booking["reference"],
                "Table ID": booking["table_id"],
                "Customer Name": booking["name"],
                "Date": booking["date"],
                "Start Time": assistant._format_time(booking["time"]),
                "End Time": booking["end_time"],
                "Party Size": booking["party_size"],
                "Duration (minutes)": booking["duration_minutes"],
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Use the Reservation Reference (for example, TT1001) "
        "when cancelling or changing a reservation. A physical "
        "table can have multiple bookings at different times."
    )
else:
    st.info("No confirmed reservations yet.")


# ---------------------------------------------------------
# Current conversation state
# ---------------------------------------------------------

with st.expander("Debug information"):
    st.write("Conversation state:", assistant.state)
    st.write("Pending action:", assistant.pending_action)
    st.write("Pending reservation:", assistant.pending_reference)
    st.write("Pending change:", assistant.pending_change_field)

    st.json(
        {
            "draft": {
                "date": (
                    assistant.slots["date"].isoformat()
                    if assistant.slots["date"]
                    else None
                ),
                "party_size": assistant.slots["party_size"],
                "time": assistant.slots["time"],
                "name": assistant.slots["name"],
            },
            "reservations": assistant.reservations,
        }
    )
