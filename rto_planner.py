import streamlit as st
import requests
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta, timezone
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
    pacific = pytz.timezone("America/Los_Angeles")
    departure_time_pacific = datetime.fromtimestamp(timestamp, tz=pytz.utc).astimezone(pacific)
    return departure_time_pacific.strftime("%I:%M %p")

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

def find_upcoming_bart_trips(feed):
    current_time = datetime.now(timezone.utc).timestamp()  # Current time in UTC
    next_hour = current_time + 3600  # One hour from now
    destination_station = "12TH"
    
    bart_trips = []

    for entity in feed.entity:
        if entity.trip_update:
            stops = entity.trip_update.stop_time_update
            for stop in stops:
                if stop.stop_id == "DALY" and stop.HasField("departure"):
                    departure_time = stop.departure.time
                    if current_time <= departure_time <= next_hour:
                        # Ensure the train goes to 12th Street Oakland
                        if any(s.stop_id == destination_station for s in stops):
                            bart_trips.append({
                                "route": entity.trip_update.trip.route_id,
                                "departure_time": format_time(departure_time),
                                "destination": destination_station
                            })

    return bart_trips
