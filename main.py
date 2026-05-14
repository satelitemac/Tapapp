# VERSION: 35.0 - THE COHERENT GRAPH (Fragments + Anti-Gravity Map + Text Wrap)
import streamlit as st
from neo4j import GraphDatabase
import time, re, urllib.parse, random, requests, textwrap
from streamlit_agraph import agraph, Node, Edge, Config

# 1. CONFIGURACIÓN
st.set_page_config(layout="wide", page_title="RADAR DJ PRO", initial_sidebar_state="collapsed")
st.markdown("""<style>
    header, footer, [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
    .stApp { background-color: #050505; }
    
    /* 🟢 AIRE POR ARRIBA: Ajustado a 1rem */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; padding-left: 5rem !important; padding-right: 5rem !important; margin-top: 0rem !important; }
    
    .art-title { font-size: 6vh; font-weight: 900; color: white; text-transform: uppercase; text-align: center; line-height: 1; margin-top: 0 !important; }
    .art-subtitle { font-size: 2.5vh; color: #ff4b4b; font-weight: 700; text-transform: uppercase; text-align: center; margin-bottom: 2vh; }
    .img-box { width: 100%; padding-top: 100%; position: relative; border-radius: 18px; overflow: hidden; border: 1px solid #333; margin-bottom: 1.5vh; background: #000; }
    .img-box img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
    
    .c3-wrapper { display: flex; flex-direction: column; height: 65vh; }
    .bio-container { flex-grow: 1; overflow-y: auto; margin-top: 1vh; scrollbar-width: none; padding-right: 5px; }
    
    .radar-box { background: rgba(20,20,20,0.9); padding: 1.8vh; border-radius: 12px; border-left: 5px solid #ff4b4b; margin-bottom: 1.2vh; }
    .label-tag { font-size: 0.9vh; font-weight: 800; color: #ff4b4b; text-transform: uppercase; margin-top: 0.8vh; display: block; }
    
    /* 🟢 TÍTULO HISTORY CENTRADO */
    .history-label { 
        font-size: 1.4vh; 
        font-weight: 800; 
        color: #ff4b4b; 
        text-transform: uppercase; 
        margin-bottom: 1vh; 
        display: block; 
        text-align: center; 
        width: 100%;
        letter-spacing: 1px;
    }
    
    .value-text { font-size: 1.7vh; font-weight: 700; color: white; text-transform: uppercase; }
    .remix-highlight { color: #00ffcc; font-size: 2vh; font-weight: 800; }
    .side-panel { background: rgba(255,255,255,0.03); padding: 2vh; border-radius: 15px; border: 1px solid #ff4b4b; height: 75vh; overflow-y: auto; }
    .bio-box { background: rgba(255,255,255,0.03); padding: 1.2vh; border-radius: 10px; color: #ccc; border: 1px solid #222; font-size: 1.25vh; margin-bottom: 1vh; }
    .bio-label { color: #888; text-transform: uppercase; font-size: 0.9vh; font-weight: 800; display: block; }
    .credits-container { background: rgba(255,255,255,0.02); border: 1px solid #222; padding: 1.2vh; border-radius: 8px; max-height: 15vh; overflow-y: auto; scrollbar-width: none; margin-bottom: 0.5vh; }
    .credit-item { font-size: 1.05vh; color: #777; text-transform: uppercase; padding: 4px 0; border-bottom: 1px solid #1a1a1a; }
    
    /* FORZAMOS LA ALTURA DEL MAPA NEURONAL AQUÍ */
    iframe[title="streamlit_agraph.agraph"] { height: 75vh !important; }
    
    /* 🟢 HACK DE BOTONES: Reduce tamaño y afina la caja */
    div[data-testid="stButton"] button p, 
    div[data-testid="stLinkButton"] a p {
        font-size: 1.1vh !important; 
        font-weight: 800 !important;
    }
    div[data-testid="stButton"] button, 
    div[data-testid="stLinkButton"] a {
        padding-top: 0.4rem !important;
        padding-bottom: 0.4rem !important;
    }
</style>""", unsafe_allow_html=True)

URI, USER, PASS = "neo4j+s://3ba4e632.databases.neo4j.io", "3ba4e632", "MWwAJKrv6xxOC3cI17CR5-oKjCtKyN9IMnjwZa5KYKI"
VINILO_FALLBACK = "https://images.unsplash.com/photo-1603048588665-791ca8aea617?q=80&w=1000"

# --- INICIALIZACIÓN DE MEMORIA ---
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

