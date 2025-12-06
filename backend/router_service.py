import requests
import math
from typing import List, Tuple, Optional

OSRM_API_URL = 'https://router.project-osrm.org/route/v1/driving'
OSRM_TABLE_URL = 'https://router.project-osrm.org/table/v1/driving'

# Simple in-memory cache to avoid hitting API for same pairs
# Key: (lat1, lon1, lat2, lon2), Value: minutes
_travel_time_cache = {}

def get_real_travel_time(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[int]:
    """
    Get travel time in minutes between two points using OSRM.
    Returns None if API fails.
    """
    cache_key = (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5))
    if cache_key in _travel_time_cache:
        return _travel_time_cache[cache_key]

    try:
        # Format: lon,lat;lon,lat
        url = f"{OSRM_API_URL}/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url, timeout=5) # Increased timeout to 5s
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok' and data['routes']:
                duration_seconds = data['routes'][0]['duration']
                minutes = int(duration_seconds / 60)
                _travel_time_cache[cache_key] = minutes
                return minutes
    except Exception as e:
        print(f"OSRM API Error: {e}")
    
    return None

def get_travel_time_matrix(sources: List[Tuple[float, float]], destinations: List[Tuple[float, float]]) -> List[List[Optional[int]]]:
    """
    Fetch travel time matrix for multiple sources and destinations.
    Handles chunking to respect OSRM limits (100 coords per request).
    Returns a 2D list where result[i][j] is time from sources[i] to destinations[j].
    """
    n_src = len(sources)
    n_dest = len(destinations)
    
    # Initialize result matrix with None
    matrix = [[None for _ in range(n_dest)] for _ in range(n_src)]
    
    # Chunk size (keep it safe, e.g., 40 to allow 40+40=80 < 100)
    CHUNK_SIZE = 40
    
    for i in range(0, n_src, CHUNK_SIZE):
        src_chunk = sources[i : i + CHUNK_SIZE]
        
        for j in range(0, n_dest, CHUNK_SIZE):
            dest_chunk = destinations[j : j + CHUNK_SIZE]
            
            # Prepare coordinates for this request
            # We need to combine src and dest into one list for the URL
            # The URL format is: /lon,lat;lon,lat...?sources=0,1,2&destinations=3,4,5
            
            all_coords = []
            src_indices = []
            dest_indices = []
            
            idx = 0
            for lat, lon in src_chunk:
                all_coords.append(f"{lon},{lat}")
                src_indices.append(str(idx))
                idx += 1
                
            for lat, lon in dest_chunk:
                all_coords.append(f"{lon},{lat}")
                dest_indices.append(str(idx))
                idx += 1
                
            coord_str = ";".join(all_coords)
            src_str = ";".join(src_indices)
            dest_str = ";".join(dest_indices)
            
            url = f"{OSRM_TABLE_URL}/{coord_str}?sources={src_str}&destinations={dest_str}&annotations=duration"
            
            try:
                print(f"DEBUG: Fetching matrix chunk {i}-{i+len(src_chunk)} x {j}-{j+len(dest_chunk)}")
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data['code'] == 'Ok' and 'durations' in data:
                        durations = data['durations']
                        # Map back to main matrix
                        for r, row in enumerate(durations):
                            for c, duration in enumerate(row):
                                if duration is not None:
                                    matrix[i + r][j + c] = int(duration / 60)
                    else:
                        print(f"OSRM Table Error: {data.get('code')}")
                else:
                    print(f"OSRM HTTP Error: {response.status_code}")
                    
            except Exception as e:
                print(f"OSRM Matrix Exception: {e}")
                
    return matrix
