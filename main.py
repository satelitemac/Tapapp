# VERSION: 35.2 - THE COHERENT GRAPH (FULL RESTORE + POPUPS)
import streamlit as st
from neo4j import GraphDatabase
import time, re, urllib.parse, random, requests, textwrap
from streamlit_agraph import agraph, Node, Edge, Config

# 1. CONFIGURACIÓN
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
    .value-text { font-size: 1.7vh; font-weight: 700; color: white; text-transform: uppercase; }
    .remix-highlight { color: #00ffcc; font-size: 2vh; font-weight: 800; }
    .bio-box { background: rgba(255,255,255,0.03); padding: 1.5vh; border-radius: 10px; color: #ccc; border: 1px solid #222; font-size: 1.35vh; margin-bottom: 1vh; min-height: 10vh; max-height: 15vh; overflow-y: auto; }
    .bio-label { color: #888; text-transform: uppercase; font-size: 0.9vh; font-weight: 800; display: block; margin-bottom: 0.5vh; }
    .credits-container { background: rgba(255,255,255,0.02); border: 1px solid #222; padding: 1.2vh; border-radius: 8px; max-height: 15vh; overflow-y: auto; scrollbar-width: none; margin-bottom: 0.5vh; }
    .credit-item { font-size: 1.05vh; color: #777; text-transform: uppercase; padding: 4px 0; border-bottom: 1px solid #1a1a1a; }
    
    /* 🟢 FORZAR MODALES (POP-UPS) OSCUROS */
    div[data-testid="stDialog"] > div, div[role="dialog"] { background-color: #0a0a0a !important; border: 2px solid #ff4b4b !important; border-radius: 15px !important; }
    div[data-testid="stDialog"] h2, div[role="dialog"] h2 { color: #ff4b4b !important; font-weight: 900 !important; text-transform: uppercase !important; text-align: center; border-bottom: 1px solid #333; padding-bottom: 10px; }
    button[aria-label="Close"] { color: #ffffff !important; }
    
    /* ESTILOS DE BOTONES */
    div[data-testid="stButton"] button p, div[data-testid="stLinkButton"] a p { font-size: 1.1vh !important; font-weight: 800 !important; margin: 0 !important; }
    div[data-testid="stButton"] button, div[data-testid="stLinkButton"] a { padding: 0.2rem 0.5rem !important; min-height: unset !important; height: auto !important; border-radius: 4px !important; }
    div[data-testid="stButton"] button:hover { border-color: #ff4b4b !important; color: #ff4b4b !important; }
</style>""", unsafe_allow_html=True)

URI, USER, PASS = "neo4j+s://3ba4e632.databases.neo4j.io", "3ba4e632", "MWwAJKrv6xxOC3cI17CR5-oKjCtKyN9IMnjwZa5KYKI"
VINILO_FALLBACK = "https://images.unsplash.com/photo-1603048588665-791ca8aea617?q=80&w=1000"

if "mapa_abierto" not in st.session_state: st.session_state.mapa_abierto = False
if "mostrar_letras" not in st.session_state: st.session_state.mostrar_letras = False 
if "last_d" not in st.session_state: st.session_state.last_d = None
if "last_p" not in st.session_state: st.session_state.last_p = None
if "last_cloud_ts" not in st.session_state: st.session_state.last_cloud_ts = None

@st.cache_resource
def get_driver(): return GraphDatabase.driver(URI, auth=(USER, PASS))

def check_cloud_trigger():
    try:
        with get_driver().session() as s:
            res = s.run("MATCH (sys:System {id: 'radar_trigger'}) RETURN sys.timestamp").single()
            return res[0] if res else None
    except: return None

# FUNCIÓN BLINDADA PARA EVITAR TYPE ERRORS
def clean_bio(text):
    if not text: return ""
    if isinstance(text, list): text = text[0] if text else ""
    if not isinstance(text, str): text = str(text)
    return re.sub(r'\[url=[^\]]+\](.*?)\[/url\]|\[[^\]]+\]', r'\1', text, flags=re.IGNORECASE).strip()

@st.cache_data(ttl=86400) 
def get_lyrics(artist, song):
    clean_song = re.sub(r'\(.*?\)', '', song).strip()
    genius_url = f"https://genius.com/search?q={urllib.parse.quote(artist + ' ' + clean_song)}"
    fallback_html = f"Letra no disponible en API libre. 🎶 <br><br><a href='{genius_url}' target='_blank' style='color:#ff00ff; text-decoration:none; font-weight:bold;'>👉 Buscar en Genius</a>"
    try:
        url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(clean_song)}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            lyrics = res.json().get('lyrics', '')
            lyrics = re.sub(r'Paroles de la chanson .*? par .*?\r?\n', '', lyrics, flags=re.IGNORECASE).strip()
            if lyrics: 
                lyrics_html = lyrics.replace('\n', '<br>')
                return f"{lyrics_html}<br><br><a href='{genius_url}' target='_blank' style='color:#ff00ff; font-size:0.8em; text-decoration:none;'>🔍 Ver en Genius</a>"
    except: pass
    return fallback_html

def fetch_data():
    try:
        with get_driver().session() as s:
            q = """
                MATCH (son:Song:Actual)-[:VERSION]->(r:Remix:Actual)
                MATCH (a:Artist:Actual)-[:INTERPRETA]->(son)
                OPTIONAL MATCH (r)-[:RELEASED_BY]->(l:Label)
                OPTIONAL MATCH (staff:Artist)-[c:CONTRIBUTED_TO]->(r)
                OPTIONAL MATCH (oc:Artist)-[tc:TAMBIEN_CANTO]->(son)
                RETURN son, r, 
                       son.display_artist as titulo_original,
                       collect(DISTINCT a) as nodos_artistas,
                       r.estilos_discogs as estilos_oficiales,
                       l.name as sello,
                       r.year as anio,
                       r.name as remix_name,
                       collect(DISTINCT {name: staff.name, role: c.role}) as creditos_nodos,
                       collect(DISTINCT oc.name) as covers_nodos,
                       r.timestamp as ts
                LIMIT 1
            """
            res = s.run(q).single()
            if res:
                prev = [dict(rec['r']) for rec in s.run("MATCH (r:Remix) WHERE NOT r:Actual AND r.timestamp IS NOT NULL RETURN r ORDER BY r.timestamp DESC LIMIT 2")]
                return res, prev
    except Exception as e: print(f"Error fetch: {e}")
    return None, None

@st.fragment(run_every=2)
def cloud_watcher():
    ts_ahora = check_cloud_trigger()
    if ts_ahora and ts_ahora != st.session_state.last_cloud_ts:
        st.session_state.last_cloud_ts = ts_ahora
        new_d, new_p = fetch_data()
        if new_d:
            st.session_state.last_d = new_d
            st.session_state.last_p = new_p
            st.session_state.mostrar_letras = False 
            try:
                artistas_nombres = " & ".join([a['name'] for a in new_d['nodos_artistas']])
                titulo = new_d['son']['name']
                bgs = new_d['nodos_artistas'][0].get('backgrounds', []) if new_d['nodos_artistas'] else []
                imagen = new_d['r'].get('foto') or (bgs[0] if bgs else VINILO_FALLBACK)
                requests.post("https://tapapp.onrender.com/update_cover", json={"url": imagen, "artist": artistas_nombres, "track": titulo}, timeout=2)
            except Exception as e: print("Error avisando a Render:", e)
            st.rerun() 

cloud_watcher()

d = st.session_state.last_d
p = st.session_state.last_p

# --- 📝 FUNCIONES PARA MODALES (POP-UPS GIGANTES) ---
@st.dialog("TRACK HISTORY", width="large")
def show_history_modal(text):
    st.markdown(f"<div style='font-size: 2.2vh; line-height: 1.8; color: #eee; padding: 2vh;'>{text}</div>", unsafe_allow_html=True)

@st.dialog("TRACK NOTES", width="large")
def show_notes_modal(text):
    st.markdown(f"<div style='font-size: 2.2vh; line-height: 1.8; color: #eee; padding: 2vh;'>{text}</div>", unsafe_allow_html=True)

@st.dialog("ARTIST PROFILE", width="large")
def show_profile_modal(name, text):
    st.markdown(f"<div style='font-size: 2.2vh; line-height: 1.8; color: #eee; padding: 2vh;'>{text}</div>", unsafe_allow_html=True)

@st.dialog("PRODUCTION CREDITS", width="large")
def show_credits_modal(credits_list):
    html_credits = "".join([f"<div style='font-size: 1.8vh; color: #ddd; padding: 8px 0; border-bottom: 1px solid #333;'><b>{c['role']}:</b> <span style='color: #ff9900;'>{c['name']}</span></div>" for c in credits_list])
    st.markdown(f"<div style='padding: 2vh;'>{html_credits}</div>", unsafe_allow_html=True)

if d:
    artistas = d['nodos_artistas']
    titulo_raw = d.get('titulo_original')
    if not titulo_raw:
        titulo_raw = " & ".join([a.get('name', 'UNKNOWN') for a in artistas])
        
    nombres_display = str(titulo_raw).upper()
    primer_art = artistas[0]
    
    if st.session_state.mapa_abierto:
        st.markdown(f"<h2 style='text-align:center; color:#ff4b4b; font-size:3vh;'>NEURAL MAP: {nombres_display}</h2>", unsafe_allow_html=True)
        nodes, edges = [], []
        added_nodes = set() 
        def add_node(n_id, label, color, is_song=False):
            if n_id not in added_nodes:
                f_color = "black" if is_song else "white"
                f_size = 15 if is_song else 11 
                nodes.append(Node(id=n_id, label=label, color=color, shape="circle", font={"size":f_size, "color":f_color, "bold":is_song}))
                added_nodes.add(n_id)
        song_display = d['son']['name'].replace(" (", "\n(")
        add_node("SONG", song_display, "#00ffcc", is_song=True)
        for a in artistas:
            add_node(a['name'], f"{a['name']}\n(INTERPRETA)", "#ff4b4b")
            edges.append(Edge(source=a['name'], target="SONG", color="#ff4b4b"))
        creditos_nombres = [c['name'] for c in d['creditos_nodos']]
        covers = [c for c in d.get('covers_nodos', []) if c]
        for cover_artist in covers:
            if cover_artist in creditos_nombres:
                roles = [c['role'] for c in d['creditos_nodos'] if c['name'] == cover_artist]
                rol_str = " / ".join(roles).upper()
                add_node(cover_artist, f"{cover_artist}\n⭐ ORIGINAL ({rol_str})", "#ff6600") 
                edges.append(Edge(source=cover_artist, target="SONG", color="#ff6600"))
            else:
                add_node(cover_artist, f"{cover_artist}\n(TAMBIÉN CANTÓ)", "#ffd700")
                edges.append(Edge(source=cover_artist, target="SONG", color="#ffd700", dashed=True))
        tech_keywords = ["producer", "engineer", "mix", "master", "record", "program", "arrange", "edit", "cut", "technician", "remix", "written", "writer", "composer", "author", "lyric"]
        music_keywords = ["vocal", "bass", "drum", "guitar", "key", "piano", "synth", "percussion", "sax", "trumpet", "horn", "string", "violin", "cello", "flute", "choir", "solo", "instrument", "conga", "bongo", "brass", "woodwind", "rhythm"]
        for c in d['creditos_nodos']:
            if c['name'] and c['name'] not in added_nodes:
                raw_role = c.get('role') or "Contributor"
                role_lower = raw_role.lower()
                short_role = re.sub(r'\[.*?\]|\(.*?\)', '', raw_role).strip()
                if not short_role: short_role = "CONTRIBUTOR"
                wrapped_name = "\n".join(textwrap.wrap(c['name'], width=12))
                if any(keyword in role_lower for keyword in music_keywords): node_color = "#d926ff" 
                elif any(keyword in role_lower for keyword in tech_keywords): node_color = "#4444ff" 
                else: node_color = "#333333" 
                add_node(c['name'], f"{wrapped_name}\n({short_role.upper()})", node_color)
                edges.append(Edge(source=c['name'], target="SONG", color=node_color))
        config = Config(width="100%", height=750, directed=True, physics={"barnesHut": {"gravitationalConstant": -15000, "centralGravity": 0.2, "springLength": 300, "avoidOverlap": 1}}, interaction={"selectable": False})
        agraph(nodes=nodes, edges=edges, config=config)
        col_btn, _ = st.columns([1, 8]) 
        with col_btn:
            if st.button("CLOSE MAP", use_container_width=True): 
                st.session_state.mapa_abierto = False
                st.rerun()
    else:
        st.markdown(f'<div class="art-title">{d["son"]["name"]}</div><div class="art-subtitle">{nombres_display}</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2.1, 1.4], gap="large")
        with c1:
            st.markdown('<span style="color:#888; font-size: 1.4vh; font-weight:800; text-transform:uppercase; margin-bottom: 1vh; display:block;">History</span>', unsafe_allow_html=True)
            for track in (p or []): 
                st.markdown(f'<div class="img-box"><img src="{track.get("foto") or VINILO_FALLBACK}" onerror="this.onerror=null; this.src=\'{VINILO_FALLBACK}\';"></div>', unsafe_allow_html=True)
        with c2:
            bgs = primer_art.get('backgrounds', [])
            main_img = d['r'].get('foto') or (bgs[0] if bgs else VINILO_FALLBACK)
            st.markdown(f'<div class="img-box"><img src="{main_img}" onerror="this.onerror=null; this.src=\'{VINILO_FALLBACK}\';"></div>', unsafe_allow_html=True)
        
        with c3:
            wiki_url = primer_art.get('wiki_url') or primer_art.get('wikipedia')
            if not wiki_url and isinstance(primer_art.get('wiki'), str) and primer_art.get('wiki').startswith('http'):
                wiki_url = primer_art.get('wiki')
            if not wiki_url:
                wiki_url = f"https://www.google.com/search?q={urllib.parse.quote(primer_art['name'] + ' wikipedia')}"

            ws_query = f"{primer_art['name']} {d['son']['name']}"
            ws_url = f"https://www.whosampled.com/search/?q={urllib.parse.quote(ws_query)}"

            col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
            with col_b1: st.button("GRAPH", on_click=lambda: setattr(st.session_state, "mapa_abierto", True), use_container_width=True)
            with col_b2: st.link_button("DISCOGS", d['r'].get('discogs', "#"), use_container_width=True)
            with col_b3: st.link_button("WIKI", wiki_url, use_container_width=True) 
            with col_b4: st.link_button("SAMPLES", ws_url, use_container_width=True) 
            with col_b5:
                if st.button("LYRICS", use_container_width=True): st.session_state.mostrar_letras = not st.session_state.mostrar_letras

            # INFO BÁSICA (Radar Box)
            estilos = d['estilos_oficiales'] or []
            gen_str = " • ".join(estilos).upper() if estilos else "ELECTRONIC"
            st.markdown(f'''
                <div class="radar-box">
                    <span class="label-tag">Version / Remix</span>
                    <span class="value-text remix-highlight">{d['remix_name'] or "ORIGINAL MIX"}</span>
                    <span class="label-tag">Discogs Styles</span>
                    <span class="value-text">{gen_str}</span>
                    <span class="label-tag">Label / Year</span>
                    <span class="value-text">{d['sello'] or "---"} ({d['anio'] or "---"})</span>
                </div>
            ''', unsafe_allow_html=True)
            
            # --- CONTENEDOR MAESTRO DE LECTURA (Caja Fija) ---
            with st.container(height=600, border=False):
                
                # 1. Producción
                valid_credits = [c for c in d['creditos_nodos'] if c.get('name')]
                if valid_credits:
                    col_cred, col_btn_cred = st.columns([4, 1])
                    col_cred.markdown('<span class="label-tag" style="margin-bottom:0.5vh;">Production Credits</span>', unsafe_allow_html=True)
                    if col_btn_cred.button("➕ VER", key="btn_cred_modal", use_container_width=True):
                        show_credits_modal(valid_credits)
                    
                    cred_preview = "".join([f'<div class="credit-item"><b>{c["role"]}:</b> {c["name"]}</div>' for c in valid_credits[:3]])
                    if len(valid_credits) > 3: cred_preview += '<div class="credit-item" style="color:#ff4b4b;">... y más (Ver)</div>'
                    st.markdown(f'<div class="credits-container">{cred_preview}</div>', unsafe_allow_html=True)

                # 2. Letras
                if st.session_state.mostrar_letras:
                    letras_txt = get_lyrics(primer_art['name'], d['son']['name'])
                    st.markdown(f'''<div class="bio-box" style="border-left: 3px solid #ff00ff; background: rgba(255, 0, 255, 0.05);"><span class="bio-label" style="color: #ff00ff;">🎵 LYRICS</span><div style="font-size: 1.4vh; line-height: 1.4; color: #eee;">{letras_txt}</div></div>''', unsafe_allow_html=True)

                # 3. Historia
                historia_txt = clean_bio(d['son'].get('historia', ""))
                if historia_txt and historia_txt != "---":
                    col_hist, col_btn_hist = st.columns([4, 1])
                    col_hist.markdown('<span class="bio-label" style="color: #00ffcc;">Track History</span>', unsafe_allow_html=True)
                    if col_btn_hist.button("➕ VER", key="btn_hist_modal", use_container_width=True):
                        show_history_modal(historia_txt)
                    st.markdown(f'<div class="bio-box" style="border-left: 3px solid #00ffcc; background: rgba(0, 255, 204, 0.05);">{historia_txt}</div>', unsafe_allow_html=True)

                # 4. Notas
                notas_txt = clean_bio(str(d['son'].get('wiki') or d['r'].get('notas') or ""))
                if notas_txt and notas_txt != "---":
                    col_notes, col_btn_notes = st.columns([4, 1])
                    col_notes.markdown('<span class="bio-label" style="color: #ffd700;">📝 TRACK NOTES</span>', unsafe_allow_html=True)
                    if col_btn_notes.button("➕ VER", key="btn_notes_modal", use_container_width=True):
                        show_notes_modal(notas_txt)
                    st.markdown(f'<div class="bio-box" style="border-left: 3px solid #ffd700; background: rgba(255, 215, 0, 0.05);">{notas_txt}</div>', unsafe_allow_html=True)

                # 5. Bios Artistas
                for i, a in enumerate(artistas):
                    b = clean_bio(a.get('bio', ""))
                    if b and b != "---":
                        col_bio, col_btn_bio = st.columns([4, 1])
                        col_bio.markdown(f'<span class="bio-label">👤 {a["name"].upper()}</span>', unsafe_allow_html=True)
                        if col_btn_bio.button("➕ VER", key=f"btn_bio_modal_{i}", use_container_width=True):
                            show_profile_modal(a['name'].upper(), b)
                        st.markdown(f'<div class="bio-box">{b}</div>', unsafe_allow_html=True)

else:
    st.markdown('<div style="color:#222; text-align:center; padding-top:45vh;">📡 STANDBY FOR DATA...</div>', unsafe_allow_html=True)