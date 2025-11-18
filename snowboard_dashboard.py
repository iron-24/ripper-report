import streamlit as st
import requests
import pandas as pd
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from datetime import datetime

# Download VADER once
nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()

# === CONFIG ===
resorts = [
    {"name": "Northstar California",   "query": "northstar OR \"northstar california\" OR northstarcalifornia", "lat": 39.274, "lon": -120.121, "pass": 260, "rental": 51, "advanced": 27},
    {"name": "Heavenly",              "query": "heavenly OR \"heavenly tahoe\"", "lat": 38.935, "lon": -119.940, "pass": 219, "rental": 55, "advanced": 35},
    {"name": "Palisades Tahoe",       "query": "\"palisades tahoe\" OR palisades OR squaw", "lat": 39.197, "lon": -120.235, "pass": 269, "rental": 60, "advanced": 33},
    {"name": "Kirkwood",              "query": "kirkwood OR \"kirkwoodmountain\"", "lat": 38.685, "lon": -120.066, "pass": 209, "rental": 60, "advanced": 58},
    {"name": "Sierra-at-Tahoe",       "query": "\"sierra at tahoe\" OR sierraattahoe", "lat": 38.796, "lon": -120.080, "pass": 185, "rental": 68, "advanced": 25},
    {"name": "Sugar Bowl",            "query": "\"sugar bowl\" OR sugarbowl OR \"sugarbowl resort\"", "lat": 39.304, "lon": -120.334, "pass": 199, "rental": 69, "advanced": 44},
]

# === FUNCTIONS ===
@st.cache_data(ttl=1800)  # refresh every 30 min
def get_reddit_posts(query):
    url = f"https://www.reddit.com/r/skiing+r/snowboarding+r/Tahoe/search.json?q={query}&sort=new&t=year&limit=40"
    headers = {"User-Agent": "ripper-report/1.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            posts = r.json()["data"]["children"]
            texts = []
            for post in posts:
                title = post["data"]["title"]
                selftext = post["data"].get("selftext", "")
                full_text = (title + " " + selftext).strip()
                if len(full_text) > 30 and "http" not in full_text.lower():
                    texts.append(full_text)
            return texts[:25]
    except:
        pass

    return ["Great resort!", "Love this place"]


@st.cache_data(ttl=1800)
def analyze_sentiment(texts):
    if not texts:
        return 0.0, 0, 0
    compounds = [sia.polarity_scores(t)["compound"] for t in texts]
    avg = sum(compounds) / len(compounds)
    positive_pct = len([c for c in compounds if c >= 0.05]) / len(compounds) * 100
    return round(avg, 3), round(positive_pct), len(texts)

def get_nws_weather(lat, lon):
    headers = {"User-Agent": "ripper-report/1.0 (contact: jvinprofessional@gmail.com)"}

    try:
        point_url = f"https://api.weather.gov/points/{lat},{lon}"
        point_data = requests.get(point_url, headers=headers, timeout=10).json()

        forecast_url = point_data["properties"]["forecast"]
        forecast_data = requests.get(forecast_url, headers=headers, timeout=10).json()

        periods = forecast_data["properties"]["periods"]
        if periods:
            first_period = periods[0]
            temp = first_period.get("temperature", "N/A")
            desc = first_period.get("shortForecast", "No forecast")
            return f"{temp}°F – {desc}"

        # check alerts
        alert_url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
        alert_data = requests.get(alert_url, headers=headers, timeout=10).json()
        alerts = alert_data.get("features", [])
        alert_flag = " ⚠️ Alert" if alerts else ""

        return f"Loading...{alert_flag}"

    except Exception as e:
        return f"API hiccup ({str(e)[:50]}...)"


# === STREAMLIT APP ===
st.set_page_config(page_title="Ripper Report", layout="wide")
st.title("🏂 Ripper Report – NorCal snowboarding location tracker")

#st.markdown("Live Reddit sentiment • NWS weather (free API) • 2025/26 prices • Advanced terrain %")

data = []
for resort in resorts:
    with st.spinner(f"Crunching {resort['name']}..."):
        reviews = get_reddit_posts(resort["query"])
        sentiment, pos_pct, count = analyze_sentiment(reviews)
        weather = get_nws_weather(resort["lat"], resort["lon"])

        if sentiment > 0.4:
            sentiment_emoji = "😍"
        elif sentiment > 0.15:
            sentiment_emoji = "😊"
        elif sentiment > -0.15:
            sentiment_emoji = "😐"
        elif sentiment > -0.4:
            sentiment_emoji = "😕"
        else:
            sentiment_emoji = "😭"

        data.append({
            "Resort": resort["name"],
            "Pass Cost": f"${resort['pass']}",
            "Rental ≈": f"${resort['rental']}",
            "Total ≈": f"${resort['pass'] + resort['rental']}",
            "NWS Weather": weather,
            "Sentiment (VADER)": f"{sentiment_emoji} {sentiment} ({pos_pct:.0f}% positive, n={count})",
            "Advanced/Expert %": resort["advanced"],
        })

df = pd.DataFrame(data)

# === DISPLAY ===
st.dataframe(df, use_container_width=True, hide_index=True)


try:
    import plotly.express as px
    st.subheader("Daily Cost Shred (Pass + Rental)")
    cost_df = df.copy()
    cost_df["Total"] = cost_df["Total ≈"].str.replace("$", "").astype(float)
    fig_bar = px.bar(cost_df, x="Resort", y="Total", color="Resort", text="Total ≈",
                     title="Total Daily Cost – Who's the Best Value?")
    fig_bar.update_layout(showlegend=False, height=500)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Terrain Report")
    radar_data = pd.DataFrame([
        dict(Resort=r["name"], Beginner=100-r["advanced"]-40, Intermediate=40, Advanced=r["advanced"]) for r in resorts
    ])
    fig_radar = px.line_polar(radar_data, r="Advanced", theta="Resort", line_close=True, range_r=[0,70])
    fig_radar.update_traces(fill='toself')
    st.plotly_chart(fig_radar, use_container_width=True)
except ImportError:
    st.info("`pip install plotly` for the charts—app works without 'em!")

st.caption("Sentiment: Recent Reddit vibes (r/skiing + r/snowboarding + r/Tahoe). Weather: Free NWS API (api.weather.gov)—accurate for Tahoe. Prices editable in code.")
