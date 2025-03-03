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
    now_local = datetime.now(pacific)

    # If it's after noon (12 PM), get the next workday
    if now_local.hour >= 12:
        next_day = now_local + timedelta(days=1)
    else:
        next_day = now_local  # Keep today if it's before noon

    # Skip weekends
    while next_day.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
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
    items = ["Laptop", "Work Badge", "AirPods", "Webcam", "BART Parking or Amtrak Ticket Paid"]  # Default essentials

    if weather:
        if weather["temp"] < 55:
            items.append("Jacket")
        if "rain" in weather["condition"]:
            items.append("Umbrella")
        if "clear" in weather["condition"] and weather["temp"] > 75:
            items.append("Sunglasses")

    return items

# Function to convert Unix timestamp to readable time
def format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%I:%M %p')

def get_motivational_quote():
    response = requests.get("https://zenquotes.io/api/random")
    if response.status_code == 200:
        quote_data = response.json()
        return f"💡 *{quote_data[0]['q']}* - {quote_data[0]['a']}"
    return "💡 Stay positive, work hard, and make it happen!"

def get_daly_city_alerts():
    response = requests.get("https://api.bart.gov/api/bsa.aspx?cmd=bsa&json=y")
    data = response.json()
    
    alerts = data.get('root', {}).get('bsa', [])
    daly_city_alerts = []
    
    if alerts and isinstance(alerts, list):
        for alert in alerts:
            description = alert.get('description', {}).get('#cdata-section', '')
            if "Daly City" in description:
                daly_city_alerts.append(description)
    
    if daly_city_alerts:
        print("🚨 Daly City Alerts 🚨")
        for alert in daly_city_alerts:
            print(f"⚠️ {alert}")
    else:
        print("✅ No service alerts for Daly City!")

def get_bart_real_time():
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get('https://api.bart.gov/gtfsrt/tripupdate.aspx')
    feed.ParseFromString(response.content)
    return feed

def filter_bart_trips(feed):
    filtered_trips = []
    oakland_stations = ["12TH", "19TH", "LAKE", "FTVL", "COLM"]  # Expanded Oakland stops
    min_time = 6 * 60 + 30  # 6:30 AM
    max_time = 7 * 60 + 30  # 7:30 AM

    for entity in feed.entity:
        if entity.trip_update:
            for stop in entity.trip_update.stop_time_update:
                stop_id = stop.stop_id  # Debugging
                arrival_time = stop.arrival.time if stop.HasField("arrival") else None
                
                if stop_id == "DALY" and arrival_time:
                    departure_time = datetime.fromtimestamp(arrival_time)
                    departure_minutes = departure_time.hour * 60 + departure_time.minute

                    if departure_time.weekday() < 5 and min_time <= departure_minutes <= max_time:
                        # Check for a later Oakland-bound stop
                        is_oakland_trip = any(
                            s.stop_id in oakland_stations and s.arrival.time > arrival_time
                            for s in entity.trip_update.stop_time_update
                        )

                        if is_oakland_trip:
                            filtered_trips.append({
                                "route": entity.trip_update.trip.route_id,
                                "time": format_time(arrival_time)
                            })

    # Debugging: Print if no trains found
    if not filtered_trips:
        print("⚠️ No BART trains found in time window! Check stop IDs and time filtering.")

    return filtered_trips

# Streamlit UI
st.title("🏢 Ethan's Commute App")

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

# Podcast 
st.subheader("🎙 Podcasts")
st.markdown("[🎧 The Best One Yet (TBOY)](https://open.spotify.com/show/5RllMBgvDnTau8nnsCUdse)")
st.markdown("[🎧 Morning Brew Daily](https://open.spotify.com/show/7nc7OQdPTekErtFSRxOBKh)")
st.markdown("[🎧 NPR Life Kit](https://open.spotify.com/show/5J0xAfsLX7bEYzGxOin4Sd)")


# Fetch BART real-time data
bart_feed = get_bart_real_time()
filtered_trips = filter_bart_trips(bart_feed)

# Fetch BART alerts
bart_alerts = get_daly_city_alerts()

# Display BART alerts
st.subheader("🚆 Current Daly City BART alerts")
st.write(bart_alerts)

# Display BART real-time departures
st.subheader("🚆 BART Real-Time Departures from Daly City (Weekdays 6:40 AM - 7:20 AM)")

if filtered_trips:
    for trip in filtered_trips:
        st.write(f"Train to {trip['route']} departing at {trip['time']}")
else:
    st.write("No trains available in this time window.")


