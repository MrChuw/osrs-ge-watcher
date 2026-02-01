# OSRS GE Tracker

This project was developed as a self-hosted alternative to existing online tools, avoiding reliance on third-party platforms and subscriptions. It is designed for personal use rather than as a public-facing service.

## Live Demo
A live demonstration is available at [alchemy](https://osrs-ge.mrchuw.com.br/alchemy) or [items](https://osrs-ge.mrchuw.com.br/items). I still need to make the main page. 

> **Note:** The demo version includes a significant delay between WebSocket updates and uses [Umami](https://github.com/umami-software/umami) for basic analytics.

## Installation and Setup

### Environment Configuration
Before starting the application, you must set up your environment variables:
```bash
cp .env.example .env
```

### Option 1: Docker (Recommended)
The fastest way to deploy the stack is using Docker Compose:
```bash
docker compose up -d
```

### Option 2: Manual Setup (uv)
If you prefer to run the services locally, this project utilizes [uv](https://github.com/astral-sh/uv) for dependency management. 

**Note:** This project requires a **ClickHouse** database instance to be running and accessible.

1. **Sync dependencies:**
```bash
uv sync
```

2. **Run the data ingester:**
```bash
uv run ingester.py
```

3. **Run the web server:**
```bash
uv run webserver.py
```

## Configuration Variables

The following table lists the available environment variables. Note that Database and User Agent settings are required for the application to function.

| Variable | Description | Default / Requirement |
| :--- | :--- | :--- |
| **DB_HOST** | ClickHouse database host address | **Required** |
| **DB_PORT** | ClickHouse database port | **Required** |
| **DB_USERNAME** | ClickHouse database username | **Required** |
| **DB_PASSWORD** | ClickHouse database password | **Required** |
| **DB_DATABASE** | ClickHouse database name | **Required** |
| **USER_AGENT** | Email/Contact for API identification | **Required** |
| HOST_BIND | Interface for the web server to bind to | 0.0.0.0 |
| HOST_PORT | Local machine port for the service | 25000 |
| CONTAINER_PORT | Internal container port | 25000 |
| DEFAULT_FALL_THRESHOLD | Default percentage for price drop alerts | 20.0 |
| MIN_ALLOWED_THRESHOLD | Minimum allowed percentage for alerts | 5.0 |
| CHECK_INTERVAL | Frequency of price checks (seconds) | 5 |
| CHECK_INTERVAL_RAW | Frequency of raw data updates | 5 |
| TTL_FORCED_UPDATE | Time-to-live for forced data refresh | 60 |
| ANALYTICS_URL | URL for Umami analytics script | Optional |
| ANALYTICS_UUID | Website UUID for Umami tracking | Optional |