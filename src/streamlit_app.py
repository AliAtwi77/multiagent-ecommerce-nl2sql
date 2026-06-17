# app.py
import os
import streamlit as st
import plotly.io as pio
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

# --- 1. Page Config ---
st.set_page_config(
    page_title="NL2SQL E-Commerce Assistant",
    page_icon="🛍️",
    layout="wide"
)

# --- 2. Sidebar: Settings & Visualization ---
with st.sidebar:
    st.header("🔧 Debug & Workflow")

    if st.checkbox("Show Workflow Diagram", value=False):
        st.subheader("Agent Workflow")
        try:
            resp = requests.get(f"{API_URL}/workflow-image", timeout=30)
            if resp.status_code == 200:
                st.image(resp.content, caption="LangGraph Workflow", use_column_width=True)
            else:
                st.warning("Could not generate graph image. Ensure 'graphviz' is installed.")
        except requests.RequestException as e:
            st.error(f"API connection error: {e}")

    st.markdown("---")
    st.markdown("### 💡 Example Questions")
    examples = [
        "How many orders were delivered?",
        "Top 5 product categories by sales?",
        "Find the top 10 customers who spent the most money across all their orders",
        "Which sellers have the most orders?"
    ]
    def set_input(text):
        st.session_state.user_input = text

    for ex in examples:
        st.button(ex, on_click=set_input, args=(ex,))

# --- 3. Chat Logic ---
if "messages" not in st.session_state:
    st.session_state.messages = [
    {"role": "assistant", "content": (
        "👋 **Welcome to the NL2SQL E-commerce Assistant!**\n\n"
        "I’m here to help you explore the e-commerce database using simple, natural language. "
        "You can ask me about:\n"
        "- Orders and their status\n"
        "- Customers and their locations\n"
        "- Products and categories\n"
        "- Payments and transactions\n"
        "- Reviews and ratings\n"
        "- Sellers and their information\n\n"
        "Just type your question, and I’ll fetch the answers for you—no SQL knowledge needed!\n"
    )}
]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "graph_json" in msg and msg["graph_json"]:
            try:
                fig = pio.from_json(msg["graph_json"])
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass
        if "sql" in msg and msg["sql"]:
            with st.expander("🔎 View SQL Query"):
                st.code(msg["sql"], language="sql")

if prompt := st.chat_input("Ask a question about your data...", key="user_input"):

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🤖 Thinking & Querying Database..."):
            try:
                resp = requests.post(f"{API_URL}/ask", json={"question": prompt}, timeout=120)
                resp.raise_for_status()
                response = resp.json()

                final_answer = response.get("final_answer", "No answer generated.")
                sql_query = response.get("query_generated", "")
                graph_json = response.get("graph_json", "")

                st.markdown(final_answer)

                if graph_json:
                    fig = pio.from_json(graph_json)
                    st.plotly_chart(fig, use_container_width=True)

                if sql_query:
                    with st.expander("🔎 View SQL Query"):
                        st.code(sql_query, language="sql")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_answer,
                    "sql": sql_query,
                    "graph_json": graph_json
                })

            except requests.RequestException as e:
                error_msg = f"⚠️ API connection error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"⚠️ An error occurred: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})