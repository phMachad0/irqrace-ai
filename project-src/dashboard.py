"""Streamlit launcher for the IRQRace Pipeline Visualizer & Dashboard.

Run with:
    .\\venv\\Scripts\\python.exe -m streamlit run project-src/dashboard.py
or:
    irqrace ui
"""

from irqrace.ui.app import main

if __name__ == "__main__":
    main()
