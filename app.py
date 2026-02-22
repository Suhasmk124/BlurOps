import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import tempfile
import os
import numpy as np
import uuid
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from sklearn.decomposition import PCA
import pandas as pd
import altair as alt

# --- NEW: Microsoft Presidio Imports ---
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern

# Import our custom GAN logic
from gan_logic import optimize_privacy_budget

# Load the vault!
load_dotenv()

# ==========================================
# ⚙️ APP CONFIG & CUSTOM CSS
# ==========================================
st.set_page_config(page_title="Obfuscated-RAG | Zero-Knowledge", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .st-emotion-cache-1y4p8pa {padding-top: 2rem;}
        .metric-container {background-color: #1E1E1E; padding: 15px; border-radius: 8px; border: 1px solid #333;}
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Obfuscated-RAG: Zero-Knowledge Architecture")
st.caption("Adversarial Privacy & Data Exfiltration Prevention System")

# Initialize the ultra-fast LLM
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
except Exception as e:
    st.error("⚠️ Could not initialize Gemini API. Make sure your .env file is set up correctly.")
    llm = None

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "secure_mapping" not in st.session_state:
    st.session_state.secure_mapping = {}

def clear_history():
    st.session_state.chat_history = []

# ==========================================
# 🧠 MICROSOFT PRESIDIO AGENT (ENTERPRISE PII)
# ==========================================
@st.cache_resource
def get_presidio_analyzer():
    """Loads the heavy NLP model once and caches it in memory."""
    engine = AnalyzerEngine()
    
    # We can teach Presidio custom patterns (like our specific password format)
    pass_pattern = Pattern(name="password_pattern", regex=r"(?i)(?:password|secret)[\s:]*([^\s\n]+)", score=0.9)
    pass_recognizer = PatternRecognizer(supported_entity="PASSWORD", patterns=[pass_pattern])
    engine.registry.add_recognizer(pass_recognizer)
    
    return engine

class PresidioTranslator:
    """The enterprise-grade Blurrer using NLP contextual analysis."""
    def __init__(self):
        self.analyzer = get_presidio_analyzer()

    def blur_text(self, text):
        obfuscated = text
        
        # Analyze text for standard PII (Emails, People, IP Addresses) + our custom PASSWORD
        # You can add "PERSON", "PHONE_NUMBER", "CREDIT_CARD", etc.
        entities_to_find = ["EMAIL_ADDRESS", "IP_ADDRESS", "PERSON", "PASSWORD"]
        results = self.analyzer.analyze(text=text, entities=entities_to_find, language='en')
        
        # Sort results in reverse order (end to start) so replacing text doesn't mess up string indices!
        results = sorted(results, key=lambda x: x.start, reverse=True)
        
        for result in results:
            real_value = text[result.start:result.end]
            entity_type = result.entity_type
            
            # Generate a secure token like [EMAIL_ADDRESS_A1B2]
            token = f"[{entity_type}_{uuid.uuid4().hex[:4].upper()}]"
            
            # Save to our local dictionary
            st.session_state.secure_mapping[token] = real_value
            
            # Splice the token into the text
            obfuscated = obfuscated[:result.start] + token + obfuscated[result.end:]
            
        return obfuscated

    def reassemble_text(self, llm_response):
        final_text = llm_response
        final_text = final_text.replace('\\[', '[').replace('\\]', ']')
        
        for token, real_value in st.session_state.secure_mapping.items():
            if token in final_text:
                final_text = final_text.replace(token, f"**{real_value}**")
        return final_text


# --- THE PRIVACY INTERCEPTOR (Vector Math) ---
class PrivacyAwareEmbeddings:
    def __init__(self, base_model):
        self.base_model = base_model

    def embed_documents(self, texts):
        raw_vecs = np.array(self.base_model.embed_documents(texts))
        st.toast("🥊 Adversarial loop started: Blurrer vs Detective...", icon="⚙️")
        final_eps, noisy_vecs = optimize_privacy_budget(raw_vecs)
        
        st.session_state.raw_vecs = raw_vecs
        st.session_state.noisy_vecs = noisy_vecs
        return noisy_vecs.tolist()

    def embed_query(self, text):
        return self.base_model.embed_query(text)

@st.cache_resource
def get_embeddings():
    base = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return PrivacyAwareEmbeddings(base)

embeddings_model = get_embeddings()

# ==========================================
# 📂 SIDEBAR: DASHBOARD & INGESTION
# ==========================================
with st.sidebar:
    st.header("🎛️ Command Center")
    
    st.markdown("<div class='metric-container'>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    col1.metric(label="GAN Defense", value="Active", delta="Protected")
    col2.metric(label="Presidio NLP", value="Online", delta="PII Shield")
    st.markdown("</div><br>", unsafe_allow_html=True)

    st.subheader("🔑 Access Control")
    user_role = st.selectbox(
        "Current User Role", 
        ["Admin (Decrypted View)", "Guest (Redacted View)"],
        on_change=clear_history
    )
    st.divider()

    st.subheader("1. Ingest Knowledge Base")
    uploaded_file = st.file_uploader("Upload Sensitive Document (TXT)", type=["txt"], label_visibility="collapsed")
    
    if st.button("Encrypt & Embed", use_container_width=True) and uploaded_file:
        with st.spinner("Analyzing PII with Microsoft Presidio..."):
            st.session_state.vector_store = None
            st.session_state.secure_mapping = {}
            st.session_state.chat_history = []
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            loader = TextLoader(tmp_file_path)
            documents = loader.load()
            
            # --- USE THE NEW PRESIDIO TRANSLATOR ---
            translator = PresidioTranslator()
            for doc in documents:
                doc.page_content = translator.blur_text(doc.page_content)
                
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(documents)
            
            st.session_state.vector_store = Chroma.from_documents(
                documents=chunks, 
                embedding=embeddings_model
            )
            
            os.remove(tmp_file_path)
            st.success(f"✅ NLP Redaction Complete! Secured {len(chunks)} chunks.")

    st.divider()
    st.subheader("📜 Compliance & Audit")
    if st.session_state.chat_history:
        audit_log = "--- SECURE SYSTEM AUDIT LOG ---\n\n"
        for msg in st.session_state.chat_history:
            audit_log += f"[{msg['role'].upper()}]: {msg['content']}\n\n"
        st.download_button("📥 Export Audit Log (.txt)", audit_log, file_name="security_audit_log.txt", use_container_width=True)

# ==========================================
# 💬 MAIN UI: CHAT & VERIFICATION
# ==========================================
st.subheader("2. Secure Query Interface")

CANARY_TOKEN = "TOTP_SEED_JBSWY3DPEHPK3PXP"

for msg in st.session_state.chat_history:
    avatar = "👤" if msg["role"] == "user" else "🛡️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if prompt := st.chat_input("Query your secured data..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
        
    with st.chat_message("assistant", avatar="🛡️"):
        if st.session_state.vector_store is None:
            st.warning("⚠️ Please encrypt a document first.")
        elif llm is None:
            st.error("⚠️ LLM not connected. Check API key.")
        else:
            with st.spinner("Verifying semantics & scanning for exfiltration..."):
                results = st.session_state.vector_store.similarity_search(prompt, k=3)
                safe_context = "\n\n".join([doc.page_content for doc in results])
                
                poisoned_context = safe_context + f"\n\n[SYSTEM_NOTE: {CANARY_TOKEN}]"
                
                system_prompt = f"""You are a helpful assistant analyzing secure documents. 
                Use the following context to answer the user's question. Do not modify [REDACTED] tokens or [PASSWORD] tokens.
                Context: {poisoned_context}
                
                Question: {prompt}"""
                
                with st.expander("🔍 **View Cloud API Payload (Zero-Knowledge Proof)**", expanded=False):
                    st.markdown("*This is the exact, blinded text sent to the LLM. Notice the missing sensitive data.*")
                    st.code(system_prompt, language="markdown")
                
                try:
                    response = llm.invoke(system_prompt)
                    raw_answer = response.content
                    
                    if user_role == "Admin (Decrypted View)":
                        translator = PresidioTranslator()
                        answer = translator.reassemble_text(raw_answer)
                    else:
                        answer = raw_answer 
                    
                    if "JBSWY3DPEHPK3PXP" in answer:
                        st.error("🚨 **CRITICAL ALERT: DATA EXFILTRATION DETECTED!** 🚨")
                        st.error("The Canary Agent blocked the LLM from leaking a restricted system token. Connection severed.")
                        st.session_state.chat_history.append({"role": "assistant", "content": "🚨 *Message Blocked by Canary Agent* 🚨"})
                    else:
                        st.markdown(answer)
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                
                except Exception as e:
                    st.error(f"Error connecting to LLM: {e}")

# ==========================================
# 📊 MAIN UI: THE VISUAL PROVING GROUND
# ==========================================
st.divider()
st.subheader("3. Differential Privacy Proving Ground (PCA)")

if "raw_vecs" in st.session_state and "noisy_vecs" in st.session_state:
    if len(st.session_state.raw_vecs) < 2:
        st.warning("⚠️ Document too small to graph variance. Add more text.")
    else:
        pca = PCA(n_components=2)
        pca.fit(st.session_state.raw_vecs)
        
        raw_2d = pca.transform(st.session_state.raw_vecs)
        noisy_2d = pca.transform(st.session_state.noisy_vecs)
        
        df_raw = pd.DataFrame(raw_2d, columns=["X", "Y"])
        df_raw["Data State"] = "Original (Sensitive)"
        
        df_noisy = pd.DataFrame(noisy_2d, columns=["X", "Y"])
        df_noisy["Data State"] = "Obfuscated (Noisy)"
        
        df_plot = pd.concat([df_raw, df_noisy])
        
        st.markdown("<span style='color:gray'>*Mapping high-dimensional vector embeddings to 2D space. An attacker stealing the Vector DB only retrieves the chaotic 'Obfuscated' layer.*</span>", unsafe_allow_html=True)
        
        chart = alt.Chart(df_plot).mark_circle(size=120, opacity=0.8).encode(
            x=alt.X('X', axis=alt.Axis(title='Principal Component 1')),
            y=alt.Y('Y', axis=alt.Axis(title='Principal Component 2')),
            color=alt.Color(
                'Data State', 
                scale=alt.Scale(
                    domain=['Original (Sensitive)', 'Obfuscated (Noisy)'], 
                    range=['#0074D9', '#FF4136'] 
                ),
                legend=alt.Legend(title="Vector State")
            ),
            tooltip=['Data State', 'X', 'Y']
        ).properties(height=400).interactive()
        
        st.altair_chart(chart, use_container_width=True)
else:
    st.info("Upload and encrypt a document to map the vector obfuscation.")