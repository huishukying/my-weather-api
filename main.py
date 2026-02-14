from fastapi import FastAPI, HTTPException, Depends
import requests
from typing import List, Optional
import time
from database import get_db, engine
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime
from auth import hash_password
from models import User, Base, WeatherLog

Base.metadata.create_all(bind=engine)

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime  
    
    class Config:
        from_attributes = True

app = FastAPI(
    title="Hong Kong Weather API",
    description="Real-time weather data from Hong Kong Observatory",
    version="1.0.0"
)

weather_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_hko_data(data_type: str = "rhrread") -> dict:
    
    cache_key = data_type
    current_time = time.time()

    if cache_key in weather_cache:
        cached_time, cached_data = weather_cache[cache_key]
        if current_time - cached_time < CACHE_DURATION:
            return cached_data
    
    url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
    params = {"dataType": data_type, "lang": "en"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        weather_cache[cache_key] = (current_time, data)
        
        return data
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"HKO service unavailable: {str(e)}")

@app.get("/")
def home():
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

@app.post("/users/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        (User.email == user.email) | (User.username == user.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email or username already registered"
        )

    hashed_pw = hash_password(user.password)
    
    new_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_pw
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@app.get("/health")
def health_check():
    try:
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
    
    data = get_hko_data("rhrread")
    
    temp_data = data.get("temperature", {}).get("data", [])
    
    if not temp_data:
        raise HTTPException(status_code=404, detail="Temperature data not available")
    
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
    
    data = get_hko_data("rhrread")
    temp_data = data.get("temperature", {}).get("data", [])
    
    station_name_lower = station_name.lower()
    
    for station in temp_data:
        if station.get("place", "").lower() == station_name_lower:
            return {
                "station": station.get("place"),
                "temperature": station.get("value"),
                "unit": station.get("unit", "C"),
                "timestamp": data.get("iconUpdateTime", "")
            }
    
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
    
    data = get_hko_data("fnd")
    forecast_data = data.get("weatherForecast", [])
    
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
    return {
        "cached_items": len(weather_cache),
        "cached_keys": list(weather_cache.keys()),
        }
    
@app.get("/db/users")
def get_users(db: Session = Depends(get_db)):
    """Get all users from database"""
    result = db.execute(text("SELECT * FROM users"))
    users = result.fetchall()
    
    return [
        {"id": u[0], "name": u[1], "email": u[2]}
        for u in users
    ]

@app.get("/db/weather")
def get_weather_logs(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM weather_logs ORDER BY recorded_at DESC"))
    logs = result.fetchall()
    
    return [
        {
            "location": log[1],
            "temperature": log[2],
            "recorded_at": log[3]
        }
        for log in logs
    ]

@app.get("/users", response_model=List[UserResponse])
def get_all_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
