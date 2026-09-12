
import io
import math
import re
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

JAPANESE_FONT_NAME = None


def configure_japanese_matplotlib_font():
    """
    Streamlit Cloudでは packages.txt から fonts-noto-cjk を導入し、
    Noto Sans CJK JP を優先して明示使用する。
    """
    global JAPANESE_FONT_NAME

    # Aptで導入したフォントをMatplotlibへ再スキャン。
    try:
        font_paths = font_manager.findSystemFonts(
            fontpaths=None,
            fontext="ttf",
        ) + font_manager.findSystemFonts(
            fontpaths=None,
            fontext="ttc",
        )

        for font_path in font_paths:
            try:
                font_manager.fontManager.addfont(font_path)
            except Exception:
                pass
    except Exception:
        pass

    installed_names = {
        font.name
        for font in font_manager.fontManager.ttflist
    }

    # Streamlit Cloudでは fonts-noto-cjk で通常この名前が利用可能。
    preferred = [
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAexGothic",
        "IPAGothic",
        "Yu Gothic",
        "Meiryo",
    ]

    for candidate in preferred:
        if candidate in installed_names:
            JAPANESE_FONT_NAME = candidate
            break

    # 名前で拾えない場合は、Noto CJKの実ファイルを直接探索する。
    if JAPANESE_FONT_NAME is None:
        noto_paths = [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf"),
        ]

        for font_path in noto_paths:
            if font_path.exists():
                try:
                    font_manager.fontManager.addfont(str(font_path))
                    prop = font_manager.FontProperties(
                        fname=str(font_path)
                    )
                    JAPANESE_FONT_NAME = prop.get_name()
                    break
                except Exception:
                    pass

    if JAPANESE_FONT_NAME is None:
        JAPANESE_FONT_NAME = "DejaVu Sans"

    matplotlib.rcParams["font.family"] = JAPANESE_FONT_NAME
    matplotlib.rcParams["font.sans-serif"] = [
        JAPANESE_FONT_NAME,
        "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False


configure_japanese_matplotlib_font()


def apply_japanese_font_to_axes(axis):
    """
    Axes内の日本語文字列に選択フォントを明示適用する。
    """
    if not JAPANESE_FONT_NAME:
        return

    font_prop = font_manager.FontProperties(
        family=JAPANESE_FONT_NAME
    )

    axis.title.set_fontproperties(font_prop)
    axis.xaxis.label.set_fontproperties(font_prop)
    axis.yaxis.label.set_fontproperties(font_prop)

    for label in axis.get_xticklabels():
        label.set_fontproperties(font_prop)

    for label in axis.get_yticklabels():
        label.set_fontproperties(font_prop)

    legend = axis.get_legend()
    if legend is not None:
        for text_item in legend.get_texts():
            text_item.set_fontproperties(font_prop)

    for text_item in axis.texts:
        text_item.set_fontproperties(font_prop)


import folium
from folium import Element
from streamlit_folium import st_folium
from scipy.spatial import cKDTree

import hmac

def check_password():
    if st.session_state.get("password_correct", False):
        return True

    st.title("ログイン")
    password = st.text_input(
        "パスワードを入力してください",
        type="password",
    )

    if st.button("ログイン"):
        if hmac.compare_digest(
            password,
            st.secrets["APP_PASSWORD"],
        ):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")

    return False


if not check_password():
    st.stop()


SO2_MOLAR_MASS_KG_MOL = 0.064066
ASSUMED_EMISSION_T_DAY = 1000.0

DEFAULT_CRATER_LAT = 32.8847282
DEFAULT_CRATER_LON = 131.0848191
# 全カラム積分では排出高度は濃度式に直接影響しないため、解析条件として保持する。
DEFAULT_CRATER_ALT_M = 2000.0

GPV_NORTH = 47.6
GPV_WEST = 120.0

DEFAULT_STATIONS = [
    {"station": "SC1", "latitude": 32.886104, "longitude": 131.075142, "height_m": 1141.0},
    {"station": "SC2", "latitude": 32.887972, "longitude": 131.075713, "height_m": 1136.0},
    {"station": "SC3", "latitude": 32.890154, "longitude": 131.077456, "height_m": 1150.0},
    {"station": "SC4", "latitude": 32.891062, "longitude": 131.079561, "height_m": 1169.0},
    {"station": "SC5", "latitude": 32.891685, "longitude": 131.082029, "height_m": 1179.0},
]

WIND_DIRECTION_OFFSETS = list(range(-12, 13, 2))

PPMM_COLOR_BOUNDS = [
    10, 50, 100, 200, 300, 400, 500, 700,
    1000, 2000, 3000, 4000, 5000, 7000,
]
# ppm·mの離散表示色。
PPMM_COLORS = [
    "#fff7bc",  # 10–50
    "#fee8c8",  # 50–100
    "#fff7a8",  # 100–200
    "#ffff66",  # 200–300
    "#fff04a",  # 300–400
    "#ffd34d",  # 400–500
    "#ffbf3f",  # 500–700
    "#ff9f43",  # 700–1000
    "#ff6b5f",  # 1000–2000
    "#ff7fa5",  # 2000–3000
    "#ef7ac8",  # 3000–4000
    "#d66bd6",  # 4000–5000
    "#aa5abf",  # 5000–7000
    "#6f4b8b",  # 7000+
]


def local_xy_m(lat, lon, origin_lat, origin_lon):
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    y = (lat - origin_lat) * 111_320.0
    x = (lon - origin_lon) * 111_320.0 * math.cos(math.radians(origin_lat))
    return x, y


def xy_to_latlon(x_m, y_m, origin_lat, origin_lon):
    x_m = np.asarray(x_m, dtype=float)
    y_m = np.asarray(y_m, dtype=float)
    lat = origin_lat + y_m / 111_320.0
    lon = origin_lon + x_m / (
        111_320.0 * max(math.cos(math.radians(origin_lat)), 1e-6)
    )
    return lat, lon


def parse_gpv_filename(filename: str):
    name = Path(filename).name
    patterns = [
        # 30分大気解析: YYYYMMDDHHMMpPPPu/v
        (
            re.compile(
                r"^(?P<date>\d{8})(?P<hour>\d{2})(?P<minute>\d{2})"
                r"p(?P<pressure>\d{3,4})(?P<component>[uv])(?:\.txt)?$",
                re.IGNORECASE,
            ),
            "30分大気解析",
            0.02,
            0.025,
        ),
        # 毎時大気解析: YYYYMMDDHHpPPPu/v
        (
            re.compile(
                r"^(?P<date>\d{8})(?P<hour>\d{2})"
                r"p(?P<pressure>\d{3,4})(?P<component>[uv])(?:\.txt)?$",
                re.IGNORECASE,
            ),
            "毎時大気解析",
            0.05,
            0.0625,
        ),
    ]

    for pattern, analysis_type, lat_step, lon_step in patterns:
        match = pattern.match(name)
        if match:
            info = match.groupdict()
            minute = int(info.get("minute") or 0)
            return {
                "filename": name,
                "date": info["date"],
                "hour": int(info["hour"]),
                "minute": minute,
                "pressure_hpa": int(info["pressure"]),
                "component": info["component"].lower(),
                "analysis_type": analysis_type,
                "lat_step_deg": lat_step,
                "lon_step_deg": lon_step,
                "timestamp_key": (
                    f"{info['date']}{int(info['hour']):02d}{minute:02d}"
                ),
            }

    raise ValueError(
        "GPVファイル名を解釈できません。"
        "例: 202302090330p850u.txt / 2023121203p900v.txt"
    )


def read_uploaded_text(uploaded_file):
    uploaded_file.seek(0)
    return uploaded_file.getvalue()


@st.cache_data(show_spinner=False)
def load_gpv_array(file_bytes: bytes):
    return np.loadtxt(io.BytesIO(file_bytes), dtype=np.float32)


def build_gpv_grid(array, meta):
    rows, cols = array.shape
    lat_step = float(meta["lat_step_deg"])
    lon_step = float(meta["lon_step_deg"])

    latitudes = GPV_NORTH - np.arange(rows, dtype=float) * lat_step
    longitudes = GPV_WEST + np.arange(cols, dtype=float) * lon_step

    expected_cols = round((150.0 - GPV_WEST) / lon_step) + 1
    shape_warning = None
    if cols != expected_cols:
        shape_warning = (
            f"経度方向の列数が想定値 {expected_cols} と異なります"
            f"（実データ: {cols}）。実データ配列を優先して使用します。"
        )

    implied_south = float(latitudes[-1])
    return latitudes, longitudes, implied_south, shape_warning


def crop_gpv_near_crater(array, meta, crater_lat, crater_lon, margin_deg=0.20):
    lats, lons, implied_south, shape_warning = build_gpv_grid(array, meta)

    lat_mask = (lats >= crater_lat - margin_deg) & (lats <= crater_lat + margin_deg)
    lon_mask = (lons >= crater_lon - margin_deg) & (lons <= crater_lon + margin_deg)

    if not np.any(lat_mask) or not np.any(lon_mask):
        raise RuntimeError(
            "火口位置がGPVデータ範囲外です。"
            f" データ緯度範囲={lats[-1]:.3f}～{lats[0]:.3f}, "
            f"経度範囲={lons[0]:.3f}～{lons[-1]:.3f}"
        )

    cropped = array[np.ix_(lat_mask, lon_mask)]
    crop_lats = lats[lat_mask]
    crop_lons = lons[lon_mask]
    lon_grid, lat_grid = np.meshgrid(crop_lons, crop_lats)
    x_grid, y_grid = local_xy_m(
        lat_grid, lon_grid, crater_lat, crater_lon
    )
    return {
        "array": cropped,
        "lat_grid": lat_grid,
        "lon_grid": lon_grid,
        "x_grid_m": x_grid,
        "y_grid_m": y_grid,
        "implied_south": implied_south,
        "shape_warning": shape_warning,
        "full_shape": array.shape,
    }


def pair_uploaded_gpv(uploaded_files, crater_lat, crater_lon):
    parsed = []
    for uploaded in uploaded_files:
        meta = parse_gpv_filename(uploaded.name)
        file_bytes = read_uploaded_text(uploaded)
        meta["bytes"] = file_bytes
        meta["sha256"] = hashlib.sha256(file_bytes).hexdigest()
        parsed.append(meta)

    groups = {}
    for item in parsed:
        key = (
            item["timestamp_key"],
            item["pressure_hpa"],
            item["analysis_type"],
            item["lat_step_deg"],
            item["lon_step_deg"],
        )
        groups.setdefault(key, {})[item["component"]] = item

    pairs = []
    errors = []

    for key, components in sorted(groups.items()):
        if "u" not in components or "v" not in components:
            errors.append(
                f"{key[0]} / {key[1]} hPa: u/vの片方しかありません。"
            )
            continue

        u_meta = components["u"]
        v_meta = components["v"]
        u_array = load_gpv_array(u_meta["bytes"])
        v_array = load_gpv_array(v_meta["bytes"])

        if u_array.shape != v_array.shape:
            errors.append(
                f"{key[0]} / {key[1]} hPa: u/vの配列サイズが一致しません。"
            )
            continue

        u_crop = crop_gpv_near_crater(
            u_array, u_meta, crater_lat, crater_lon
        )
        v_crop = crop_gpv_near_crater(
            v_array, v_meta, crater_lat, crater_lon
        )

        pair = {
            "label": (
                f"{u_meta['date'][:4]}-{u_meta['date'][4:6]}-"
                f"{u_meta['date'][6:8]} "
                f"{u_meta['hour']:02d}:{u_meta['minute']:02d} "
                f"/ {u_meta['pressure_hpa']} hPa "
                f"/ {u_meta['analysis_type']}"
            ),
            "timestamp_key": u_meta["timestamp_key"],
            "pressure_hpa": u_meta["pressure_hpa"],
            "analysis_type": u_meta["analysis_type"],
            "lat_step_deg": u_meta["lat_step_deg"],
            "lon_step_deg": u_meta["lon_step_deg"],
            "u": u_crop["array"],
            "v": v_crop["array"],
            "x_grid_m": u_crop["x_grid_m"],
            "y_grid_m": u_crop["y_grid_m"],
            "lat_grid": u_crop["lat_grid"],
            "lon_grid": u_crop["lon_grid"],
            "full_shape": u_crop["full_shape"],
            "implied_south": u_crop["implied_south"],
            "shape_warning": u_crop["shape_warning"],
            "hash": hashlib.sha256(
                (u_meta["sha256"] + v_meta["sha256"]).encode()
            ).hexdigest(),
        }
        pair["valid"] = np.isfinite(pair["u"]) & np.isfinite(pair["v"])
        pairs.append(pair)

    return pairs, errors


def interpolate_idw_wind(field, x_m, y_m, radius_m=10_000.0):
    valid = field["valid"]
    gx = field["x_grid_m"][valid]
    gy = field["y_grid_m"][valid]
    gu = field["u"][valid]
    gv = field["v"][valid]

    distance = np.hypot(gx - x_m, gy - y_m)
    if distance.size == 0:
        raise RuntimeError("有効なGPV風データがありません。")

    very_near = distance < 1.0
    if np.any(very_near):
        idx = int(np.argmin(distance))
        return float(gu[idx]), float(gv[idx])

    in_radius = distance <= radius_m
    if not np.any(in_radius):
        idx = int(np.argmin(distance))
        return float(gu[idx]), float(gv[idx])

    d = distance[in_radius]
    weights = 1.0 / np.maximum(d, 1.0) ** 2
    return (
        float(np.sum(weights * gu[in_radius]) / np.sum(weights)),
        float(np.sum(weights * gv[in_radius]) / np.sum(weights)),
    )


def rotate_uv(u, v, degrees):
    theta = math.radians(degrees)
    return (
        u * math.cos(theta) - v * math.sin(theta),
        u * math.sin(theta) + v * math.cos(theta),
    )


def calculate_main_axis(
    field,
    maximum_distance_km=5.0,
    initial_direction_offset_deg=0.0,
    nominal_step_m=100.0,
):
    u0, v0 = interpolate_idw_wind(field, 0.0, 0.0)
    speed0 = math.hypot(u0, v0)
    if speed0 < 0.2:
        raise RuntimeError("火口位置の風速が小さすぎます。")

    delta_t = nominal_step_m / speed0
    max_distance_m = maximum_distance_km * 1000.0

    xs = [0.0]
    ys = [0.0]
    distances = [0.0]
    speeds = [speed0]

    # 火口風の方向補正は第1ステップに適用する。
    first_u, first_v = rotate_uv(u0, v0, initial_direction_offset_deg)
    x1 = first_u * delta_t
    y1 = first_v * delta_t
    first_segment = math.hypot(x1, y1)
    xs.append(x1)
    ys.append(y1)
    distances.append(first_segment)
    speeds.append(speed0)

    for _ in range(500):
        if distances[-1] >= max_distance_m:
            break
        u, v = interpolate_idw_wind(field, xs[-1], ys[-1])
        speed = math.hypot(u, v)
        if speed < 0.1:
            break

        nx = xs[-1] + u * delta_t
        ny = ys[-1] + v * delta_t
        seg = math.hypot(nx - xs[-1], ny - ys[-1])
        xs.append(nx)
        ys.append(ny)
        distances.append(distances[-1] + seg)
        speeds.append(speed)

    return {
        "x_m": np.asarray(xs, dtype=float),
        "y_m": np.asarray(ys, dtype=float),
        "distance_m": np.asarray(distances, dtype=float),
        "speed_ms": np.asarray(speeds, dtype=float),
        "delta_t_s": float(delta_t),
        "crater_u_ms": float(u0),
        "crater_v_ms": float(v0),
        "crater_speed_ms": float(speed0),
        "direction_offset_deg": float(initial_direction_offset_deg),
    }


def sigma_y_values(distance_m, wind_speed_ms, mode, cy, n):
    x = np.maximum(np.asarray(distance_m, dtype=float), 1.0)
    v = np.maximum(np.asarray(wind_speed_ms, dtype=float), 0.1)

    if mode == "風速依存（式11）":
        return 0.045 * (23.0 / v + 4.75) * x ** 0.86

    return (float(cy) / np.sqrt(2.0)) * x ** (1.0 - float(n) / 2.0)


def model_column_mol_m2(
    x_m,
    y_m,
    wind_speed_ms,
    diffusion_mode,
    cy,
    n,
    emission_t_day=ASSUMED_EMISSION_T_DAY,
):
    sigma_y = sigma_y_values(x_m, wind_speed_ms, diffusion_mode, cy, n)
    emission_kg_s = emission_t_day * 1000.0 / 86400.0
    emission_mol_s = emission_kg_s / SO2_MOLAR_MASS_KG_MOL

    return (
        emission_mol_s
        / (
            np.sqrt(2.0 * np.pi)
            * np.maximum(sigma_y, 1.0)
            * np.maximum(wind_speed_ms, 0.1)
        )
        * np.exp(
            -(np.asarray(y_m, dtype=float) ** 2)
            / (2.0 * np.maximum(sigma_y, 1.0) ** 2)
        )
    )


def point_model_values(stations, axis, diffusion_mode, cy, n):
    station_x, station_y = local_xy_m(
        stations["latitude"].to_numpy(),
        stations["longitude"].to_numpy(),
        st.session_state["crater_lat_for_calc"],
        st.session_state["crater_lon_for_calc"],
    )

    tree = cKDTree(
        np.column_stack([axis["x_m"], axis["y_m"]])
    )
    distance_to_axis, nearest = tree.query(
        np.column_stack([station_x, station_y]),
        k=1,
    )
    along = axis["distance_m"][nearest]
    speed = axis["speed_ms"][nearest]

    values = model_column_mol_m2(
        along,
        distance_to_axis,
        speed,
        diffusion_mode,
        cy,
        n,
    )

    values = np.where(
        (along >= 1.0) & (along <= axis["distance_m"][-1]),
        values,
        0.0,
    )
    return values


def convert_model_unit(values_mol_m2, obs_unit, pressure_hpa, temp_c):
    values_mol_m2 = np.asarray(values_mol_m2, dtype=float)
    if obs_unit == "mol/m²":
        return values_mol_m2

    # 理想気体近似で mol/m² → ppm·m を換算。
    R = 8.314462618
    temperature_k = temp_c + 273.15
    pressure_pa = pressure_hpa * 100.0
    factor = R * temperature_k / pressure_pa * 1.0e6
    return values_mol_m2 * factor


def fit_zero_intercept(model_1000, observed):
    model_1000 = np.asarray(model_1000, dtype=float)
    observed = np.asarray(observed, dtype=float)

    valid = np.isfinite(model_1000) & np.isfinite(observed)
    x = model_1000[valid]
    y = observed[valid]

    if len(x) < 2:
        raise RuntimeError("回帰に使える観測点が2点未満です。")

    denominator = float(np.dot(x, x))
    if denominator <= 0:
        raise RuntimeError("モデル値がすべて0のため回帰できません。")

    slope = float(np.dot(x, y) / denominator)
    fitted = slope * x
    residual = y - fitted
    rmse = float(np.sqrt(np.mean(residual ** 2)))

    sse = float(np.sum(residual ** 2))
    sst0 = float(np.sum(y ** 2))
    r2_uncentered = (
        1.0 - sse / sst0 if sst0 > 0 else np.nan
    )

    pearson_r = (
        float(np.corrcoef(x, y)[0, 1])
        if len(x) >= 2
        and np.std(x) > 0
        and np.std(y) > 0
        else np.nan
    )

    return {
        "slope": slope,
        "estimated_emission_t_day": ASSUMED_EMISSION_T_DAY * slope,
        "rmse": rmse,
        "r2_uncentered": r2_uncentered,
        "pearson_r": pearson_r,
        "valid_count": len(x),
    }


def build_pattern_cache(
    pairs,
    selected_labels,
    stations,
    diffusion_mode,
    cy,
    cz,
    n,
    axis_distance_km,
):
    selected = [p for p in pairs if p["label"] in selected_labels]
    if not selected:
        raise RuntimeError("GPV高度パターンが選択されていません。")
    if len(selected) > 3:
        raise RuntimeError("高度（GPV）パターンは最大3つです。")

    patterns = []
    for pair in selected:
        for offset in WIND_DIRECTION_OFFSETS:
            axis = calculate_main_axis(
                pair,
                maximum_distance_km=axis_distance_km,
                initial_direction_offset_deg=offset,
                nominal_step_m=100.0,
            )
            station_values = point_model_values(
                stations, axis, diffusion_mode, cy, n
            )
            patterns.append(
                {
                    "gpv_label": pair["label"],
                    "pressure_hpa": pair["pressure_hpa"],
                    "analysis_type": pair["analysis_type"],
                    "timestamp_key": pair["timestamp_key"],
                    "wind_offset_deg": offset,
                    "axis": axis,
                    "station_model_mol_m2": station_values,
                    "crater_speed_ms": axis["crater_speed_ms"],
                    "crater_u_ms": axis["crater_u_ms"],
                    "crater_v_ms": axis["crater_v_ms"],
                    "cz": cz,
                }
            )
    return patterns


def summarize_model_patterns(patterns, station_df):
    rows = []

    for index, pattern in enumerate(patterns):
        axis = pattern["axis"]
        end_x = float(axis["x_m"][-1])
        end_y = float(axis["y_m"][-1])

        bearing = (
            math.degrees(math.atan2(end_x, end_y)) + 360.0
        ) % 360.0

        row = {
            "モデルNo": index + 1,
            "GPV": pattern["gpv_label"],
            "気圧面_hPa": int(pattern["pressure_hpa"]),
            "火口風向補正_deg": float(pattern["wind_offset_deg"]),
            "火口u_m_s": float(pattern["crater_u_ms"]),
            "火口v_m_s": float(pattern["crater_v_ms"]),
            "火口風速_m_s": float(pattern["crater_speed_ms"]),
            "主軸終端距離_km": float(
                axis["distance_m"][-1]
            ) / 1000.0,
            "主軸終端方位_deg": float(bearing),
        }

        for station_name, value in zip(
            station_df["station"],
            pattern["station_model_mol_m2"],
        ):
            row[f"{station_name}_1000t_day_mol_m2"] = float(value)

        rows.append(row)

    return pd.DataFrame(rows)


def observation_signature(
    observations,
    obs_unit,
    pressure_hpa,
    temp_c,
):
    payload = (
        list(np.asarray(observations, dtype=float))
        + [
            str(obs_unit),
            float(pressure_hpa),
            float(temp_c),
        ]
    )
    return hashlib.sha256(
        repr(payload).encode("utf-8")
    ).hexdigest()


def evaluate_patterns(patterns, observations, obs_unit, pressure_hpa, temp_c):
    rows = []
    for idx, pattern in enumerate(patterns):
        model_values = convert_model_unit(
            pattern["station_model_mol_m2"],
            obs_unit,
            pressure_hpa,
            temp_c,
        )
        try:
            fit = fit_zero_intercept(model_values, observations)
        except Exception as error:
            rows.append(
                {
                    "pattern_index": idx,
                    "GPV": pattern["gpv_label"],
                    "気圧面_hPa": pattern["pressure_hpa"],
                    "火口風向補正_deg": pattern["wind_offset_deg"],
                    "推定放出率_t_day": np.nan,
                    "RMSE": np.nan,
                    "R2_切片0": np.nan,
                    "Pearson_r": np.nan,
                    "エラー": str(error),
                }
            )
            continue

        rows.append(
            {
                "pattern_index": idx,
                "GPV": pattern["gpv_label"],
                "気圧面_hPa": pattern["pressure_hpa"],
                "火口風向補正_deg": pattern["wind_offset_deg"],
                "推定放出率_t_day": fit["estimated_emission_t_day"],
                "RMSE": fit["rmse"],
                "R2_切片0": fit["r2_uncentered"],
                "Pearson_r": fit["pearson_r"],
                "火口風速_m_s": pattern["crater_speed_ms"],
                "回帰傾き": fit["slope"],
                "エラー": "",
            }
        )

    df = pd.DataFrame(rows)
    valid_df = df[np.isfinite(df["RMSE"])].copy()
    if valid_df.empty:
        raise RuntimeError("有効な回帰結果がありません。")

    best_row = valid_df.sort_values(
        ["RMSE", "R2_切片0"],
        ascending=[True, False],
    ).iloc[0]
    best_index = int(best_row["pattern_index"])
    return df, best_index


def ppm_color(value):
    """添付図の離散カラーバーに対応する色を返す。"""
    if value is None or not np.isfinite(value) or value < PPMM_COLOR_BOUNDS[0]:
        return None

    for i in range(len(PPMM_COLOR_BOUNDS) - 1):
        if PPMM_COLOR_BOUNDS[i] <= value < PPMM_COLOR_BOUNDS[i + 1]:
            return PPMM_COLORS[i]

    return PPMM_COLORS[-1]


def build_leaflet_model_map(
    pattern,
    bundle,
    station_df,
    fitted_slope,
    pressure_hpa,
    temp_c,
    axis_distance_km,
    map_grid_spacing_m=40,
):
    """
    最適モデルをLeaflet地図へ重ねる。

    - SO2濃度は離散色の半透明CircleMarker格子
    - 主軸は点列
    - 火口・SC観測点を重畳
    - マウス位置のモデル濃度をLeaflet上でリアルタイム表示
      （主軸データからJavaScript側で再計算）
    """
    crater_lat = float(bundle["crater_lat"])
    crater_lon = float(bundle["crater_lon"])

    fmap = folium.Map(
        location=[crater_lat, crater_lon],
        zoom_start=14,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )

    # ---- SO2 concentration layer ----
    half_extent = float(axis_distance_km) * 1000.0
    coords = np.arange(
        -half_extent,
        half_extent + map_grid_spacing_m,
        float(map_grid_spacing_m),
        dtype=float,
    )
    xx, yy = np.meshgrid(coords, coords)

    axis = pattern["axis"]
    tree = cKDTree(np.column_stack([axis["x_m"], axis["y_m"]]))
    distance_to_axis, nearest = tree.query(
        np.column_stack([xx.ravel(), yy.ravel()]),
        k=1,
    )
    along = axis["distance_m"][nearest]
    speed = axis["speed_ms"][nearest]

    field_mol = model_column_mol_m2(
        along,
        distance_to_axis,
        speed,
        bundle["diffusion_mode"],
        bundle["cy"],
        bundle["n"],
    )
    valid = (along >= 1.0) & (along <= axis["distance_m"][-1])
    field_mol = np.where(valid, field_mol, np.nan)

    field_ppm = convert_model_unit(
        field_mol,
        "ppm·m",
        pressure_hpa,
        temp_c,
    ) * float(fitted_slope)

    lat_grid, lon_grid = xy_to_latlon(
        xx.ravel(),
        yy.ravel(),
        crater_lat,
        crater_lon,
    )

    concentration_group = folium.FeatureGroup(
        name="最適モデル SO₂カラム濃度",
        show=True,
    )

    # 表示量を抑えるため、10 ppm·m以上のみ描画。
    for lat, lon, value in zip(
        lat_grid,
        lon_grid,
        field_ppm,
    ):
        color = ppm_color(value)
        if color is None:
            continue
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=3.2,
            stroke=False,
            fill=True,
            fill_color=color,
            fill_opacity=0.56,
            tooltip=f"{float(value):.1f} ppm·m",
        ).add_to(concentration_group)

    concentration_group.add_to(fmap)

    # ---- plume centerline points ----
    axis_group = folium.FeatureGroup(name="プルーム主軸（点）", show=True)
    axis_lat, axis_lon = xy_to_latlon(
        axis["x_m"],
        axis["y_m"],
        crater_lat,
        crater_lon,
    )
    for lat, lon, distance_m in zip(
        axis_lat, axis_lon, axis["distance_m"]
    ):
        folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=3.2,
            color="#111111",
            weight=1,
            fill=True,
            fill_color="#ffffff",
            fill_opacity=1.0,
            tooltip=f"主軸 {float(distance_m)/1000.0:.2f} km",
        ).add_to(axis_group)
    axis_group.add_to(fmap)

    # ---- crater ----
    folium.Marker(
        [crater_lat, crater_lon],
        tooltip="火口",
        popup=(
            f"火口<br>緯度 {crater_lat:.6f}<br>"
            f"経度 {crater_lon:.6f}"
        ),
        icon=folium.Icon(color="red", icon="fire", prefix="fa"),
    ).add_to(fmap)

    # ---- stations ----
    station_group = folium.FeatureGroup(name="SC観測点", show=True)
    for _, row in station_df.iterrows():
        folium.CircleMarker(
            location=[
                float(row["latitude"]),
                float(row["longitude"]),
            ],
            radius=7,
            color="#000000",
            weight=1.5,
            fill=True,
            fill_color="#ffffff",
            fill_opacity=1.0,
            tooltip=str(row["station"]),
            popup=(
                f"{row['station']}<br>"
                f"緯度 {row['latitude']:.6f}<br>"
                f"経度 {row['longitude']:.6f}<br>"
                f"標高 {row['height_m']:.0f} m"
            ),
        ).add_to(station_group)
    station_group.add_to(fmap)

    # ---- requested discrete legend ----
    legend_items = [
        ("10–50", PPMM_COLORS[0]),
        ("50–100", PPMM_COLORS[1]),
        ("100–200", PPMM_COLORS[2]),
        ("200–300", PPMM_COLORS[3]),
        ("300–400", PPMM_COLORS[4]),
        ("400–500", PPMM_COLORS[5]),
        ("500–700", PPMM_COLORS[6]),
        ("700–1000", PPMM_COLORS[7]),
        ("1000–2000", PPMM_COLORS[8]),
        ("2000–3000", PPMM_COLORS[9]),
        ("3000–4000", PPMM_COLORS[10]),
        ("4000–5000", PPMM_COLORS[11]),
        ("5000–7000", PPMM_COLORS[12]),
        ("7000–", PPMM_COLORS[13]),
    ]
    legend_html = """
    <div style="
        position: fixed;
        bottom: 35px;
        right: 15px;
        z-index: 9999;
        background: rgba(255,255,255,0.94);
        padding: 10px 12px;
        border: 1px solid #777;
        border-radius: 4px;
        font-size: 12px;
        line-height: 1.15;
        box-shadow: 0 1px 5px rgba(0,0,0,0.25);
    ">
      <div style="font-weight:700; font-size:14px; margin-bottom:5px;">ppm·m</div>
    """
    for label, color in legend_items:
        legend_html += (
            '<div style="display:flex;align-items:center;margin:1px 0;">'
            f'<span style="display:inline-block;width:22px;height:13px;'
            f'background:{color};margin-right:6px;"></span>'
            f'<span>{label}</span></div>'
        )
    legend_html += "</div>"
    fmap.get_root().html.add_child(Element(legend_html))

    # マウス位置の濃度はJavaScript側で主軸最近傍から再計算する。
    axis_js = []
    for x, y, dist, speed in zip(
        axis["x_m"],
        axis["y_m"],
        axis["distance_m"],
        axis["speed_ms"],
    ):
        axis_js.append(
            {
                "x": float(x),
                "y": float(y),
                "d": float(dist),
                "v": float(speed),
            }
        )

    emission_kg_s = (
        ASSUMED_EMISSION_T_DAY
        * float(fitted_slope)
        * 1000.0
        / 86400.0
    )
    emission_mol_s = emission_kg_s / SO2_MOLAR_MASS_KG_MOL

    R = 8.314462618
    temp_k = float(temp_c) + 273.15
    pressure_pa = float(pressure_hpa) * 100.0
    mol_to_ppmm = R * temp_k / pressure_pa * 1.0e6

    map_name = fmap.get_name()
    axis_json = str(axis_js).replace("'", '"')
    diffusion_is_wind = bundle["diffusion_mode"] == "風速依存（式11）"

    mouse_js = f"""
    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        var mapObj = {map_name};
        var axisData = {axis_json};
        var craterLat = {crater_lat};
        var craterLon = {crater_lon};
        var emissionMolS = {emission_mol_s};
        var molToPpmm = {mol_to_ppmm};
        var cy = {float(bundle["cy"])};
        var n = {float(bundle["n"])};
        var windDependent = {str(diffusion_is_wind).lower()};
        var maxDistance = {float(axis["distance_m"][-1])};

        var info = L.control({{position: 'topright'}});
        info.onAdd = function(map) {{
            this._div = L.DomUtil.create('div', 'mouse-so2-info');
            this._div.style.background = 'rgba(255,255,255,0.94)';
            this._div.style.padding = '8px 10px';
            this._div.style.border = '1px solid #777';
            this._div.style.borderRadius = '4px';
            this._div.style.fontSize = '13px';
            this._div.style.minWidth = '180px';
            this._div.innerHTML = '<b>マウス位置のSO₂</b><br>地図上にカーソルを移動';
            return this._div;
        }};
        info.addTo(mapObj);

        function localXY(lat, lon) {{
            var y = (lat - craterLat) * 111320.0;
            var x = (lon - craterLon) * 111320.0 *
                    Math.cos(craterLat * Math.PI / 180.0);
            return [x, y];
        }}

        function sigmaY(distance, speed) {{
            var x = Math.max(distance, 1.0);
            var v = Math.max(speed, 0.1);
            if (windDependent) {{
                return 0.045 * (23.0 / v + 4.75) * Math.pow(x, 0.86);
            }}
            return (cy / Math.sqrt(2.0)) *
                   Math.pow(x, 1.0 - n / 2.0);
        }}

        mapObj.on('mousemove', function(e) {{
            var xy = localXY(e.latlng.lat, e.latlng.lng);
            var x = xy[0], y = xy[1];

            var best = null;
            var bestD2 = Infinity;
            for (var i = 0; i < axisData.length; i++) {{
                var dx = x - axisData[i].x;
                var dy = y - axisData[i].y;
                var d2 = dx*dx + dy*dy;
                if (d2 < bestD2) {{
                    bestD2 = d2;
                    best = axisData[i];
                }}
            }}

            var valueText = '範囲外';
            if (best && best.d >= 1.0 && best.d <= maxDistance) {{
                var cross = Math.sqrt(bestD2);
                var sy = sigmaY(best.d, best.v);
                var molm2 =
                    emissionMolS /
                    (Math.sqrt(2.0*Math.PI) * Math.max(sy,1.0) *
                     Math.max(best.v,0.1)) *
                    Math.exp(-(cross*cross)/(2.0*sy*sy));
                var ppmm = molm2 * molToPpmm;
                if (isFinite(ppmm)) {{
                    valueText = ppmm.toFixed(1) + ' ppm·m';
                }}
            }}

            info._div.innerHTML =
                '<b>マウス位置のSO₂</b><br>' +
                valueText +
                '<br><span style="font-size:11px;">' +
                e.latlng.lat.toFixed(5) + ', ' +
                e.latlng.lng.toFixed(5) + '</span>';
        }});
    }});
    </script>
    """
    fmap.get_root().html.add_child(Element(mouse_js))

    folium.LayerControl(collapsed=False).add_to(fmap)

    bounds = [
        [float(np.min(np.r_[axis_lat, station_df["latitude"].to_numpy()])),
         float(np.min(np.r_[axis_lon, station_df["longitude"].to_numpy()]))],
        [float(np.max(np.r_[axis_lat, station_df["latitude"].to_numpy()])),
         float(np.max(np.r_[axis_lon, station_df["longitude"].to_numpy()]))],
    ]
    fmap.fit_bounds(bounds, padding=(30, 30))

    return fmap


