import os
import uuid
import hmac

import streamlit as st
from pathlib import Path
import pandas as pd

from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory
from langchain.memory import AstraDBChatMessageHistory
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage
from langchain.schema.runnable import RunnableMap
from langchain.callbacks.base import BaseCallbackHandler

import openai

print("School Chatbot Started")
st.set_page_config(page_title='School Sidekick', page_icon='🎓')

# Check for a unique session ID
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4()

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs):
        self.text += token
        self.container.markdown(self.text + "▌")

def check_password():
    """Verifies user credentials."""
    def login_form():
        with st.form("credentials"):
            st.text_input('Username', key='username')
            st.text_input('Password', type='password', key='password')
            st.form_submit_button('Login', on_click=password_entered)

    def password_entered():
        if st.session_state['username'] in st.secrets['passwords'] and \
           hmac.compare_digest(st.session_state['password'], st.secrets.passwords[st.session_state['username']]):
            st.session_state['password_correct'] = True
            st.session_state.user = st.session_state['username']
            del st.session_state['password']
        else:
            st.session_state['password_correct'] = False

    if st.session_state.get('password_correct', False):
        return True

    login_form()
    if "password_correct" in st.session_state:
        st.error('User not known or password incorrect')
    return False

def logout():
    """Clears the session state and reruns the app."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.experimental_rerun()

def load_model():
    """Loads the GPT-based model for generating responses."""
    return ChatOpenAI(
        temperature=0.3,
        model='gpt-4-1106-preview',
        streaming=True,
        verbose=True
    )

@st.cache_resource()
def load_memory(top_k_history):
    """Loads conversation memory for maintaining context."""
    return ConversationBufferWindowMemory(
        chat_memory=chat_history,
        return_messages=True,
        k=top_k_history,
        memory_key="chat_history",
        input_key="question",
        output_key='answer'
    )

def get_prompt(type):
    """Generates prompt template based on request type."""
    if type == 'Extended results':
        template = "Your task is to help students with their queries in an educational setting. Respond extensively with multiple sentences."
    elif type == 'Short results':
        template = "Respond to student queries in an educational setting with brief answers."
    else:
        template = custom_prompt

    return ChatPromptTemplate.from_messages([("system", template)])

if not check_password():
    st.stop()

username = st.session_state.user
language = st.secrets.languages[username]

# Load chat history from a database
chat_history = AstraDBChatMessageHistory(
    session_id=f"{username}_{st.session_state.session_id}",
    api_endpoint=os.environ["ASTRA_ENDPOINT"],
    token=st.secrets["ASTRA_TOKEN"]
)

with st.sidebar:
    logout_button = st.button('Logout')
    if logout_button:
        logout()

# Displaying and managing chat interactions
for message in st.session_state.messages:
    st.chat_message(message.type).markdown(message.content)

question = st.chat_input('What do you need help with today?')

if question:
    st.session_state.messages.append(HumanMessage(content=question))
    with st.chat_message('human'):
        st.markdown(question)

    model = load_model()
    memory = load_memory(top_k_history=5)

    inputs = RunnableMap({
        'chat_history': lambda x: x['chat_history'],
        'question': lambda x: x['question']
    })

    chain = inputs | get_prompt('Extended results') | model
    response = chain.invoke({'question': question, 'chat_history': memory.load_memory_variables({})})

    st.chat_message('assistant').markdown(response.content)
    st.session_state.messages.append(A
