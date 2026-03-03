import streamlit as st 
from Pathlib import Path
from agent.understand_agent import UnderstandAgent
import pandas as pd


def create_ui():
    st.set_page_config(page_title="AI Data Understand Agent", layout="wide")
    
    st.title("🤖 AI Data Understand Agent - Phase 1")
    st.markdown("Upload any CSV/Excel/JSON file and AI will understand it")
    
    # Initialize agent
    agent = UnderstandAgent(api_key=st.secrets.get("OPENAI_API_KEY", None))
    
    # Sidebar for API key
    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("OpenAI API Key", type="password")
        if api_key:
            agent.client.api_key = api_key
        
        st.divider()
        st.header("About")
        st.markdown("""
        **Phase 1: AI-Powered Data Understanding**
        - Week 1: Single file understanding
        - Week 2: Multi-file comparison + mapping
        """)
    
    # Main content
    tab1, tab2 = st.tabs(["📁 Single File Analysis (Week 1)", "🔄 File Comparison (Week 2)"])
    
    # Tab 1: Single file analysis
    with tab1:
        st.header("Upload a file to analyze")
        uploaded_file = st.file_uploader(
            "Choose a file", 
            type=['csv', 'xlsx', 'xls', 'json'],
            key="single"
        )
        
        if uploaded_file:
            # Save temporarily
            temp_path = f"data/temp/{uploaded_file.name}"
            Path("data/temp").mkdir(exist_ok=True)
            
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            with st.spinner("AI is analyzing your file..."):
                result = agent.analyze_file(temp_path)
            
            # Display results
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("📊 File Info")
                st.json({
                    "filename": result['file_info']['filename'],
                    "format": result['file_info']['format'],
                    "rows": result['file_info']['rows'],
                    "columns": len(result['file_info']['columns'])
                })
                
                st.subheader("🔍 Sample Data")
                st.dataframe(pd.DataFrame(result['file_info']['sample_rows']))
            
            with col2:
                st.subheader("🧠 AI Analysis")
                st.markdown(result['analysis'])
    
    # Tab 2: File comparison
    with tab2:
        st.header("Compare two files")
        
        col1, col2 = st.columns(2)
        
        with col1:
            file1 = st.file_uploader("File A", type=['csv', 'xlsx', 'xls', 'json'], key="file1")
        with col2:
            file2 = st.file_uploader("File B", type=['csv', 'xlsx', 'xls', 'json'], key="file2")
        
        if file1 and file2:
            # Save temporarily
            Path("data/temp").mkdir(exist_ok=True)
            
            path1 = f"data/temp/{file1.name}"
            path2 = f"data/temp/{file2.name}"
            
            with open(path1, 'wb') as f:
                f.write(file1.getbuffer())
            with open(path2, 'wb') as f:
                f.write(file2.getbuffer())
            
            with st.spinner("AI is comparing files..."):
                result = agent.compare_files(path1, path2)
            
            # Display results
            st.subheader("🔄 Comparison Results")
            
            if result['same_type']:
                st.success(f"✅ Both files are {result['data_type']} data (Confidence: {result['confidence']}%)")
                
                st.subheader("📋 Suggested Mappings")
                mappings_df = pd.DataFrame([
                    {"File B Column": k, "Maps to File A Column": v} 
                    for k, v in result['mappings'].items()
                ])
                st.dataframe(mappings_df)
                
                st.subheader("🔧 Transformations Needed")
                for i, step in enumerate(result['transformations'], 1):
                    st.markdown(f"{i}. {step}")
                
                # Save mapping button
                if st.button("💾 Save This Mapping"):
                    agent.save_mapping(file1.name, file2.name, result)
                    st.success("Mapping saved!")
            else:
                st.warning(f"⚠️ Files are different types: {result['reasoning']}")
            
            st.subheader("🧠 AI Reasoning")
            st.info(result['reasoning'])