def load_default_stations():
    return pd.DataFrame(DEFAULT_STATIONS)


def station_signature(df):
    cols = ["station", "latitude", "longitude", "height_m"]
    return hashlib.sha256(
        df[cols].to_csv(index=False).encode()
    ).hexdigest()


st.set_page_config(
    page_title="阿蘇山 SO₂ 5点観測・準定常逆解析",
    page_icon="🌋",
    layout="wide",
)

st.title("阿蘇山 SO₂ 5点観測・準定常ガス拡散モデル逆解析")
st.caption(
    "SC1–SC5のSO₂カラム濃度とローカルGPV風データから、"
    "準定常ガス拡散モデルを用いてSO₂放出率を推定します。"
)

with st.expander("日本語フォント設定", expanded=False):
    st.write(
        "Matplotlib使用フォント："
        f"**{JAPANESE_FONT_NAME}**"
    )
    st.caption(
        "Streamlit Cloudでは packages.txt で導入した"
        "Noto Sans CJK JPを優先して使用します。"
    )

# ----------------------------
# Sidebar: coordinates/settings
# ----------------------------
with st.sidebar:
    st.header("解析設定")

    crater_lat = st.number_input(
        "火口緯度",
        value=DEFAULT_CRATER_LAT,
        format="%.7f",
        step=0.0001,
    )
    crater_lon = st.number_input(
        "火口経度",
        value=DEFAULT_CRATER_LON,
        format="%.7f",
        step=0.0001,
    )
    crater_alt = st.number_input(
        "火口・排出基準高度（m）",
        value=DEFAULT_CRATER_ALT_M,
        step=10.0,
        help=(
            "旧アプリの手入力排出高度初期値2000 mを踏襲。"
            "本アプリは全カラム積分を用いるため、"
            "この値は濃度式には直接影響せず解析条件として保持します。"
        ),
    )

    st.session_state["crater_lat_for_calc"] = float(crater_lat)
    st.session_state["crater_lon_for_calc"] = float(crater_lon)

    st.markdown("#### 拡散パラメータ")
    diffusion_mode = st.radio(
        "横方向拡散幅 σy",
        ["風速依存（式11）", "Sutton固定パラメータ"],
        index=0,
    )
    cy = st.number_input("cy", value=0.467, step=0.001, format="%.4f")
    cz = st.number_input("cz", value=0.07, step=0.001, format="%.4f")
    n = st.number_input("n", value=0.28, step=0.01, format="%.2f")
    if diffusion_mode == "風速依存（式11）":
        st.caption(
            "σy = 0.045 × (23 / V′ + 4.75) × x^0.86"
        )
    else:
        st.caption(
            "σy = cy / √2 × x^(1 − n/2)"
        )
    st.caption(
        "全カラム積分ではσz・排出高度は解析積分で消去されます。"
        "czは解析条件の記録用として保持します。"
    )

    axis_distance_km = st.number_input(
        "主軸計算距離（km）",
        min_value=1.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
    )
    grid_spacing_m = st.selectbox(
        "最適モデル図の格子間隔",
        options=[10, 20, 25, 50],
        index=3,
        format_func=lambda v: f"{v} m",
    )

