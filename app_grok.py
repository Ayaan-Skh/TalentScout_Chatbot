import streamlit as st
import json
from datetime import datetime
import os
import requests

# --- Page config ---
st.set_page_config(
    page_title="TalentScout - AI Hiring Assistant",
    page_icon="🤖",
    layout="centered"
)

# --- Minimal custom CSS ---
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #065ede 30%, #164bc2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 2rem;
        word-wrap: break-word;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 2rem;
        word-wrap: break-word;
    }
</style>
""", unsafe_allow_html=True)

# --- Session state initialization (only our app keys) ---
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'candidate_data' not in st.session_state:
    st.session_state.candidate_data = {
        'name': None,
        'email': None,
        'phone': None,
        'experience': None,
        'position': None,
        'location': None,
        'tech_stack': None,
        'technical_answers': []
    }
if 'current_field_index' not in st.session_state:
    st.session_state.current_field_index = 0
if 'tech_questions_asked' not in st.session_state:
    st.session_state.tech_questions_asked = 0
if 'conversation_active' not in st.session_state:
    st.session_state.conversation_active = True
if 'technical_questions' not in st.session_state:
    st.session_state.technical_questions = ""
if 'stage' not in st.session_state:
    st.session_state.stage = 'greeting'  # greeting -> collect_info -> technical_questions -> done
if 'greeted' not in st.session_state:
    st.session_state.greeted = False
if 'last_user_message' not in st.session_state:
    st.session_state.last_user_message = None

# Field order and prompts
FIELD_ORDER = ['name', 'email', 'phone', 'experience', 'position', 'location', 'tech_stack']
FIELD_PROMPTS = {
    'name': 'full name',
    'email': 'email address',
    'phone': 'phone number',
    'experience': 'years of experience',
    'position': 'desired position',
    'location': 'current location',
    'tech_stack': 'tech stack (programming languages, frameworks, tools)'
}

# --- Groq API wrapper (keeps your original interface) ---
def call_groq_api(prompt, system_prompt):
    """Call Groq API (safe guard: returns message if API key missing)."""
    try:
        api_key = os.getenv("GROQ_API_KEY", st.secrets.get("GROQ_API_KEY", ""))

        if not api_key:
            return "⚠️ Add GROQ_API_KEY in environment or Streamlit secrets to enable AI responses."

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Groq API: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

# System prompts
SYSTEM_PROMPTS = {
    'greeting': """You are a friendly AI hiring assistant for TalentScout. 
Greet the candidate warmly and explain you'll collect their information and ask technical questions. Keep it to 2-3 sentences.""",

    'collect_info': """You are collecting candidate information. 
Ask for the specified information naturally and briefly. One short question only. If the prompt contains 'Thank them briefly', include a short thank you before the question.""",

    'generate_questions': """Generate 5 technical interview questions based on the tech stack.
Be specific to the technologies mentioned. Return ONLY numbered questions 1-5.""",

    'evaluate_answer': """Provide brief encouraging feedback in 1-2 sentences. Under 30 words.""",

    'farewell': """Thank the candidate professionally. Mention the team will review responses 
and contact them in 3-5 business days. Keep brief."""
}

def generate_technical_questions(tech_stack):
    prompt = f"Tech stack: {tech_stack}\n\nGenerate 5 specific technical questions. Format: numbered 1-5 only."
    return call_groq_api(prompt, SYSTEM_PROMPTS['generate_questions'])

