import streamlit as st
import requests
import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import json
import time

# Download VADER once
try:
    nltk.download('vader_lexicon', quiet=True)
    sia = SentimentIntensityAnalyzer()
except:
    sia = None

# === DYNAMIC LOCATION & RESORT DISCOVERY ===
@st.cache_data(ttl=3600)
def get_location_coordinates(location_name):
    """Convert location name to coordinates"""
    try:
        geolocator = Nominatim(user_agent="ski_resort_finder_v2")
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude, location.address
        return None, None, None
    except Exception as e:
        st.error(f"Location error: {e}")
        return None, None, None

@st.cache_data(ttl=3600)
def search_ski_resorts_web(location_name, radius_miles):
    """Search for ski resorts using web search"""
    resorts_found = []
    
    # Search query
    search_query = f"ski resorts near {location_name}"
    
    try:
        # Use DuckDuckGo or similar free search (simplified version)
        # In production, you'd use Google Places API or similar
        
        # For now, we'll use a combination of OpenStreetMap Overpass API
        # and known resort databases
        
        st.info(f"🔍 Searching for ski resorts within {radius_miles} miles of {location_name}...")
        
    except Exception as e:
        st.warning(f"Search issue: {e}")
    
    return resorts_found

@st.cache_data(ttl=3600)
def find_ski_resorts_osm(lat, lon, radius_miles):
    """Find ski resorts using OpenStreetMap Overpass API"""
    resorts = []
    
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        radius_meters = int(radius_miles * 1609.34)
        
        # Query for ski-related places
        query = f"""
        [out:json][timeout:25];
        (
          node["sport"="skiing"](around:{radius_meters},{lat},{lon});
          way["sport"="skiing"](around:{radius_meters},{lat},{lon});
          node["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
          way["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
          relation["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
        );
        out center;
        """
        
        response = requests.post(overpass_url, data={"data": query}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            seen = set()
            
            for elem in data.get("elements", []):
                tags = elem.get("tags", {})
                name = tags.get("name", "")
                
                if not name or name in seen:
                    continue
                
                # Get coordinates
                if "lat" in elem and "lon" in elem:
                    elem_lat, elem_lon = elem["lat"], elem["lon"]
                elif "center" in elem:
                    elem_lat = elem["center"]["lat"]
                    elem_lon = elem["center"]["lon"]
                else:
                    continue
                
                distance = geodesic((lat, lon), (elem_lat, elem_lon)).miles
                
                if distance <= radius_miles:
                    resorts.append({
                        "name": name,
                        "lat": elem_lat,
                        "lon": elem_lon,
                        "distance": round(distance, 1),
                        "website": tags.get("website", tags.get("contact:website", "")),
                        "phone": tags.get("phone", tags.get("contact:phone", "")),
                        "source": "OpenStreetMap"
                    })
                    seen.add(name)
        
        return sorted(resorts, key=lambda x: x["distance"])
        
    except Exception as e:
        st.warning(f"OpenStreetMap search error: {e}")
        return []

def scrape_booking_info(resort_name, date_from, date_to, need_lesson):
    """Scrape or search for booking links and prices"""
    
    # Clean resort name for search
    clean_name = resort_name.lower().replace(" ", "+")
    
    booking_info = {
        "lift_ticket_link": "",
        "lift_ticket_price": "N/A",
        "lesson_link": "",
        "lesson_price": "N/A",
        "rental_link": "",
        "rental_price": "N/A"
    }
    
    # Generate likely booking URLs (most ski resorts follow patterns)
    base_searches = [
        f"https://www.google.com/search?q={clean_name}+ski+resort+lift+tickets+booking",
        f"https://www.google.com/search?q={clean_name}+ski+lessons",
        f"https://www.google.com/search?q={clean_name}+ski+rental",
    ]
    
    # Common booking URL patterns
    resort_slug = resort_name.lower().replace(" ", "").replace("-", "")
    common_urls = [
        f"https://www.{resort_slug}.com/tickets",
        f"https://www.{resort_slug}.com/plan-your-trip/lift-tickets",
        f"https://www.{resort_slug}.com/ski-lessons",
        f"https://www.{resort_slug}.com/rentals",
    ]
    
    booking_info["lift_ticket_link"] = base_searches[0]
    booking_info["lesson_link"] = base_searches[1] if need_lesson else ""
    booking_info["rental_link"] = base_searches[2]
    
    # Estimated pricing (would need real scraping in production)
    booking_info["lift_ticket_price"] = "$120-250/day (est.)"
    booking_info["lesson_price"] = "$180-300 (group) (est.)" if need_lesson else ""
    booking_info["rental_price"] = "$40-70/day (est.)"
    
    return booking_info

@st.cache_data(ttl=1800)
def get_reddit_sentiment(resort_name):
    """Get Reddit sentiment for resort"""
    if not sia:
        return 0.0, 50, 0
    
    query = resort_name.lower().replace(" ", "+")
    url = f"https://www.reddit.com/r/skiing+r/snowboarding/search.json?q={query}&sort=new&t=year&limit=30"
    headers = {"User-Agent": "ski-finder/1.0"}
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            posts = r.json()["data"]["children"]
            texts = []
            for post in posts:
                title = post["data"]["title"]
                selftext = post["data"].get("selftext", "")
                full_text = (title + " " + selftext).strip()
                if len(full_text) > 20:
                    texts.append(full_text)
            
            if texts:
                compounds = [sia.polarity_scores(t)["compound"] for t in texts[:15]]
                avg = sum(compounds) / len(compounds)
                pos_pct = len([c for c in compounds if c >= 0.05]) / len(compounds) * 100
                return round(avg, 3), round(pos_pct), len(texts)
    except:
        pass
    
    return 0.0, 50, 0

def get_weather_forecast(lat, lon):
    """Get NWS weather forecast"""
    headers = {"User-Agent": "ski-finder/1.0"}
    
    try:
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        point_data = requests.get(point_url, headers=headers, timeout=10).json()
        
        forecast_url = point_data["properties"]["forecast"]
        forecast_data = requests.get(forecast_url, headers=headers, timeout=10).json()
        
        periods = forecast_data["properties"]["periods"]
        if periods:
            return f"{periods[0]['temperature']}°F – {periods[0]['shortForecast']}"
    except:
        pass
    
    return "Weather unavailable"

# === STREAMLIT APP ===
st.set_page_config(page_title="Dynamic Ski Resort Finder", layout="wide")
st.title("🏔️ Dynamic Ski Resort Finder & Booking Tool")
st.markdown("Find ski resorts anywhere, get real-time info, and book your trip!")

# === SIDEBAR INPUTS ===
with st.sidebar:
    st.header("🎯 Search Parameters")
    
    location_input = st.text_input(
        "📍 Enter Location", 
        value="Lake Tahoe, CA",
        help="City, address, or landmark"
    )
    
    radius = st.slider(
        "🔍 Search Radius (miles)", 
        min_value=5, 
        max_value=100, 
        value=20, 
        step=5
    )
    
    st.divider()
    
    st.header("📅 Trip Dates")
    date_from = st.date_input(
        "From", 
        value=datetime.now() + timedelta(days=7)
    )
    date_to = st.date_input(
        "To", 
        value=datetime.now() + timedelta(days=9)
    )
    
    trip_days = (date_to - date_from).days + 1
    
    st.divider()
    
    st.header("🎿 Add-ons")
    need_lesson = st.checkbox("I need ski/snowboard lessons", value=False)
    need_rental = st.checkbox("I need equipment rental", value=True)
    
    st.divider()
    
    search_button = st.button("🔍 Find Resorts", type="primary", use_container_width=True)

# === MAIN CONTENT ===
if search_button:
    # Get coordinates
    lat, lon, address = get_location_coordinates(location_input)
    
    if lat and lon:
        st.success(f"📍 Searching near: {address}")
        st.info(f"📅 Trip: {trip_days} day(s) from {date_from} to {date_to}")
        
        # Find resorts
        with st.spinner(f"Finding ski resorts within {radius} miles..."):
            resorts = find_ski_resorts_osm(lat, lon, radius)
            
            if not resorts:
                st.warning("No resorts found via OpenStreetMap. Try increasing the radius or different location.")
                st.info("💡 Try searching for: 'Denver, CO', 'Salt Lake City, UT', 'Lake Tahoe, CA', or 'Stowe, VT'")
            else:
                st.success(f"Found {len(resorts)} ski resort(s)!")
                
                # Process each resort
                resort_data = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, resort in enumerate(resorts):
                    status_text.text(f"Analyzing {resort['name']}... ({idx+1}/{len(resorts)})")
                    
                    # Get booking info
                    booking = scrape_booking_info(
                        resort["name"], 
                        date_from, 
                        date_to, 
                        need_lesson
                    )
                    
                    # Get sentiment
                    sentiment, pos_pct, review_count = get_reddit_sentiment(resort["name"])
                    
                    # Get weather
                    weather = get_weather_forecast(resort["lat"], resort["lon"])
                    
                    # Sentiment emoji
                    if sentiment > 0.3:
                        emoji = "😍"
                    elif sentiment > 0.1:
                        emoji = "😊"
                    elif sentiment > -0.1:
                        emoji = "😐"
                    else:
                        emoji = "😕"
                    
                    resort_data.append({
                        "Resort": resort["name"],
                        "Distance": f"{resort['distance']} mi",
                        "Weather": weather,
                        "Vibe": f"{emoji} {sentiment}",
                        "Lift Tickets": f"[Book Tickets]({booking['lift_ticket_link']})",
                        "Est. Ticket Price": booking["lift_ticket_price"],
                        "Lessons": f"[Book Lesson]({booking['lesson_link']})" if need_lesson else "N/A",
                        "Est. Lesson Price": booking["lesson_price"] if need_lesson else "N/A",
                        "Rentals": f"[Book Rental]({booking['rental_link']})" if need_rental else "N/A",
                        "Est. Rental Price": booking["rental_price"] if need_rental else "N/A",
                        "Website": f"[Visit]({resort['website']})" if resort['website'] else "N/A",
                    })
                    
                    progress_bar.progress((idx + 1) / len(resorts))
                    time.sleep(0.3)  # Rate limiting
                
                status_text.empty()
                progress_bar.empty()
                
                # Display results
                df = pd.DataFrame(resort_data)
                
                st.subheader("🎿 Your Ski Resorts")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Quick booking section
                st.divider()
                st.subheader("⚡ Quick Booking Links")
                
                cols = st.columns(min(3, len(resorts)))
                for idx, resort_info in enumerate(resort_data[:3]):
                    with cols[idx % 3]:
                        st.markdown(f"### {resort_info['Resort']}")
                        st.markdown(f"**Distance:** {resort_info['Distance']}")
                        st.markdown(f"**Vibe:** {resort_info['Vibe']}")
                        st.markdown(resort_info['Lift Tickets'])
                        if need_lesson and resort_info['Lessons'] != "N/A":
                            st.markdown(resort_info['Lessons'])
                        if need_rental and resort_info['Rentals'] != "N/A":
                            st.markdown(resort_info['Rentals'])
    else:
        st.error("❌ Could not find that location. Please try again with a different search term.")

else:
    st.info("👈 Enter your location and trip details in the sidebar, then click 'Find Resorts'")
    
    st.markdown("""
    ### How to use:
    1. **Enter a location** (city, address, or landmark)
    2. **Set your search radius** (how far you're willing to travel)
    3. **Choose your trip dates**
    4. **Select if you need lessons or rentals**
    5. **Click 'Find Resorts'** and we'll search for nearby ski areas!
    
    ### Features:
    - 🗺️ Dynamic resort discovery using OpenStreetMap
    - 📊 Reddit sentiment analysis
    - 🌤️ Live weather forecasts
    - 🔗 Direct booking links
    - 💰 Price estimates
    """)

st.divider()
st.caption("Data sources: OpenStreetMap, Reddit, National Weather Service • Booking links are search queries - verify prices on resort websites")