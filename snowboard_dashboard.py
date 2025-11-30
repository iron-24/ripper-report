import streamlit as st
import requests
import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
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
def find_ski_resorts_osm(lat, lon, radius_miles):
    """Find ski resorts using OpenStreetMap Overpass API"""
    resorts = []
    
    try:
        overpass_url = "http://overpass-api.de/api/interpreter"
        radius_meters = int(radius_miles * 1609.34)
        
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
        st.warning(f"OpenStreetMap search: {str(e)[:100]}")
        return []

def generate_booking_urls(resort_name, resort_website, date_from, date_to, need_lesson, need_rental):
    """Generate smart booking URLs with dates pre-filled"""
    
    booking_info = {
        "lift_ticket_link": "",
        "lift_ticket_display": "",
        "lesson_link": "",
        "lesson_display": "",
        "rental_link": "",
        "rental_display": "",
        "full_package_link": "",
        "estimated_total": ""
    }
    
    # Format dates
    date_from_str = date_from.strftime("%Y-%m-%d")
    date_to_str = date_to.strftime("%Y-%m-%d")
    
    # Clean resort name for URLs
    resort_slug = resort_name.lower().replace(" ", "").replace("-", "")
    resort_dash = resort_name.lower().replace(" ", "-")
    resort_plus = resort_name.replace(" ", "+")
    
    trip_days = (date_to - date_from).days + 1
    
    # Known resort booking URL patterns with date parameters
    known_patterns = {
        # Vail Resorts (Epic Pass)
        "northstar": f"https://www.northstarcalifornia.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "heavenly": f"https://www.skiheavenly.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "kirkwood": f"https://www.kirkwood.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "vail": f"https://www.vail.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "breckenridge": f"https://www.breckenridge.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "keystone": f"https://www.keystoneresort.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        "parkcity": f"https://www.parkcitymountain.com/plan-your-trip/lift-access/tickets.aspx?startDate={date_from_str}&endDate={date_to_str}",
        
        # Alterra Resorts (Ikon Pass)
        "palisades": f"https://www.palisadestahoe.com/tickets-passes?arrival={date_from_str}&departure={date_to_str}",
        "sugarbowl": f"https://www.sugarbowl.com/plan/tickets?date={date_from_str}",
        "squaw": f"https://www.palisadestahoe.com/tickets-passes?arrival={date_from_str}&departure={date_to_str}",
        "mammoth": f"https://www.mammothmountain.com/tickets-and-passes/lift-tickets?startDate={date_from_str}",
        "deervalley": f"https://www.deervalley.com/plan/tickets-passes?arrival={date_from_str}&departure={date_to_str}",
        "steamboat": f"https://www.steamboat.com/plan-your-trip/lift-access/tickets?arrival={date_from_str}&departure={date_to_str}",
        
        # Independent resorts
        "sierra": f"https://www.sierraattahoe.com/lift-tickets/?date={date_from_str}",
        "alta": f"https://www.alta.com/tickets?date={date_from_str}",
        "snowbird": f"https://www.snowbird.com/lift-tickets/?arrivaldate={date_from_str}&departuredate={date_to_str}",
        "jacksonhole": f"https://www.jacksonhole.com/lift-tickets-passes.html?arrival={date_from_str}&departure={date_to_str}",
        "jackson": f"https://www.jacksonhole.com/lift-tickets-passes.html?arrival={date_from_str}&departure={date_to_str}",
        "aspen": f"https://www.aspensnowmass.com/tickets-passes/lift-tickets?startDate={date_from_str}&endDate={date_to_str}",
        "stowe": f"https://www.stowe.com/plan-your-trip/lift-access/tickets?arrival={date_from_str}",
        "killington": f"https://www.killington.com/plan-your-trip/tickets-and-passes?arrival={date_from_str}",
    }
    
    # Match resort to known pattern
    matched_url = None
    for key, url in known_patterns.items():
        if key in resort_slug:
            matched_url = url
            break
    
    # Generate lift ticket URL
    if matched_url:
        booking_info["lift_ticket_link"] = matched_url
        booking_info["lift_ticket_display"] = "🎫 Book Lift Tickets"
    elif resort_website:
        base_url = resort_website.rstrip('/')
        booking_info["lift_ticket_link"] = f"{base_url}/plan-your-trip/lift-access/tickets?startDate={date_from_str}&endDate={date_to_str}"
        booking_info["lift_ticket_display"] = "🎫 Book Lift Tickets"
    else:
        booking_info["lift_ticket_link"] = f"https://www.google.com/search?q={resort_plus}+lift+tickets+{date_from_str}+to+{date_to_str}"
        booking_info["lift_ticket_display"] = "🔍 Search Lift Tickets"
    
    # Lesson URLs
    if need_lesson:
        lesson_patterns = {
            "northstar": f"https://www.northstarcalifornia.com/plan-your-trip/ski-and-ride-school.aspx?startDate={date_from_str}",
            "heavenly": f"https://www.skiheavenly.com/plan-your-trip/ski-and-ride-school.aspx?startDate={date_from_str}",
            "palisades": f"https://www.palisadestahoe.com/ski-ride-school?date={date_from_str}",
            "vail": f"https://www.vail.com/plan-your-trip/ski-and-ride-school.aspx?startDate={date_from_str}",
            "breckenridge": f"https://www.breckenridge.com/plan-your-trip/ski-and-ride-school.aspx?startDate={date_from_str}",
        }
        
        lesson_url = None
        for key, url in lesson_patterns.items():
            if key in resort_slug:
                lesson_url = url
                break
        
        if lesson_url:
            booking_info["lesson_link"] = lesson_url
        elif resort_website:
            booking_info["lesson_link"] = f"{resort_website.rstrip('/')}/ski-school?date={date_from_str}"
        else:
            booking_info["lesson_link"] = f"https://www.google.com/search?q={resort_plus}+ski+lessons+{date_from_str}"
        
        booking_info["lesson_display"] = "🎿 Book Lessons"
    
    # Rental URLs
    if need_rental:
        rental_patterns = {
            "northstar": f"https://www.northstarcalifornia.com/plan-your-trip/rentals-and-demos.aspx?startDate={date_from_str}",
            "heavenly": f"https://www.skiheavenly.com/plan-your-trip/rentals-and-demos.aspx?startDate={date_from_str}",
            "palisades": f"https://www.palisadestahoe.com/rentals?date={date_from_str}",
            "vail": f"https://www.vail.com/plan-your-trip/rentals-and-demos.aspx?startDate={date_from_str}",
        }
        
        rental_url = None
        for key, url in rental_patterns.items():
            if key in resort_slug:
                rental_url = url
                break
        
        if rental_url:
            booking_info["rental_link"] = rental_url
        elif resort_website:
            booking_info["rental_link"] = f"{resort_website.rstrip('/')}/rentals?date={date_from_str}"
        else:
            booking_info["rental_link"] = f"https://www.google.com/search?q={resort_plus}+ski+rental+{date_from_str}"
        
        booking_info["rental_display"] = "⛷️ Book Rentals"
    
    # Full package search
    package_query = f"{resort_plus}+ski+package"
    if need_lesson:
        package_query += "+lessons"
    if need_rental:
        package_query += "+rentals"
    package_query += f"+{date_from_str}+to+{date_to_str}"
    
    booking_info["full_package_link"] = f"https://www.google.com/search?q={package_query}"
    
    # Estimate costs
    base_ticket_price = 150
    lesson_price = 200 if need_lesson else 0
    rental_price = 50 if need_rental else 0
    
    daily_cost = base_ticket_price + rental_price
    total_cost = (daily_cost * trip_days) + lesson_price
    
    booking_info["estimated_total"] = f"~${total_cost}"
    booking_info["trip_days"] = trip_days
    
    return booking_info

