
import streamlit as st
import pandas as pd
import pickle
import altair as alt
import numpy as np

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Kilter Explorer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for buttons and canvas
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { margin-bottom: 0px; font-size: 1.5rem; }
        canvas { image-rendering: pixelated; } 
        
        /* Compact button row */
        div[data-testid="column"] button {
            padding: 0rem 0.5rem;
            line-height: 1.2;
            min-height: 0px;
            height: 2.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATA LOADING
# ==========================================
@st.cache_data
def load_data():
    try:
        with open('kilter_app_data.pkl', 'rb') as f:
            data = pickle.load(f)
        return data['metadata'], data['holds_map'], data['layout_map']
    except FileNotFoundError:
        return None, None, None

raw_df, holds_map, layout_map = load_data()

if raw_df is None:
    st.error("Data file 'kilter_app_data.pkl' not found. Please run the pipeline script.")
    st.stop()

df = raw_df.copy()

# ==========================================
# SESSION STATE (ZOOM/PAN)
# ==========================================
if 'view_x' not in st.session_state:
    st.session_state['view_x'] = [0.0, 1.0]
if 'view_y' not in st.session_state:
    st.session_state['view_y'] = [0.0, 1.0]

def update_zoom(action):
    x_min, x_max = st.session_state['view_x']
    y_min, y_max = st.session_state['view_y']
    x_span = x_max - x_min
    y_span = y_max - y_min
    step = 0.2

    if action == 'in':
        st.session_state['view_x'] = [x_min + x_span*0.1, x_max - x_span*0.1]
        st.session_state['view_y'] = [y_min + y_span*0.1, y_max - y_span*0.1]
    elif action == 'out':
        st.session_state['view_x'] = [x_min - x_span*0.1, x_max + x_span*0.1]
        st.session_state['view_y'] = [y_min - y_span*0.1, y_max + y_span*0.1]
    elif action == 'left':
        st.session_state['view_x'] = [x_min - x_span*step, x_max - x_span*step]
    elif action == 'right':
        st.session_state['view_x'] = [x_min + x_span*step, x_max + x_span*step]
    elif action == 'up':
        st.session_state['view_y'] = [y_min + y_span*step, y_max + y_span*step]
    elif action == 'down':
        st.session_state['view_y'] = [y_min - y_span*step, y_max - y_span*step]
    elif action == 'reset':
        st.session_state['view_x'] = [0.0, 1.0]
        st.session_state['view_y'] = [0.0, 1.0]

# ==========================================
# SIDEBAR: SETTINGS
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # --- Intelligent Name Detection ---
    cols = df.columns.tolist()
    
    # Priority list for name columns
    priority_names = ['climb_name', 'name', 'route_name', 'title']
    default_name_col = cols[0]
    
    # Find best match
    for p in priority_names:
        matches = [c for c in cols if p.lower() in c.lower()]
        if matches:
            default_name_col = matches[0]
            break
            
    name_col = st.selectbox("Name Column", cols, index=cols.index(default_name_col))
    
    # --- Grade Detection ---
    default_grade_col = cols[0]
    for c in ['difficulty', 'grade', 'display_difficulty', 'v_grade']:
        if c in cols:
            default_grade_col = c
            break
    grade_col = st.selectbox("Grade Column", cols, index=cols.index(default_grade_col))
    
    # Normalize grade
    df['normalized_grade'] = pd.to_numeric(df[grade_col], errors='coerce').fillna(0).astype(int)
    
    st.divider()
    max_points = st.slider("Max Dots", 500, len(df), 2000, 500)

# ==========================================
# MAIN FILTERS
# ==========================================
f_col1, f_col2 = st.columns([1, 2])
with f_col1:
    min_g, max_g = int(df['normalized_grade'].min()), int(df['normalized_grade'].max())
    grade_range = st.slider("Grade Range", min_g, max_g, (min_g, max_g))

with f_col2:
    search_query = st.text_input("Search Route Name", placeholder="e.g. 'Jedi Mind Tricks'...")

mask = ((df['normalized_grade'] >= grade_range[0]) & (df['normalized_grade'] <= grade_range[1]))
if search_query:
    mask = mask & (df[name_col].astype(str).str.contains(search_query, case=False, na=False))

filtered_df = df[mask].copy()

# ==========================================
# CHART DATA PREP
# ==========================================
if len(filtered_df) > max_points:
    sort_candidates = [c for c in df.columns if 'ascent' in c.lower() or 'star' in c.lower()]
    if sort_candidates:
        chart_df = filtered_df.sort_values(sort_candidates[0], ascending=False).head(max_points)
        st.caption(f"Showing top {max_points} routes (sorted by {sort_candidates[0]})")
    else:
        chart_df = filtered_df.sample(max_points, random_state=42)
        st.caption(f"Showing random {max_points} routes")
else:
    chart_df = filtered_df
    st.caption(f"Showing {len(chart_df)} routes")

# ==========================================
# UI LAYOUT
# ==========================================
col1, col2 = st.columns([1.5, 1])

# --- LEFT: MAP & CONTROLS ---
with col1:
    # 1. Map Controls (Visible Buttons)
    c1, c2, c3, c4, c5, c6 = st.columns([1,1,1,1,1,1])
    c1.button("➕", on_click=update_zoom, args=('in',), use_container_width=True, help="Zoom In")
    c2.button("➖", on_click=update_zoom, args=('out',), use_container_width=True, help="Zoom Out")
    c3.button("⬅️", on_click=update_zoom, args=('left',), use_container_width=True, help="Pan Left")
    c4.button("➡️", on_click=update_zoom, args=('right',), use_container_width=True, help="Pan Right")
    c5.button("⬆️", on_click=update_zoom, args=('up',), use_container_width=True, help="Pan Up")
    c6.button("⬇️", on_click=update_zoom, args=('down',), use_container_width=True, help="Pan Down")
    
    # 2. Map
    sel = alt.selection_point(name="point_select", on="click", fields=['uuid'], empty=False)
    
    base = alt.Chart(chart_df).encode(
        x=alt.X('x', axis=None, scale=alt.Scale(domain=st.session_state['view_x'])),
        y=alt.Y('y', axis=None, scale=alt.Scale(domain=st.session_state['view_y'])),
        color=alt.Color('normalized_grade', title="Grade", scale=alt.Scale(scheme='turbo')),
        tooltip=[name_col, grade_col]
    )
    
    points = base.mark_circle(size=80, opacity=0.8).encode(
        opacity=alt.condition(sel, alt.value(1), alt.value(0.1)),
        size=alt.condition(sel, alt.value(200), alt.value(80))
    ).add_params(sel).interactive()

    try:
        event = st.altair_chart(points, on_select="rerun", theme="streamlit", use_container_width=True)
    except TypeError:
        st.error("⚠️ Streamlit version issue. Please restart runtime.")
        event = None

# --- RIGHT: BOARD VIEW ---
with col2:
    selected_uuid = None
    selected_name = "None"
    selected_grade = ""

    # Selection Logic
    if event and hasattr(event, 'selection') and 'point_select' in event.selection:
        selection_data = event.selection['point_select']
        if selection_data:
            selected_uuid = selection_data[0]['uuid']
            
    if search_query and len(filtered_df) == 1:
        selected_uuid = filtered_df.iloc[0]['uuid']

    # --- BOARD RENDERER ---
    def generate_board_svg(uuid, holds_map, layout):
        # Kilter Dimensions: ~144 units wide, ~156 units high (standard)
        # We increase ViewBox slightly to add padding
        width, height = 160, 170 
        
        svg = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#111" rx="6" />']
        
        # Color Map
        colors = { 12: '#00DD00', 13: '#00FFFF', 14: '#FF00FF', 15: '#FFA500' }
        
        route_holds = holds_map.get(uuid, [])
        if not route_holds:
            return f'<svg viewBox="0 0 {width} {height}"><text x="50%" y="50%" fill="#555" text-anchor="middle" font-family="sans-serif">Select Route</text></svg>'

        for h_data in route_holds:
            if isinstance(h_data, (list, tuple)) and len(h_data) == 2:
                h_id, role = h_data
            else:
                h_id, role = h_data, 13
            
            c = colors.get(role, '#00FFFF')
            
            # Coordinate Scaling
            # NOTE: We assume 'layout' contains coords normalized to roughly 0-150 range.
            coords = layout.get(h_id) or layout.get(str(h_id)) or layout.get(int(h_id) if str(h_id).isdigit() else -1)
            
            if coords:
                cx, cy = coords['x'], coords['y']
                
                # SVG Padding Adjust (add +5 to X and +10 to Y to center it)
                cx += 5
                cy += 5
                
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{c}" opacity="0.3" />') # Glow
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="{c}" />') # Core
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="3.5" stroke="{c}" stroke-width="0.7" fill="none" />') # Ring
        
        return f'<svg viewBox="0 0 {width} {height}" style="width:100%; height:auto; max-height:70vh; background:#222; border-radius:8px;">{ "".join(svg) }</svg>'

    if selected_uuid and selected_uuid in df['uuid'].values:
        row = df[df['uuid'] == selected_uuid].iloc[0]
        selected_name = row[name_col]
        selected_grade = f"V{row['normalized_grade']}"
        
        st.markdown(f"### {selected_name} <span style='color:cyan'>{selected_grade}</span>", unsafe_allow_html=True)
        st.markdown(generate_board_svg(selected_uuid, holds_map, layout_map), unsafe_allow_html=True)
    else:
        st.info("👆 Tap a dot to view")
        st.markdown(generate_board_svg(None, {}, {}), unsafe_allow_html=True)
