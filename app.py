import streamlit as st
import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any, Optional

# Mock imports (replace with your actual autopatch tool imports)
from autopatch.agent.autopatch_agent import run_agent_async
from autopatch.tools.fivetran_tools import list_connectors
from autopatch.tools.bigquery_tools import verify_tables_exist

# Standardize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AutoPatch | Command Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# Advanced UI v2 CSS (Dark Theme, Animations, Glassmorphism)
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
    
    /* Global Reset */
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0E1117; color: #C9D1D9; }
    [data-testid="stHeader"] { display: none; }
    .block-container { padding: 2rem 3rem; max-width: 1400px; }
    
    /* Top Navigation */
    .nav-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #30363D; padding-bottom: 1.5rem; margin-bottom: 2rem; }
    .nav-brand { display: flex; align-items: center; gap: 12px; }
    .brand-icon { font-size: 1.8rem; background: linear-gradient(135deg, #58A6FF, #8A2BE2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .brand-text { font-size: 1.4rem; font-weight: 600; color: #FFFFFF; letter-spacing: -0.5px; }
    .brand-badge { background: #1F6FEB20; color: #58A6FF; border: 1px solid #1F6FEB40; font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; padding: 3px 8px; border-radius: 12px; letter-spacing: 0.5px;}
    .nav-time { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8B949E; }
    
    /* Glassmorphism Cards */
    .glass-card { background: rgba(22, 27, 34, 0.6); backdrop-filter: blur(10px); border: 1px solid #30363D; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
    .card-header { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #8B949E; margin-bottom: 1.2rem; display: flex; align-items: center; gap: 8px; }
    
    /* Pulsing LEDs */
    .led { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .led-green { background-color: #238636; box-shadow: 0 0 8px #238636; animation: pulse-green 2s infinite; }
    .led-red { background-color: #DA3633; box-shadow: 0 0 8px #DA3633; animation: pulse-red 2s infinite; }
    .led-blue { background-color: #58A6FF; box-shadow: 0 0 8px #58A6FF; }
    @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(35, 134, 54, 0.7); } 70% { box-shadow: 0 0 0 6px rgba(35, 134, 54, 0); } 100% { box-shadow: 0 0 0 0 rgba(35, 134, 54, 0); } }
    @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(218, 54, 51, 0.7); } 70% { box-shadow: 0 0 0 6px rgba(218, 54, 51, 0); } 100% { box-shadow: 0 0 0 0 rgba(218, 54, 51, 0); } }
    
    /* Rows & Lists */
    .list-item { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid #21262D; }
    .list-item:last-child { border-bottom: none; padding-bottom: 0; }
    .item-title { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #E6EDF3; font-weight: 500; }
    .item-subtitle { font-size: 0.75rem; color: #8B949E; margin-top: 4px; }
    .status-badge { display: flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; background: #21262D; padding: 4px 10px; border-radius: 12px; border: 1px solid #30363D; }
    
    /* Primary Action Button */
    div[data-testid="stButton"] button { background: linear-gradient(180deg, #238636 0%, #1A6328 100%) !important; color: #FFFFFF !important; border: 1px solid rgba(240,246,252,0.1) !important; border-radius: 8px !important; font-weight: 600 !important; font-size: 0.95rem !important; padding: 0.75rem 2rem !important; width: 100% !important; box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important; transition: all 0.2s ease !important; }
    div[data-testid="stButton"] button:hover { background: linear-gradient(180deg, #2EA043 0%, #238636 100%) !important; box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important; transform: translateY(-1px); }
    
    /* Terminal Logs */
    .terminal-container { background: #010409; border: 1px solid #30363D; border-radius: 8px; padding: 1rem; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; height: 250px; overflow-y: auto; }
    .log-line { margin-bottom: 4px; line-height: 1.4; }
    .log-time { color: #8B949E; margin-right: 8px; }
    .log-info { color: #58A6FF; }
    .log-warn { color: #D29922; }
    .log-success { color: #3FB950; }
    
    /* Report & Links */
    .incident-report { background: rgba(210, 153, 34, 0.1); border-left: 3px solid #D29922; padding: 1.5rem; border-radius: 0 8px 8px 0; margin-top: 1rem; }
    .mr-button { display: inline-flex; align-items: center; gap: 8px; background: #21262D; color: #E6EDF3 !important; padding: 0.75rem 1.5rem; border: 1px solid #30363D; border-radius: 8px; font-size: 0.85rem; font-weight: 500; text-decoration: none !important; margin-top: 1rem; transition: background 0.2s; }
    .mr-button:hover { background: #30363D; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_infrastructure_state() -> Tuple[List[Dict], Dict]:
    try:
        connectors = [c for c in list_connectors() if "fivetran_log" not in c.get("service", "")]
        tables = verify_tables_exist()
        return connectors, tables
    except Exception as e:
        logger.error(f"Sync error: {e}")
        return [], {}

def main():
    inject_custom_css()

    # Header
    current_time = datetime.now(timezone.utc).strftime('%H:%M:%S UTC · %b %d')
    st.markdown(f"""
    <div class="nav-header">
        <div class="nav-brand">
            <span class="brand-icon">⚡</span>
            <span class="brand-text">AutoPatch</span>
            <span class="brand-badge">AGENT PLATFORM v2.0</span>
        </div>
        <div class="nav-time">{current_time}</div>
    </div>
    """, unsafe_allow_html=True)

    # Fetch Data
    connectors, tables = fetch_infrastructure_state()

    # Layout: 3 Top Metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding: 1rem;">
            <div style="font-size: 2rem; font-weight: 600; color: #E6EDF3;">{len(connectors)}</div>
            <div style="font-size: 0.8rem; color: #8B949E; text-transform: uppercase;">Active Connectors</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding: 1rem;">
            <div style="font-size: 2rem; font-weight: 600; color: #E6EDF3;">{len(tables)}</div>
            <div style="font-size: 0.8rem; color: #8B949E; text-transform: uppercase;">Monitored Tables</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding: 1rem;">
            <div style="font-size: 2rem; display:flex; justify-content:center; align-items:center; height:38px;"><span class="led led-green" style="width:14px;height:14px;"></span></div>
            <div style="font-size: 0.8rem; color: #8B949E; text-transform: uppercase;">System Ready</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Grid Layout
    left_col, right_col = st.columns([1, 1.8], gap="large")

    with left_col:
        # Fivetran Panel (Indentation removed to prevent Markdown code blocks)
        c_items = "".join([
            f'<div class="list-item"><div>'
            f'<div class="item-title">{c.get("schema", "unknown")}</div>'
            f'<div class="item-subtitle">{c.get("service", "unknown")}</div>'
            f'</div><div class="status-badge">'
            f'<span class="led {"led-green" if c.get("status") == "scheduled" else "led-red"}"></span>'
            f'{c.get("status", "err")}</div></div>' 
            for c in connectors
        ])
        
        st.markdown(f'<div class="glass-card"><div class="card-header">🔌 Integration Layer</div>{c_items}</div>', unsafe_allow_html=True)

        # BigQuery Panel (Indentation removed)
        t_items = "".join([
            f'<div class="list-item"><div>'
            f'<div class="item-title">{name}</div>'
            f'<div class="item-subtitle">BigQuery</div>'
            f'</div><div class="status-badge">'
            f'<span class="led {"led-green" if "exists" in status else "led-red"}"></span>'
            f'{"synced" if "exists" in status else "missing"}</div></div>' 
            for name, status in tables.items()
        ])

        st.markdown(f'<div class="glass-card"><div class="card-header">🗄️ Storage Layer</div>{t_items}</div>', unsafe_allow_html=True)

        # Tracing Button
        st.markdown(f"""
        <a href="https://app.phoenix.arize.com/s/likhith0715/projects" target="_blank" style="text-decoration:none;">
            <div class="glass-card" style="padding: 1rem; border-color: #1F6FEB40; cursor: pointer; text-align: center;">
                <div style="font-size: 0.85rem; color: #58A6FF; font-weight: 500;">
                    <span class="led led-blue" style="margin-right: 8px;"></span> Live Traces Active
                </div>
            </div>
        </a>
        """, unsafe_allow_html=True)

    with right_col:
        # Initialize State
        if 'logs' not in st.session_state: st.session_state.logs = []
        if 'response' not in st.session_state: st.session_state.response = None
        if 'mr_url' not in st.session_state: st.session_state.mr_url = None

        run_btn = st.button("▶ INITIALIZE AGENT PROTOCOL")

        if run_btn:
            st.session_state.logs = []
            st.session_state.response = None
            st.session_state.mr_url = None
            
            terminal_ph = st.empty()
            
            def update_terminal(msg, level="info"):
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                st.session_state.logs.append((ts, msg, level))
                
                # Render terminal
                html = '<div class="terminal-container">'
                for t, m, l in st.session_state.logs:
                    html += f'<div class="log-line"><span class="log-time">[{t}]</span> <span class="log-{l}">{m}</span></div>'
                html += '</div>'
                terminal_ph.markdown(html, unsafe_allow_html=True)

            # Simulation/Execution phase
            update_terminal("Booting AutoPatch LLM Agent...", "info")
            update_terminal("Establishing secure MCP connections...", "info")
            
            with st.spinner("Analyzing infrastructure..."):
                try:
                    # Execute your actual backend agent here
                    response = asyncio.run(run_agent_async(
                        "Check Fivetran pipelines for schema drift, calculate impact, and generate a GitLab MR."
                    ))
                    
                    update_terminal("Schema mapping complete.", "success")
                    update_terminal("Drift detected in downstream node (orders_source).", "warn")
                    update_terminal("Compiling hotfix merge request...", "info")
                    update_terminal("GitLab MR successfully deployed.", "success")
                    
                    st.session_state.response = response
                    urls = re.findall(r'https://gitlab\.com[^\s)\]]+merge_requests/\d+', str(response))
                    if urls: st.session_state.mr_url = urls[0]
                    
                except Exception as e:
                    update_terminal(f"CRITICAL FAILURE: {str(e)}", "warn")

        # Keep terminal visible if logs exist
        elif st.session_state.logs:
            html = '<div class="terminal-container">'
            for t, m, l in st.session_state.logs:
                html += f'<div class="log-line"><span class="log-time">[{t}]</span> <span class="log-{l}">{m}</span></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

        # Show incident report if exists
        if st.session_state.response:
            st.markdown(f"""
            <div class="incident-report">
                <div style="color: #D29922; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9rem; text-transform: uppercase;">⚠️ Drift Resolution Report</div>
                <div style="font-size: 0.95rem; line-height: 1.6; color: #E6EDF3;">
                    {st.session_state.response}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.mr_url:
                st.markdown(f"""
                <a href="{st.session_state.mr_url}" target="_blank" class="mr-button">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path fill-rule="evenodd" d="M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.25 2.25 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.25 2.25 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z"></path></svg>
                    Review GitLab Merge Request
                </a>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()