@st.cache_data(ttl=1800)
def get_reddit_sentiment(resort_name):
    """Get Reddit sentiment"""
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
    """Get NWS weather"""
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
st.set_page_config(page_title="Smart Ski Resort Finder", layout="wide")
st.title("🏔️ Smart Ski Resort Finder with Auto-Filled Booking Links")
st.markdown("Find resorts anywhere • Get dates pre-filled in booking URLs • Book instantly!")

# === SIDEBAR ===
with st.sidebar:
    st.header("🎯 Search Parameters")
    
    location_input = st.text_input(
        "📍 Location", 
        value="Lake Tahoe, CA",
        help="City, address, or landmark"
    )
    
    radius = st.slider(
        "🔍 Radius (miles)", 
        min_value=5, 
        max_value=100, 
        value=20, 
        step=5
    )
    
    st.divider()
    
    st.header("📅 Trip Dates")
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input(
            "From", 
            value=datetime.now() + timedelta(days=7)
        )
    with col2:
        date_to = st.date_input(
            "To", 
            value=datetime.now() + timedelta(days=9)
        )
    
    trip_days = (date_to - date_from).days + 1
    
    if trip_days < 1:
        st.error("End date must be after start date!")
    else:
        st.success(f"Trip: {trip_days} day{'s' if trip_days > 1 else ''}")
    
    st.divider()
    
    st.header("🎿 Options")
    need_lesson = st.checkbox("Include ski/snowboard lessons", value=False)
    need_rental = st.checkbox("Include equipment rental", value=True)
    
    st.divider()
    
    search_button = st.button("🔍 Find Resorts & Build Booking Links", type="primary", use_container_width=True)

