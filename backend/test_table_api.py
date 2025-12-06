import requests
import random

def test_table_api(n_points):
    base_url = "https://router.project-osrm.org/table/v1/driving/"
    
    coords = []
    for _ in range(n_points):
        lat = 40.0 + random.random() * 0.1
        lon = -3.0 + random.random() * 0.1
        coords.append(f"{lon},{lat}")
        
    coord_str = ";".join(coords)
    url = f"{base_url}{coord_str}?annotations=duration"
    
    print(f"Testing with {n_points} points...")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok':
                print("Success!")
                # print(data)
            else:
                print(f"Failed with code: {data.get('code')}")
        else:
            print(f"HTTP Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_table_api(10)
    test_table_api(100)
    test_table_api(101) # Test limit
