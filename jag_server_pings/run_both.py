import subprocess
import threading


def run_ping_tracker():
    # This runs the ping tracker (traceroute tool)
    subprocess.run(["python", "check_jag_connections.py"])


def run_shiny_app():
    # This runs the Shiny app
    subprocess.run(["python", "app.py"])


# Run both the ping tracker and Shiny app in parallel threads
if __name__ == "__main__":
    tracker_thread = threading.Thread(target=run_ping_tracker)
    app_thread = threading.Thread(target=run_shiny_app)

    # Start both threads
    tracker_thread.start()
    app_thread.start()

    # Wait for both to finish
    tracker_thread.join()
    app_thread.join()
