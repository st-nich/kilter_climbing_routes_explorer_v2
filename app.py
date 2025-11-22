
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

# Optimize for mobile interactions
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 0rem; }
        h1 { margin-bottom: 0px; font-size: 1.5rem; }
        /* Force canvas to be crisp */
        canvas { image-rendering: pixelated; } 
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
# SIDEBAR: SETTINGS & DEBUGGING
# ==========================================
with st.sidebar:
    st.header("⚙️ App Settings")
    
    # --- 1. Fix Route Names ---
    st.subheader("Data Mapping")
    cols = df.columns.tolist()
    
    # Intelligent default for name column
    default_name_col = cols[0]
    for c in ['climb_name', 'name', 'title', 'route']:
        if c in cols:
            default_name_col = c
            break
            
    name_col = st.selectbox(
        "Which column is the Name?", 
        cols, 
        index=cols.index(default_name_col),
        help="If names look wrong, change this column."
    )
    
    # --- 2. Fix Difficulty ---
    # Intelligent default for grade
    default_grade_col = cols[0]
    for c in ['difficulty', 'grade', 'display_difficulty', 'v_grade']:
        if c in cols:
            default_grade_col = c
            break
            
    grade_col = st.selectbox("Which column is the Grade?", cols, index=cols.index(default_grade_col))
    
    # Ensure grade is numeric for sliders
    df['normalized_grade'] = pd.to_numeric(df[grade_col], errors='coerce').fillna(0).astype(int)
    
    # --- 3. Performance Tuning ---
    st.divider()
    st.subheader("Performance")
    max_points = st.slider(
        "Max Dots (Improves Zoom Speed)", 
        min_value=500, 
        max_value=len(df), 
        value=2000, 
        step=500,
        help="Showing 8k points on a phone is laggy. Lower this for smoother zooming."
    )

# ==========================================
# MAIN FILTERS
# ==========================================
# Top bar filters for quick access
f_col1, f_col2 = st.columns([1, 2])

with f_col1:
    # Grade Range
    min_g = int(df['normalized_grade'].min())
    max_g = int(df['normalized_grade'].max())
    grade_range = st.slider("Grade Range", min_g, max_g, (min_g, max_g))

with f_col2:
    # Text Search (Replaces useless dropdown)
    search_query = st.text_input("Search Route Name", placeholder="e.g. 'Jedi Mind Tricks'...")

# Apply Filters
mask = (
    (df['normalized_grade'] >= grade_range[0]) & 
    (df['normalized_grade'] <= grade_range[1])
)

# Text Search Logic
if search_query:
    mask = mask & (df[name_col].astype(str).str.contains(search_query, case=False, na=False))

filtered_df = df[mask].copy()

# ==========================================
# CHART OPTIMIZATION
# ==========================================
# Subsample for performance if needed
if len(filtered_df) > max_points:
    # Try to sort by 'ascents' or 'stars' if available to show "best" routes first
    sort_candidates = [c for c in df.columns if 'ascent' in c.lower() or 'star' in c.lower()]
    if sort_candidates:
        chart_df = filtered_df.sort_values(sort_candidates[0], ascending=False).head(max_points)
        st.caption(f"Showing top {max_points} of {len(filtered_df)} routes (sorted by {sort_candidates[0]})")
    else:
        chart_df = filtered_df.sample(max_points)
        st.caption(f"Showing random {max_points} of {len(filtered_df)} routes")
else:
    chart_df = filtered_df
    st.caption(f"Showing {len(chart_df)} routes")

# ==========================================
# UI LAYOUT
# ==========================================
col1, col2 = st.columns([1.5, 1])

# --- LEFT: INTERACTIVE MAP ---
with col1:
    # Selection object
    sel = alt.selection_point(
        name="point_select",
        on="click", 
        fields=['uuid'], 
        empty=False
    )

    # Base Chart
    base = alt.Chart(chart_df).encode(
        x=alt.X('x', axis=None),
        y=alt.Y('y', axis=None),
        color=alt.Color('normalized_grade', title="Grade", scale=alt.Scale(scheme='turbo')),
        tooltip=[name_col, grade_col]
    )

    # Points
    points = base.mark_circle(size=80, opacity=0.8).encode(
        # Conditional opacity for selection
        opacity=alt.condition(sel, alt.value(1), alt.value(0.1)),
        # Conditional size for selection (make selected pop)
        size=alt.condition(sel, alt.value(200), alt.value(80))
    ).add_params(sel).interactive()

    # RENDER WITH ON_SELECT (Fixes the clicking issue)
    # This requires Streamlit >= 1.35.0
    try:
        event = st.altair_chart(points, use_container_width=True, on_select="rerun", theme="streamlit")
    except TypeError:
        st.error("⚠️ You need a newer version of Streamlit (>=1.35) for click events to work perfectly.")
        event = st.altair_chart(points, use_container_width=True, theme="streamlit")

# --- RIGHT: BOARD VIEW ---
with col2:
    selected_uuid = None
    selected_name = "None"
    selected_grade = ""

    # 1. Check if user CLICKED the chart
    if event and hasattr(event, 'selection') and 'point_select' in event.selection:
        selection_data = event.selection['point_select']
        if selection_data:
            # Altair returns a list of dicts, grab the first one
            selected_uuid = selection_data[0]['uuid']
            
            # Look up details
            row = df[df['uuid'] == selected_uuid].iloc[0]
            selected_name = row[name_col]
            selected_grade = f"V{row['normalized_grade']}"

    # 2. Check if user SEARCHED (Override click if search matches exactly 1)
    if search_query and len(filtered_df) == 1:
        row = filtered_df.iloc[0]
        selected_uuid = row['uuid']
        selected_name = row[name_col]
        selected_grade = f"V{row['normalized_grade']}"

    # --- BOARD RENDERER ---
    def generate_board_svg(uuid, holds_map, layout):
        width, height = 150, 160
        svg = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#151515" rx="4" />']
        
        route_holds = holds_map.get(uuid, [])
        if not route_holds:
            return f'<svg viewBox="0 0 {width} {height}"><text x="75" y="80" fill="#555" text-anchor="middle" font-family="sans-serif" font-size="10">Select a Route</text></svg>'

        for h in route_holds:
            # Robust lookup (int/str)
            coords = layout.get(h) or layout.get(str(h)) or layout.get(int(h) if str(h).isdigit() else -1)
            if coords:
                cx, cy = coords['x'], coords['y']
                # Glow
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="#00FFFF" opacity="0.4" filter="blur(2px)" />')
                # Core
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="#EEFFFF" />')
                # Ring
                svg.append(f'<circle cx="{cx}" cy="{cy}" r="4" stroke="#00FFFF" stroke-width="0.8" fill="none" />')
        
        return f'<svg viewBox="0 0 {width} {height}" style="width:100%; height:auto; max-height:70vh; background:#222; border-radius:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">{ "".join(svg) }</svg>'

    # Display Selection Info
    if selected_uuid:
        st.markdown(f"### {selected_name} <span style='color:cyan'>{selected_grade}</span>", unsafe_allow_html=True)
        # Show board
        st.markdown(generate_board_svg(selected_uuid, holds_map, layout_map), unsafe_allow_html=True)
    else:
        st.info("👆 Tap a dot on the chart to view")
        st.markdown(generate_board_svg(None, {}, {}), unsafe_allow_html=True)
