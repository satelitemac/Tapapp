# VERSION: 35.1 - THE COHERENT GRAPH (FULL RESTORE + BLINDED)
import streamlit as st
from neo4j import GraphDatabase
import time, re, urllib.parse, random, requests, textwrap
from streamlit_agraph import agraph, Node, Edge, Config

# 1. CONFIGURACIÓN Y CSS
st.set_page_config(layout="wide", page_title="RADAR DJ PRO", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
    .stApp { background-color: #050505; }
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; padding-left: 5rem !important; padding-right: 5rem !important; margin-top: 0rem !important; }
    .art-title { font-size: 6vh; font-weight: 900; color: white; text-transform: uppercase; text-align: center; line-height: 1; margin-top: 0 !important; }
    .art-subtitle { font-size: 2.5vh; color: #ff4b4b; font-weight: 700; text-transform: uppercase; text-align: center; margin-bottom: 2vh; }
    .img-box { width: 100%; padding-top: 100%; position: relative; border-radius: 18px; overflow: hidden; border: 1px solid #333; margin-bottom: 1.5vh; background: #000; }
    .img-box img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
    .radar-box { background: rgba(20,20,20,0.9); padding: 1.8vh; border-radius: 12px; border-left: 5px solid #ff4b4b; margin-bottom: 1.2vh; }
    .label-tag { font-size: 0.9vh; font-weight: 800; color: #ff4b4b; text-transform: uppercase; margin-top: 0.8vh; display: block; }
    .bio-box { background: rgba(255,255,255,0.03); padding: 1.2vh; border-radius: 10px; color: #ccc; border: 1px solid #222; font-size: 1.25vh; margin-bottom: 1vh; height: 10vh; overflow-y: auto; }
    .bio-label { color: #888; text-transform: uppercase; font-size: 0.9vh; font-weight: 800; display: block; }
    .expanded-right-panel { background: rgba(15,15,15,0.98) !important; border: 2px solid #ff4b4b !important; padding: 2.5vh !important; border-radius: 12px !important; color: #ffffff !important; font-size: 2.2vh !important; line-height: 1.6 !important; height: 550px !important; overflow-y: auto !important; box-shadow: 0 0 25px rgba(255, 75, 75, 0.25); }
    .expanded-right-title { font-size: 2.6vh !important; color: #ff4b4b !important; font-weight: 900 !important; margin-bottom: 2vh !important; text-transform: uppercase !important; border-bottom: 1px solid #333; padding-bottom: 1vh; }
</style>""", unsafe_allow_html=True)

# 2. LÓGICA
URI, USER, PASS = "neo4j+s://3ba4e632.databases.neo4j.io", "3ba4e632", "MWwAJKrv6xxOC3cI17CR5-oKjCtKyN9IMnjwZa5KYKI"
VINILO_FALLBACK = "https://images.unsplash.com/photo-1603048588665-791ca8aea617?q=80&w=1000"

if "mapa_abierto" not in st.session_state: st.session_state.mapa_abierto = False
if "panel_derecho_contenido" not in st.session_state: st.session_state.panel_derecho_contenido = None
if "panel_derecho_titulo" not in st.session_state: st.session_state.panel_derecho_titulo = ""
if "mostrar_letras" not in st.session_state: st.session_state.mostrar_letras = False
if "last_d" not in st.session_state: st.session_state.last_d = None

def clean_bio(text):
    if not text: return ""
    if isinstance(text, list): text = text[0] if text else ""
    if not isinstance(text, str): text = str(text)
    return re.sub(r'\[url=[^\]]+\](.*?)\[/url\]|\[[^\]]+\]', r'\1', text, flags=re.IGNORECASE).strip()

@st.cache_resource
def get_driver(): return GraphDatabase.driver(URI, auth=(USER, PASS))

def fetch_data():
    try:
        with get_driver().session() as s:
            q = "MATCH (son:Song:Actual)-[:VERSION]->(r:Remix:Actual) MATCH (a:Artist:Actual)-[:INTERPRETA]->(son) OPTIONAL MATCH (staff:Artist)-[c:CONTRIBUTED_TO]->(r) RETURN son, r, son.display_artist as titulo_original, collect(DISTINCT a) as nodos_artistas, r.estilos_discogs as estilos_oficiales, r.name as remix_name, r.year as anio, collect(DISTINCT {name: staff.name, role: c.role}) as creditos_nodos LIMIT 1"
            res = s.run(q).single()
            prev = [dict(rec['r']) for rec in s.run("MATCH (r:Remix) WHERE NOT r:Actual RETURN r ORDER BY r.timestamp DESC LIMIT 2")]
            return res, prev
    except: return None, None

d, p = fetch_data()

# 3. INTERFAZ
if d:
    artistas = d['nodos_artistas']
    nombres_display = str(d.get('titulo_original') or " & ".join([a.get('name', 'UNKNOWN') for a in artistas])).upper()
    
    st.markdown(f'<div class="art-title">{d["son"]["name"]}</div><div class="art-subtitle">{nombres_display}</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2.1, 1.4], gap="large")
    
    with c1:
        st.markdown('<span style="color:#888; font-size: 1.4vh; font-weight:800; text-transform:uppercase;">History</span>', unsafe_allow_html=True)
        for track in (p or []):
            st.markdown(f'<div class="img-box"><img src="{track.get("foto") or VINILO_FALLBACK}"></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="img-box"><img src="{d["r"].get("foto") or VINILO_FALLBACK}"></div>', unsafe_allow_html=True)
    
    with c3:
        # BOTONES
        cols_b = st.columns(3)
        cols_b[0].link_button("DISCOGS", d['r'].get('discogs', "#"), use_container_width=True)
        cols_b[1].link_button("WIKI", d['son'].get('wiki', "#"), use_container_width=True)
        if cols_b[2].button("LYRICS", use_container_width=True): st.session_state.mostrar_letras = not st.session_state.mostrar_letras

        # INFO TÉCNICA
        estilos = d['estilos_oficiales'] or []
        st.markdown(f'''<div class="radar-box"><span class="label-tag">Version</span><span class="value-text">{d["remix_name"] or "ORIGINAL"}</span><span class="label-tag">Styles</span><span class="value-text">{" • ".join(estilos).upper()}</span></div>''', unsafe_allow_html=True)
        
        # --- BLOQUE DERECHO ÚNICO (650px) ---
        with st.container(height=650, border=False):
            # MODO AMPLIADO (POP-UP)
            if st.session_state.panel_derecho_contenido:
                st.markdown(f"""<div class="expanded-right-panel"><div class="expanded-right-title">🔍 {st.session_state.panel_derecho_titulo}</div><div>{st.session_state.panel_derecho_contenido}</div></div>""", unsafe_allow_html=True)
                if st.button("❌ CERRAR", use_container_width=True): st.session_state.panel_derecho_contenido = None; st.rerun()
            # MODO MAQUETA
            else:
                h = clean_bio(d['son'].get('historia', ""))
                if h:
                    c_h, c_bh = st.columns([4, 1])
                    c_h.markdown('<span class="bio-label">⏳ HISTORY</span>', unsafe_allow_html=True)
                    if c_bh.button("👁️", key="b1"): st.session_state.panel_derecho_contenido = h; st.session_state.panel_derecho_titulo = "HISTORY"; st.rerun()
                    st.markdown(f'<div class="bio-box">{h}</div>', unsafe_allow_html=True)
                
                for i, a in enumerate(artistas):
                    b = clean_bio(a.get('bio', ""))
                    if b:
                        c_b, c_bb = st.columns([4, 1])
                        c_b.markdown(f'<span class="bio-label">👤 {a["name"].upper()}</span>', unsafe_allow_html=True)
                        if c_bb.button("➕", key=f"b{i}"): st.session_state.panel_derecho_contenido = b; st.session_state.panel_derecho_titulo = a['name']; st.rerun()
                        st.markdown(f'<div class="bio-box">{b}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div style="text-align:center; padding-top:40vh;">📡 STANDBY...</div>', unsafe_allow_html=True)