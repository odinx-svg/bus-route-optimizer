import pandas as pd
import random

def create_mock_excel(filename="mock_routes.xlsx"):
    # Create Routes DataFrame
    routes_data = {
        "Contrato": ["C1"] * 5,
        "Código ruta": [f"R{i}" for i in range(1, 6)],
        "Nome ruta": [f"Ruta {i}" for i in range(1, 6)],
        "Hora chegada centros": ["09:00", "09:30", "08:30", "09:00", "08:00"],
        "Hora saida": [None] * 5,
        "Prazas vehiculo": ["55", "20", "55", "30", "55"],
        "Código centros": ["S1", "S1", "S2", "S2", "S3"],
        "Nome centros": ["School A", "School A", "School B", "School B", "School C"]
    }
    df_routes = pd.DataFrame(routes_data)
    
    # Create Stops DataFrame
    stops_data = {
        "Código ruta": [],
        "Nome parada": [],
        "Latitude": [],
        "Longitude": [],
        "Orde parada": []
    }
    
    for i in range(1, 6):
        route_id = f"R{i}"
        for j in range(1, 5): # 4 stops per route
            stops_data["Código ruta"].append(route_id)
            stops_data["Nome parada"].append(f"Stop {j} of {route_id}")
            stops_data["Latitude"].append(40.0 + random.random() * 0.1)
            stops_data["Longitude"].append(-3.0 + random.random() * 0.1)
            stops_data["Orde parada"].append(j)
            
    df_stops = pd.DataFrame(stops_data)
    
    with pd.ExcelWriter(filename) as writer:
        df_routes.to_excel(writer, sheet_name="Rutas", index=False)
        df_stops.to_excel(writer, sheet_name="Paradas", index=False)
    
    print(f"Created {filename}")

if __name__ == "__main__":
    create_mock_excel()
