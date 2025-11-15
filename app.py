import streamlit as st
import json
from datetime import datetime
import os

# Page config
st.set_page_config(
    page_title="TalentScout - AI Hiring Assistant",
    page_icon="🤖",
    layout="centered"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
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
    st.session_state.stage = 'greeting'
    st.session_state.tech_questions_asked = 0
    st.session_state.conversation_active = True

# LLM Integration
def call_llm(prompt, system_prompt):
    """
    Call LLM API. You can use:
    - OpenAI API (requires key)
    - Anthropic API (requires key)
    - Groq API (free tier available)
    - Together AI (free tier available)
    """
    try:
        # Example using OpenAI (replace with your preferred API)
        import openai
        
        # Set your API key here or use environment variable
        openai.api_key = os.getenv("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
        
        if not openai.api_key:
            return "⚠️ Please configure your API key in the .streamlit/secrets.toml file or environment variables."
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error calling LLM: {str(e)}\n\nPlease check your API configuration."

# Prompt templates
SYSTEM_PROMPTS = {
    'greeting': """You are a friendly AI hiring assistant for TalentScout, a recruitment agency. 
    Greet the candidate warmly and briefly explain that you'll be collecting their information 
    and asking some technical questions. Keep it concise and professional.""",
    
    'collect_info': """You are collecting candidate information. Based on what's already collected,
    ask for the next missing piece of information in a natural, conversational way.
    Missing info will be provided in the prompt. Ask only ONE question at a time.
    Be professional but friendly.""",
    
    'generate_questions': """You are a technical interviewer. Generate {num} relevant technical 
    questions based on the candidate's tech stack. Questions should:
    - Be specific to the technologies mentioned
    - Range from intermediate to advanced level
    - Test practical knowledge and problem-solving
    - Be clear and concise
    Return ONLY the questions, numbered 1-{num}.""",
    
    'evaluate_answer': """You are evaluating a technical answer. Provide brief, constructive feedback.
    Be encouraging but honest. Keep response under 50 words.""",
    
    'farewell': """Thank the candidate professionally for their time. Mention that the recruitment 
    team will review their responses and get back to them within 3-5 business days. Keep it brief."""
}

def get_missing_info():
    """Identify what information is still needed"""
    data = st.session_state.candidate_data
    required_fields = ['name', 'email', 'phone', 'experience', 'position', 'location', 'tech_stack']
    
    for field in required_fields:
        if data[field] is None:
            return field
    return None

def extract_info_from_response(user_input, field):
    """Extract information from user response"""
    # Simple extraction logic - can be enhanced with LLM
    user_input = user_input.strip()
    
    if field == 'experience':
        # Look for numbers
        import re
        numbers = re.findall(r'\d+', user_input)
        if numbers:
            return numbers[0] + ' years'
    
    return user_input

def generate_technical_questions(tech_stack):
    """Generate technical questions based on tech stack"""
    prompt = f"""Based on this tech stack: {tech_stack}
    
Generate 5 technical interview questions that assess practical knowledge and problem-solving.
Make questions specific, clear, and progressively challenging.
Format: Return only numbered questions (1-5), nothing else."""

    system_prompt = SYSTEM_PROMPTS['generate_questions'].format(num=5)
    questions = call_llm(prompt, system_prompt)
    return questions

def process_user_input(user_input):
    """Process user input based on conversation stage"""
    user_input_lower = user_input.lower().strip()
    
    # Check for exit keywords
    exit_keywords = ['bye', 'goodbye', 'exit', 'quit', 'end', 'stop', 'no thanks', 'that\'s all']
    if any(keyword in user_input_lower for keyword in exit_keywords):
        st.session_state.stage = 'farewell'
        farewell_msg = call_llm("Generate farewell message", SYSTEM_PROMPTS['farewell'])
        st.session_state.messages.append({"role": "assistant", "content": farewell_msg})
        st.session_state.conversation_active = False
        save_candidate_data()
        return
    
    # Stage-based processing
    if st.session_state.stage == 'greeting':
        # Move to info collection
        st.session_state.stage = 'collect_info'
        missing = get_missing_info()
        prompt = f"Ask for candidate's {missing}. Be friendly and professional."
        response = call_llm(prompt, SYSTEM_PROMPTS['collect_info'])
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    elif st.session_state.stage == 'collect_info':
        # Extract and store information
        missing = get_missing_info()
        if missing:
            info = extract_info_from_response(user_input, missing)
            st.session_state.candidate_data[missing] = info
            
            # Check if we need more info
            next_missing = get_missing_info()
            if next_missing:
                prompt = f"The candidate just provided their {missing}: {info}. Now ask for their {next_missing}."
                response = call_llm(prompt, SYSTEM_PROMPTS['collect_info'])
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                # All info collected, move to technical questions
                st.session_state.stage = 'technical_questions'
                tech_stack = st.session_state.candidate_data['tech_stack']
                
                transition_msg = f"Great! I have all your information. Now let's assess your technical skills in {tech_stack}. I'll ask you 5 questions."
                st.session_state.messages.append({"role": "assistant", "content": transition_msg})
                
                # Generate questions
                questions = generate_technical_questions(tech_stack)
                st.session_state.technical_questions = questions
                st.session_state.messages.append({"role": "assistant", "content": questions})
                st.session_state.messages.append({"role": "assistant", "content": "Please answer Question 1:"})
    
    elif st.session_state.stage == 'technical_questions':
        # Store answer
        st.session_state.candidate_data['technical_answers'].append({
            'question_number': st.session_state.tech_questions_asked + 1,
            'answer': user_input,
            'timestamp': datetime.now().isoformat()
        })
        
        st.session_state.tech_questions_asked += 1
        
        # Provide brief feedback
        feedback_prompt = f"Provide brief encouraging feedback on this answer: {user_input[:200]}"
        feedback = call_llm(feedback_prompt, SYSTEM_PROMPTS['evaluate_answer'])
        st.session_state.messages.append({"role": "assistant", "content": feedback})
        
        # Check if more questions needed
        if st.session_state.tech_questions_asked < 5:
            next_q_msg = f"Please answer Question {st.session_state.tech_questions_asked + 1}:"
            st.session_state.messages.append({"role": "assistant", "content": next_q_msg})
        else:
            # All questions answered
            st.session_state.stage = 'farewell'
            farewell_msg = call_llm("Generate farewell message", SYSTEM_PROMPTS['farewell'])
            st.session_state.messages.append({"role": "assistant", "content": farewell_msg})
            st.session_state.conversation_active = False
            save_candidate_data()

def save_candidate_data():
    """Save candidate data to JSON file"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"candidate_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(st.session_state.candidate_data, f, indent=2)
        
        st.success(f"✅ Candidate data saved to {filename}")
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")

# UI
st.markdown('<div class="main-header"><h1>🤖 TalentScout AI Hiring Assistant</h1><p>Intelligent Candidate Screening</p></div>', unsafe_allow_html=True)

# Display chat history
chat_container = st.container()
with chat_container:
    # Initial greeting if no messages
    if len(st.session_state.messages) == 0:
        greeting = call_llm("Greet the candidate", SYSTEM_PROMPTS['greeting'])
        st.session_state.messages.append({"role": "assistant", "content": greeting})
    
    # Display all messages
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'<div class="chat-message user-message">👤 <b>You:</b><br>{message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-message assistant-message">🤖 <b>Assistant:</b><br>{message["content"]}</div>', unsafe_allow_html=True)

# Chat input
if st.session_state.conversation_active:
    user_input = st.chat_input("Type your response here...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Process input
        process_user_input(user_input)
        
        # Rerun to update display
        st.rerun()
else:
    st.info("💼 Conversation ended. Thank you for your time!")
    
    # Show summary
    with st.expander("📋 View Collected Information"):
        st.json(st.session_state.candidate_data)
    
    if st.button("🔄 Start New Conversation"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Sidebar
with st.sidebar:
    st.header("📊 Interview Progress")
    
    # Progress indicators
    total_fields = 7
    filled_fields = sum(1 for v in st.session_state.candidate_data.values() if v is not None and v != [])
    progress = filled_fields / total_fields
    
    st.progress(progress)
    st.write(f"Information collected: {filled_fields}/{total_fields}")
    
    st.write(f"Technical questions answered: {st.session_state.tech_questions_asked}/5")
    
    st.markdown("---")
    st.header("ℹ️ About")
    st.write("This AI assistant helps TalentScout screen candidates efficiently by collecting information and assessing technical skills.")
    
    st.markdown("---")
    st.caption("💡 Type 'bye' or 'exit' to end the conversation anytime")