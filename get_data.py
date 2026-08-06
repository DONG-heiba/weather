from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path
from typing import Iterable

import openmeteo_requests
import pandas as pd
import requests_cache
from openmeteo_requests.Client import HTTPVerb
from retry_requests import retry

RAW_CACHE = ".cache"
CLEAN_DB = Path("cache.sqlite")
API_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_REGION = {
    "west": 70.0,
    "east": 150.0,
    "south": 0.0,
    "north": 55.0,
    "step": 2.5,
}

REFERENCE_PLACES = [
    {"name": "上海", "latitude": 31.23, "longitude": 121.47},
    {"name": "北京", "latitude": 39.90, "longitude": 116.40},
    {"name": "成都", "latitude": 30.67, "longitude": 104.06},
    {"name": "广州", "latitude": 23.13, "longitude": 113.26},
    {"name": "武汉", "latitude": 30.59, "longitude": 114.30},
    {"name": "西安", "latitude": 34.34, "longitude": 108.94},
    {"name": "乌鲁木齐", "latitude": 43.82, "longitude": 87.62},
    {"name": "拉萨", "latitude": 29.65, "longitude": 91.13},
    {"name": "台北", "latitude": 25.03, "longitude": 121.56},
    {"name": "香港", "latitude": 22.32, "longitude": 114.17},
    {"name": "东京", "latitude": 35.68, "longitude": 139.69},
    {"name": "首尔", "latitude": 37.57, "longitude": 126.98},
    {"name": "新加坡", "latitude": 1.35, "longitude": 103.82},
    {"name": "曼谷", "latitude": 13.75, "longitude": 100.50},
    {"name": "河内", "latitude": 21.03, "longitude": 105.85},
    {"name": "马尼拉", "latitude": 14.60, "longitude": 120.98},
    {"name": "孟买", "latitude": 19.08, "longitude": 72.88},
]

HOURLY_VARIABLES = [
    "temperature_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation_probability",
    "precipitation",
    "cloud_cover",
    "pressure_msl",
]


