"""FastAPI backend for weather visualization webpage.

Serves weather grid data, point queries, and metadata from cache.sqlite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

DB_PATH = Path(__file__).parent / "cache.sqlite"

app = FastAPI(title="Weather Viz API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Layer definitions – shared between /api/meta and /api/field
# ---------------------------------------------------------------------------

LAYERS: dict[str, dict[str, Any]] = {
    "temperature": {
        "id": "temperature",
        "name": "温度",
        "name_en": "Temperature",
        "column": "temperature",
        "unit": "°C",
        "type": "scalar",
        "color_scheme": "thermal",
        "description": "2 米气温，表示地面以上 2 米处的空气温度",
    },
    "precipitation": {
        "id": "precipitation",
        "name": "降雨",
        "name_en": "Precipitation",
        "column": "precipitation",
        "unit": "mm/h",
        "type": "scalar",
        "color_scheme": "blues",
        "description": "小时降水量，表示每小时的降雨量",
    },
    "wind": {
        "id": "wind",
        "name": "风场",
        "name_en": "Wind",
        "column": None,
        "unit": "m/s",
        "type": "vector",
        "color_scheme": "wind",
        "description": "10 米风速与风向，箭头指向下风向，长度和颜色表示风速大小",
    },
    "clouds": {
        "id": "clouds",
        "name": "云量",
        "name_en": "Cloud Cover",
        "column": "clouds",
        "unit": "%",
        "type": "scalar",
        "color_scheme": "greys",
        "description": "总云量，表示天空被云覆盖的百分比",
    },
    "pressure": {
        "id": "pressure",
        "name": "气压",
        "name_en": "Pressure",
        "column": "pressure",
        "unit": "hPa",
        "type": "scalar",
        "color_scheme": "pressure",
        "description": "海平面气压，用于分析高低压系统分布",
    },
}

LAYER_ORDER = ["temperature", "precipitation", "wind", "clouds", "pressure"]


def _get_db() -> sqlite3.Connection:
    """Return a read-only connection to the SQLite database."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="数据库文件不存在，请先运行 get_data.py")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _get_times(conn: sqlite3.Connection) -> list[str]:
    """Return distinct sorted time_iso values."""
    rows = conn.execute(
        "SELECT DISTINCT time_iso FROM weather_hourly ORDER BY time_iso"
    ).fetchall()
    return [r["time_iso"] for r in rows]


