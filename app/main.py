import streamlit as st
import cv2
import tempfile
import time
import pandas as pd
from PIL import Image
import numpy as np
from datetime import datetime
import os
import pytz
import plotly.express as px

from database import get_all_vehicles, add_or_update_vehicle, delete_vehicle, get_all_challans, init_db
from detector import VehicleDetector, draw_annotations
from logic import check_violations, get_summary_stats

IST = pytz.timezone('Asia/Kolkata')

# Page Configuration
st.set_page_config(page_title="AI Smart Vehicle Pollution & Violation Detection", layout="wide")

# Initialize Database
init_db()

# --- Custom Styling (High-Contrast Light Theme) ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    .stMarkdown, .stText, h1, h2, h3, p, span, label { color: #111827 !important; }
    section[data-testid="stSidebar"] { background-color: #f3f4f6 !important; border-right: 1px solid #e5e7eb; }
    section[data-testid="stSidebar"] * { color: #111827 !important; }
    div[data-testid="stMetricValue"] { color: #2563eb !important; font-weight: bold !important; }
    div[data-testid="stMetricLabel"] { color: #4b5563 !important; }
    .stTable { background-color: #f9fafb !important; border: 1px solid #e5e7eb !important; border-radius: 8px !important; }
    .stTable th { background-color: #f3f4f6 !important; color: #111827 !important; font-weight: bold !important; }
    .stTable td { color: #374151 !important; border-bottom: 1px solid #f3f4f6 !important; }
    .stAlert { background-color: #fef2f2 !important; color: #991b1b !important; border: 1px solid #fee2e2 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("🚔 System Controls")
app_mode = st.sidebar.selectbox("Choose the App Mode", ["Real-time Dashboard", "Database Management", "Analytics & Reports"])

# --- Cache Detector ---
@st.cache_resource
def get_detector():
    return VehicleDetector()

detector = get_detector()

# --- Real-time Dashboard ---
if app_mode == "Real-time Dashboard":
    st.title("🚦 Real-time Pollution & Violation Detection")
    st.info("Upload a traffic video to start the AI analysis.")

    video_file = st.file_uploader("Upload Traffic Video (MP4, AVI)", type=['mp4', 'avi', 'mov'])
    
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📺 Live Feed & Detection")
        video_placeholder = st.empty()
        
    with col2:
        st.subheader("📝 Detected Vehicles")
        table_placeholder = st.empty()
        st.subheader("⚠️ Violation Alerts")
        alert_placeholder = st.empty()

    if video_file is not None:
        # Session state to track data across mode switches
        if 'last_vid' not in st.session_state or st.session_state.last_vid != video_file.name:
            st.session_state.processed_this_video = set()
            st.session_state.detected_list = []
            st.session_state.alerts_log = []
            st.session_state.last_vid = video_file.name
            st.session_state.processing_complete = False
            st.session_state.current_frame = 0

        # Only process if not already complete for this file
        if not st.session_state.get('processing_complete', False):
            tfile = tempfile.NamedTemporaryFile(delete=False)
            tfile.write(video_file.read())
            cap = cv2.VideoCapture(tfile.name)
            
            if st.session_state.current_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, st.session_state.current_frame)
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret: break
                
                st.session_state.current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

                if st.session_state.current_frame % 5 != 0:
                    continue

                detections = detector.detect_vehicles(frame)
                
                for det in detections:
                    plate_text, plate_box = detector.extract_plate(frame, det['coords'])
                    
                    if plate_text and plate_text in st.session_state.processed_this_video:
                        continue

                    has_smoke = detector.detect_smoke(frame, det['coords'])
                    det['plate'] = plate_text
                    det['plate_coords'] = plate_box
                    det['smoke'] = has_smoke
                    
                    if plate_text:
                        violations, fine, owner = check_violations(plate_text, has_smoke)
                        status = "VIOLATION" if violations else "OK"
                        
                        st.session_state.processed_this_video.add(plate_text)

                        already_listed = any(d['Plate'] == plate_text for d in st.session_state.detected_list)
                        if not already_listed:
                            st.session_state.detected_list.append({
                                'Time': datetime.now(IST).strftime("%H:%M:%S"),
                                'Plate': plate_text,
                                'Type': det['label'].capitalize(),
                                'Owner': owner,
                                'Status': status
                            })
                            if violations:
                                st.session_state.alerts_log.insert(0, f"🔔 {plate_text}: {', '.join(violations)}")

                annotated_frame = draw_annotations(frame, detections)
                frame_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
                video_placeholder.image(frame_rgb, use_column_width=True)
                
                if st.session_state.detected_list:
                    df = pd.DataFrame(st.session_state.detected_list).tail(10)
                    table_placeholder.table(df)
                
                if st.session_state.alerts_log:
                    alert_placeholder.markdown("\n".join(st.session_state.alerts_log[:5]))
                
                time.sleep(0.01)

            cap.release()
            st.session_state.processing_complete = True
            st.success("Video processing complete!")

    # --- PERSISTENT DISPLAY ---
    # This part runs even if video_file is None, as long as app_mode is "Real-time Dashboard"
    if st.session_state.get('detected_list'):
        with col2:
            df = pd.DataFrame(st.session_state.detected_list).tail(10)
            table_placeholder.table(df)
        if st.session_state.alerts_log:
            alert_placeholder.markdown("\n".join(st.session_state.alerts_log[:5]))

# --- Database Management ---
elif app_mode == "Database Management":
    st.title("🗃️ RTO Vehicle Database Manager")
    vehicles = get_all_vehicles()
    df_vehicles = pd.DataFrame(vehicles, columns=['Plate', 'Owner', 'Type', 'Reg Year', 'PUC Expiry'])
    df_vehicles['Reg Year'] = df_vehicles['Reg Year'].astype(str)
    st.dataframe(df_vehicles, use_container_width=True)

    st.divider()
    st.subheader("Add or Update Vehicle Record")
    colA, colB, colC = st.columns(3)
    with colA:
        plate = st.text_input("License Plate Number", placeholder="MH12DE1234")
        owner = st.text_input("Owner Name")
    with colB:
        vtype = st.selectbox("Vehicle Type", ["Car", "Bus", "Truck", "Bike", "Auto", "Other"])
        regyear = st.selectbox("Registration Year", list(range(1990, 2026)), index=25)
    with colC:
        pucdate = st.date_input("PUC Expiry Date")
        
    if st.button("💾 Save to Database"):
        if plate and owner:
            add_or_update_vehicle(plate, owner, vtype, regyear, pucdate.strftime('%Y-%m-%d'))
            st.success(f"Vehicle {plate} updated successfully!")
            time.sleep(1)
            st.rerun()

    st.divider()
    st.subheader("🗑️ Delete Vehicle Record")
    col1, col2 = st.columns([2, 1])
    with col1:
        delete_plate = st.selectbox("Select Plate Number to Remove", [""] + [v[0] for v in vehicles])
    with col2:
        st.write("##") # Alignment
        if st.button("Permanently Delete", use_container_width=True):
            if delete_plate:
                delete_vehicle(delete_plate)
                st.error(f"Record for {delete_plate} has been removed.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Please select a plate number first.")

# --- Analytics & Reports ---
elif app_mode == "Analytics & Reports":
    st.title("📊 Pollution & Violation Analytics")
    challans = get_all_challans()
    if not challans:
        st.warning("No violations logged yet.")
    else:
        stats = get_summary_stats(challans)
        # --- Top Metrics Dashboard ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🚨 Total Challans", stats['total_violations'])
        m2.metric("💰 Total Fines (₹)", f"{stats['total_fines']:,}")
        m3.metric("📅 PUC Violations", stats['puc_violations'])
        m4.metric("💨 Smoke Violations", stats['smoke_violations'])
        
        st.divider()

        # --- Violation Data Processing ---
        df_c = pd.DataFrame(challans, columns=['ID', 'Plate', 'Violation', 'Amount', 'Timestamp'])
        
        # Flatten and count individual violations
        all_violations = []
        for v_str in df_c['Violation']:
            # Handle comma-separated violations reliably
            parts = [v.strip() for v in v_str.split(',') if v.strip()]
            all_violations.extend(parts)
        
        if all_violations:
            v_counts = pd.Series(all_violations).value_counts().reset_index()
            v_counts.columns = ['Violation Type', 'Frequency']

            # --- Layout: Charts Row ---
            c1, c2 = st.columns([1, 1.2])

            with c1:
                st.subheader("💡 Violation Contribution")
                fig_pie = px.pie(
                    v_counts, 
                    values='Frequency', 
                    names='Violation Type', 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                st.subheader("📊 Violation Intensity")
                fig_bar = px.bar(
                    v_counts, 
                    x='Violation Type', 
                    y='Frequency', 
                    color='Violation Type',
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    text_auto=True
                )
                fig_bar.update_layout(
                    xaxis_title="", 
                    yaxis_title="Total Count",
                    showlegend=False,
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()
        st.subheader("📜 Recent Challan Records")
        st.table(df_c)
