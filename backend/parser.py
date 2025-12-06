import pandas as pd
from models import Route, Stop
from typing import List
from datetime import time, datetime

def parse_time(t):
    if isinstance(t, time):
        return t
    if isinstance(t, str):
        try:
            return datetime.strptime(t, "%H:%M").time()
        except ValueError:
            return None
    return None

def parse_routes(file_path: str) -> List[Route]:
    try:
        with pd.ExcelFile(file_path) as xls:
            sheet_names = xls.sheet_names
            print(f"DEBUG: Sheet names found: {sheet_names}")
            
            # Find sheets
            routes_sheet = next((s for s in sheet_names if "ruta" in s.lower() and "(" not in s), sheet_names[0])
            stops_sheet = next((s for s in sheet_names if "parada" in s.lower() and "(" not in s), None)
            expedicions_sheet = next((s for s in sheet_names if "expedic" in s.lower() and "(" not in s), None)
            
            print(f"DEBUG: Using routes sheet: {routes_sheet}")
            print(f"DEBUG: Using stops sheet: {stops_sheet}")
            print(f"DEBUG: Using expedicions sheet: {expedicions_sheet}")
            
            df_routes = pd.read_excel(xls, sheet_name=routes_sheet)
            df_stops = pd.read_excel(xls, sheet_name=stops_sheet) if stops_sheet else pd.DataFrame()
            df_expedicions = pd.read_excel(xls, sheet_name=expedicions_sheet) if expedicions_sheet else pd.DataFrame()
        
        # Normalize columns
        df_routes.columns = [str(c).strip().lower() for c in df_routes.columns]
        if not df_stops.empty:
            df_stops.columns = [str(c).strip().lower() for c in df_stops.columns]
        if not df_expedicions.empty:
            df_expedicions.columns = [str(c).strip().lower() for c in df_expedicions.columns]
        
        print(f"DEBUG: Routes columns: {df_routes.columns.tolist()}")
        if not df_stops.empty:
            print(f"DEBUG: Stops columns: {df_stops.columns.tolist()}")
        if not df_expedicions.empty:
            print(f"DEBUG: Expedicions columns: {df_expedicions.columns.tolist()}")
            print(f"DEBUG: First expedition sample:")
            print(df_expedicions.head(1).to_dict('records'))
        
        routes = []
        
        # Group stops by route code
        route_code_col_stops = None
        stops_by_route = None
        if not df_stops.empty:
            route_code_col_stops = next((c for c in df_stops.columns if "código" in c and "ruta" in c), df_stops.columns[1] if len(df_stops.columns) > 1 else df_stops.columns[0])
            stops_by_route = df_stops.groupby(route_code_col_stops)
        
        # Group expedicions by route code
        expedicions_by_route = None
        if not df_expedicions.empty:
            route_code_col_exp = next((c for c in df_expedicions.columns if "código" in c and "ruta" in c), df_expedicions.columns[1] if len(df_expedicions.columns) > 1 else df_expedicions.columns[0])
            expedicions_by_route = df_expedicions.groupby(route_code_col_exp)
        
        # Find route code column
        route_code_col = next((c for c in df_routes.columns if "código" in c and "ruta" in c), df_routes.columns[1] if len(df_routes.columns) > 1 else df_routes.columns[0])
        
        for idx, row in df_routes.iterrows():
            route_id = str(row.get(route_code_col, f"Route_{idx}"))
            
            # Get stops for this route
            parsed_stops = []
            if stops_by_route is not None and route_id in stops_by_route.groups:
                route_stops_df = stops_by_route.get_group(route_id)
                
                # Sort by order
                order_col = next((c for c in route_stops_df.columns if "orde" in c), None)
                if order_col:
                    route_stops_df = route_stops_df.sort_values(order_col)
                
                for _, stop_row in route_stops_df.iterrows():
                    lat_col = next((c for c in stop_row.index if "latitud" in c.lower() or "latitude" in c.lower()), None)
                    lon_col = next((c for c in stop_row.index if "lonxitud" in c.lower() or "longitud" in c.lower() or "longitude" in c.lower()), None)
                    
                    lat = stop_row.get(lat_col, 0.0) if lat_col else 0.0
                    lon = stop_row.get(lon_col, 0.0) if lon_col else 0.0
                    
                    if isinstance(lat, str): lat = float(lat.replace(',', '.'))
                    if isinstance(lon, str): lon = float(lon.replace(',', '.'))
                    
                    name_col = next((c for c in stop_row.index if "nome" in c.lower() or "nombre" in c.lower() or "parada" in c.lower()), None)
                    stop_name = stop_row.get(name_col, 'Unknown') if name_col else 'Unknown'
                    
                    parsed_stops.append(Stop(
                        name=str(stop_name),
                        lat=float(lat) if lat else 0.0,
                        lon=float(lon) if lon else 0.0,
                        order=int(stop_row.get(order_col, 0)) if order_col else 0,
                        time_from_start=0
                    ))
            
            # Get expedition times
            route_type = "entry"
            arrival_time = None
            departure_time = None
            
            if expedicions_by_route is not None and route_id in expedicions_by_route.groups:
                exp_df = expedicions_by_route.get_group(route_id)
                
                # Try to find time columns - could be "hora" or "chegada" or "saída"
                time_cols = [c for c in exp_df.columns if "hora" in c or "chegada" in c or "saída" in c or "salida" in c or "llegada" in c]
                print(f"DEBUG: Route {route_id} has expedicions. Time-related columns: {time_cols}")
                
                if not exp_df.empty:
                    # Get first expedition
                    first_exp = exp_df.iloc[0]
                    print(f"DEBUG: First expedition for {route_id}: {first_exp.to_dict()}")
                    
                    # Try to determine entry vs exit and get times
                    for col in time_cols:
                        val = first_exp[col]
                        if pd.notna(val):
                            parsed = parse_time(val)
                            parsed = parse_time(val)
                            if parsed:
                                # Heuristic: If time is after 12:00, it's likely a departure (Exit)
                                # If time is before 12:00, it's likely an arrival (Entry)
                                if parsed.hour >= 12:
                                    departure_time = parsed
                                    route_type = "exit"
                                    # Clear arrival time if it was set by mistake
                                    arrival_time = None 
                                else:
                                    arrival_time = parsed
                                    route_type = "entry"
                                    departure_time = None
            
            if arrival_time or departure_time:
                print(f"DEBUG: Route {route_id} is {route_type.upper()}, arrival={arrival_time}, departure={departure_time}")
            else:
                # Fallback: Check route row for times
                for col in row.index:
                    col_lower = str(col).lower()
                    if "hora" in col_lower:
                        val = row[col]
                        if pd.notna(val):
                            parsed = parse_time(val)
                            if parsed:
                                if "chegada" in col_lower or "llegada" in col_lower:
                                    arrival_time = parsed
                                    route_type = "entry"
                                elif "saída" in col_lower or "salida" in col_lower:
                                    departure_time = parsed
                                    route_type = "exit"
                                    
                if arrival_time or departure_time:
                     print(f"DEBUG: Found time in routes sheet for {route_id}: {arrival_time or departure_time}")
                else:
                     print(f"DEBUG: Route {route_id} has NO TIME INFO even after checking expedicions and route sheet")
            
            # Capacity
            capacity_col = next((c for c in df_routes.columns if "praza" in c or "plaza" in c or "capacidad" in c), None)
            capacity = 0
            if capacity_col and pd.notna(row.get(capacity_col)):
                val = str(row[capacity_col])
                import re
                nums = re.findall(r'\d+', val)
                if nums:
                    capacity = int(max(nums, key=int))
            
            # School info
            school_id_col = next((c for c in df_routes.columns if "código" in c and "centro" in c), None)
            school_name_col = next((c for c in df_routes.columns if "nome" in c and "centro" in c), None)
            route_name_col = next((c for c in df_routes.columns if "nome" in c and "ruta" in c), None)
            contract_col = next((c for c in df_routes.columns if "contrato" in c), None)
            
            routes.append(Route(
                id=route_id,
                name=str(row.get(route_name_col, route_id)) if route_name_col else route_id,
                stops=parsed_stops,
                school_id=str(row.get(school_id_col, 'Unknown')) if school_id_col else 'Unknown',
                school_name=str(row.get(school_name_col, 'Unknown')) if school_name_col else 'Unknown',
                arrival_time=arrival_time,
                departure_time=departure_time,
                capacity_needed=capacity,
                contract_id=str(row.get(contract_col, 'Unknown')) if contract_col else 'Unknown',
                type=route_type
            ))
        
        print(f"DEBUG: Successfully parsed {len(routes)} routes")
        return routes

    except Exception as e:
        print(f"ERROR parsing excel: {e}")
        import traceback
        traceback.print_exc()
        return []