def _get_ranges(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    """Return min/max for each scalar variable."""
    ranges: dict[str, dict[str, float]] = {}
    for layer_id, layer in LAYERS.items():
        col = layer["column"]
        if col is None:
            continue
        row = conn.execute(
            f"SELECT MIN({col}) AS mn, MAX({col}) AS mx FROM weather_hourly"
        ).fetchone()
        ranges[layer_id] = {
            "min": round(row["mn"], 2) if row["mn"] is not None else 0,
            "max": round(row["mx"], 2) if row["mx"] is not None else 0,
        }
    # wind speed range
    row = conn.execute(
        "SELECT MIN(wind_speed) AS mn, MAX(wind_speed) AS mx FROM weather_hourly"
    ).fetchone()
    ranges["wind"] = {
        "min": round(row["mn"], 2) if row["mn"] is not None else 0,
        "max": round(row["mx"], 2) if row["mx"] is not None else 0,
    }
    return ranges


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    """Check service and database availability."""
    try:
        conn = _get_db()
        row = conn.execute("SELECT COUNT(*) AS cnt FROM weather_hourly").fetchone()
        time_row = conn.execute(
            "SELECT MIN(time_iso) AS tmin, MAX(time_iso) AS tmax FROM weather_hourly"
        ).fetchone()
        conn.close()
        return {
            "status": "ok",
            "row_count": row["cnt"],
            "time_start": time_row["tmin"],
            "time_end": time_row["tmax"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/meta")
def meta():
    """Return metadata: timeline, layers, legend, cities, sources."""
    conn = _get_db()
    try:
        times = _get_times(conn)
        ranges = _get_ranges(conn)

        # reference places
        places = [
            {"name": r["place_name"], "lat": r["lat"], "lon": r["lon"]}
            for r in conn.execute("SELECT * FROM places ORDER BY place_name").fetchall()
        ]

        # grid metadata
        grid_meta = dict(
            conn.execute(
                "SELECT key, value FROM metadata WHERE key LIKE 'grid_%' OR key LIKE 'region_%'"
            ).fetchall()
        )

        # Unique lat/lon grid lines
        lat_rows = conn.execute(
            "SELECT DISTINCT lat FROM weather_hourly ORDER BY lat"
        ).fetchall()
        lon_rows = conn.execute(
            "SELECT DISTINCT lon FROM weather_hourly ORDER BY lon"
        ).fetchall()

        conn.close()

        layers_out = []
        for lid in LAYER_ORDER:
            layer = LAYERS[lid]
            entry = {
                "id": layer["id"],
                "name": layer["name"],
                "name_en": layer["name_en"],
                "unit": layer["unit"],
                "type": layer["type"],
                "description": layer["description"],
            }
            if lid in ranges:
                entry["range"] = ranges[lid]
            layers_out.append(entry)

        return {
            "times": times,
            "time_count": len(times),
            "time_start": times[0] if times else None,
            "time_end": times[-1] if times else None,
            "layers": layers_out,
            "places": places,
            "grid": {
                "lats": [round(r["lat"], 2) for r in lat_rows],
                "lons": [round(r["lon"], 2) for r in lon_rows],
                "step": float(grid_meta.get("grid_step_degrees", 2.5)),
            },
            "sources": {
                "weather": "Open-Meteo Forecast API (ECMWF IFS Open Data)",
                "map": "OpenStreetMap",
            },
        }
    finally:
        conn.close()


@app.get("/api/field")
def field(
    layer: str = Query(..., description="Layer id: temperature|precipitation|wind|clouds|pressure"),
    time_idx: int = Query(0, ge=0, description="Time index into the sorted time list"),
):
    """Return grid field data for the given layer and time index."""
    if layer not in LAYERS:
        raise HTTPException(status_code=400, detail=f"Unknown layer: {layer}")

    conn = _get_db()
    try:
        times = _get_times(conn)
        if time_idx >= len(times):
            raise HTTPException(
                status_code=400,
                detail=f"time_idx {time_idx} out of range (0..{len(times)-1})",
            )
        time_iso = times[time_idx]

        layer_def = LAYERS[layer]

        # Fetch unique grid coordinates
        lat_rows = conn.execute(
            "SELECT DISTINCT lat FROM weather_hourly ORDER BY lat"
        ).fetchall()
        lon_rows = conn.execute(
            "SELECT DISTINCT lon FROM weather_hourly ORDER BY lon"
        ).fetchall()
        lats = [round(r["lat"], 2) for r in lat_rows]
        lons = [round(r["lon"], 2) for r in lon_rows]

        if layer_def["type"] == "vector":
            # Return u, v, and wind_speed for wind layer
            rows = conn.execute(
                """
                SELECT lat, lon, u, v, wind_speed
                FROM weather_hourly
                WHERE time_iso = ?
                ORDER BY lat, lon
                """,
                (time_iso,),
            ).fetchall()

            # Build 2D arrays
            u_arr = [[0.0] * len(lons) for _ in range(len(lats))]
            v_arr = [[0.0] * len(lons) for _ in range(len(lats))]
            speed_arr = [[0.0] * len(lons) for _ in range(len(lats))]

            lat_to_idx = {lat: i for i, lat in enumerate(lats)}
            lon_to_idx = {lon: j for j, lon in enumerate(lons)}

            for row in rows:
                i = lat_to_idx[round(row["lat"], 2)]
                j = lon_to_idx[round(row["lon"], 2)]
                u_arr[i][j] = round(row["u"], 4)
                v_arr[i][j] = round(row["v"], 4)
                speed_arr[i][j] = round(row["wind_speed"], 4)

            # Compute wind speed range for this time slice
            speeds = [s for s in row for row in speed_arr for s in [row] if isinstance(s, (int, float))]  # noqa: F812
            max_speed = max(max(s for row in speed_arr for s in row), 0.01)

            conn.close()
            return {
                "layer": layer,
                "time_iso": time_iso,
                "time_idx": time_idx,
                "lats": lats,
                "lons": lons,
                "u": u_arr,
                "v": v_arr,
                "speed": speed_arr,
                "max_speed": round(max_speed, 2),
                "unit": layer_def["unit"],
            }
        else:
            # Scalar field
            col = layer_def["column"]
            rows = conn.execute(
                f"""
                SELECT lat, lon, {col} AS value
                FROM weather_hourly
                WHERE time_iso = ?
                ORDER BY lat, lon
                """,
                (time_iso,),
            ).fetchall()

            values = [[0.0] * len(lons) for _ in range(len(lats))]
            lat_to_idx = {lat: i for i, lat in enumerate(lats)}
            lon_to_idx = {lon: j for j, lon in enumerate(lons)}

            for row in rows:
                i = lat_to_idx[round(row["lat"], 2)]
                j = lon_to_idx[round(row["lon"], 2)]
                values[i][j] = round(row["value"], 4)

            # Compute actual min/max for this slice
            flat = [v for row in values for v in row]
            slice_min = round(min(flat), 2)
            slice_max = round(max(flat), 2)

            conn.close()
            return {
                "layer": layer,
                "time_iso": time_iso,
                "time_idx": time_idx,
                "lats": lats,
                "lons": lons,
                "values": values,
                "min": slice_min,
                "max": slice_max,
                "unit": layer_def["unit"],
            }
    finally:
        conn.close()


@app.get("/api/point")
def point(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    time_idx: int = Query(0, ge=0, description="Time index"),
):
    """Return weather details for a specific point at a given time."""
    conn = _get_db()
    try:
        times = _get_times(conn)
        if time_idx >= len(times):
            raise HTTPException(
                status_code=400,
                detail=f"time_idx {time_idx} out of range (0..{len(times)-1})",
            )
        time_iso = times[time_idx]

        # Find nearest grid point (simple nearest-neighbor)
        row = conn.execute(
            """
            SELECT *,
                   (lat - ?) * (lat - ?) + (lon - ?) * (lon - ?) AS dist_sq
            FROM weather_hourly
            WHERE time_iso = ?
            ORDER BY dist_sq
            LIMIT 1
            """,
            (lat, lat, lon, lon, time_iso),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="No data found for this location")

        # Try to find the nearest named place (within ~3 degrees)
        place_row = conn.execute(
            """
            SELECT place_name,
                   (lat - ?) * (lat - ?) + (lon - ?) * (lon - ?) AS dist_sq
            FROM places
            ORDER BY dist_sq
            LIMIT 1
            """,
            (lat, lat, lon, lon),
        ).fetchone()

        # Only show city name if within ~3° (≈330km), otherwise just coordinates
        MAX_PLACE_DIST = 9.0  # 3° squared
        if place_row and place_row["dist_sq"] is not None and place_row["dist_sq"] <= MAX_PLACE_DIST:
            place_name = place_row["place_name"]
        else:
            place_name = None

        def wind_dir_str(deg: float) -> str:
            dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
            idx = round(deg / 45) % 8
            return dirs[idx]

        wd = row["wind_direction"] or 0

        conn.close()
        return {
            "query": {"lat": lat, "lon": lon},
            "nearest_grid": {"lat": round(row["lat"], 2), "lon": round(row["lon"], 2)},
            "place_name": place_name,
            "time_iso": time_iso,
            "time_idx": time_idx,
            "temperature": round(row["temperature"], 1),
            "wind_speed": round(row["wind_speed"], 1),
            "wind_direction": round(wd, 0),
            "wind_direction_text": wind_dir_str(wd),
            "precipitation_probability": round(row["precipitation_probability"], 0),
            "precipitation": round(row["precipitation"], 1),
            "clouds": round(row["clouds"], 0),
            "pressure": round(row["pressure"], 1),
            "u": round(row["u"], 2),
            "v": round(row["v"], 2),
            "layers": {
                "temperature": {"value": round(row["temperature"], 1), "unit": "°C"},
                "precipitation": {"value": round(row["precipitation"], 1), "unit": "mm/h"},
                "wind": {"value": round(row["wind_speed"], 1), "unit": "m/s"},
                "clouds": {"value": round(row["clouds"], 0), "unit": "%"},
                "pressure": {"value": round(row["pressure"], 1), "unit": "hPa"},
            },
        }
    finally:
        conn.close()


# 托管前端静态文件（必须在 API 路由之后，否则会拦截 API 请求）
app.mount("/", StaticFiles(directory="dist", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