def build_client() -> openmeteo_requests.Client:
    cache_session = requests_cache.CachedSession(RAW_CACHE, expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


def float_range(start: float, stop: float, step: float) -> Iterable[float]:
    value = start
    while value <= stop + step / 10:
        yield round(value, 4)
        value += step


def build_grid(west: float, east: float, south: float, north: float, step: float) -> list[dict[str, float | str]]:
    if west >= east:
        raise ValueError("west must be smaller than east")
    if south >= north:
        raise ValueError("south must be smaller than north")
    if step <= 0:
        raise ValueError("step must be positive")

    points: list[dict[str, float | str]] = []
    for lat in float_range(south, north, step):
        for lon in float_range(west, east, step):
            points.append(
                {
                    "name": f"grid_{lat:.2f}_{lon:.2f}",
                    "latitude": lat,
                    "longitude": lon,
                }
            )
    return points


def chunked(items: list[dict[str, float | str]], size: int) -> Iterable[list[dict[str, float | str]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def wind_components(speed: float, direction: float) -> tuple[float, float]:
    if pd.isna(speed) or pd.isna(direction):
        return 0.0, 0.0
    radians = math.radians(direction)
    return -speed * math.sin(radians), -speed * math.cos(radians)


def response_to_frame(response, location: dict[str, float | str]) -> pd.DataFrame:
    hourly = response.Hourly()
    date_index = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )
    frame = pd.DataFrame(
        {
            "time": date_index,
            "temperature": hourly.Variables(0).ValuesAsNumpy(),
            "wind_speed": hourly.Variables(1).ValuesAsNumpy(),
            "wind_direction": hourly.Variables(2).ValuesAsNumpy(),
            "precipitation_probability": hourly.Variables(3).ValuesAsNumpy(),
            "precipitation": hourly.Variables(4).ValuesAsNumpy(),
            "clouds": hourly.Variables(5).ValuesAsNumpy(),
            "pressure": hourly.Variables(6).ValuesAsNumpy(),
        }
    )
    frame["location_name"] = str(location["name"])
    frame["lat"] = float(location["latitude"])
    frame["lon"] = float(location["longitude"])
    frame["time_iso"] = frame["time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    components = frame.apply(lambda row: wind_components(row["wind_speed"], row["wind_direction"]), axis=1)
    frame["u"] = [item[0] for item in components]
    frame["v"] = [item[1] for item in components]
    return frame[
        [
            "location_name",
            "lat",
            "lon",
            "time_iso",
            "temperature",
            "wind_speed",
            "wind_direction",
            "precipitation_probability",
            "precipitation",
            "clouds",
            "pressure",
            "u",
            "v",
        ]
    ]


def fetch_batch(
    client: openmeteo_requests.Client,
    locations: list[dict[str, float | str]],
    forecast_days: int,
) -> list[pd.DataFrame]:
    responses = client.weather_api(
        API_URL,
        params={
            "latitude": [location["latitude"] for location in locations],
            "longitude": [location["longitude"] for location in locations],
            "hourly": HOURLY_VARIABLES,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        },
        method=HTTPVerb.POST,
    )
    if len(responses) != len(locations):
        raise RuntimeError(f"Open-Meteo returned {len(responses)} responses for {len(locations)} locations")
    return [response_to_frame(response, location) for response, location in zip(responses, locations)]


def clean_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "lat",
        "lon",
        "temperature",
        "wind_speed",
        "wind_direction",
        "precipitation_probability",
        "precipitation",
        "clouds",
        "pressure",
        "u",
        "v",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["temperature", "wind_speed", "wind_direction", "precipitation", "clouds", "pressure"])
    frame["precipitation_probability"] = frame["precipitation_probability"].fillna(0).clip(0, 100)
    frame["precipitation"] = frame["precipitation"].fillna(0).clip(lower=0)
    frame["clouds"] = frame["clouds"].clip(0, 100)
    frame["wind_direction"] = frame["wind_direction"] % 360
    return frame.sort_values(["time_iso", "lat", "lon"]).reset_index(drop=True)


def write_sqlite(frame: pd.DataFrame, places: list[dict[str, float | str]], metadata: dict[str, str]) -> None:
    if CLEAN_DB.exists():
        CLEAN_DB.unlink()
    with sqlite3.connect(CLEAN_DB) as connection:
        frame.to_sql("weather_hourly", connection, index=False)

        locations = frame[["location_name", "lat", "lon"]].drop_duplicates().sort_values(["lat", "lon"])
        locations.to_sql("locations", connection, index=False)

        place_frame = pd.DataFrame(
            [
                {"place_name": place["name"], "lat": place["latitude"], "lon": place["longitude"]}
                for place in places
            ]
        )
        place_frame.to_sql("places", connection, index=False)

        base_metadata = [
            {"key": "source", "value": "Open-Meteo Forecast API"},
            {"key": "raw_cache", "value": f"{RAW_CACHE}.sqlite"},
            {"key": "cleaned_at", "value": pd.Timestamp.now("UTC").isoformat()},
            {"key": "time_start", "value": frame["time_iso"].min()},
            {"key": "time_end", "value": frame["time_iso"].max()},
            {"key": "time_count", "value": str(frame["time_iso"].nunique())},
            {"key": "variables", "value": ",".join(HOURLY_VARIABLES)},
        ]
        base_metadata.extend({"key": key, "value": value} for key, value in metadata.items())
        pd.DataFrame(base_metadata).to_sql("metadata", connection, index=False)

        connection.execute("CREATE INDEX idx_weather_time ON weather_hourly(time_iso)")
        connection.execute("CREATE INDEX idx_weather_location ON weather_hourly(location_name)")
        connection.execute("CREATE INDEX idx_weather_lat_lon ON weather_hourly(lat, lon)")
        connection.execute("CREATE INDEX idx_places_lat_lon ON places(lat, lon)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Open-Meteo forecast data as an East Asia weather grid.")
    parser.add_argument("--west", type=float, default=DEFAULT_REGION["west"])
    parser.add_argument("--east", type=float, default=DEFAULT_REGION["east"])
    parser.add_argument("--south", type=float, default=DEFAULT_REGION["south"])
    parser.add_argument("--north", type=float, default=DEFAULT_REGION["north"])
    parser.add_argument("--step", type=float, default=DEFAULT_REGION["step"], help="Grid step in degrees. Smaller is sharper but slower.")
    parser.add_argument("--forecast-days", type=int, default=16, choices=range(1, 17))
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="Print grid size without calling Open-Meteo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grid = build_grid(args.west, args.east, args.south, args.north, args.step)
    metadata = {
        "grid_mode": "regular_region_grid",
        "region_west": str(args.west),
        "region_east": str(args.east),
        "region_south": str(args.south),
        "region_north": str(args.north),
        "grid_step_degrees": str(args.step),
        "grid_point_count": str(len(grid)),
        "reference_place_count": str(len(REFERENCE_PLACES)),
    }

    print(
        "Grid:",
        f"{args.west}E-{args.east}E, {args.south}N-{args.north}N,",
        f"step {args.step}°, {len(grid)} points",
    )
    if args.dry_run:
        print("Dry run only; cache.sqlite was not changed.")
        return

    client = build_client()
    frames: list[pd.DataFrame] = []
    batches = list(chunked(grid, args.batch_size))
    for batch_index, batch in enumerate(batches, start=1):
        batch_frames = fetch_batch(client, batch, args.forecast_days)
        frames.extend(batch_frames)
        print(f"Batch {batch_index}/{len(batches)}: {len(batch)} grid points")

    cleaned = clean_numeric(pd.concat(frames, ignore_index=True))
    write_sqlite(cleaned, REFERENCE_PLACES, metadata)
    print(f"\nSaved cleaned weather grid to {CLEAN_DB.resolve()}")
    print(f"Rows: {len(cleaned)}")
    print(f"Times: {cleaned['time_iso'].min()} -> {cleaned['time_iso'].max()}")
    print(f"Grid points: {cleaned['location_name'].nunique()}")


if __name__ == "__main__":
    main()
