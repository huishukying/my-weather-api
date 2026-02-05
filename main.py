from fastapi import FastAPI, HTTPException
import requests
from typing import List, Optional
import time

app = FastAPI(
    title="Hong Kong Weather API",
    description="Real-time weather data from Hong Kong Observatory",
    version="1.0.0"
)

# Cache to avoid too many API calls
weather_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_hko_data(data_type: str = "rhrread") -> dict:
    """Fetch data from HKO API with caching"""
    
    cache_key = data_type
    current_time = time.time()
    
    # Check cache
    if cache_key in weather_cache:
        cached_time, cached_data = weather_cache[cache_key]
        if current_time - cached_time < CACHE_DURATION:
            return cached_data
    
    # Fetch from HKO
    url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
    params = {"dataType": data_type, "lang": "en"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Cache it
        weather_cache[cache_key] = (current_time, data)
        
        return data
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"HKO service unavailable: {str(e)}")

@app.get("/")
def home():
    """API home page with available endpoints"""
    return {
        "name": "Hong Kong Weather API",
        "version": "1.0.0",
        "description": "Real-time weather data from HKO",
        "endpoints": {
            "/": "This page",
            "/health": "API health status",
            "/temperature/current": "Current temperatures from all stations",
            "/temperature/{station}": "Temperature for specific station",
            "/rainfall": "Current rainfall data",
            "/humidity": "Current humidity data",
            "/warnings": "Weather warnings",
            "/forecast": "9-day forecast",
            "/cache/clear": "Clear API cache"
        },
        "source": "Hong Kong Observatory Open Data"
    }

@app.get("/health")
def health_check():
    """Check API and HKO service status"""
    try:
        # Test HKO connection
        test_data = get_hko_data("rhrread")
        
        return {
            "status": "healthy",
            "hko_service": "available",
            "cache_size": len(weather_cache),
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "hko_service": "unavailable",
            "error": str(e),
            "timestamp": time.time()
        }

@app.get("/temperature/current")
def get_current_temperatures():
    """Get current temperature readings from all stations"""
    
    data = get_hko_data("rhrread")
    
    # Extract temperature data
    temp_data = data.get("temperature", {}).get("data", [])
    
    if not temp_data:
        raise HTTPException(status_code=404, detail="Temperature data not available")
    
    # Calculate average
    temperatures = [item.get("value", 0) for item in temp_data if item.get("value")]
    avg_temp = sum(temperatures) / len(temperatures) if temperatures else None
    
    return {
        "timestamp": data.get("iconUpdateTime", ""),
        "stations_count": len(temp_data),
        "average_temperature": round(avg_temp, 1) if avg_temp else None,
        "unit": "°C",
        "stations": [
            {
                "name": station.get("place", "Unknown"),
                "temperature": station.get("value"),
                "unit": station.get("unit", "C")
            }
            for station in temp_data
        ]
    }

@app.get("/temperature/{station_name}")
def get_station_temperature(station_name: str):
    """Get temperature for a specific weather station"""
    
    data = get_hko_data("rhrread")
    temp_data = data.get("temperature", {}).get("data", [])
    
    # Find station (case-insensitive search)
    station_name_lower = station_name.lower()
    
    for station in temp_data:
        if station.get("place", "").lower() == station_name_lower:
            return {
                "station": station.get("place"),
                "temperature": station.get("value"),
                "unit": station.get("unit", "C"),
                "timestamp": data.get("iconUpdateTime", "")
            }
    
    # If not found, show available stations
    available_stations = [s.get("place") for s in temp_data]
    raise HTTPException(
        status_code=404,
        detail={
            "error": f"Station '{station_name}' not found",
            "available_stations": available_stations
        }
    )

@app.get("/rainfall")
def get_rainfall_data():
    
    data = get_hko_data("rhrread")
    rainfall_data = data.get("rainfall", {}).get("data", [])

    raining_places = [
        {
            "district": item.get("place"),
            "rainfall": item.get("max", 0),
            "unit": item.get("unit", "mm")
        }
        for item in rainfall_data
        if item.get("max", 0) > 0
    ]

    return {
        "timestamp": data.get("iconUpdateTime", ""),
        "total_stations": len(rainfall_data),
        "stations_with_rain": len(raining_places),
        "raining_places": raining_places,
        "all_stations": [
            {
                "district": item.get("place"),
                "rainfall": item.get("max", 0),
                "unit": item.get("unit", "mm")
            }
            for item in rainfall_data
        ]
    }

@app.get("/forecast")
def get_forecast(days: Optional[int] = None):
    """Get weather forecast (default: all 9 days)"""
    
    data = get_hko_data("fnd")
    forecast_data = data.get("weatherForecast", [])
    
    # Limit days if specified
    if days and 1 <= days <= 9:
        forecast_data = forecast_data[:days]
    
    return {
        "forecast_generated": data.get("general", {}).get("forecastTime", ""),
        "days_count": len(forecast_data),
        "forecast": [
            {
                "date": day.get("forecastDate"),
                "day_of_week": day.get("week"),
                "weather": day.get("forecastWeather"),
                "wind": day.get("forecastWind"),
                "max_temp": day.get("forecastMaxtemp", {}).get("value"),
                "min_temp": day.get("forecastMintemp", {}).get("value"),
                "max_humidity": day.get("forecastMaxrh", {}).get("value"),
                "min_humidity": day.get("forecastMinrh", {}).get("value")
            }
            for day in forecast_data
        ]
    }

@app.delete("/cache/clear")
def clear_cache():
    """Clear the API cache"""
    cleared_count = len(weather_cache)
    weather_cache.clear()
    return {
        "message": "Cache cleared successfully",
        "items_cleared": cleared_count
    }

@app.get("/cache/status")
def cache_status():
    """Get cache statistics"""
    return {
        "cached_items": len(weather_cache),
        "cached_keys": list(weather_cache.keys()),
        }