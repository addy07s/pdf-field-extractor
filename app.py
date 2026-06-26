"""Deprecated Streamlit entrypoint — use FastAPI + React instead."""

from __future__ import annotations

import streamlit as st

DEPRECATION_MESSAGE = (
    "This legacy Streamlit interface has been deprecated. "
    "Please use the new high-interactivity React frontend. "
    "Start the application by running the FastAPI backend "
    "(uvicorn main:app --port 8000) and the React client "
    "(npm run dev inside the frontend directory)."
)


def main() -> None:
    st.set_page_config(page_title="Deprecated — GST Invoice Field Extractor", layout="centered")
    st.error(DEPRECATION_MESSAGE)
    st.markdown(
        """
        ### How to run the current application

        **Terminal 1 — API**
        ```bash
        uvicorn main:app --reload --port 8000
        ```

        **Terminal 2 — UI**
        ```bash
        cd frontend
        npm run dev
        ```

        Open [http://localhost:5173](http://localhost:5173) in your browser.
        """
    )


if __name__ == "__main__":
    print(DEPRECATION_MESSAGE)
    main()