def save_candidate_data():
    """Save to JSON"""
    try:
        os.makedirs('candidate_data', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = st.session_state.candidate_data.get('name', 'unknown') or 'unknown'
        name = str(name).replace(" ", "_")
        filename = f"candidate_data/{name}_{timestamp}.json"

        data_to_save = st.session_state.candidate_data.copy()
        with open(filename, 'w') as f:
            json.dump(data_to_save, f, indent=2)

        return f"✅ Data saved: `{filename}`"
    except Exception as e:
        return f"Error saving data: {str(e)}"

# --- Core logic, without any st.rerun() inside helpers --- #
def handle_greeting_stage():
    """Perform greeting only once."""
    if not st.session_state.greeted:
        greeting = call_groq_api("Greet the candidate for a hiring interview", SYSTEM_PROMPTS['greeting'])
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.greeted = True
        st.session_state.stage = 'collect_info'
        # Ask the first info field right away
        ask_next_info_field(is_first_field=True)

def ask_next_info_field(is_first_field=False):
    """Push an assistant message asking for the next info field."""
    if st.session_state.current_field_index < len(FIELD_ORDER):
        next_field = FIELD_ORDER[st.session_state.current_field_index]
        if is_first_field:
            prompt = f"Ask for their {FIELD_PROMPTS[next_field]}. One short question."
        else:
            prompt = f"Thank them briefly. Then ask for their {FIELD_PROMPTS[next_field]}. Keep short."

        response = call_groq_api(prompt, SYSTEM_PROMPTS['collect_info'])
        st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        # All info gathered -> proceed to technical questions
        st.session_state.stage = 'technical_questions'
        tech_stack = st.session_state.candidate_data.get('tech_stack') or "unspecified tech stack"
        transition_msg = f"Perfect! Now let's assess your **{tech_stack}** skills. I'll ask 5 questions."
        st.session_state.messages.append({"role": "assistant", "content": transition_msg})
        questions = generate_technical_questions(tech_stack)
        st.session_state.technical_questions = questions
        st.session_state.messages.append({"role": "assistant", "content": questions})
        # ask first technical question prompt
        st.session_state.messages.append({"role": "assistant", "content": "\n**Please answer Question 1:**"})

def process_user_input_info(user_input):
    """Store user input for the current info field and append next ask message (no rerun)."""
    idx = st.session_state.current_field_index
    if idx < len(FIELD_ORDER):
        current_field = FIELD_ORDER[idx]
        st.session_state.candidate_data[current_field] = user_input.strip()
        st.session_state.current_field_index += 1
        # Ask next field or move forward
        ask_next_info_field(is_first_field=False)
    else:
        # Defensive: if somehow called when all fields done, move to technical
        st.session_state.stage = 'technical_questions'
        ask_next_info_field()

def process_user_input_technical(user_input):
    """Store technical answer, request feedback from API, and proceed to next question or finish."""
    qa = {
        'question_number': st.session_state.tech_questions_asked + 1,
        'answer': user_input,
        'timestamp': datetime.now().isoformat()
    }
    st.session_state.candidate_data['technical_answers'].append(qa)
    st.session_state.tech_questions_asked += 1

    # Get feedback and append
    feedback_prompt = f"Brief encouraging feedback on the answer: {user_input[:200]}..."
    feedback = call_groq_api(feedback_prompt, SYSTEM_PROMPTS['evaluate_answer'])
    st.session_state.messages.append({"role": "assistant", "content": feedback})

    # Ask next or finish
    if st.session_state.tech_questions_asked < 5:
        next_q = f"\n**Please answer Question {st.session_state.tech_questions_asked + 1}:**"
        st.session_state.messages.append({"role": "assistant", "content": next_q})
    else:
        farewell = call_groq_api("Generate farewell", SYSTEM_PROMPTS['farewell'])
        st.session_state.messages.append({"role": "assistant", "content": farewell})
        save_message = save_candidate_data()
        st.session_state.messages.append({"role": "assistant", "content": save_message})
        st.session_state.conversation_active = False

# --- UI header ---
st.markdown('''
<div class="main-header">
    <h1>🤖 TalentScout AI Hiring Assistant</h1>
    <p>Intelligent Candidate Screening System</p>
</div>
''', unsafe_allow_html=True)

# Ensure greeting/first question happens once
if st.session_state.stage == 'greeting':
    handle_greeting_stage()

# Display chat messages
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'''
                <div class="chat-message user-message">
                    👤 <b>You:</b><br>{message["content"]}
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
                <div class="chat-message assistant-message">
                    🤖 <b>Assistant:</b><br>{message["content"]}
                </div>
                ''', unsafe_allow_html=True)

