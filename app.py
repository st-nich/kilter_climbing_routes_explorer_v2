
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

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { margin-bottom: 0px; font-size: 1.5rem; }
        canvas { width: 100% !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATA LOADING & NORMALIZATION
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
    st.error("Data file 'kilter_app_data.pkl' not found. Run the pipeline script first.")
    st.stop()

# --- Normalize Columns ---
df = raw_df.copy()

# 1. Fix Difficulty
if 'display_difficulty' in df.columns:
    df.rename(columns={'display_difficulty': 'difficulty'}, inplace=True)
elif 'difficulty' not in df.columns:
    cols = [c for c in df.columns if 'diff' in c.lower() or 'grade' in c.lower()]
    if cols:
        df.rename(columns={cols[0]: 'difficulty'}, inplace=True)
    else:
        df['difficulty'] = 0 

# 2. Fix Name
if 'name' not in df.columns:
    name_candidates = ['Name', 'climb_name', 'title', 'route_name']
    found = False
    for c in name_candidates:
        if c in df.columns:
            df.rename(columns={c: 'name'}, inplace=True)
            found = True
            break
    if not found:
        df['name'] = "Route " + df['uuid'].astype(str).str[:6]

# 3. Fix Angle
if 'angle' not in df.columns:
    df['angle'] = 'Unknown'

df['difficulty'] = pd.to_numeric(df['difficulty'], errors='coerce').fillna(0).astype(int)

# ==========================================
# SIDEBAR / FILTERS
# ==========================================
with st.sidebar:
    st.header("Filters")
    
    min_grade = int(df['difficulty'].min())
    max_grade = int(df['difficulty'].max())
    
    if min_grade == max_grade:
        grade_range = (min_grade, max_grade)
        st.info(f"All climbs are V{min_grade}")
    else:
        grade_range = st.slider("Difficulty", min_grade, max_grade, (min_grade, max_grade))
    
    mask = (
        (df['difficulty'] >= grade_range[0]) & 
        (df['difficulty'] <= grade_range[1])
    )
    filtered_df = df[mask].copy()

# ==========================================
# VIZ: BOARD RENDERER (SVG)
# ==========================================
def generate_board_svg(route_uuid, all_holds, layout):
    width, height = 150, 160 
    
    svg_elements = []
    svg_elements.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#111" rx="5" />')
    
    route_holds = all_holds.get(route_uuid, [])
    
    if not route_holds:
        return f"""
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
            <text x="50%" y="50%" fill="gray" text-anchor="middle">Select a route</text>
        </svg>
        """

    for hold_id in route_holds:
        # Try both int and string lookup for robustness
        coords = layout.get(hold_id) or layout.get(str(hold_id)) or layout.get(int(hold_id) if str(hold_id).isdigit() else -1)
        
        if coords:
            cx, cy = coords['x'], coords['y']
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#00FFFF" opacity="0.6" filter="blur(2px)" />')
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="2" fill="white" />')
            svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="3.5" stroke="#00FFFF" stroke-width="0.5" fill="none" />')

    return f"""
    <svg viewBox="0 0 {width} {height}" style="width:100%; height:auto; max-height:60vh; background:#222; border-radius:8px;">
        {''.join(svg_elements)}
    </svg>
    """

# ==========================================
# UI LAYOUT
# ==========================================
col1, col2 = st.columns([1.5, 1])

# --- LEFT COLUMN: MAP ---
with col1:
    st.caption(f"Showing {len(filtered_df)} routes")
    
    selection = alt.selection_point(fields=['uuid'], on='click', empty=False)

    tooltip_fields = ['name', 'difficulty']
    if 'angle' in filtered_df.columns:
        tooltip_fields.append('angle')

    chart = alt.Chart(filtered_df).mark_circle(size=80).encode(
        x=alt.X('x', axis=None),
        y=alt.Y('y', axis=None),
        color=alt.Color('difficulty', scale=alt.Scale(scheme='turbo'), legend=None),
        tooltip=tooltip_fields,
        opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
    ).add_params(
        selection
    ).properties(
        height=500
    ).interactive()

    # UPDATED: Use width='stretch' as requested by warning logs
    try:
        st.altair_chart(chart, width="stretch", theme="streamlit")
    except:
        st.altair_chart(chart, use_container_width=True, theme="streamlit")


# --- RIGHT COLUMN: BOARD VIEW ---
with col2:
    selected_uuid = None
    
    unique_names = filtered_df['name'].astype(str).unique()
    
    route_choice = st.selectbox(
        "Search or Select", 
        unique_names,
        index=None,
        placeholder="Tap point on map..."
    )
    
    if route_choice:
        record = filtered_df[filtered_df['name'] == route_choice].iloc[0]
        selected_uuid = record['uuid']
        
        st.write(f"**{record['name']}** (V{record['difficulty']})")
        
        svg_code = generate_board_svg(selected_uuid, holds_map, layout_map)
        st.markdown(svg_code, unsafe_allow_html=True)
        
    else:
        st.info("👈 Tap a route on the map or search above")
        st.markdown(generate_board_svg(None, {}, {}), unsafe_allow_html=True)
