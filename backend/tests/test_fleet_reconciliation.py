from services.fleet_reconciliation import _build_company_mix


def test_build_company_mix_keeps_all_scope_companies_visible():
    rows = [
        {
            "bus_id": "B001",
            "suggestions": [
                {
                    "company_id": "estevez",
                    "company_name": "ESTEVEZ",
                    "vehicle_id": "veh-e-1",
                    "vehicle_code": "E001",
                },
                {
                    "company_id": "aav",
                    "company_name": "AAV & COND'BUS",
                    "vehicle_id": "veh-a-1",
                    "vehicle_code": "A001",
                },
            ],
        }
    ]
    company_capacity_summary = [
        {
            "company_id": "aav",
            "company_name": "AAV & COND'BUS",
            "available_vehicle_count": 21,
            "vehicle_codes": ["A001", "A002"],
        },
        {
            "company_id": "autna",
            "company_name": "AUTNA",
            "available_vehicle_count": 8,
            "vehicle_codes": ["U001"],
        },
        {
            "company_id": "estevez",
            "company_name": "ESTEVEZ",
            "available_vehicle_count": 18,
            "vehicle_codes": ["E001", "E002"],
        },
        {
            "company_id": "melytour",
            "company_name": "MELYTOUR",
            "available_vehicle_count": 28,
            "vehicle_codes": ["M001", "M002"],
        },
    ]

    company_mix = _build_company_mix(rows, company_capacity_summary)

    assert company_mix["companies_with_options"] == 4
    returned_names = {row["company_name"] for row in company_mix["recommended_companies"]}
    assert returned_names == {"AAV & COND'BUS", "AUTNA", "ESTEVEZ", "MELYTOUR"}

    melytour = next(row for row in company_mix["recommended_companies"] if row["company_name"] == "MELYTOUR")
    assert melytour["recommended_count"] == 0
    assert melytour["available_vehicle_count"] == 28
    assert melytour["vehicle_codes"] == ["M001", "M002"]
