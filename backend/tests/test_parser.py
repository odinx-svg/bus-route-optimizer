"""
Tests for Excel parser module.
"""
import pytest
from datetime import time
from typing import List
import os
import tempfile

from models import Route, Stop
from parser import (
    parse_routes,
    parse_time_value,
    parse_frecuencia_semanal,
    parse_duration_to_minutes,
    normalize_columns,
    find_column
)


# ============================================================
# TIME PARSING TESTS
# ============================================================

class TestTimeParsing:
    """Test suite for time parsing functions."""
    
    def test_parse_time_string_hhmmss(self):
        """Test parsing time string in HH:MM:SS format."""
        result = parse_time_value("08:30:00")
        assert result == time(8, 30, 0)
    
    def test_parse_time_string_hhmm(self):
        """Test parsing time string in HH:MM format."""
        result = parse_time_value("14:45")
        assert result == time(14, 45)
    
    def test_parse_time_object(self):
        """Test parsing time object (pass-through)."""
        t = time(9, 15)
        result = parse_time_value(t)
        assert result == t
    
    def test_parse_time_integer(self):
        """Test parsing integer as time."""
        result = parse_time_value(8)
        assert result == time(8, 0)
    
    def test_parse_time_float_decimal(self):
        """Test parsing float with decimal as time."""
        # 8.5 should be 8:30 (half past 8)
        result = parse_time_value(8.5)
        assert result == time(8, 30)
    
    def test_parse_time_float_8_3(self):
        """Test parsing float 8.3 as time."""
        # 8.3 -> 8:18 (0.3 * 60 = 18 minutes)
        result = parse_time_value(8.3)
        assert result == time(8, 18)
    
    def test_parse_time_none(self):
        """Test parsing None returns None."""
        result = parse_time_value(None)
        assert result is None
    
    def test_parse_time_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_time_value("")
        assert result is None
    
    def test_parse_time_invalid_string(self):
        """Test parsing invalid string returns None."""
        result = parse_time_value("not a time")
        assert result is None
    
    def test_parse_time_whitespace(self):
        """Test parsing time with whitespace."""
        result = parse_time_value("  09:30  ")
        assert result == time(9, 30)


# ============================================================
# FREQUENCY PARSING TESTS
# ============================================================

class TestFrequencyParsing:
    """Test suite for weekly frequency parsing."""
    
    def test_parse_frecuencia_lmmcxv(self):
        """Test parsing full week frequency."""
        result = parse_frecuencia_semanal("LMMcXV")
        assert result == ["L", "M", "Mc", "X", "V"]
    
    def test_parse_frecuencia_single_day(self):
        """Test parsing single day frequency."""
        result = parse_frecuencia_semanal("L")
        assert result == ["L"]
    
    def test_parse_frecuencia_miercoles_mc(self):
        """Test parsing Wednesday (Mc) correctly."""
        result = parse_frecuencia_semanal("Mc")
        assert result == ["Mc"]
    
    def test_parse_frecuencia_martes_vs_miercoles(self):
        """Test that M (Martes) and Mc (Miércoles) are distinguished."""
        result_m = parse_frecuencia_semanal("M")
        result_mc = parse_frecuencia_semanal("Mc")
        assert result_m == ["M"]
        assert result_mc == ["Mc"]
    
    def test_parse_frecuencia_none(self):
        """Test parsing None returns default."""
        result = parse_frecuencia_semanal(None)
        assert result == ["L", "M", "Mc", "X", "V"]
    
    def test_parse_frecuencia_empty(self):
        """Test parsing empty string returns default."""
        result = parse_frecuencia_semanal("")
        assert result == ["L", "M", "Mc", "X", "V"]
    
    def test_parse_frecuencia_with_spaces(self):
        """Test parsing frequency with whitespace."""
        result = parse_frecuencia_semanal("  L M Mc  ")
        assert result == ["L", "M", "Mc"]
    
    def test_parse_frecuencia_unknown_chars(self):
        """Test parsing frequency with unknown characters."""
        result = parse_frecuencia_semanal("LMXZ123")
        # Z, 1, 2, 3 should be skipped
        assert "L" in result
        assert "M" in result
        assert "X" in result


# ============================================================
# DURATION PARSING TESTS
# ============================================================

class TestDurationParsing:
    """Test suite for duration parsing."""
    
    def test_parse_duration_hhmmss(self):
        """Test parsing duration from HH:MM:SS."""
        result = parse_duration_to_minutes("00:45:00")
        assert result == 45
    
    def test_parse_duration_minutes(self):
        """Test parsing duration from minutes integer."""
        result = parse_duration_to_minutes(30)
        assert result == 30
    
    def test_parse_duration_time_object(self):
        """Test parsing duration from time object."""
        result = parse_duration_to_minutes(time(0, 25))
        assert result == 25
    
    def test_parse_duration_none(self):
        """Test parsing None duration."""
        result = parse_duration_to_minutes(None)
        assert result == 0


