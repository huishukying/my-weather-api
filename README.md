# Hong Kong Weather API

A FastAPI-based REST API providing real-time weather data from Hong Kong Observatory.

## Features
- Real-time temperature, rainfall, and forecast data
- User authentication with secure password hashing
- PostgreSQL database with SQLAlchemy ORM
- Caching system for improved performance

## Tech Stack
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL with SQLAlchemy
- **Authentication**: PBKDF2 password hashing
- **Deployment**: Railway

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hk-weather-api.git
cd hk-weather-api
