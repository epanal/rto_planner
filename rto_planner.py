import streamlit as st
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta
import pytz

API_KEY = st.secrets["API_KEY"]

if not API_KEY:
    raise ValueError("weather api is missing! Check .env file.")

def get_next_workday():
    pacific = pytz.timezone("America/Los_Angeles")
    today_local = datetime.now(pacific)  # Get current time in California
    next_day = today_local + timedelta(days=1)

    while next_day.weekday() >= 5:  # Skip Saturday (5) and Sunday (6)
        next_day += timedelta(days=1)

    return next_day

def get_weather(zip_code):
    # Get current weather
    current_url = f"https://api.openweathermap.org/data/2.5/weather?zip={zip_code},us&appid={API_KEY}&units=imperial"
    current_response = requests.get(current_url)

    # Get forecasted weather
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?zip={zip_code},us&appid={API_KEY}&units=imperial"
    forecast_response = requests.get(forecast_url)

    current_weather = None
    forecast_weather = None

    if current_response.status_code == 200:
        current_data = current_response.json()
        current_weather = {
            "temp": current_data["main"]["temp"],
            "condition": current_data["weather"][0]["description"],
        }

    if forecast_response.status_code == 200:
        forecast_data = forecast_response.json()
        next_workday = get_next_workday().date()

        # Find the forecast closest to noon (12 PM) on the next workday
        closest_forecast = None
        min_time_diff = float("inf")

        for entry in forecast_data["list"]:
            forecast_time = datetime.fromtimestamp(entry["dt"])
            if forecast_time.date() == next_workday:
                # Calculate the time difference from noon (12:00 PM)
                time_diff = abs(forecast_time.hour - 12)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_forecast = entry

        if closest_forecast:
            forecast_weather = {
                "date": forecast_time.strftime("%A, %B %d"),
                "temp": closest_forecast["main"]["temp"],
                "condition": closest_forecast["weather"][0]["description"],
            }

    return current_weather, forecast_weather


# Packing suggestions based on forecasted weather
def get_packing_recommendations(weather):
    items = ["Laptop", "Work Badge", "AirPods", "Podcast Playlist", "Webcam", "BART Parking or Amtrak Ticket Paid"]  # Default essentials

    if weather:
        if weather["temp"] < 55:
            items.append("Jacket")
        if "rain" in weather["condition"]:
            items.append("Umbrella")
        if "clear" in weather["condition"] and weather["temp"] > 75:
            items.append("Sunglasses")

    return items

# Function to fetch and parse BART GTFS-Realtime data
def get_bart_real_time():
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get('https://api.bart.gov/gtfsrt/tripupdate.aspx')
    feed.ParseFromString(response.content)
    return feed

# Function to convert Unix timestamp to readable time
def format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%I:%M %p')

def get_motivational_quote():
    response = requests.get("https://zenquotes.io/api/random")
    if response.status_code == 200:
        quote_data = response.json()
        return f"💡 *{quote_data[0]['q']}* - {quote_data[0]['a']}"
    return "💡 Stay positive, work hard, and make it happen!"

# Function to filter trips from Daly City within the desired time range
def filter_bart_trips(feed):
    filtered_trips = []
    for entity in feed.entity:
        if entity.trip_update:
            for stop in entity.trip_update.stop_time_update:
                if stop.stop_id == "DALY" and stop.arrival.time:
                    departure_time = datetime.fromtimestamp(stop.arrival.time)
                    if departure_time.weekday() < 5 and 6*60 + 40 <= departure_time.hour*60 + departure_time.minute <= 7*60 + 20:
                        filtered_trips.append({
                            "route": entity.trip_update.trip.route_id,
                            "time": format_time(stop.arrival.time)
                        })
    return filtered_trips

# Streamlit UI
st.title("🏢 Ethan's RTO Planner")

st.subheader("🌟 Daily Motivation")
st.write(get_motivational_quote())

# Get the next workday
next_workday = get_next_workday().strftime("%A, %B %d")
st.subheader(f"🌤 Weather for {next_workday}")

# Get weather for both locations
home_current, home_forecast = get_weather("94040")  # Mountain View, CA
office_current, office_forecast = get_weather("94612")  # Oakland, CA

col1, col2 = st.columns(2)

# Display Home Weather (Current & Forecasted)
with col1:
    st.write("🏠 **Home (Mountain View, 94040)**")
    if home_current:
        st.write(f"**Current:** {home_current['temp']}°F, {home_current['condition']}")
    else:
        st.write("⚠️ Error fetching current weather")

    if home_forecast:
        st.write(f"**Forecast for {next_workday}:** {home_forecast['temp']}°F, {home_forecast['condition']}")
    else:
        st.write("⚠️ Error fetching forecast")

# Display Office Weather (Current & Forecasted)
with col2:
    st.write("🏢 **Office (Oakland, 94612)**")
    if office_current:
        st.write(f"**Current:** {office_current['temp']}°F, {office_current['condition']}")
    else:
        st.write("⚠️ Error fetching current weather")

    if office_forecast:
        st.write(f"**Forecast for {next_workday}:** {office_forecast['temp']}°F, {office_forecast['condition']}")
    else:
        st.write("⚠️ Error fetching forecast")

# Get packing recommendations based on next workday's forecast
packing_list = get_packing_recommendations(office_forecast)

st.subheader("🎒 Packing Checklist")
for item in packing_list:
    st.checkbox(item, key=item)

# Fetch BART real-time data
bart_feed = get_bart_real_time()
filtered_trips = filter_bart_trips(bart_feed)

# Display BART real-time departures
st.subheader("🚆 BART Real-Time Departures from Daly City (Weekdays 6:40 AM - 7:20 AM)")

if filtered_trips:
    for trip in filtered_trips:
        st.write(f"Train to {trip['route']} departing at {trip['time']}")
else:
    st.write("No trains available in this time window.")
