# Smart Ski Resort Finder

A powerful web application that helps skiers and snowboarders discover nearby ski resorts and generate pre-filled booking links with integrated weather forecasts and community sentiment analysis.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Technologies

### Core Framework
- **[Streamlit](https://streamlit.io/)** - Interactive web application framework
- **Python 3.8+** - Primary programming language

### APIs & Data Sources
- **[OpenStreetMap Overpass API](https://overpass-api.de/)** - Real-time ski resort discovery worldwide
- **[GeoPy](https://geopy.readthedocs.io/)** - Location geocoding and distance calculations
- **[National Weather Service API](https://www.weather.gov/documentation/services-web-api)** - Live weather forecasts
- **[NLTK VADER](https://www.nltk.org/)** - Sentiment analysis for resort reputation scoring

### Key Libraries
- **pandas** - Data manipulation and analysis
- **requests** - HTTP requests for API interactions
- **geopy** - Geocoding and geodesic distance calculations
- **nltk** - Natural language processing and sentiment analysis

## Features

### Dynamic Resort Discovery
- Search for ski resorts anywhere in the world using location names, cities, or landmarks
- Configurable search radius (5-100 miles)
- Real-time resort discovery via OpenStreetMap
- Fallback database for popular regions (Lake Tahoe, Colorado, Utah, etc.)
- Smart filtering to exclude hiking trails and non-resort locations

### Intelligent Booking Links
- Automatically generates booking URLs with **pre-filled dates** for:
  - Lift tickets
  - Ski/snowboard lessons
  - Equipment rentals
- Supports major resort chains:
  - **Vail Resorts** (Epic Pass) - Heavenly, Northstar, Kirkwood, Vail, Breckenridge, etc.
  - **Alterra Resorts** (Ikon Pass) - Palisades Tahoe, Mammoth, Deer Valley, Steamboat, etc.
  - Independent resorts with custom URL patterns
- Package deal search aggregation

### Resort Intelligence
- **Weather Forecasts**: Real-time conditions from the National Weather Service
- **Community Sentiment**: Reputation-based scoring system for 80+ resorts
- **Distance Calculation**: Precise distance from your location to each resort
- **Cost Estimation**: Projected trip costs based on duration and selected services

### User Experience
- **Quick Booking Cards**: Visual interface for instant booking access
- **Comprehensive Data Table**: Sortable overview of all discovered resorts
- **Export Functionality**: Download all booking links as a text file
- **Debug Mode**: Optional detailed logging for troubleshooting
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## The Process

### 1. Location Processing
The application starts by converting user input into geographic coordinates:
```
User Input → GeoPy Geocoding → Latitude/Longitude → Address Validation
```

### 2. Resort Discovery
Multiple data sources ensure comprehensive results:
```
OpenStreetMap Query → Filter Non-Resorts → Calculate Distances → Sort by Proximity
                ↓ (If empty)
        Fallback Database (Lake Tahoe, etc.)
```

**Smart Filtering Logic:**
- Excludes: trails, roads, loops, parking areas, rental shops
- Includes: `leisure=ski_resort`, `sport=skiing` with valid names
- Validates: Geographic distance within user-specified radius

### 3. Data Enrichment
For each discovered resort, the system fetches:

**Weather Data:**
```
Resort Coordinates → NWS Points API → Forecast URL → Current Conditions
```

**Sentiment Analysis:**
```
Resort Name → Reputation Database Lookup → Sentiment Score (0.0 to 0.30)
```

The reputation database contains curated sentiment scores for 80+ popular ski resorts based on:
- Community feedback and reviews
- Resort popularity and amenities
- General skier satisfaction patterns

### 4. Booking URL Generation
The system intelligently constructs booking URLs:

**For Known Resorts:**
```python
# Example: Vail Resorts
base_url = "https://www.northstarcalifornia.com"
ticket_url = f"{base_url}/plan-your-trip/lift-access/tickets.aspx?startDate={date_from}&endDate={date_to}"
```

**For Unknown Resorts:**
```
Resort Name + Service Type + Dates → Google Search Query
```

### 5. Results Presentation
```
Resort Data + Booking Links + Weather + Sentiment → Display Cards & Tables
                                                    ↓
                                            Export to Text File
```

## Running the Project

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/ski-resort-finder.git
cd ski-resort-finder
```

2. **Create a virtual environment** (recommended)
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Download NLTK data** (first-time setup)
```python
python -c "import nltk; nltk.download('vader_lexicon')"
```

### Running the Application

**Start the Streamlit server:**
```bash
streamlit run ski_resort_finder_fixed.py
```

The application will automatically open in the default web browser at `http://localhost:8501`

### Usage

1. **Configure Search Parameters** (left sidebar):
   - Enter a location (e.g., "Lake Tahoe, CA", "Denver, CO", "Salt Lake City, UT")
   - Set search radius in miles
   
2. **Set Trip Dates**:
   - Choose start date
   - Choose end date
   
3. **Select Options**:
   - Check "Include ski/snowboard lessons" if needed
   - Check "Include equipment rental" if needed
   - Enable "Show sentiment debug info" for detailed logging (optional)
   
4. **Find Resorts**:
   - Click the "Find Resorts & Build Booking Links" button
   - Browse results in the quick booking cards or data table
   - Click booking links to go directly to resort websites with pre-filled dates
   
5. **Export Links** (optional):
   - Scroll to bottom and click "Download All Links (TXT)"
   - Save the text file with all booking URLs for later reference

### Troubleshooting

**Issue: "No resorts found via OpenStreetMap"**
- Solution: Try increasing the search radius
- Solution: Use a more specific location (e.g., "Truckee, CA" instead of "Northern California")
- Solution: For Lake Tahoe, the app will automatically use the fallback database

**Issue: Weather shows "Weather unavailable"**
- Cause: Location outside the US (NWS API only covers US territories)
- Solution: Weather feature only works for US-based resorts

**Issue: All sentiment scores showing as neutral**
- Solution: Enable "Show sentiment debug info" to see what's happening
- Note: Smaller/unknown resorts will show neutral scores if not in the reputation database

### Configuration

**Customize Resort Database:**
Edit the `reputation_map` dictionary in `get_reddit_sentiment()` function to add or modify resort sentiment scores.

**Adjust Search Radius:**
Modify the slider range in the sidebar section:
```python
radius = st.slider("Radius (miles)", min_value=5, max_value=100, value=20, step=5)
```


## Dependencies

Create a `requirements.txt` file with:
```
streamlit>=1.28.0
pandas>=2.0.0
nltk>=3.8.0
geopy>=2.3.0
requests>=2.31.0
```

## Known Limitations

- Weather data only available for US-based resorts (NWS API limitation)
- OpenStreetMap data quality varies by region
- Booking URL patterns may need updates as resort websites change
- Sentiment scores are reputation-based estimates, not real-time social media analysis
- Some smaller or newly opened resorts may not be in the database

## Potential Future Enhancements

- [ ] Add snow report integration
- [ ] Include real-time lift status and trail counts
- [ ] Implement user reviews and ratings
- [ ] Add webcam feeds from resorts
- [ ] Support for international weather APIs
- [ ] Price comparison across booking platforms
- [ ] Save favorite resorts
- [ ] Trip planning with multi-resort itineraries