# Chat input and processing
if st.session_state.conversation_active:
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your response here...", key="user_input_key")
        submit_button = st.form_submit_button("Send")

    if submit_button:
        raw = (user_input or "").strip()
        if not raw:
            st.warning("Please type something before sending.")
        else:
            # simple duplicate guard: prevents accidental double-processing from UI quirks.
            if raw == st.session_state.get('last_user_message'):
                st.info("Duplicate message detected — ignored.")
            else:
                st.session_state.last_user_message = raw
                st.session_state.messages.append({"role": "user", "content": raw})

                # exit keywords
                if any(word in raw.lower() for word in ['bye', 'goodbye', 'exit', 'quit', 'end', 'stop']):
                    farewell = call_groq_api("Generate farewell", SYSTEM_PROMPTS['farewell'])
                    save_message = save_candidate_data()
                    st.session_state.messages.append({"role": "assistant", "content": farewell})
                    st.session_state.messages.append({"role": "assistant", "content": save_message})
                    st.session_state.conversation_active = False
                    # rerun to immediately show final messages
                    st.experimental_rerun()
                else:
                    # route by stage
                    if st.session_state.stage == 'collect_info':
                        process_user_input_info(raw)
                    elif st.session_state.stage == 'technical_questions':
                        process_user_input_technical(raw)
                    else:
                        st.session_state.messages.append({"role": "assistant", "content": "I'm not sure what to do next. Restarting interview."})
                        st.session_state.conversation_active = False

                    # IMPORTANT: single safe rerun so the assistant's next message shows immediately.
                    st.experimental_rerun()

else:
    st.info("💼 Interview completed! Thank you.")
    with st.expander("📋 View Collected Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Personal Info:**")
            st.write(f"Name: {st.session_state.candidate_data.get('name', 'N/A')}")
            st.write(f"Email: {st.session_state.candidate_data.get('email', 'N/A')}")
            st.write(f"Phone: {st.session_state.candidate_data.get('phone', 'N/A')}")
        with col2:
            st.write("**Professional Info:**")
            st.write(f"Experience: {st.session_state.candidate_data.get('experience', 'N/A')}")
            st.write(f"Position: {st.session_state.candidate_data.get('position', 'N/A')}")
            st.write(f"Location: {st.session_state.candidate_data.get('location', 'N/A')}")
        st.write(f"**Tech Stack:** {st.session_state.candidate_data.get('tech_stack', 'N/A')}")
        st.write(f"**Questions Answered:** {len(st.session_state.candidate_data['technical_answers'])}/5")

        if st.session_state.candidate_data['technical_answers']:
            st.markdown("---")
            st.subheader("Technical Responses")
            for i, ans in enumerate(st.session_state.candidate_data['technical_answers']):
                st.markdown(f"**Q{i+1} Answer:** {ans['answer']}")

    if st.button("🔄 Start New Interview"):
        # Reset our app-specific keys only
        st.session_state.messages = []
        st.session_state.candidate_data = {
            'name': None,
            'email': None,
            'phone': None,
            'experience': None,
            'position': None,
            'location': None,
            'tech_stack': None,
            'technical_answers': []
        }
        st.session_state.current_field_index = 0
        st.session_state.tech_questions_asked = 0
        st.session_state.conversation_active = True
        st.session_state.technical_questions = ""
        st.session_state.stage = 'greeting'
        st.session_state.greeted = False
        st.session_state.last_user_message = None
        st.experimental_rerun()  # single, explicit rerun on restart

# Sidebar / debug info
with st.sidebar:
    st.header("📊 Interview Progress")
    if st.session_state.stage != 'greeting':
        info_progress = st.session_state.current_field_index / len(FIELD_ORDER)
        st.progress(info_progress)
        st.write(f"**Info Collected:** {st.session_state.current_field_index}/{len(FIELD_ORDER)}")
    else:
        st.progress(0.0)
        st.write("**Info Collected:** 0/" + str(len(FIELD_ORDER)))

    st.write(f"**Tech Questions:** {st.session_state.tech_questions_asked}/5")

    with st.expander("🔍 Debug Info"):
        st.write(f"**Stage:** {st.session_state.stage}")
        st.write(f"**Field Index:** {st.session_state.current_field_index}")
        if st.session_state.current_field_index < len(FIELD_ORDER):
            st.write(f"**Next Field:** {FIELD_ORDER[st.session_state.current_field_index]}")
        st.write(f"**Messages:** {len(st.session_state.messages)}")
        st.write("**Stored Data:**")
        for field in FIELD_ORDER:
            value = st.session_state.candidate_data.get(field, 'N/A')
            st.caption(f"{field}: {value if value else 'None'}")

    st.markdown("---")
    st.header("✨ Features")
    st.write("✅ Robust state handling")
    st.write("✅ Context-aware responses")
    st.write("✅ Tech stack-based questions")
    st.markdown("---")
    st.caption("💡 Type 'bye' to end")
    st.caption("🔧 Built with Streamlit & Groq")
