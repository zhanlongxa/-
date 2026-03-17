#!/usr/bin/env python3
"""
Launcher wrapper for Smart Caption Studio
Opens browser and keeps the Flask app running
"""
import subprocess
import time
import webbrowser
import sys
import os

def main():
    print("🚀 Starting Smart Caption Studio...")
    
    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        bundle_dir = sys._MEIPASS
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        bundle_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = bundle_dir
    
    # Import and run the Flask app
    sys.path.insert(0, bundle_dir)
    
    # Start the Flask app in a separate thread
    from threading import Thread
    
    def run_flask():
        # Import the Flask app
        import app
        # The app will start automatically when imported
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)
    
    # Open browser
    print("🌐 Opening browser...")
    webbrowser.open('http://localhost:5031')
    
    print("✅ Smart Caption Studio is running!")
    print("📌 Access: http://localhost:5031")
    print("⚠️  Do not close this window - it will stop the application")
    print("\nPress Ctrl+C to quit")
    
    # Keep the app running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)

if __name__ == '__main__':
    main()
