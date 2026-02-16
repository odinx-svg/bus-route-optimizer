"""
Generate a sample Excel file for parser testing.
Run this script to create sample_excel.xlsx
"""
import pandas as pd
import os

# Create data for I. Rutas sheet
rutas_data = {
    'Código Ruta': ['R001', 'R002', 'R003', 'R004', 'R005'],
    'Nome Ruta': ['Ruta 001 - Zona Norte', 'Ruta 002 - Zona Sur', 'Ruta 003 - Zona Este', 
                  'Ruta 004 - Zona Oeste', 'Ruta 005 - Zona Central'],
    'Código Centro': ['SCH001', 'SCH002', 'SCH001', 'SCH002', 'SCH001'],
    'Nome Centro': ['Colexio Principal', 'Colexio Secundario', 'Colexio Principal',
                    'Colexio Secundario', 'Colexio Principal'],
    'Contrato': ['UE3617', 'UE3618', 'UE3617', 'UE3618', 'UE3617'],
    'Distancia Aprox. (km)': [12.5, 8.3, 15.2, 10.1, 6.7]
}

# Create data for I. Rutas (2) sheet
rutas_2_data = {
    'Código Ruta': ['R001', 'R002', 'R003', 'R004', 'R005'],
    'Horario Entrada Centro': ['09:00', '08:45', '09:15', '08:30', '09:30'],
    'Observacións': ['', '', '', '', '']
}

# Create data for II. Paradas sheet
paradas_data = {
    'Código Ruta': ['R001', 'R001', 'R001', 'R002', 'R002', 'R003', 'R003', 'R004', 'R004', 'R005', 'R005'],
    'Nome Parada': ['Parada A - Rúa Principal', 'Parada B - Praza Maior', 'Colexio Principal',
                    'Parada C - Avenida Sur', 'Colexio Secundario',
                    'Parada D - Rúa Este', 'Colexio Principal',
                    'Parada E - Zona Oeste', 'Colexio Secundario',
                    'Parada F - Centro', 'Colexio Principal'],
    'Latitude': [42.2406, 42.2416, 42.2500, 42.2350, 42.2450, 42.2300, 42.2500, 42.2380, 42.2450, 42.2550, 42.2500],
    'Lonxitude': [-8.7207, -8.7217, -8.7300, -8.7150, -8.7250, -8.7100, -8.7300, -8.7180, -8.7250, -8.7350, -8.7300],
    'Orde Parada': [1, 2, 3, 1, 2, 1, 2, 1, 2, 1, 2],
    'Tempo a Orixe (min)': [0, 8, 25, 0, 22, 0, 18, 0, 15, 0, 12],
    'Usuarios Totais': [5, 8, 0, 6, 0, 10, 0, 7, 0, 4, 0]
}

# Create data for III. Expedicions sheet
expedicions_data = {
    'Código Ruta': ['R001', 'R001', 'R002', 'R003', 'R004', 'R005'],
    'Código Expedición': ['E001', 'E002', 'E003', 'E004', 'E005', 'E006'],
    'Sentido': ['Entrada', 'Saída', 'Entrada', 'Entrada', 'Saída', 'Entrada'],
    'Hora Saída': ['', '14:30', '', '', '18:25', ''],
    'Hora Chegada': ['09:00', '', '08:45', '16:30', '', '09:30'],
    'Código Centro': ['SCH001', 'SCH001', 'SCH002', 'SCH001', 'SCH002', 'SCH001'],
    'Frecuencia Semanal': ['LMMcXV', 'LMMcXV', 'LMXV', 'LMMcXV', 'LMMcXV', 'McXV']
}

def create_sample_excel():
    """Create the sample Excel file."""
    output_path = os.path.join(os.path.dirname(__file__), 'sample_excel.xlsx')
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(rutas_data).to_excel(writer, sheet_name='I. Rutas', index=False)
        pd.DataFrame(rutas_2_data).to_excel(writer, sheet_name='I. Rutas (2)', index=False)
        pd.DataFrame(paradas_data).to_excel(writer, sheet_name='II. Paradas', index=False)
        pd.DataFrame(expedicions_data).to_excel(writer, sheet_name='III. Expedicions', index=False)
    
    print(f"Sample Excel file created: {output_path}")
    return output_path

if __name__ == '__main__':
    create_sample_excel()
