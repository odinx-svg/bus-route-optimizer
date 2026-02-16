"""
Parser for Galician school bus route Excel files.
"""

import logging
import re
import unicodedata
from collections import Counter
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from models import Route, Stop

logger = logging.getLogger(__name__)

DataFrame = pd.DataFrame
WEEKDAYS_DEFAULT = ["L", "M", "Mc", "X", "V"]
EMPTY_TOKENS = {"", "nan", "none", "null", "nat", "<na>"}


def _normalize_text(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _clean_nullable_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if _normalize_text(text) in EMPTY_TOKENS:
        return ""
    return text


def _is_empty_value(value: Any) -> bool:
    return _clean_nullable_str(value) == ""


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if _is_empty_value(value):
            return default
        return int(float(value))
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if _is_empty_value(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_columns(df: DataFrame) -> DataFrame:
    """Normalize columns with accent-insensitive lowercase keys."""
    df.columns = [_normalize_text(c) for c in df.columns]
    return df


def find_column(columns: Union[List[str], pd.Index, Any], *patterns: str) -> Optional[str]:
    """Find a column that contains any of the given patterns."""
    normalized_patterns = [_normalize_text(p) for p in patterns]
    for col in columns:
        col_str = str(col)
        col_lower = _normalize_text(col_str)
        for pattern in normalized_patterns:
            if pattern and pattern in col_lower:
                return col_str
    return None


def parse_time_value(val: Any) -> Optional[time]:
    """
    Parse time values from common formats.
    """
    if val is None:
        return None
    if isinstance(val, str) and _normalize_text(val) in EMPTY_TOKENS:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(val, time):
        return val

    if isinstance(val, datetime):
        return val.time()

    if isinstance(val, str):
        val = val.strip()
        for fmt in ["%H:%M:%S", "%H:%M", "%H.%M"]:
            try:
                return datetime.strptime(val, fmt).time()
            except ValueError:
                continue
        return None

    if isinstance(val, (int, float)):
        val_float = float(val)
        h = int(val_float)
        frac = val_float - h
        m = int(round(frac * 60)) if frac > 0 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return time(h, m)

    return None


def parse_frecuencia_semanal(val: Any) -> List[str]:
    """
    Parse weekly frequency string into weekday codes.
    """
    if val is None:
        return WEEKDAYS_DEFAULT.copy()
    try:
        if pd.isna(val):
            return WEEKDAYS_DEFAULT.copy()
    except (TypeError, ValueError):
        pass

    s = str(val).strip()
    if _normalize_text(s) in EMPTY_TOKENS:
        return WEEKDAYS_DEFAULT.copy()
    if not s:
        return WEEKDAYS_DEFAULT.copy()

    days: List[str] = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i : i + 2] == "Mc":
            days.append("Mc")
            i += 2
        elif s[i] == "L":
            days.append("L")
            i += 1
        elif s[i] == "M":
            days.append("M")
            i += 1
        elif s[i] == "X":
            days.append("X")
            i += 1
        elif s[i] == "V":
            days.append("V")
            i += 1
        else:
            i += 1

    return days if days else WEEKDAYS_DEFAULT.copy()


def parse_duration_to_minutes(val: Any) -> int:
    """
    Parse duration values to minutes.
    """
    if val is None:
        return 0
    try:
        if pd.isna(val):
            return 0
    except (TypeError, ValueError):
        pass

    if isinstance(val, pd.Timedelta):
        seconds = float(val.total_seconds())
        return max(0, int(round(seconds / 60.0)))

    if isinstance(val, timedelta):
        seconds = float(val.total_seconds())
        return max(0, int(round(seconds / 60.0)))

    if isinstance(val, (int, float)):
        return int(val)

    if isinstance(val, time):
        return val.hour * 60 + val.minute

    if isinstance(val, str):
        if _normalize_text(val) in EMPTY_TOKENS:
            return 0
        # Handles "00:02:30.976000" and similar timedeltas with fraction.
        td = pd.to_timedelta(val, errors="coerce")
        try:
            if not pd.isna(td):
                return max(0, int(round(float(td.total_seconds()) / 60.0)))
        except Exception:
            pass
        t = parse_time_value(val)
        if t:
            return t.hour * 60 + t.minute

    return 0


def parse_vehicle_capacity_range(val: Any) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Parse vehicle seat range from strings like:
    - "26-38"
    - "39 - 55"
    - "26/38"
    - "35" (single value -> min=max)
    """
    if val is None:
        return None, None, None
    try:
        if pd.isna(val):
            return None, None, None
    except (TypeError, ValueError):
        pass

    text = str(val).strip()
    if _normalize_text(text) in EMPTY_TOKENS:
        return None, None, None

    nums = [int(x) for x in re.findall(r"\d+", text)]
    if not nums:
        return None, None, None

    text_norm = _normalize_text(text)
    if ">" in text or "maior" in text_norm or "superior" in text_norm:
        low = max(1, nums[0] + 1)
        # Open upper bound: keep textual range but avoid artificial caps (e.g. 120).
        return low, None, f">{nums[0]}"

    if "<" in text or "menor" in text_norm or "inferior" in text_norm:
        high = max(1, nums[0])
        return 1, high, f"<={high}"

    if len(nums) == 1:
        v = max(1, nums[0])
        return v, v, str(v)

    low = max(1, min(nums[0], nums[1]))
    high = max(low, max(nums[0], nums[1]))
    return low, high, f"{low}-{high}"


def load_sheet(xls: pd.ExcelFile, pattern: str, with_suffix: Optional[str] = None) -> DataFrame:
    """
    Load a single sheet by name pattern.
    """
    normalized_pattern = _normalize_text(pattern)
    normalized_suffix = _normalize_text(with_suffix) if with_suffix else None
    for sheet_name in xls.sheet_names:
        sheet_str = str(sheet_name)
        name_lower = _normalize_text(sheet_str)
        if normalized_pattern in name_lower:
            if normalized_suffix:
                if normalized_suffix in name_lower:
                    df = pd.read_excel(xls, sheet_name=sheet_str)
                    return normalize_columns(df)
            elif "(" not in sheet_str:
                df = pd.read_excel(xls, sheet_name=sheet_str)
                return normalize_columns(df)
    return pd.DataFrame()


def load_sheets(
    xls: pd.ExcelFile,
    pattern: str,
    with_suffix: Optional[str] = None,
    include_parenthesized: bool = True,
) -> List[Tuple[str, DataFrame]]:
    """
    Load all sheets matching a pattern.
    """
    normalized_pattern = _normalize_text(pattern)
    normalized_suffix = _normalize_text(with_suffix) if with_suffix else None
    result: List[Tuple[str, DataFrame]] = []

    for sheet_name in xls.sheet_names:
        sheet_str = str(sheet_name)
        name_lower = _normalize_text(sheet_str)
        if normalized_pattern not in name_lower:
            continue
        if normalized_suffix and normalized_suffix not in name_lower:
            continue
        if not include_parenthesized and "(" in sheet_str and not normalized_suffix:
            continue
        df = pd.read_excel(xls, sheet_name=sheet_str)
        result.append((sheet_str, normalize_columns(df)))
    return result


def _empty_parse_report(file_path: Optional[str] = None) -> Dict[str, Any]:
    return {
        "file_name": file_path or "",
        "sheets_detected": [],
        "rows_total": 0,
        "rows_dropped_invalid": 0,
        "invalid_reasons": [],
        "warnings": [],
        "unknown_fields_count": 0,
    }


def _get_stop_name_column(df_stops: DataFrame) -> Optional[str]:
    for col in df_stops.columns:
        col_lower = _normalize_text(col)
        if ("nome" in col_lower or "nombre" in col_lower) and "parada" in col_lower and "codigo" not in col_lower:
            return col
    return find_column(df_stops.columns, "nome parada", "nombre parada")


def _append_report_warning(report: Dict[str, Any], warning: str) -> None:
    warnings = report.get("warnings") or []
    warnings.append(warning)
    report["warnings"] = warnings


def _score_stops_sheet(df_stops: DataFrame) -> Tuple[int, int, int, int, int]:
    """Quality score to choose the best stops sheet when duplicates exist."""
    if df_stops is None or df_stops.empty:
        return (0, 0, 0, 0, 0)

    route_code_col = find_column(df_stops.columns, "codigo ruta")
    order_col = find_column(df_stops.columns, "orde parada", "orden", "orde")
    time_col = find_column(df_stops.columns, "tempo a orixe", "tiempo a origen", "tempo")
    passengers_col = find_column(df_stops.columns, "usuarios totais", "usuarios", "pasajeros", "viajeros")

    route_non_empty = 0
    order_non_empty = 0
    time_non_empty = 0
    passengers_non_empty = 0

    for _, row in df_stops.iterrows():
        if route_code_col and not _is_empty_value(row.get(route_code_col)):
            route_non_empty += 1
        if order_col and not _is_empty_value(row.get(order_col)):
            order_non_empty += 1
        if time_col and parse_duration_to_minutes(row.get(time_col)) > 0:
            time_non_empty += 1
        if passengers_col and not _is_empty_value(row.get(passengers_col)):
            passengers_non_empty += 1

    return (route_non_empty, order_non_empty, time_non_empty, passengers_non_empty, int(len(df_stops)))


def _select_stops_sheet(df_paradas: DataFrame, df_paradas_2: DataFrame) -> DataFrame:
    """Pick the highest-quality stops sheet between base and '(2)' variant."""
    if df_paradas.empty and df_paradas_2.empty:
        return pd.DataFrame()
    if df_paradas.empty:
        return df_paradas_2
    if df_paradas_2.empty:
        return df_paradas

    base_score = _score_stops_sheet(df_paradas)
    alt_score = _score_stops_sheet(df_paradas_2)
    return df_paradas_2 if alt_score > base_score else df_paradas


def _clone_and_mark_school_stop(stops: List[Stop], route_type: str) -> List[Stop]:
    """Clone stops per route instance and mark school stop by route direction."""
    cloned: List[Stop] = []
    for s in stops:
        if hasattr(s, "model_copy"):
            cloned.append(s.model_copy(update={"is_school": False}))
        else:
            cloned.append(s.copy(update={"is_school": False}))

    if not cloned:
        return cloned

    if route_type == "exit":
        school_idx = min(range(len(cloned)), key=lambda i: cloned[i].order)
    else:
        school_idx = max(range(len(cloned)), key=lambda i: cloned[i].order)

    stop = cloned[school_idx]
    if hasattr(stop, "model_copy"):
        cloned[school_idx] = stop.model_copy(update={"is_school": True})
    else:
        cloned[school_idx] = stop.copy(update={"is_school": True})
    return cloned


def _estimate_route_capacity(stops: List[Stop]) -> int:
    """Estimate required seats from stops using peak on-board students."""
    if not stops:
        return 0
    positive_values = [max(0, int(s.passengers or 0)) for s in stops if int(s.passengers or 0) > 0]
    if not positive_values:
        return 0
    return int(max(positive_values))


def parse_routes_with_report(file_path: str) -> Tuple[List[Route], Dict[str, Any]]:
    """
    Parse an Excel file and return routes plus parse-quality report.
    """
    report = _empty_parse_report(file_path=file_path)
    invalid_reason_counter: Counter[str] = Counter()
    dropped_rows_counter = 0

    try:
        with pd.ExcelFile(file_path) as xls:
            logger.info("Parsing file: %s", file_path)
            logger.debug("Sheets found: %s", xls.sheet_names)
            report["sheets_detected"] = [str(s) for s in xls.sheet_names]

            df_rutas = load_sheet(xls, "ruta")
            df_rutas_2 = load_sheet(xls, "ruta", with_suffix="(2)")
            df_paradas = load_sheet(xls, "parada")
            df_paradas_2 = load_sheet(xls, "parada", with_suffix="(2)")

            expeditions_by_sheet = load_sheets(xls, "expedic", include_parenthesized=True)
            if not expeditions_by_sheet:
                expeditions_by_sheet = load_sheets(xls, "expedi", include_parenthesized=True)

            report["rows_total"] = int(
                len(df_rutas)
                + len(df_rutas_2)
                + len(df_paradas)
                + len(df_paradas_2)
                + sum(len(df) for _, df in expeditions_by_sheet)
            )

        # STEP 1: Stops by route
        stops_by_route: Dict[str, List[Stop]] = {}
        df_stops = _select_stops_sheet(df_paradas, df_paradas_2)
        if df_stops.empty:
            logger.warning("No stops sheet found")
            _append_report_warning(report, "No stops sheet found")
            df_stops = df_paradas

        if not df_stops.empty:
            route_code_col = find_column(df_stops.columns, "codigo ruta")
            lat_col = find_column(df_stops.columns, "latitude", "latitud")
            lon_col = find_column(df_stops.columns, "lonxitude", "longitud", "longitude")
            name_col = _get_stop_name_column(df_stops)
            order_col = find_column(df_stops.columns, "orde parada", "orden", "orde")
            time_col = find_column(df_stops.columns, "tempo a orixe", "tiempo a origen", "tempo")
            passengers_col = find_column(df_stops.columns, "usuarios totais", "usuarios", "pasajeros", "viajeros")

            for _, row in df_stops.iterrows():
                route_code = _clean_nullable_str(row.get(route_code_col, "")) if route_code_col else ""
                if not route_code:
                    continue

                stop = Stop(
                    name=(_clean_nullable_str(row.get(name_col, "Unknown")) if name_col else "Unknown") or "Unknown",
                    lat=_as_float(row.get(lat_col, 0), 0.0) if lat_col else 0.0,
                    lon=_as_float(row.get(lon_col, 0), 0.0) if lon_col else 0.0,
                    order=_as_int(row.get(order_col, 0), 0) if order_col else 0,
                    time_from_start=parse_duration_to_minutes(row.get(time_col)) if time_col else 0,
                    passengers=_as_int(row.get(passengers_col, 0), 0) if passengers_col else 0,
                )

                if route_code not in stops_by_route:
                    stops_by_route[route_code] = []
                stops_by_route[route_code].append(stop)

            for route_code in stops_by_route:
                stops_by_route[route_code].sort(key=lambda s: s.order)

        # STEP 2: Route metadata
        route_info: Dict[str, Dict[str, Any]] = {}

        if not df_rutas.empty:
            route_code_col = find_column(df_rutas.columns, "codigo ruta")
            school_code_col = find_column(df_rutas.columns, "codigo centro")
            school_name_col = find_column(df_rutas.columns, "nome centro", "nombre centro")
            route_name_col = find_column(df_rutas.columns, "nome ruta", "nombre ruta")
            contract_col = find_column(df_rutas.columns, "contrato")
            vehicle_capacity_col = find_column(
                df_rutas.columns,
                "prazas vehiculo",
                "plazas vehiculo",
                "capacidade vehiculo",
                "capacidad vehiculo",
                "prazas observatorio",
                "plazas observatorio",
            )

            for _, row in df_rutas.iterrows():
                route_code = _clean_nullable_str(row.get(route_code_col, "")) if route_code_col else ""
                if not route_code:
                    continue
                cap_min, cap_max, cap_range = parse_vehicle_capacity_range(
                    row.get(vehicle_capacity_col) if vehicle_capacity_col else None
                )

                route_info[route_code] = {
                    "school_id": _clean_nullable_str(row.get(school_code_col, "Unknown")) if school_code_col else "Unknown",
                    "school_name": _clean_nullable_str(row.get(school_name_col, "Unknown")) if school_name_col else "Unknown",
                    "route_name": _clean_nullable_str(row.get(route_name_col, route_code)) if route_name_col else route_code,
                    "contract_id": _clean_nullable_str(row.get(contract_col, "Unknown")) if contract_col else "Unknown",
                    "vehicle_capacity_min": cap_min,
                    "vehicle_capacity_max": cap_max,
                    "vehicle_capacity_range": cap_range,
                }

        if not df_rutas_2.empty:
            route_code_col = find_column(df_rutas_2.columns, "codigo ruta")
            entry_time_col = find_column(df_rutas_2.columns, "horario entrada", "hora entrada")
            for _, row in df_rutas_2.iterrows():
                route_code = _clean_nullable_str(row.get(route_code_col, "")) if route_code_col else ""
                if not route_code:
                    continue
                info = route_info.setdefault(route_code, {})
                entry_time = parse_time_value(row.get(entry_time_col)) if entry_time_col else None
                if entry_time:
                    info["school_entry_time"] = entry_time

        # STEP 3: Build routes from every expedition sheet
        routes: List[Route] = []
        if not expeditions_by_sheet:
            _append_report_warning(report, "No expeditions sheet found")

        for sheet_name, df_expedicions in expeditions_by_sheet:
            if df_expedicions.empty:
                continue

            route_code_col = find_column(df_expedicions.columns, "codigo ruta")
            exp_code_col = find_column(df_expedicions.columns, "codigo expedicion")
            sentido_col = find_column(df_expedicions.columns, "sentido")
            hora_salida_col = find_column(df_expedicions.columns, "hora salida", "hora saida")
            hora_chegada_col = find_column(df_expedicions.columns, "hora chegada", "hora llegada")
            school_code_col = find_column(df_expedicions.columns, "codigo centro")
            school_name_col = find_column(df_expedicions.columns, "nome centro", "nombre centro")
            route_name_col = find_column(df_expedicions.columns, "nome ruta", "nombre ruta")
            contract_col = find_column(df_expedicions.columns, "contrato")
            frecuencia_col = find_column(df_expedicions.columns, "frecuencia semanal", "frecuencia")
            vehicle_capacity_col = find_column(
                df_expedicions.columns,
                "prazas vehiculo",
                "plazas vehiculo",
                "capacidade vehiculo",
                "capacidad vehiculo",
                "prazas observatorio",
                "plazas observatorio",
            )

            logger.debug(
                "Expedition sheet %s columns route=%s sentido=%s salida=%s chegada=%s",
                sheet_name,
                route_code_col,
                sentido_col,
                hora_salida_col,
                hora_chegada_col,
            )

            for _, row in df_expedicions.iterrows():
                route_code = _clean_nullable_str(row.get(route_code_col, "")) if route_code_col else ""
                exp_code = _clean_nullable_str(row.get(exp_code_col, "")) if exp_code_col else ""
                sentido_raw = _clean_nullable_str(row.get(sentido_col, "")) if sentido_col else ""
                sentido_norm = _normalize_text(sentido_raw)
                raw_hora_salida = row.get(hora_salida_col) if hora_salida_col else None
                raw_hora_chegada = row.get(hora_chegada_col) if hora_chegada_col else None
                raw_school_code = row.get(school_code_col) if school_code_col else None
                raw_school_name = row.get(school_name_col) if school_name_col else None
                raw_route_name = row.get(route_name_col) if route_name_col else None
                raw_contract = row.get(contract_col) if contract_col else None

                row_is_effectively_empty = all(
                    _is_empty_value(v)
                    for v in [
                        route_code,
                        exp_code,
                        sentido_raw,
                        raw_hora_salida,
                        raw_hora_chegada,
                        raw_school_code,
                        raw_school_name,
                        raw_route_name,
                        raw_contract,
                    ]
                )

                if not route_code:
                    if row_is_effectively_empty:
                        continue
                    invalid_reason_counter["missing_route_code"] += 1
                    dropped_rows_counter += 1
                    continue
                if not sentido_norm:
                    invalid_reason_counter["missing_sentido"] += 1
                    dropped_rows_counter += 1
                    continue

                is_exit = ("saida" in sentido_norm) or ("salida" in sentido_norm)
                if not is_exit and "entrada" not in sentido_norm:
                    invalid_reason_counter["invalid_sentido"] += 1
                    dropped_rows_counter += 1
                    continue

                hora_salida = parse_time_value(raw_hora_salida) if hora_salida_col else None
                hora_chegada = parse_time_value(raw_hora_chegada) if hora_chegada_col else None

                if is_exit and hora_salida is None:
                    invalid_reason_counter["missing_exit_departure_time"] += 1
                    dropped_rows_counter += 1
                    continue
                if (not is_exit) and hora_chegada is None:
                    invalid_reason_counter["missing_entry_arrival_time"] += 1
                    dropped_rows_counter += 1
                    continue

                if not exp_code:
                    exp_code = route_code

                info = route_info.setdefault(route_code, {})
                if not info.get("school_id"):
                    info["school_id"] = _clean_nullable_str(row.get(school_code_col, "")) if school_code_col else ""
                if not info.get("school_name"):
                    info["school_name"] = _clean_nullable_str(row.get(school_name_col, "")) if school_name_col else ""
                if not info.get("route_name"):
                    info["route_name"] = _clean_nullable_str(row.get(route_name_col, "")) if route_name_col else route_code
                if not info.get("contract_id"):
                    info["contract_id"] = _clean_nullable_str(row.get(contract_col, "")) if contract_col else ""
                if not info.get("vehicle_capacity_range"):
                    cap_min, cap_max, cap_range = parse_vehicle_capacity_range(
                        row.get(vehicle_capacity_col) if vehicle_capacity_col else None
                    )
                    if cap_range:
                        info["vehicle_capacity_min"] = cap_min
                        info["vehicle_capacity_max"] = cap_max
                        info["vehicle_capacity_range"] = cap_range

                base_stops = stops_by_route.get(route_code, [])

                if is_exit:
                    route_type = "exit"
                    departure_time = hora_salida
                    arrival_time = None
                else:
                    route_type = "entry"
                    arrival_time = hora_chegada or info.get("school_entry_time")
                    departure_time = None

                stops = _clone_and_mark_school_stop(base_stops, route_type)
                estimated_capacity = _estimate_route_capacity(stops)

                route_days = parse_frecuencia_semanal(row.get(frecuencia_col) if frecuencia_col else None)

                school_id = info.get("school_id") or "Unknown"
                school_name = info.get("school_name") or "Unknown"
                route_name = info.get("route_name") or route_code
                contract_id = info.get("contract_id") or "Unknown"
                cap_min, cap_max, cap_range = parse_vehicle_capacity_range(
                    row.get(vehicle_capacity_col) if vehicle_capacity_col else None
                )
                if not cap_range:
                    cap_min = info.get("vehicle_capacity_min")
                    cap_max = info.get("vehicle_capacity_max")
                    cap_range = info.get("vehicle_capacity_range")

                if school_id == "Unknown" or school_name == "Unknown" or contract_id == "Unknown":
                    report["unknown_fields_count"] = int(report["unknown_fields_count"] or 0) + 1

                route = Route(
                    id=f"{route_code}_{exp_code}_{route_type[0].upper()}",
                    name=route_name,
                    stops=stops,
                    school_id=school_id,
                    school_name=school_name,
                    arrival_time=arrival_time,
                    departure_time=departure_time,
                    capacity_needed=estimated_capacity if estimated_capacity > 0 else 50,
                    vehicle_capacity_min=cap_min,
                    vehicle_capacity_max=cap_max,
                    vehicle_capacity_range=cap_range,
                    contract_id=contract_id,
                    type=route_type,
                    days=route_days,
                )
                routes.append(route)

        if not routes and not df_rutas.empty:
            _append_report_warning(report, "No expeditions found; fallback to rutas sheet")
            for route_code, info in route_info.items():
                base_stops = stops_by_route.get(route_code, [])
                stops = _clone_and_mark_school_stop(base_stops, "entry")
                estimated_capacity = _estimate_route_capacity(stops)
                routes.append(
                    Route(
                        id=route_code,
                        name=info.get("route_name", route_code) or route_code,
                        stops=stops,
                        school_id=info.get("school_id", "Unknown") or "Unknown",
                        school_name=info.get("school_name", "Unknown") or "Unknown",
                        arrival_time=info.get("school_entry_time"),
                        departure_time=None,
                        capacity_needed=estimated_capacity if estimated_capacity > 0 else 50,
                        vehicle_capacity_min=info.get("vehicle_capacity_min"),
                        vehicle_capacity_max=info.get("vehicle_capacity_max"),
                        vehicle_capacity_range=info.get("vehicle_capacity_range"),
                        contract_id=info.get("contract_id", "Unknown") or "Unknown",
                        type="entry",
                        days=WEEKDAYS_DEFAULT.copy(),
                    )
                )

        # Deduplicate route ids: preserve every valid service by renaming duplicates.
        seen_ids: set[str] = set()
        seen_service_signatures: set[Tuple[Any, ...]] = set()
        duplicate_id_counter: Counter[str] = Counter()
        duplicate_service_collapsed = 0
        unique_routes: List[Route] = []
        for route in routes:
            service_signature: Tuple[Any, ...] = (
                route.id,
                route.type,
                route.school_id,
                route.school_name,
                route.contract_id,
                route.arrival_time.isoformat() if route.arrival_time else "",
                route.departure_time.isoformat() if route.departure_time else "",
                tuple(route.days or []),
                int(getattr(route, "vehicle_capacity_min", 0) or 0),
                int(getattr(route, "vehicle_capacity_max", 0) or 0),
                tuple((s.name, s.order, round(float(s.lat), 6), round(float(s.lon), 6)) for s in route.stops[:3]),
                tuple((s.name, s.order, round(float(s.lat), 6), round(float(s.lon), 6)) for s in route.stops[-3:]),
            )
            if service_signature in seen_service_signatures:
                duplicate_service_collapsed += 1
                continue
            seen_service_signatures.add(service_signature)

            if route.id in seen_ids:
                duplicate_id_counter[route.id] += 1
                suffix = duplicate_id_counter[route.id]
                new_id = f"{route.id}__dup{suffix:03d}"
                while new_id in seen_ids:
                    suffix += 1
                    new_id = f"{route.id}__dup{suffix:03d}"
                if hasattr(route, "model_copy"):
                    route = route.model_copy(update={"id": new_id})
                else:
                    route = route.copy(update={"id": new_id})
                invalid_reason_counter["duplicate_route_id_renamed"] += 1
            seen_ids.add(route.id)
            unique_routes.append(route)
        routes = unique_routes

        if duplicate_service_collapsed > 0:
            invalid_reason_counter["duplicate_service_collapsed"] += int(duplicate_service_collapsed)

        report["rows_dropped_invalid"] = int(dropped_rows_counter)
        report["routes_generated"] = int(len(routes))
        report["invalid_reasons"] = [
            {"reason": reason, "count": int(count)}
            for reason, count in sorted(invalid_reason_counter.items())
        ]

        routes_without_time = [r for r in routes if not r.arrival_time and not r.departure_time]
        if routes_without_time:
            _append_report_warning(
                report,
                f"{len(routes_without_time)} routes have no time info: {[r.id for r in routes_without_time[:5]]}",
            )

        entry_count = sum(1 for r in routes if r.type == "entry")
        exit_count = sum(1 for r in routes if r.type == "exit")
        logger.info("Parsed %s unique routes: %s entry, %s exit", len(routes), entry_count, exit_count)

        return routes, report

    except Exception as e:
        logger.error("Error parsing Excel file: %s", e)
        import traceback

        traceback.print_exc()
        _append_report_warning(report, f"parser_error: {e}")
        return [], report


def parse_routes(file_path: str) -> List[Route]:
    """
    Backward-compatible parser returning only routes.
    """
    routes, _ = parse_routes_with_report(file_path)
    return routes


def aggregate_parse_reports(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate parse reports from multiple files.

    Returns a normalized ParseReport payload for `/upload/analyze`.
    """
    invalid_counter: Counter[str] = Counter()
    warnings: List[str] = []
    sheets_detected: List[str] = []
    file_summaries: List[Dict[str, Any]] = []

    rows_total = 0
    rows_dropped_invalid = 0
    unknown_fields_count = 0

    for report in reports:
        file_name = str(report.get("file_name", "") or "")
        file_rows_total = int(report.get("rows_total", 0) or 0)
        file_rows_dropped = int(report.get("rows_dropped_invalid", 0) or 0)
        file_unknown = int(report.get("unknown_fields_count", 0) or 0)

        rows_total += file_rows_total
        rows_dropped_invalid += file_rows_dropped
        unknown_fields_count += file_unknown

        for reason_item in report.get("invalid_reasons", []) or []:
            reason = str(reason_item.get("reason", "") or "").strip()
            if not reason:
                continue
            invalid_counter[reason] += int(reason_item.get("count", 0) or 0)

        for warning in report.get("warnings", []) or []:
            warning_text = str(warning or "").strip()
            if warning_text:
                warnings.append(warning_text)

        for sheet in report.get("sheets_detected", []) or []:
            sheet_name = str(sheet or "").strip()
            if sheet_name:
                sheets_detected.append(sheet_name)

        file_summaries.append(
            {
                "file_name": file_name,
                "rows_total": file_rows_total,
                "rows_dropped_invalid": file_rows_dropped,
                "unknown_fields_count": file_unknown,
                "invalid_reasons": report.get("invalid_reasons", []) or [],
                "warnings": report.get("warnings", []) or [],
                "sheets_detected": report.get("sheets_detected", []) or [],
            }
        )

    return {
        "files_processed": len(reports),
        "sheets_detected": sorted(set(sheets_detected)),
        "rows_total": rows_total,
        "rows_dropped_invalid": rows_dropped_invalid,
        "invalid_reasons": [
            {"reason": reason, "count": int(count)}
            for reason, count in sorted(invalid_counter.items())
        ],
        "warnings": warnings,
        "unknown_fields_count": unknown_fields_count,
        "files": file_summaries,
    }
