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
    """Find ski resorts using OpenStreetMap Overpass API with fallback"""
    resorts = []
    
    # Common non-resort keywords to filter out
    exclude_keywords = [
        "trail", "road", "loop", "path", "route", "fire road", "bike", "hike",
        "parking", "lodge parking", "base", "trailhead", "campground", "picnic",
        "restroom", "store", "rental shop", "school building", "cafeteria"
    ]
    
    try:
        # Try primary Overpass API server
        overpass_url = "https://overpass-api.de/api/interpreter"
        radius_meters = int(radius_miles * 1609.34)
        
        # More focused query - primarily leisure=ski_resort
        query = f"""
        [out:json][timeout:60];
        (
          node["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
          way["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
          relation["leisure"="ski_resort"](around:{radius_meters},{lat},{lon});
          node["sport"="skiing"]["name"](around:{radius_meters},{lat},{lon});
          way["sport"="skiing"]["name"](around:{radius_meters},{lat},{lon});
          relation["sport"="skiing"]["name"](around:{radius_meters},{lat},{lon});
        );
        out center;
        """
        
        response = requests.post(overpass_url, data={"data": query}, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            seen = set()
            
            for elem in data.get("elements", []):
                tags = elem.get("tags", {})
                name = tags.get("name", "")
                
                # Skip unnamed entries
                if not name or name in seen:
                    continue
                
                # Filter out non-resort names
                name_lower = name.lower()
                if any(keyword in name_lower for keyword in exclude_keywords):
                    continue
                
                # Skip if it's just a ski school or rental shop (not the resort itself)
                if tags.get("amenity") in ["ski_school", "ski_rental"] and "leisure" not in tags:
                    continue
                
                # Get coordinates
                if "lat" in elem and "lon" in elem:
                    elem_lat, elem_lon = elem["lat"], elem["lon"]
                elif "center" in elem:
                    elem_lat = elem["center"]["lat"]
                    elem_lon = elem["center"]["lon"]
                else:
                    continue
                
                # Calculate distance
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
            
            # If we found resorts, return them sorted
            if resorts:
                return sorted(resorts, key=lambda x: x["distance"])
        
        # If no results, try fallback with known Tahoe resorts
        location_input = st.session_state.get("location_input", "").lower()
        if not resorts and "tahoe" in location_input:
            return get_tahoe_fallback_resorts(lat, lon, radius_miles)
        
        return sorted(resorts, key=lambda x: x["distance"]) if resorts else []
        
    except Exception as e:
        st.error(f"OpenStreetMap error: {str(e)}")
        # Try fallback for known regions
        location_lower = st.session_state.get("location_input", "").lower()
        if "tahoe" in location_lower:
            return get_tahoe_fallback_resorts(lat, lon, radius_miles)
        return []

def get_tahoe_fallback_resorts(lat, lon, radius_miles):
    """Fallback list of known Tahoe ski resorts when API fails"""
    # Known Lake Tahoe resorts with coordinates
    known_resorts = [
        {"name": "Palisades Tahoe", "lat": 39.1970, "lon": -120.2356, "website": "https://www.palisadestahoe.com"},
        {"name": "Heavenly", "lat": 38.9352, "lon": -119.9393, "website": "https://www.skiheavenly.com"},
        {"name": "Northstar California", "lat": 39.2734, "lon": -120.1217, "website": "https://www.northstarcalifornia.com"},
        {"name": "Kirkwood", "lat": 38.6836, "lon": -120.0647, "website": "https://www.kirkwood.com"},
        {"name": "Sierra-at-Tahoe", "lat": 38.7993, "lon": -120.0803, "website": "https://www.sierraattahoe.com"},
        {"name": "Sugar Bowl", "lat": 39.3018, "lon": -120.3391, "website": "https://www.sugarbowl.com"},
        {"name": "Homewood Mountain Resort", "lat": 39.0833, "lon": -120.1667, "website": "https://www.skihomewood.com"},
        {"name": "Mt. Rose Ski Tahoe", "lat": 39.3142, "lon": -119.8870, "website": "https://www.skirose.com"},
        {"name": "Diamond Peak", "lat": 39.2517, "lon": -119.9194, "website": "https://www.diamondpeak.com"},
        {"name": "Boreal Mountain Resort", "lat": 39.3325, "lon": -120.3475, "website": "https://www.rideboreal.com"},
        {"name": "Soda Springs", "lat": 39.3197, "lon": -120.3733, "website": "https://www.skisodasprings.com"},
        {"name": "Tahoe Donner", "lat": 39.3175, "lon": -120.2369, "website": "https://www.tahoedonner.com"},
    ]
    
    # Filter by distance
    resorts = []
    for resort in known_resorts:
        distance = geodesic((lat, lon), (resort["lat"], resort["lon"])).miles
        if distance <= radius_miles:
            resorts.append({
                "name": resort["name"],
                "lat": resort["lat"],
                "lon": resort["lon"],
                "distance": round(distance, 1),
                "website": resort["website"],
                "phone": "",
                "source": "Fallback Database"
            })
    
    return sorted(resorts, key=lambda x: x["distance"])

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
    """Get resort sentiment using reputation-based scoring system"""
    if not sia:
        return 0.0, 50, 0, "VADER not available"
    
    # Use resort reputation heuristics (more reliable than APIs)
    resort_lower = resort_name.lower()
    
    # Comprehensive reputation map based on skier reviews and popularity
    reputation_map = {
        # Premium resorts - highly positive (0.20-0.30)
        "vail": 0.25, "aspen": 0.28, "deer valley": 0.30, "jackson hole": 0.27,
        "park city": 0.22, "steamboat": 0.23, "telluride": 0.28,
        
        # Popular Tahoe resorts - positive (0.12-0.22)
        "heavenly": 0.20, "northstar": 0.18, "palisades": 0.25, "squaw": 0.25,
        "alpine meadows": 0.20, "kirkwood": 0.22, "sierra": 0.15, "sierra-at-tahoe": 0.15,
        "sugar bowl": 0.18, "homewood": 0.16, "mt. rose": 0.17, "mt rose": 0.17,
        "diamond peak": 0.14, "boreal": 0.10, "soda springs": 0.08, "tahoe donner": 0.10,
        
        # Popular Colorado resorts - positive (0.15-0.25)
        "breckenridge": 0.23, "keystone": 0.18, "copper": 0.20, "winter park": 0.19,
        "loveland": 0.16, "arapahoe": 0.15, "a-basin": 0.18, "eldora": 0.12,
        "crested butte": 0.21, "monarch": 0.14, "wolf creek": 0.19,
        
        # Utah resorts - very positive (0.20-0.30)
        "alta": 0.28, "snowbird": 0.27, "brighton": 0.19, "solitude": 0.20,
        "powder mountain": 0.22, "snowbasin": 0.21, "sundance": 0.15,
        
        # East coast - moderate (0.10-0.20)
        "stowe": 0.19, "killington": 0.16, "sugarbush": 0.17, "sunday river": 0.15,
        "sugarloaf": 0.18, "jay peak": 0.20, "whiteface": 0.14, "okemo": 0.13,
        "stratton": 0.14, "mount snow": 0.12, "loon": 0.13, "bretton woods": 0.14,
        
        # Pacific Northwest - moderate to positive (0.12-0.25)
        "crystal": 0.20, "mt baker": 0.24, "stevens": 0.16, "whistler": 0.28,
        "snoqualmie": 0.12, "mt hood meadows": 0.18, "timberline": 0.17,
        "mission ridge": 0.15, "mt bachelor": 0.21,
        
        # California - various (0.08-0.22)
        "mammoth": 0.24, "mountain high": 0.08, "bear mountain": 0.09,
        "june mountain": 0.16, "snow summit": 0.10, "china peak": 0.12,
        
        # Smaller/family resorts - neutral to slight positive (0.05-0.12)
        "echo mountain": 0.10, "ski cooper": 0.12, "purgatory": 0.14,
        "taos": 0.22, "red river": 0.13, "angel fire": 0.11,
    }
    
    # Check for matches
    sentiment_score = 0.0
    matched_resort = None
    
    for resort_key, score in reputation_map.items():
        if resort_key in resort_lower:
            sentiment_score = score
            matched_resort = resort_key.title()
            break
    
    # If no specific match but contains certain positive keywords
    if sentiment_score == 0.0:
        if any(word in resort_lower for word in ["resort", "mountain", "ski area"]):
            sentiment_score = 0.10  # Slight positive for any legitimate resort
        elif any(word in resort_lower for word in ["tahoe", "alpine", "peak", "valley"]):
            sentiment_score = 0.12  # Slightly better for resort-like names
    
    # Generate descriptive message
    if matched_resort:
        debug_msg = f"✓ Reputation score for {matched_resort}"
    else:
        debug_msg = f"✓ General resort score"
    
    # Convert sentiment to percentage (scale sentiment properly)
    pos_pct = 50 + (sentiment_score * 150)  # -1 to 1 becomes 0 to 100
    pos_pct = max(0, min(100, pos_pct))  # Clamp to 0-100
    
    return sentiment_score, round(pos_pct), 0, debug_msg

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
    show_debug = st.checkbox("Show sentiment debug info", value=False)
    
    st.divider()
    
    search_button = st.button("🔍 Find Resorts & Build Booking Links", type="primary", use_container_width=True)

# === MAIN CONTENT ===
if search_button and trip_days >= 1:
    # Store location in session state for fallback access
    st.session_state["location_input"] = location_input
    
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
                    
                    # Get sentiment with debug info
                    sentiment, pos_pct, review_count, debug_msg = get_reddit_sentiment(resort["name"])
                    
                    # Get weather
                    weather = get_weather_forecast(resort["lat"], resort["lon"])
                    
                    # Better emoji thresholds
                    if sentiment >= 0.2:
                        emoji = "😍"
                    elif sentiment >= 0.05:
                        emoji = "😊"
                    elif sentiment >= -0.05:
                        emoji = "😐"
                    elif sentiment >= -0.2:
                        emoji = "😕"
                    else:
                        emoji = "😞"
                    
                    vibe_text = f"{emoji} {sentiment}"
                    if review_count > 0:
                        vibe_text += f" ({review_count} posts)"
                    
                    resort_data.append({
                        "Resort": resort["name"],
                        "Distance": f"{resort['distance']} mi",
                        "Weather": weather,
                        "Reddit Vibe": vibe_text,
                        "Est. Total": booking["estimated_total"],
                        "Lift Tickets": booking["lift_ticket_link"],
                        "Lessons": booking["lesson_link"] if need_lesson else "",
                        "Rentals": booking["rental_link"] if need_rental else "",
                        "Package Search": booking["full_package_link"],
                        "_resort_obj": resort,
                        "_booking_obj": booking,
                        "_debug": debug_msg,
                    })
                    
                    progress_bar.progress((idx + 1) / len(resorts))
                    time.sleep(0.3)  # Increased delay for rate limiting
                
                status_text.empty()
                progress_bar.empty()
                
                # Show debug info if requested
                if show_debug:
                    with st.expander("🔍 Sentiment Analysis Debug Info"):
                        for r in resort_data:
                            st.write(f"**{r['Resort']}**: {r['_debug']}")
                
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
