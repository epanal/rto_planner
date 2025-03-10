import streamlit as st
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta,timezone
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
    items = ["Laptop", "Work Badge", "AirPods", "Webcam", "Snacks/Water","BART Parking Ticket", "Amtrak Ticket"]  # Default essentials

    if weather:
        if weather["temp"] < 55:
            items.append("Jacket")
        if "rain" in weather["condition"]:
            items.append("Umbrella")
        if "clear" in weather["condition"] and weather["temp"] > 75:
            items.append("Sunglasses")

    return items

# Function to convert Unix timestamp to readable time
def format_local_time(timestamp):
    pacific = pytz.timezone("America/Los_Angeles")
    local_time = datetime.fromtimestamp(timestamp, pacific)
    return local_time.strftime('%A, %B %d at %I:%M %p')

def get_motivational_quote():
    response = requests.get("https://zenquotes.io/api/random")
    if response.status_code == 200:
        quote_data = response.json()
        return f"💡 *{quote_data[0]['q']}* - {quote_data[0]['a']}"
    return "💡 Stay positive, work hard, and make it happen!"

def get_all_bart_alerts():
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get("https://api.bart.gov/gtfsrt/alerts.aspx")

    if response.status_code != 200:
        return ["⚠️ Unable to fetch BART alerts."]

    feed.ParseFromString(response.content)

    all_alerts = [
        entity.alert.description_text.translation[0].text
        for entity in feed.entity if entity.HasField("alert")
    ]

    return all_alerts if all_alerts else ["✅ No active BART service alerts."]

def get_bart_real_time():
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get('https://api.bart.gov/gtfsrt/tripupdate.aspx')
    feed.ParseFromString(response.content)
    return feed

# Function to find upcoming BART trips from a given departure station
def find_upcoming_bart_trips(feed, departure_station, destination_station):
    pacific = pytz.timezone("America/Los_Angeles")
    current_time = datetime.now(pacific).timestamp()  # Current time in local timezone
    next_hour = current_time + 3600  # One hour from now
    
    bart_trips = []

    for entity in feed.entity:
        if entity.trip_update:
            stops = entity.trip_update.stop_time_update
            for stop in stops:
                if stop.stop_id == departure_station and stop.HasField("departure"):
                    departure_time = stop.departure.time
                    if current_time <= departure_time <= next_hour:
                        # Ensure the train goes to the desired destination
                        if any(s.stop_id == destination_station for s in stops):
                            bart_trips.append({
                                "route": entity.trip_update.trip.route_id,
                                "departure_time": format_local_time(departure_time),
                                "destination": destination_station
                            })

    # Sort trips by departure time (soonest first)
    bart_trips.sort(key=lambda x: x["departure_time"])

    return bart_trips

# Streamlit UI
st.title("🏢 Ethan's Commute Planner")

st.subheader("🌟 Daily Motivation")
st.write(get_motivational_quote())

response = requests.get("https://uselessfacts.jsph.pl/random.json?language=en")
if response.status_code == 200:
    fact = response.json().get("text", "Couldn't fetch a fact!")
    st.subheader("🤓 Fun Fact of the Day")
    st.write(fact)

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
# Create two columns
col1, col2 = st.columns(2)

# Distribute checkboxes across columns
for i, item in enumerate(packing_list):
    if i % 2 == 0:
        col1.checkbox(item, key=item)
    else:
        col2.checkbox(item, key=item)


# Podcast 
st.subheader("🎙 Podcasts")
st.markdown("[🎧 The Best One Yet (TBOY)](https://open.spotify.com/show/5RllMBgvDnTau8nnsCUdse)")
st.markdown("[🎧 Morning Brew Daily](https://open.spotify.com/show/7nc7OQdPTekErtFSRxOBKh)")
st.markdown("[🎧 NPR Life Kit](https://open.spotify.com/show/5J0xAfsLX7bEYzGxOin4Sd)")


# Fetch BART real-time data
bart_feed = get_bart_real_time()
# Fetch BART alerts
st.subheader("🚨 BART Service Alerts")

bart_alerts = get_all_bart_alerts()

for alert in bart_alerts:
    st.write(f"⚠️ {alert}")

# Daly City → 12th Street Oakland
daly_to_oakland_trips = find_upcoming_bart_trips(bart_feed, "DALY", "12TH")

# 12th Street Oakland → San Jose Direction
oakland_to_sj_trips = find_upcoming_bart_trips(bart_feed, "12TH", "MLPT")

# 12th Street Oakland → Daly City Direction
oakland_to_daly_trips = find_upcoming_bart_trips(bart_feed, "12TH", "DALY")

# Display results dynamically based on the current time
st.subheader("🚆 BART Real-Time Departures (Next Hour)")

# Daly City → 12th Street Oakland
with st.expander("🔽 Show/Hide Upcoming BART from Daly City to 12th Street Oakland"):
    if daly_to_oakland_trips:
        for trip in daly_to_oakland_trips:
            st.write(f"Train departing DALY CITY at {trip['departure_time']} for 12th STREET OAKLAND")
    else:
        st.write("No upcoming trains available in the next hour.")

# 12th Street Oakland → San Jose
with st.expander("🔽 Show/Hide Upcoming BART from 12th Street Oakland to Milpitas Direction"):
    if oakland_to_sj_trips:
        for trip in oakland_to_sj_trips:
            st.write(f"Train departing 12TH STREET OAKLAND at {trip['departure_time']} for Milpitas")
    else:
        st.write("No upcoming trains available in the next hour.")

# 12th Street Oakland → Daly City
with st.expander("🔽 Show/Hide Upcoming BART from 12th Street Oakland to Daly City Direction"):
    if oakland_to_daly_trips:
        for trip in oakland_to_daly_trips:
            st.write(f"Train departing 12TH STREET OAKLAND at {trip['departure_time']} for DALY CITY")
    else:
        st.write("No upcoming trains available in the next hour.")

