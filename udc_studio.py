#!/usr/bin/env python3
"""
UDC-Studio - Visual Configuration Builder for UDC01
----------------------------------------------------
Streamlit-based UI for building UDC01 conversion configurations with AI assistance.

Features:
- Safety verification with 2/3 consensus
- Intelligent data profiling
- YAML configuration generation
- Multi-agent validation

Usage:
    python udc_studio.py

This will launch the Streamlit web interface at http://localhost:8501
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch UDC-Studio Streamlit application"""
    # Path to Streamlit app
    studio_app = Path(__file__).parent / "studio" / "ui" / "streamlit_app.py"

    if not studio_app.exists():
        print(f"Error: Studio app not found at {studio_app}")
        print("Please ensure the studio/ directory is properly set up.")
        sys.exit(1)

    # Launch Streamlit
    print("🛠️  Launching UDC-Studio...")
    print(f"📂 App location: {studio_app}")
    print("🌐 Opening browser at http://localhost:8501")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 60)

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(studio_app),
            "--server.headless", "false"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error launching Streamlit: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down UDC-Studio...")
        sys.exit(0)

if __name__ == "__main__":
    main()