# === MAIN CONTENT ===
if search_button and trip_days >= 1:
    lat, lon, address = get_location_coordinates(location_input)
    
    if lat and lon:
        st.success(f"📍 Searching near: **{address}**")
        st.info(f"📅 Trip dates: **{date_from.strftime('%b %d')}** to **{date_to.strftime('%b %d, %Y')}** ({trip_days} day{'s' if trip_days > 1 else ''})")
        
        with st.spinner(f"Finding ski resorts within {radius} miles..."):
            resorts = find_ski_resorts_osm(lat, lon, radius)
            
            if not resorts:
                st.warning("No resorts found via OpenStreetMap. Try increasing radius or different location.")
                st.info("💡 Try: 'Denver, CO', 'Salt Lake City, UT', 'Lake Tahoe, CA', 'Stowe, VT'")
            else:
                st.success(f"✅ Found **{len(resorts)}** resort(s)! Generating booking links...")
                
                resort_data = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, resort in enumerate(resorts):
                    status_text.text(f"Building links for {resort['name']}... ({idx+1}/{len(resorts)})")
                    
                    # Generate booking URLs
                    booking = generate_booking_urls(
                        resort["name"], 
                        resort["website"],
                        date_from, 
                        date_to, 
                        need_lesson,
                        need_rental
                    )
                    
                    # Get sentiment
                    sentiment, pos_pct, review_count = get_reddit_sentiment(resort["name"])
                    
                    # Get weather
                    weather = get_weather_forecast(resort["lat"], resort["lon"])
                    
                    # Emoji
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
                        "Reddit Vibe": f"{emoji} {sentiment}",
                        "Est. Total": booking["estimated_total"],
                        "Lift Tickets": booking["lift_ticket_link"],
                        "Lessons": booking["lesson_link"] if need_lesson else "",
                        "Rentals": booking["rental_link"] if need_rental else "",
                        "Package Search": booking["full_package_link"],
                        "_resort_obj": resort,
                        "_booking_obj": booking,
                    })
                    
                    progress_bar.progress((idx + 1) / len(resorts))
                    time.sleep(0.2)
                
                status_text.empty()
                progress_bar.empty()
                
                # Display quick booking cards
                st.divider()
                st.subheader("⚡ Quick Booking")
                
                cols = st.columns(min(3, len(resort_data)))
                for idx, resort_info in enumerate(resort_data[:6]):
                    with cols[idx % 3]:
                        st.markdown(f"### {resort_info['Resort']}")
                        st.markdown(f"**{resort_info['Distance']}** away • {resort_info['Reddit Vibe']}")
                        st.markdown(f"**{resort_info['Weather']}**")
                        st.markdown(f"**Estimated: {resort_info['Est. Total']}** for {trip_days} day(s)")
                        
                        st.link_button(
                            "🎫 Book Lift Tickets ➜",
                            resort_info['Lift Tickets'],
                            use_container_width=True
                        )
                        
                        if need_lesson and resort_info['Lessons']:
                            st.link_button(
                                "🎿 Book Lessons ➜",
                                resort_info['Lessons'],
                                use_container_width=True,
                                type="secondary"
                            )
                        
                        if need_rental and resort_info['Rentals']:
                            st.link_button(
                                "⛷️ Book Rentals ➜",
                                resort_info['Rentals'],
                                use_container_width=True,
                                type="secondary"
                            )
                        
                        st.link_button(
                            "📦 Search Package Deals",
                            resort_info['Package Search'],
                            use_container_width=True,
                            type="secondary"
                        )
                
                # Full table
                st.divider()
                st.subheader("📊 All Resorts")
                
                df_display = pd.DataFrame([{
                    "Resort": r["Resort"],
                    "Distance": r["Distance"],
                    "Weather": r["Weather"],
                    "Vibe": r["Reddit Vibe"],    
                    "Est. Cost": r["Est. Total"],
                } for r in resort_data])
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # Export links
                st.divider()
                st.subheader("📎 Export All Booking Links")
                
                links_text = f"# Ski Trip Booking Links\n"
                links_text += f"Location: {location_input}\n"
                links_text += f"Dates: {date_from} to {date_to}\n\n"
                
                for r in resort_data:
                    links_text += f"## {r['Resort']} ({r['Distance']} away)\n"
                    links_text += f"- Lift Tickets: {r['Lift Tickets']}\n"
                    if need_lesson:
                        links_text += f"- Lessons: {r['Lessons']}\n"
                    if need_rental:
                        links_text += f"- Rentals: {r['Rentals']}\n"
                    links_text += f"- Package: {r['Package Search']}\n\n"
                
                st.download_button(
                    label="💾 Download All Links (TXT)",
                    data=links_text,
                    file_name=f"ski_trip_links_{date_from}.txt",
                    mime="text/plain"
                )
    else:
        st.error("❌ Location not found. Try a different search term.")

else:
    # Welcome screen
    st.info("👈 Configure your trip in the sidebar and click 'Find Resorts'!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### ✨ Features
        - 🗺️ **Dynamic resort discovery** anywhere in the world
        - 📅 **Auto-filled booking URLs** with your exact dates
        - 🔗 **Direct links** to lift tickets, lessons, rentals
        - 💰 **Cost estimates** for planning
        - 🌤️ **Live weather** from National Weather Service
        - 📊 **Reddit sentiment** from skiing communities
        """)
    
    with col2:
        st.markdown("""
        ### 🎿 How It Works
        1. **Enter your location** (city, address, or ski town)
        2. **Set search radius** (how far you'll travel)
        3. **Choose trip dates**
        4. **Select add-ons** (lessons, rentals)
        5. **Click 'Find Resorts'** and get instant booking links!
        
        *All booking URLs have your dates pre-filled for instant booking!*
        """)

st.divider()
st.caption("🔗 Smart booking links • 🗺️ OpenStreetMap data • 🌤️ NWS weather • 📊 Reddit sentiment • Made with Streamlit")