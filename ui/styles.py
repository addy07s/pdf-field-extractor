"""Minimal Streamlit styling — CSS only, no custom HTML widgets."""

import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background-color: #f8fafc;
            }
            [data-testid="stSidebar"] {
                background-color: #ffffff;
                border-right: 1px solid #e2e8f0;
            }
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
                max-width: 1100px;
            }
            h1 {
                color: #0f172a !important;
                font-weight: 700 !important;
            }
            .stButton > button[kind="primary"] {
                border-radius: 8px;
                font-weight: 600;
                padding: 0.55rem 1.5rem;
            }
            [data-testid="stFileUploader"] {
                border: 1px dashed #cbd5e1;
                border-radius: 10px;
                padding: 0.25rem;
                background: #ffffff;
            }
            [data-testid="stDataFrame"] {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                overflow: hidden;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
