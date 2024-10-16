import os
import time
import re
import pandas as pd
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from datetime import datetime

# Load world list from the bundled or local CSV file
csv_path = 'Members World List - Non-PvP - Sheet1.csv'
world_list = pd.read_csv(csv_path)
log_file = 'traceroute_log.txt'

# Available regions
regions = {
    "United States (west)": "United States (west)",
    "United States (east)": "United States (east)",
    "United States (combined)": ["United States (east)", "United States (west)"],
    "United Kingdom": "United Kingdom",
    "Germany": "Germany",
    "Australia": "Australia"
}

# CSV file to store traceroute results
csv_output = 'traceroute_data.csv'


# Ensure CSV has headers if starting fresh
def ensure_csv_headers():
    if not os.path.exists(csv_output):
        with open(csv_output, 'w') as csv_file:
            csv_file.write('Weekday,Date,Time,World,Ping (ms),Packet Loss (%),Jitter (ms),Hops,Status\n')


ensure_csv_headers()


# Function to filter worlds by region(s) and return the URLs
def filter_urls_by_region(selected_region):
    if selected_region == "United States (combined)":
        filtered_worlds = world_list[world_list['Location'].isin(regions["United States (combined)"])]
    else:
        filtered_worlds = world_list[world_list['Location'] == selected_region]

    return filtered_worlds['URL'].tolist()


def run_ping(destination):
    if os.name == 'nt':  # For Windows
        command = f'ping -n 10 -w 10000 {destination}'  # 3 pings, 10-second timeout for each
    else:  # For Unix/Linux systems
        command = f'ping -c 10 -W 10 {destination}'  # 3 pings, 10-second timeout
    result = os.popen(command).read()
    return result


def extract_rtt_and_status(ping_output):
    rtt_pattern = re.compile(r'(\d+)\s?ms')
    packet_loss_pattern = re.compile(r'(\d+)%\s*loss')

    if "Ping request could not find host" in ping_output or not ping_output.strip():
        return None, None, None, 0, False  # Return False to indicate the destination was not reachable

    rtts = []
    for line in ping_output.splitlines():
        match = rtt_pattern.search(line)
        if match:
            rtt = int(match.group(1))
            rtts.append(rtt)

    if not rtts:
        return None, None, None, 0, False  # If no RTTs were captured, the destination was not reachable

    # Calculate average RTT and jitter
    avg_rtt = sum(rtts) // len(rtts)
    jitter = max(rtts) - min(rtts) if len(rtts) > 1 else 0

    # Simulate 0 packet loss if not found
    packet_loss_match = packet_loss_pattern.search(ping_output)
    packet_loss = int(packet_loss_match.group(1)) if packet_loss_match else 0

    # For traceroute, calculate number of hops based on ping responses
    # Here, hops will be the number of distinct RTT entries (i.e., the number of pings that successfully returned)
    hops = len(rtts)

    return avg_rtt, packet_loss, jitter, hops, True


# GUI Class with start/stop functionality and 15-minute interval
class TracerouteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Traceroute Tool")
        self.run_flag = False  # Control the start/stop toggle
        self.traceroute_thread = None  # Thread for running traceroutes

        # Configure grid to allow resizing
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(3, weight=1)  # For the output box

        # Dropdown for region selection
        self.region_label = ttk.Label(root, text="Select Region:")
        self.region_label.grid(row=0, column=0, padx=10, pady=10, sticky="e")

        self.region_var = tk.StringVar()
        self.region_dropdown = ttk.Combobox(root, textvariable=self.region_var, values=list(regions.keys()))
        self.region_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Set default to "United States (combined)"
        self.region_dropdown.current(list(regions.keys()).index("United States (combined)"))

        # Add a toggle button to start/stop the traceroute loop
        self.toggle_button = ttk.Button(root, text="Start Traceroute", command=self.toggle_traceroute)
        self.toggle_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        # Output text box for displaying results
        self.output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD)
        self.output_box.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")  # Make it resizable

    def toggle_traceroute(self):
        if not self.run_flag:
            self.run_flag = True
            self.toggle_button.config(text="Stop Traceroute")
            self.traceroute_thread = threading.Thread(target=self.run_traceroutes_loop)
            self.traceroute_thread.start()
        else:
            self.run_flag = False
            self.toggle_button.config(text="Start Traceroute")

    def run_traceroutes(self):
        region = self.region_var.get()
        return filter_urls_by_region(region)

    def run_traceroutes_loop(self):
        while self.run_flag:
            # Filter the worlds by region and show progress
            region = self.region_var.get()
            worlds = filter_urls_by_region(region)
            total_worlds = len(worlds)

            self.output_box.insert(tk.END, f"Starting scan for {total_worlds} worlds...\n")
            self.output_box.see(tk.END)

            for idx, world in enumerate(worlds, start=1):
                # Update the output for each world
                self.output_box.insert(tk.END, f"Running traceroute for {world} ({idx} of {total_worlds})...\n")
                self.output_box.see(tk.END)

                # Perform the traceroute and store the result
                traceroute_output = run_ping(world)
                final_rtt, packet_loss, jitter, hops, success = extract_rtt_and_status(traceroute_output)

                if success:
                    self.output_box.insert(tk.END, f"Traceroute for {world} successful: {final_rtt} ms, {hops} hops\n")
                else:
                    self.output_box.insert(tk.END, f"Skipping {world} due to traceroute failure.\n")

                self.output_box.see(tk.END)

                # Save the result after processing each world
                self.save_single_traceroute_to_csv(world, final_rtt, packet_loss, jitter, hops, success)

                # Add 10-second delay before moving to the next traceroute
                time.sleep(10)

            self.output_box.insert(tk.END, "Finished, waiting for next scan...\n")
            self.output_box.see(tk.END)

            # Wait for 15 minutes before running again
            for _ in range(2 * 60):
                if not self.run_flag:
                    break  # If stopped during wait, exit the loop
                time.sleep(1)  # Sleep in 1-second increments to be responsive to stop requests

    @staticmethod
    def save_single_traceroute_to_csv(server, final_rtt, packet_loss, jitter, hops, success):
        # Extract world number (adjusting by +300 as needed)
        world_number = int(server[9:-14]) + 300

        # Get the current date and time
        now = datetime.now()
        weekday = now.strftime('%A')
        date = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        # Save the data to CSV immediately after each traceroute
        with open(csv_output, "a") as csv_file:
            if success:
                row = f"{weekday},{date},{time_str},{world_number},{final_rtt},{packet_loss},{jitter},{hops},Success\n"
            else:
                row = f"{weekday},{date},{time_str},{world_number},N/A,N/A,N/A,{hops},Failure\n"
            csv_file.write(row)


# Run the application
if __name__ == "__main__":
    window = tk.Tk()
    window.geometry("800x600+400+400")  # Set the window size to 800x600 (Width x Height)
    app = TracerouteApp(window)
    window.mainloop()