# ----------------------------
# Station parameter file
# ----------------------------
st.subheader("1. 観測点パラメータ")
uploaded_station_csv = st.file_uploader(
    "観測点パラメータCSV（任意）",
    type=["csv"],
    help="列: station, latitude, longitude, height_m",
)

if uploaded_station_csv is not None:
    station_df = pd.read_csv(uploaded_station_csv)
else:
    station_df = load_default_stations()

required_cols = {"station", "latitude", "longitude", "height_m"}
if not required_cols.issubset(station_df.columns):
    st.error(
        "観測点CSVには station, latitude, longitude, height_m が必要です。"
    )
    st.stop()

station_df = station_df[
    ["station", "latitude", "longitude", "height_m"]
].copy()

st.dataframe(
    station_df.rename(
        columns={
            "station": "観測点",
            "latitude": "緯度",
            "longitude": "経度",
            "height_m": "高さ(m)",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

# ----------------------------
# GPV upload
# ----------------------------
st.subheader("2. GPV風データ・モデル事前確認")
uploaded_gpv = st.file_uploader(
    "u・v成分のtxtファイルをまとめてドラッグ＆ドロップ",
    type=["txt"],
    accept_multiple_files=True,
)

pairs = []
pair_errors = []
if uploaded_gpv:
    try:
        pairs, pair_errors = pair_uploaded_gpv(
            uploaded_gpv, float(crater_lat), float(crater_lon)
        )
    except Exception as error:
        st.error(f"GPV読み込みに失敗しました：{error}")

if pair_errors:
    for error in pair_errors:
        st.warning(error)

if pairs:
    gpv_rows = []
    for pair in pairs:
        gpv_rows.append(
            {
                "GPV": pair["label"],
                "配列サイズ": f"{pair['full_shape'][0]} × {pair['full_shape'][1]}",
                "緯度南端(実配列から推定)": f"{pair['implied_south']:.3f}°",
                "経度刻み": pair["lon_step_deg"],
                "緯度刻み": pair["lat_step_deg"],
            }
        )
    st.dataframe(gpv_rows, use_container_width=True, hide_index=True)

    for pair in pairs:
        if pair["shape_warning"]:
            st.warning(f"{pair['label']}: {pair['shape_warning']}")
        if (
            pair["analysis_type"] == "30分大気解析"
            and abs(pair["implied_south"] - 22.4) > 0.05
        ):
            st.info(
                f"{pair['label']} は実ファイルが {pair['full_shape'][0]} 行のため、"
                f"緯度47.6°から0.02°刻みで復元すると南端は"
                f"{pair['implied_south']:.1f}°です。"
                "アプリは実ファイルの配列サイズを優先します。"
            )

    pair_labels = [p["label"] for p in pairs]
    selected_labels = st.multiselect(
        "計算に使うGPV高度パターン（最大3）",
        options=pair_labels,
        default=pair_labels[: min(3, len(pair_labels))],
    )
else:
    selected_labels = []

st.caption(
    "各GPVパターンについて、火口風向に −12°～+12°を2°刻みで"
    "与える13パターンを計算します。GPVを3組選ぶと最大39パターンです。"
)

# ----------------------------
# Model generation / cache
# ----------------------------
model_button = st.button(
    "GPVからモデルパターンを計算・保持",
    type="primary",
    use_container_width=True,
    disabled=not bool(pairs) or not (1 <= len(selected_labels) <= 3),
)

if len(selected_labels) > 3:
    st.error("GPV高度パターンは最大3つです。")

if model_button:
    try:
        with st.spinner("準定常モデルを計算しています…"):
            patterns = build_pattern_cache(
                pairs=pairs,
                selected_labels=selected_labels,
                stations=station_df,
                diffusion_mode=diffusion_mode,
                cy=float(cy),
                cz=float(cz),
                n=float(n),
                axis_distance_km=float(axis_distance_km),
            )

        selected_hashes = [
            p["hash"] for p in pairs if p["label"] in selected_labels
        ]
        cache_signature = hashlib.sha256(
            (
                "|".join(selected_hashes)
                + f"|{crater_lat}|{crater_lon}|{crater_alt}"
                + f"|{station_signature(station_df)}"
                + f"|{diffusion_mode}|{cy}|{cz}|{n}|{axis_distance_km}"
            ).encode()
        ).hexdigest()

        st.session_state["model_bundle"] = {
            "patterns": patterns,
            "station_df": station_df.copy(),
            "signature": cache_signature,
            "crater_lat": float(crater_lat),
            "crater_lon": float(crater_lon),
            "crater_alt": float(crater_alt),
            "diffusion_mode": diffusion_mode,
            "cy": float(cy),
            "cz": float(cz),
            "n": float(n),
            "axis_distance_km": float(axis_distance_km),
            "selected_labels": list(selected_labels),
        }
        st.success(
            f"{len(patterns)}パターンのモデル計算結果を保持しました。"
            "下にモデル一覧と、風向補正0°の濃度分布を表示します。"
        )
    except Exception as error:
        st.error(f"モデル計算に失敗しました：{error}")

# ----------------------------
# Model preview before fitting
# ----------------------------
bundle = st.session_state.get("model_bundle")

if bundle is not None:
    st.markdown("### 2-1. 計算済みモデル一覧")

    model_summary_df = summarize_model_patterns(
        bundle["patterns"],
        bundle["station_df"],
    )

    st.caption(
        f"選択GPV {len(bundle['selected_labels'])}組 × 風向補正13通り = "
        f"**{len(model_summary_df)}モデル** を表示しています。"
        "各SC地点の値は仮定放出率1000 t/dayでのモデル値です。"
    )

    st.dataframe(
        model_summary_df,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "モデル計算結果CSVをダウンロード",
        data=model_summary_df.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name="quasi_steady_model_patterns_1000t_day.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("### 2-2. 風向補正0°の濃度分布")
    st.caption(
        "各気圧面について、火口風向補正0°・仮定放出率1000 t/dayの"
        "モデル濃度分布を表示します。"
        "3気圧面を選択した場合は3枚表示します。"
    )

    preview_temp_c = st.number_input(
        "事前確認図のppm·m換算用基準気温（℃）",
        min_value=-50.0,
        max_value=50.0,
        value=15.0,
        step=1.0,
        key="preview_temperature_c",
    )

    zero_patterns = [
        pattern
        for pattern in bundle["patterns"]
        if float(pattern["wind_offset_deg"]) == 0.0
    ]

    for map_index, preview_pattern in enumerate(
        zero_patterns[:3]
    ):
        st.markdown(
            f"#### {preview_pattern['gpv_label']} / 風向補正 0°"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "気圧面",
            f"{preview_pattern['pressure_hpa']} hPa",
        )
        c2.metric(
            "火口風速",
            f"{preview_pattern['crater_speed_ms']:.2f} m/s",
        )

        u0 = float(preview_pattern["crater_u_ms"])
        v0 = float(preview_pattern["crater_v_ms"])
        bearing = (
            math.degrees(math.atan2(u0, v0)) + 360.0
        ) % 360.0
        c3.metric(
            "火口風の流下方位",
            f"{bearing:.1f}°",
        )

        try:
            preview_map = build_leaflet_model_map(
                pattern=preview_pattern,
                bundle=bundle,
                station_df=bundle["station_df"],
                fitted_slope=1.0,
                pressure_hpa=float(
                    preview_pattern["pressure_hpa"]
                ),
                temp_c=float(preview_temp_c),
                axis_distance_km=float(
                    bundle["axis_distance_km"]
                ),
                map_grid_spacing_m=max(
                    20,
                    min(60, int(grid_spacing_m) * 2),
                ),
            )

            st_folium(
                preview_map,
                height=560,
                use_container_width=True,
                returned_objects=[],
                key=f"preview_model_map_{map_index}",
            )
        except Exception as error:
            st.warning(
                f"事前確認地図の作成に失敗しました：{error}"
            )

# ----------------------------
# Fitting
# ----------------------------
st.subheader("3. 放出率Fitting")
bundle = st.session_state.get("model_bundle")

if bundle is None:
    st.info(
        "先に「2. GPV風データ・モデル事前確認」で"
        "モデルパターンを計算してください。"
    )
else:
    st.success(
        f"モデルキャッシュあり：{len(bundle['patterns'])}パターン。"
        "観測値を変更してもGPVモデルは再計算せず、"
        "Fittingだけを実行します。"
    )

    st.markdown("### 3-1. 5地点の観測カラム濃度")

    unit_col, p_col, t_col = st.columns(3)

    with unit_col:
        obs_unit = st.selectbox(
            "観測値の単位",
            ["ppm·m", "mol/m²"],
            index=0,
            key="fit_obs_unit",
        )

    with p_col:
        conversion_pressure_hpa = st.number_input(
            "ppm·m換算時の基準気圧（hPa）",
            min_value=100.0,
            max_value=1100.0,
            value=900.0,
            step=5.0,
            disabled=obs_unit != "ppm·m",
            key="fit_conversion_pressure_hpa",
        )

    with t_col:
        conversion_temp_c = st.number_input(
            "ppm·m換算時の基準気温（℃）",
            min_value=-50.0,
            max_value=50.0,
            value=15.0,
            step=1.0,
            disabled=obs_unit != "ppm·m",
            key="fit_conversion_temp_c",
        )

    with st.form(
        "observation_fitting_form",
        clear_on_submit=False,
    ):
        obs_cols = st.columns(
            len(bundle["station_df"])
        )

        for i, (_, row) in enumerate(
            bundle["station_df"].iterrows()
        ):
            station_name = str(row["station"])

            with obs_cols[i]:
                st.number_input(
                    station_name,
                    min_value=0.0,
                    value=float(
                        st.session_state.get(
                            f"fit_obs_value_{station_name}",
                            0.0,
                        )
                    ),
                    step=(
                        1.0
                        if obs_unit == "ppm·m"
                        else 0.0001
                    ),
                    format=(
                        "%.3f"
                        if obs_unit == "ppm·m"
                        else "%.6f"
                    ),
                    key=f"fit_obs_value_{station_name}",
                )

        refit = st.form_submit_button(
            "現在の観測濃度でFitting",
            type="primary",
            use_container_width=True,
        )

    if refit:
        current_observations = np.asarray(
            [
                float(
                    st.session_state[
                        f"fit_obs_value_{station_name}"
                    ]
                )
                for station_name
                in bundle["station_df"]["station"]
            ],
            dtype=float,
        )

        current_signature = observation_signature(
            current_observations,
            obs_unit,
            float(conversion_pressure_hpa),
            float(conversion_temp_c),
        )

        try:
            results_df, best_index = evaluate_patterns(
                bundle["patterns"],
                current_observations,
                obs_unit,
                float(conversion_pressure_hpa),
                float(conversion_temp_c),
            )

            st.session_state["fit_result"] = {
                "results_df": results_df,
                "best_index": best_index,
                "observations": current_observations.copy(),
                "obs_unit": obs_unit,
                "pressure_hpa": float(
                    conversion_pressure_hpa
                ),
                "temp_c": float(
                    conversion_temp_c
                ),
                "observation_signature": current_signature,
            }

        except Exception as error:
            st.session_state.pop(
                "fit_result",
                None,
            )
            st.error(
                f"フィッティングに失敗しました：{error}"
            )

fit_result = st.session_state.get("fit_result")

if fit_result and bundle:
    current_visible_observations = np.asarray(
        [
            float(
                st.session_state.get(
                    f"fit_obs_value_{station_name}",
                    0.0,
                )
            )
            for station_name
            in bundle["station_df"]["station"]
        ],
        dtype=float,
    )

    current_visible_signature = observation_signature(
        current_visible_observations,
        st.session_state.get(
            "fit_obs_unit",
            fit_result["obs_unit"],
        ),
        float(
            st.session_state.get(
                "fit_conversion_pressure_hpa",
                fit_result["pressure_hpa"],
            )
        ),
        float(
            st.session_state.get(
                "fit_conversion_temp_c",
                fit_result["temp_c"],
            )
        ),
    )

    if (
        current_visible_signature
        != fit_result.get("observation_signature")
    ):
        st.warning(
            "観測値または換算条件が前回Fitting時から変更されています。"
            "旧結果は非表示にしました。"
            "「現在の観測濃度でFitting」を押してください。"
        )
        fit_result = None

if fit_result and bundle:
    results_df = fit_result["results_df"]
    best_index = int(fit_result["best_index"])
    best_pattern = bundle["patterns"][best_index]
    best_row = results_df.loc[
        results_df["pattern_index"] == best_index
    ].iloc[0]

    st.markdown("### 最適結果")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "推定SO₂放出率",
        f"{best_row['推定放出率_t_day']:.1f} t/day",
    )
    m2.metric("RMSE", f"{best_row['RMSE']:.3f} {fit_result['obs_unit']}")
    m3.metric("R²（切片0）", f"{best_row['R2_切片0']:.3f}")
    m4.metric(
        "火口風向補正",
        f"{best_pattern['wind_offset_deg']:+.0f}°",
    )

    st.write(
        f"**採用GPV:** {best_pattern['gpv_label']}  /  "
        f"**火口風速:** {best_pattern['crater_speed_ms']:.2f} m/s"
    )

    # Station comparison
    model_1000 = convert_model_unit(
        best_pattern["station_model_mol_m2"],
        fit_result["obs_unit"],
        fit_result["pressure_hpa"],
        fit_result["temp_c"],
    )
    slope = float(best_row["回帰傾き"])
    model_fitted = model_1000 * slope

    comparison = station_df.copy()
    comparison["観測値"] = fit_result["observations"]
    comparison["モデル値_1000t_day"] = model_1000
    comparison["フィット後モデル値"] = model_fitted
    comparison["残差"] = comparison["観測値"] - comparison["フィット後モデル値"]
    st.dataframe(
        comparison.rename(
            columns={
                "station": "観測点",
                "latitude": "緯度",
                "longitude": "経度",
                "height_m": "高さ(m)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    # Observed vs model figure
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(
        comparison["観測値"],
        comparison["フィット後モデル値"],
        s=55,
    )
    for _, row in comparison.iterrows():
        annotation = ax.annotate(
            row["station"],
            (row["観測値"], row["フィット後モデル値"]),
            xytext=(4, 4),
            textcoords="offset points",
        )
        if JAPANESE_FONT_NAME:
            annotation.set_fontproperties(
                font_manager.FontProperties(
                    family=JAPANESE_FONT_NAME
                )
            )
    maxv = max(
        float(np.nanmax(comparison["観測値"])),
        float(np.nanmax(comparison["フィット後モデル値"])),
        1.0,
    )
    ax.plot([0, maxv], [0, maxv], linestyle="--")
    ax.set_xlabel(f"観測値 ({fit_result['obs_unit']})")
    ax.set_ylabel(f"フィット後モデル値 ({fit_result['obs_unit']})")
    ax.set_title("5地点の観測値と最適モデル")
    ax.grid(alpha=0.3)

    # Streamlit Cloudでも日本語フォントを確実に適用。
    apply_japanese_font_to_axes(ax)

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # Best model field: Leaflet map
    st.markdown("### 最適モデルのSO₂カラム濃度分布（Leaflet地図）")
    st.caption(
        "背景地図上に最適モデルのSO₂カラム濃度を重ねています。"
        "主軸は白抜きの点列、SC観測点は白色の四角相当マーカーで表示します。"
        "地図上でマウスを動かすと、右上にその位置のモデルカラム濃度が表示されます。"
    )

    try:
        with st.spinner("Leaflet地図を作成しています…"):
            model_map = build_leaflet_model_map(
                pattern=best_pattern,
                bundle=bundle,
                station_df=station_df,
                fitted_slope=float(best_row["回帰傾き"]),
                pressure_hpa=fit_result["pressure_hpa"],
                temp_c=fit_result["temp_c"],
                axis_distance_km=bundle["axis_distance_km"],
                map_grid_spacing_m=max(
                    20,
                    min(60, int(grid_spacing_m) * 2),
                ),
            )

        st_folium(
            model_map,
            height=720,
            use_container_width=True,
            returned_objects=[],
        )

        st.caption(
            "カラーバーは添付図に合わせ、10、50、100、200、300、400、"
            "500、700、1000、2000、3000、4000、5000、7000 ppm·mを"
            "境界とする離散表示です。10 ppm·m未満は地図上に描画しません。"
        )
    except Exception as error:
        st.warning(f"Leafletモデル地図の作成に失敗しました：{error}")

    with st.expander("全パターンの回帰結果"):
        display_df = results_df.sort_values(
            ["RMSE", "R2_切片0"],
            ascending=[True, False],
        )
        st.dataframe(
            display_df.drop(columns=["pattern_index"]),
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "回帰結果CSVをダウンロード",
            data=display_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="quasi_steady_fit_results.csv",
            mime="text/csv",
        )

with st.expander("計算仕様"):
    st.markdown(
        """
- 仮定SO₂放出率は **1000 t/day** 固定です。
- ガス主軸は河波ら（2023）の準定常モデルの考え方に基づき、
  火口風速から `V0 × Δt = 100 m` となる時間刻みで逐次計算します。
- GPV風は各主軸点の周囲10 km以内を距離二乗逆数で内挿します。
- 火口起点の風向だけに −12°～+12°を2°刻みで与え、13パターンを計算します。
- GPV高度（気圧面）は最大3組なので、最大39パターンです。
- 横方向拡散幅は式(11)の風速依存型、またはSutton式を選択できます。
- カラム濃度は式(8)を地表から無限高度まで解析積分した全カラムです。
- 5地点について、1000 t/dayモデル値を説明変数、観測値を目的変数として
  切片0固定回帰を行い、`推定放出率 = 1000 × 回帰傾き` とします。
- 最適パターンはフィット後の5地点RMSEが最小となるものです。
- GPV・モデル計算はsession_stateに保持し、観測濃度は「3. 放出率Fitting」で入力します。観測濃度を変更した場合は回帰だけ再計算します。
"""
    )