def clean_bio(text):
    if not text: return ""
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

# --- 🛡️ LA CAJA FUERTE (Vigilante Silencioso en Segundo Plano) ---
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
            
            # ---> EL CHIVATAZO AL SERVIDOR (AQUÍ ENVIAMOS A LOS MÓVILES) <---
            try:
                artistas_nombres = " & ".join([a['name'] for a in new_d['nodos_artistas']])
                titulo = new_d['son']['name']
                bgs = new_d['nodos_artistas'][0].get('backgrounds', []) if new_d['nodos_artistas'] else []
                imagen = new_d['r'].get('foto') or (bgs[0] if bgs else VINILO_FALLBACK)
                
                requests.post("https://tapapp.onrender.com/update_cover", json={
                    "url": imagen,
                    "artist": artistas_nombres,
                    "track": titulo
                }, timeout=2)
            except Exception as e:
                print("Error avisando a Render:", e)
            # ---> FIN DEL CHIVATAZO <---

            st.rerun() 

cloud_watcher()

# --- 🖼️ RENDERIZADO VISUAL CONGELADO ---
d = st.session_state.last_d
p = st.session_state.last_p

if d:
    artistas = d['nodos_artistas']
    nombres_display = d.get('titulo_original', " & ".join([a['name'] for a in artistas])).upper()
    primer_art = artistas[0]
    
    if st.session_state.mapa_abierto:
        # --- MODO NETWORK ---
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
        
        # 🟢 LÓGICA DE TEXTO ROTO Y LIMPIO 
        for c in d['creditos_nodos']:
            if c['name'] and c['name'] not in added_nodes:
                raw_role = c.get('role') or "Contributor"
                role_lower = raw_role.lower()
                
                short_role = re.sub(r'\[.*?\]|\(.*?\)', '', raw_role).strip()
                if not short_role: short_role = "CONTRIBUTOR"
                
                # Rompe el nombre en varias líneas
                wrapped_name = "\n".join(textwrap.wrap(c['name'], width=12))
                
                if any(keyword in role_lower for keyword in music_keywords): node_color = "#d926ff" 
                elif any(keyword in role_lower for keyword in tech_keywords): node_color = "#4444ff" 
                else: node_color = "#333333" 
                
                add_node(c['name'], f"{wrapped_name}\n({short_role.upper()})", node_color)
                edges.append(Edge(source=c['name'], target="SONG", color=node_color))
        
        # 🟢 FÍSICAS "ANTI-GRAVEDAD" PARA EVITAR PELOTERAS
        config = Config(
            width="100%", 
            height=750, 
            directed=True, 
            physics={
                "barnesHut": {
                    "gravitationalConstant": -15000, 
                    "centralGravity": 0.2, 
                    "springLength": 300, 
                    "avoidOverlap": 1
                }
            }, 
            interaction={"selectable": False}
        )
        agraph(nodes=nodes, edges=edges, config=config)
        
        col_btn, _ = st.columns([1, 8]) 
        with col_btn:
            if st.button("CLOSE MAP", use_container_width=True): 
                st.session_state.mapa_abierto = False
                st.rerun()

    else:
        # --- MODO DASHBOARD ---
        st.markdown(f'<div class="art-title">{d["son"]["name"]}</div><div class="art-subtitle">{nombres_display}</div>', unsafe_allow_html=True)
        
        # 🟢 CAJA DERECHA MÁS ANCHA PARA LOS BOTONES
        c1, c2, c3 = st.columns([1, 2.1, 1.4], gap="large")

        with c1:
            st.markdown('<span class="history-label">History</span>', unsafe_allow_html=True)
            for track in (p or []): 
                st.markdown(f'<div class="img-box"><img src="{track.get("foto") or VINILO_FALLBACK}"></div>', unsafe_allow_html=True)

        with c2:
            bgs = primer_art.get('backgrounds', [])
            main_img = d['r'].get('foto') or (bgs[0] if bgs else VINILO_FALLBACK)
            st.markdown(f'<div class="img-box"><img src="{main_img}"></div>', unsafe_allow_html=True)

        with c3:
            wiki_url = primer_art.get('wiki_url') or primer_art.get('wikipedia')
            if not wiki_url and isinstance(primer_art.get('wiki'), str) and primer_art.get('wiki').startswith('http'):
                wiki_url = primer_art.get('wiki')
            if not wiki_url:
                wiki_url = f"https://www.google.com/search?q={urllib.parse.quote(primer_art['name'] + ' wikipedia')}"

            ws_query = f"{primer_art['name']} {d['son']['name']}"
            ws_url = f"https://www.whosampled.com/search/?q={urllib.parse.quote(ws_query)}"

            # 🟢 BOTONES SIMÉTRICOS EXACTOS
            col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
            with col_b1: st.button("GRAPH", on_click=lambda: setattr(st.session_state, "mapa_abierto", True), use_container_width=True)
            with col_b2: st.link_button("DISCOGS", d['r'].get('discogs', "#"), use_container_width=True)
            with col_b3: st.link_button("WIKI", wiki_url, use_container_width=True) 
            with col_b4: st.link_button("SAMPLES", ws_url, use_container_width=True) 
            with col_b5:
                if st.button("LYRICS", use_container_width=True): st.session_state.mostrar_letras = not st.session_state.mostrar_letras

            # --- CAJA MAESTRA ---
            estilos = d['estilos_oficiales'] or []
            gen_str = " • ".join(estilos).upper() if estilos else "ELECTRONIC"
            
            c3_html = f'''<div class="c3-wrapper"><div class="radar-box"><span class="label-tag">Version / Remix</span><span class="value-text remix-highlight">{d['remix_name'] or "ORIGINAL MIX"}</span><span class="label-tag">Discogs Styles</span><span class="value-text">{gen_str}</span><span class="label-tag">Label / Year</span><span class="value-text">{d['sello'] or "---"} ({d['anio'] or "---"})</span></div>'''
            
            valid_credits = [c for c in d['creditos_nodos'] if c.get('name')]
            if valid_credits:
                c3_html += '<span class="label-tag" style="margin-bottom:0.5vh;">Production Credits</span><div class="credits-container">'
                c3_html += "".join([f'<div class="credit-item"><b>{c["role"]}:</b> {c["name"]}</div>' for c in valid_credits])
                c3_html += '</div>'
                
            c3_html += '<div class="bio-container">'

            if st.session_state.mostrar_letras:
                letras_txt = get_lyrics(primer_art['name'], d['son']['name'])
                c3_html += f'''<div class="bio-box" style="border-left: 3px solid #ff00ff; background: rgba(255, 0, 255, 0.05);"><span class="bio-label" style="color: #ff00ff; margin-bottom: 5px;">🎵 LYRICS</span><div style="font-size: 1.4vh; line-height: 1.4; color: #eee;">{letras_txt}</div></div>'''
            
            historia_txt = d['son'].get('historia', "")
            if historia_txt and historia_txt != "---": c3_html += f'''<div class="bio-box" style="border-left: 3px solid #00ffcc; background: rgba(0, 255, 204, 0.05);"><span class="bio-label" style="color: #00ffcc;">Track History</span>{clean_bio(historia_txt)}</div>'''

            track_wiki = d['son'].get('wiki') or d['r'].get('notas') or d['r'].get('notes')
            if track_wiki and track_wiki != "---" and not str(track_wiki).startswith("http"): c3_html += f'''<div class="bio-box" style="border-left: 3px solid #ffd700; background: rgba(255, 215, 0, 0.05);"><span class="bio-label" style="color: #ffd700;">Track Notes / Wiki</span>{clean_bio(str(track_wiki))}</div>'''
                
            for a in artistas:
                b_raw = a.get('bio', "")
                b_text = b_raw[0] if isinstance(b_raw, list) and b_raw else b_raw
                if b_text and b_text != "---": c3_html += f'''<div class="bio-box"><span class="bio-label">{a['name'].upper()} Profile</span>{clean_bio(b_text)}</div>'''
                
                perfil_raw = a.get('perfil') or a.get('profile')
                if not perfil_raw and isinstance(a.get('wiki'), str) and not a.get('wiki').startswith('http'): perfil_raw = a.get('wiki') 
                perfil_txt = perfil_raw[0] if isinstance(perfil_raw, list) and perfil_raw else perfil_raw
                if perfil_txt and perfil_txt != "---": c3_html += f'''<div class="bio-box" style="border-left: 3px solid #ff9900; background: rgba(255, 153, 0, 0.05);"><span class="bio-label" style="color: #ff9900;">{a['name'].upper()} Discogs / Wiki</span>{clean_bio(perfil_txt)}</div>'''
                    
            c3_html += '</div></div>'
            st.markdown(c3_html, unsafe_allow_html=True)

else:
    st.markdown('<div style="color:#222; text-align:center; padding-top:45vh;">📡 STANDBY FOR DATA...</div>', unsafe_allow_html=True)