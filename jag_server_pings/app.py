import pandas as pd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from shinyswatch import theme
from faicons import icon_svg
from shared import df  # Import data from shared.py
from shiny import App, reactive, render, ui

# Set the auto-refresh interval (in milliseconds, e.g., 300000 = 5 minutes)
AUTO_REFRESH_INTERVAL = 300000  # 5 minutes

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_date_range("daterange", "Select Date Range", start=df['Date'].min(), end=df['Date'].max()),
        ui.input_select("weekday", "Select Weekday",
                        choices=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                        multiple=True),
        ui.input_slider("time_range", "Select Time Range (Hours)", min=0, max=23, value=(0, 23)),
        title="Filter controls"
    ),
    ui.layout_column_wrap(
        ui.value_box(
            "Top World",
            ui.output_text("top_world"),
            showcase=icon_svg("globe"),
        ),
        ui.value_box(
            "Top World Stability",
            ui.output_text("stability"),
            showcase=icon_svg("signal"),
        ),
        fill=False,
    ),
    ui.layout_columns(
        ui.card(
            ui.card_header("Top 5 Worlds by Stability"),
            ui.output_plot("top_worlds_plot"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Data Summary"),
            ui.output_data_frame("summary_statistics"),
            full_screen=False,
        ),
    ),
    theme=theme.vapor,
    title="Jagex Server Stability Dashboard",
    fillable=True,
)


def calculate_world_stability(world_data):
    if world_data.empty or len(world_data[world_data["Status"] == "Success"]) == 0:
        return 0

    # Success rate (number of successes / total connections)
    success_rate = len(world_data[world_data["Status"] == "Success"]) / len(world_data)

    # Adjusted ping quality: smoother gradient for values 62-80ms
    def ping_quality_function(ping):
        if ping <= 62:
            return 1.0
        elif 62 < ping <= 68:
            return 0.85
        elif 68 < ping <= 72:
            return 0.7
        elif 72 < ping <= 80:
            return 0.5
        else:
            return 0.3

    ping_quality = world_data[world_data["Status"] == "Success"]["Ping (ms)"].apply(ping_quality_function)
    avg_ping_quality = ping_quality.mean() if not ping_quality.empty else 0

    # Average jitter with a focus on stability (lower is better)
    avg_jitter = world_data["Jitter (ms)"].mean() if "Jitter (ms)" in world_data.columns else 0
    jitter_penalty = 1 / (1 + avg_jitter)

    # Hop quality: focus on keeping it low but not overly penalizing
    avg_hops = world_data["Hops"].mean() if "Hops" in world_data.columns else 0
    hop_penalty = 1 / (1 + avg_hops)

    # Adjusted weights for a balanced approach
    stability_score = (
            (success_rate * 0.3) +   # Higher weight to ensure successful connections are rewarded
            (avg_ping_quality * 0.4) +  # Weight adjusted for smoother ping quality influence
            (jitter_penalty * 0.2) +  # Moderate weight for jitter
            (hop_penalty * 0.1)  # Slightly reduced weight for hops
    )

    # Convert to percentage
    return stability_score * 100


def server(input, output, session):
    @reactive.calc
    def filtered_df():
        # Set auto-refresh interval for the filtered dataframe
        reactive.invalidate_later(AUTO_REFRESH_INTERVAL)

        df_copy = pd.read_csv('traceroute_data.csv')
        df_copy['Date'] = pd.to_datetime(df_copy['Date'], format='%Y-%m-%d')
        start_date, end_date = pd.to_datetime(input.daterange())
        filtered = df_copy[(df_copy['Date'] >= start_date) & (df_copy['Date'] <= end_date)]

        if input.weekday():
            filtered = filtered[filtered['Weekday'].isin(input.weekday())]

        time_range = input.time_range()
        filtered = filtered[(pd.to_datetime(filtered['Time'], format='%H:%M:%S').dt.hour >= time_range[0]) &
                            (pd.to_datetime(filtered['Time'], format='%H:%M:%S').dt.hour <= time_range[1])]

        return filtered

    # Store the top 5 worlds result in a cached variable, so it's reused consistently
    @reactive.calc
    def cached_top_5_worlds():
        successful_worlds = filtered_df()[filtered_df()["Status"] == "Success"]
        worlds = successful_worlds.groupby("World").apply(calculate_world_stability).reset_index(name='Stability')
        return worlds.nlargest(5, 'Stability')

    @render.text
    def top_world():
        # Use the cached version of top 5 worlds to ensure consistency
        top_5 = cached_top_5_worlds()
        best_world = top_5.iloc[0]['World'] if not top_5.empty else "N/A"
        return f"World {int(best_world)}"

    @render.text
    def stability():
        top_5 = cached_top_5_worlds()
        best_world = top_5.iloc[0]['World'] if not top_5.empty else None
        if best_world is None:
            return "N/A"
        world_data = filtered_df()[filtered_df()["World"] == best_world]
        stability_score = calculate_world_stability(world_data)
        return f"{stability_score:.2f}% stability"

    @render.plot
    def top_worlds_plot():
        # Filter data based on current user selection
        filtered_top_5 = filtered_df()[filtered_df()['World'].isin(cached_top_5_worlds()['World'].values)].copy()

        # Ensure 'Date' and 'Time' are combined into a single datetime column for accurate plotting
        filtered_top_5['Datetime'] = pd.to_datetime(filtered_top_5['Date'].astype(str) + ' ' + filtered_top_5['Time'])

        # Group by 'Datetime' and 'World' to get average ping over time
        ping_and_jitter_over_time = filtered_top_5.groupby(['Datetime', 'World'], as_index=False).agg(
            avg_ping=('Ping (ms)', 'mean')
        )

        # Get the start and end datetime from the filtered DataFrame after applying all filters (date, time, weekday)
        if not filtered_top_5.empty:
            datetime_min = filtered_top_5['Datetime'].min()
            datetime_max = filtered_top_5['Datetime'].max()
        else:
            datetime_min, datetime_max = None, None

        # Plot the ping trend over time for the top 5 worlds
        plt.figure(figsize=(10, 6))

        # Loop over each world and plot ping without jitter shadows
        for world in ping_and_jitter_over_time['World'].unique():
            world_data = ping_and_jitter_over_time[ping_and_jitter_over_time['World'] == world]

            # Plot the average ping line
            plt.plot(world_data['Datetime'], world_data['avg_ping'], label=f"World {world}", marker='o')

        # Only set x-limits if there is valid data
        if datetime_min and datetime_max:
            plt.xlim(datetime_min, datetime_max)

        # Format x-axis with appropriate date and time formatting
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())

        plt.title("Ping Trends of Top 5 Stable Worlds")
        plt.ylabel("Ping (ms)")
        plt.xlabel("Date and Time")
        plt.xticks(rotation=45)
        plt.legend(title="World")
        plt.tight_layout()

        return plt.gcf()

    @render.data_frame
    def summary_statistics():
        summary_df = filtered_df().copy()
        summary_df['Date'] = pd.to_datetime(summary_df['Date']).dt.strftime('%Y-%m-%d')
        return summary_df[["Weekday", "Date", "Time", "World", "Ping (ms)", "Packet Loss (%)", "Jitter (ms)", "Hops",
                           "Status"]]


app = App(app_ui, server)
app.run(port=8000)