# ============================================================
# UTILITY FUNCTION TESTS
# ============================================================

class TestUtilityFunctions:
    """Test suite for utility functions."""
    
    def test_normalize_columns(self):
        """Test column name normalization."""
        import pandas as pd
        df = pd.DataFrame({"  Col1  ": [1], "COL2": [2], "col 3": [3]})
        result = normalize_columns(df)
        assert list(result.columns) == ["col1", "col2", "col 3"]
    
    def test_find_column_exact(self):
        """Test finding column with exact match."""
        cols = ["código ruta", "nombre", "hora"]
        result = find_column(cols, "código ruta")
        assert result == "código ruta"
    
    def test_find_column_partial(self):
        """Test finding column with partial match."""
        cols = ["código ruta", "nombre", "hora"]
        result = find_column(cols, "ruta")
        assert result == "código ruta"
    
    def test_find_column_multiple_patterns(self):
        """Test finding column with multiple patterns."""
        cols = ["codigo ruta", "nombre", "hora"]
        result = find_column(cols, "código ruta", "codigo ruta")
        assert result == "codigo ruta"
    
    def test_find_column_not_found(self):
        """Test finding column that doesn't exist."""
        cols = ["a", "b", "c"]
        result = find_column(cols, "z")
        assert result is None


# ============================================================
# EXCEL PARSING TESTS
# ============================================================

@pytest.mark.integration
class TestExcelParsing:
    """Test suite for Excel file parsing."""
    
    def test_parse_sample_excel(self, sample_excel_path):
        """Test parsing the sample Excel file."""
        if not os.path.exists(sample_excel_path):
            pytest.skip("Sample Excel file not found")
        
        routes = parse_routes(sample_excel_path)
        assert isinstance(routes, list)
        assert len(routes) > 0
        
        # Check that all routes are valid Route objects
        for route in routes:
            assert isinstance(route, Route)
            assert route.id is not None
            assert route.type in ["entry", "exit"]
    
    def test_parse_excel_returns_routes_with_stops(self, sample_excel_path):
        """Test that parsed routes have stops."""
        if not os.path.exists(sample_excel_path):
            pytest.skip("Sample Excel file not found")
        
        routes = parse_routes(sample_excel_path)
        if routes:
            route = routes[0]
            assert isinstance(route.stops, list)
            # At least one route should have stops
            routes_with_stops = [r for r in routes if r.stops]
            assert len(routes_with_stops) > 0
    
    def test_parse_excel_route_times(self, sample_excel_path):
        """Test that routes have valid times."""
        if not os.path.exists(sample_excel_path):
            pytest.skip("Sample Excel file not found")
        
        routes = parse_routes(sample_excel_path)
        for route in routes:
            if route.type == "entry":
                assert route.arrival_time is not None or route.departure_time is not None
            elif route.type == "exit":
                assert route.departure_time is not None or route.arrival_time is not None
    
    def test_parse_nonexistent_file(self):
        """Test parsing a non-existent file."""
        routes = parse_routes("/nonexistent/file.xlsx")
        assert routes == []
    
    def test_parse_invalid_file(self, tmp_path):
        """Test parsing an invalid file."""
        # Create a temp file that is not a valid Excel
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("This is not an Excel file")
        
        routes = parse_routes(str(invalid_file))
        assert routes == []


# ============================================================
# EDGE CASE TESTS
# ============================================================

class TestParserEdgeCases:
    """Test edge cases for parser functions."""
    
    def test_parse_time_24h(self):
        """Test parsing 24:00 time returns None (invalid)."""
        # 24:00 is not valid in Python time, should return None
        result = parse_time_value("24:00")
        assert result is None
    
    def test_parse_time_special_formats(self):
        """Test parsing special time formats."""
        # Test with dots instead of colons
        result = parse_time_value("08.30")
        assert result == time(8, 30)
    
    def test_parse_frecuencia_case_sensitive(self):
        """Test that frequency parsing is case sensitive."""
        # Lowercase should not match - result should be default (all weekdays)
        result = parse_frecuencia_semanal("lmmcxv")
        # All lowercase letters are skipped, returns default
        assert result == ["L", "M", "Mc", "X", "V"]
    
    def test_parse_duration_float(self):
        """Test parsing float duration."""
        result = parse_duration_to_minutes(30.7)
        assert result == 30
