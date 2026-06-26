"""Streamlit styling — global app theme and review workspace components."""

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
                max-width: 100%;
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_review_workspace_styles() -> None:
    st.markdown(
        """
        <style>
            .preview-panel-anchor {
                min-height: 4rem;
                margin-bottom: 0.75rem;
            }
            .preview-panel-empty {
                background: #f8fafc;
                border: 1px dashed #cbd5e1;
                border-radius: 10px;
                color: #64748b;
                font-size: 0.9rem;
                padding: 1rem 1.25rem;
                text-align: center;
            }
            .review-header-cell {
                font-size: 0.72rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: #475569;
                padding: 0.25rem 0.15rem 0.5rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .review-cell {
                border-radius: 8px;
                padding: 0.45rem 0.55rem;
                font-size: 0.82rem;
                color: #1e293b;
                min-height: 2.1rem;
                line-height: 1.35;
                border: 1px solid #e2e8f0;
                word-break: break-word;
            }
            .review-row {
                padding: 0.15rem 0;
            }
            .review-row--active {
                background: #eff6ff;
                border-radius: 10px;
                padding: 0.35rem 0.25rem;
                margin: 0.1rem 0;
            }
            .review-pdf-frame {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            div[data-testid="stVerticalBlock"] > div:has(.review-row) {
                gap: 0.15rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
