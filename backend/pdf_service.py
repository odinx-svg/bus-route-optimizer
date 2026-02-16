"""
PDF generation service for bus schedules - Version Visual Mejorada.

Generates professional PDF reports using ReportLab with visual enhancements
and Google Maps integration for route verification.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether,
    Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.graphics import renderPDF
from typing import List, Dict, Optional, Union, Any, Tuple
from datetime import datetime, timedelta, time
import io
import urllib.parse


# =============================================================================
# PALETA DE COLORES PROFESIONAL - MEJORADA
# =============================================================================

class Colors:
    """Paleta de colores moderna y profesional para el PDF."""
    
    # Header principal
    HEADER_BG = colors.HexColor('#1e3a5f')  # Azul corporativo oscuro
    HEADER_TEXT = colors.white
    
    # Entradas (azul moderno)
    ENTRY_BG = colors.HexColor('#dbeafe')  # Azul muy claro
    ENTRY_BG_ALT = colors.HexColor('#bfdbfe')  # Alternado
    ENTRY_TEXT = colors.HexColor('#1e40af')  # Azul oscuro
    ENTRY_BORDER = colors.HexColor('#3b82f6')  # Azul medio
    ENTRY_DARK = colors.HexColor('#2563eb')  # Para headers
    
    # Salidas (naranja/ámbar moderno)
    EXIT_BG = colors.HexColor('#fef3c7')  # Ámbar muy claro
    EXIT_BG_ALT = colors.HexColor('#fde68a')  # Alternado
    EXIT_TEXT = colors.HexColor('#b45309')  # Ámbar oscuro
    EXIT_BORDER = colors.HexColor('#f59e0b')  # Ámbar medio
    EXIT_DARK = colors.HexColor('#d97706')  # Para headers
    
    # Colegio (verde éxito)
    SCHOOL_BG = colors.HexColor('#dcfce7')  # Verde claro
    SCHOOL_TEXT = colors.HexColor('#166534')  # Verde oscuro
    SCHOOL_BORDER = colors.HexColor('#22c55e')  # Verde medio
    
    # Bus header
    BUS_HEADER_BG = colors.HexColor('#f8fafc')  # Gris muy claro
    BUS_HEADER_TEXT = colors.HexColor('#0f172a')  # Slate oscuro
    BUS_HEADER_BORDER = colors.HexColor('#cbd5e1')  # Slate medio
    
    # Tabla resumen
    TABLE_HEADER_BG = colors.HexColor('#475569')  # Slate
    TABLE_HEADER_TEXT = colors.white
    TABLE_EVEN = colors.HexColor('#f1f5f9')  # Slate 100
    TABLE_ODD = colors.white
    TABLE_BORDER = colors.HexColor('#94a3b8')  # Slate 400
    
    # Misc
    CARD_BORDER = colors.HexColor('#e2e8f0')  # Slate 200
    ARROW_COLOR = colors.HexColor('#64748b')  # Slate 500
    TEXT_MUTED = colors.HexColor('#64748b')  # Slate 500
    TEXT_DARK = colors.HexColor('#1e293b')  # Slate 800
    TEXT_LIGHT = colors.HexColor('#f8fafc')  # Slate 50
    
    # Alertas y estados
    ALERT_RED = colors.HexColor('#ef4444')
    ALERT_RED_BG = colors.HexColor('#fee2e2')
    ALERT_GREEN = colors.HexColor('#22c55e')
    ALERT_GREEN_BG = colors.HexColor('#dcfce7')
    ALERT_AMBER = colors.HexColor('#f59e0b')
    ALERT_AMBER_BG = colors.HexColor('#fef3c7')
    
    # Link Google Maps
    LINK_BLUE = colors.HexColor('#2563eb')
    LINK_BG = colors.HexColor('#eff6ff')


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def add_minutes(t_msg: Union[str, time], minutes: int) -> str:
    """Add minutes to a time value."""
    if isinstance(t_msg, str):
        try:
            t = datetime.strptime(t_msg, "%H:%M:%S").time()
        except ValueError:
            try:
                t = datetime.strptime(t_msg, "%H:%M").time()
            except ValueError:
                return t_msg
    else:
        t = t_msg

    dt = datetime.combine(datetime.today(), t)
    dt_new = dt + timedelta(minutes=minutes)
    return dt_new.strftime("%H:%M")


def format_time(t_msg: Union[str, time, None]) -> str:
    """Format time to HH:MM string."""
    if t_msg is None:
        return "--:--"
    if isinstance(t_msg, str):
        if not t_msg or t_msg == "None":
            return "--:--"
        if len(t_msg) >= 5:
            return t_msg[:5]
        return t_msg
    elif isinstance(t_msg, time):
        return t_msg.strftime("%H:%M")
    return str(t_msg)


def _time_to_sort_minutes(t_msg: Union[str, time, None]) -> int:
    """Convert a time value to minutes for stable sorting (invalid values go last)."""
    if t_msg is None:
        return 24 * 60 + 999
    if isinstance(t_msg, time):
        return (t_msg.hour * 60) + t_msg.minute

    text = str(t_msg).strip()
    if not text or text.lower() == "none":
        return 24 * 60 + 999

    try:
        base = text[:5]
        dt = datetime.strptime(base, "%H:%M")
        return (dt.hour * 60) + dt.minute
    except Exception:
        return 24 * 60 + 999


def sort_schedule_items_by_time(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return items sorted from earliest to latest start time."""
    return sorted(
        items or [],
        key=lambda item: (
            _time_to_sort_minutes(item.get("start_time")),
            _time_to_sort_minutes(item.get("end_time")),
            str(item.get("route_id", "")),
        ),
    )


def calculate_route_duration(start: Union[str, time, None], end: Union[str, time, None]) -> int:
    """Calculate duration in minutes between two times."""
    if start is None or end is None:
        return 0
    try:
        if isinstance(start, str):
            if not start or start == "None":
                return 0
            start = datetime.strptime(start[:5], "%H:%M").time()
        if isinstance(end, str):
            if not end or end == "None":
                return 0
            end = datetime.strptime(end[:5], "%H:%M").time()
        
        start_dt = datetime.combine(datetime.today(), start)
        end_dt = datetime.combine(datetime.today(), end)
        
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        
        return int((end_dt - start_dt).total_seconds() / 60)
    except Exception:
        return 0


def format_duration(minutes: int) -> str:
    """Format minutes as H:MM or MM."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}m"


def get_positioning_minutes(item: Dict[str, Any]) -> int:
    """
    Extract positioning/deadhead minutes from a schedule item.

    Tries multiple fields for backward compatibility.
    """
    if not isinstance(item, dict):
        return 0

    for key in ("positioning_minutes", "deadhead_minutes", "deadhead"):
        value = item.get(key)
        if value is None:
            continue
        try:
            minutes = int(float(value))
            return max(0, minutes)
        except (TypeError, ValueError):
            continue
    return 0


def get_item_capacity_needed(item: Dict[str, Any]) -> int:
    """Extract required seats for one route item."""
    if not isinstance(item, dict):
        return 0

    for key in ("vehicle_capacity_max", "vehicleCapacityMax"):
        value = item.get(key)
        if value is None:
            continue
        try:
            seats = int(float(value))
            if seats > 0:
                return seats
        except (TypeError, ValueError):
            continue

    for key in ("capacity_needed", "capacityNeeded"):
        value = item.get(key)
        if value is None:
            continue
        try:
            seats = int(float(value))
            if seats > 0:
                return seats
        except (TypeError, ValueError):
            continue

    stops = item.get("stops", [])
    if not isinstance(stops, list):
        return 0

    total = 0
    for stop in stops:
        if not isinstance(stop, dict):
            continue
        try:
            passengers = int(float(stop.get("passengers", 0)))
        except (TypeError, ValueError):
            passengers = 0
        if passengers > 0:
            total += passengers

    return max(0, total)


def get_bus_min_capacity_needed(items: List[Dict[str, Any]]) -> int:
    """Minimum seat capacity a bus needs for its day plan."""
    if not items:
        return 0
    return max((get_item_capacity_needed(item) for item in items), default=0)


def generate_google_maps_link(all_stops: List[Dict[str, Any]]) -> Optional[str]:
    """
    Generate a Google Maps directions link for all stops in a bus route.
    
    Google Maps has URL length limits (~2000 chars), so we limit to ~20 waypoints
    for reliability. If more stops exist, we sample strategically (first, last, 
    and evenly distributed middle points).
    
    Args:
        all_stops: List of stops with lat/lon coordinates
        
    Returns:
        Google Maps URL or None if not enough coordinates
    """
    # Filter stops with valid coordinates
    coords = []
    for stop in all_stops:
        lat = stop.get('lat')
        lon = stop.get('lon')
        if lat is not None and lon is not None:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                coords.append((lat_f, lon_f))
            except (ValueError, TypeError):
                continue
    
    if len(coords) < 2:
        return None
    
    # Google Maps URL limit - sample stops if too many
    MAX_WAYPOINTS = 20  # Safe limit for Google Maps
    if len(coords) > MAX_WAYPOINTS:
        # Always keep first and last
        first = coords[0]
        last = coords[-1]
        
        # Sample middle points evenly
        middle = coords[1:-1]
        step = len(middle) // (MAX_WAYPOINTS - 2)
        sampled_middle = [middle[i * step] for i in range(MAX_WAYPOINTS - 2)]
        
        coords = [first] + sampled_middle + [last]
    
    # Build Google Maps directions URL
    # Format: https://www.google.com/maps/dir/lat1,lon1/lat2,lon2/lat3,lon3/...
    base_url = "https://www.google.com/maps/dir/"
    
    coord_parts = [f"{lat},{lon}" for lat, lon in coords]
    path = "/".join(coord_parts)
    
    return base_url + path


def generate_google_maps_search_link(lat: float, lon: float, query: str = "") -> str:
    """Generate a Google Maps search link for a single location."""
    base_url = "https://www.google.com/maps/search/?api=1"
    params = {"query": f"{lat},{lon}"}
    if query:
        params["query"] = f"{query}@{lat},{lon}"
    return base_url + "&" + urllib.parse.urlencode(params)


# =============================================================================
# ESTILOS PERSONALIZADOS
# =============================================================================

def create_styles():
    """Create and return custom paragraph styles."""
    styles = getSampleStyleSheet()
    
    custom_styles = {
        # Header principal
        'page_header': ParagraphStyle(
            'PageHeader',
            parent=styles['Heading1'],
            fontSize=20,
            fontName='Helvetica-Bold',
            textColor=Colors.HEADER_TEXT,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        'page_header_right': ParagraphStyle(
            'PageHeaderRight',
            parent=styles['Heading1'],
            fontSize=16,
            fontName='Helvetica-Bold',
            textColor=Colors.HEADER_TEXT,
            alignment=TA_RIGHT,
            spaceAfter=6,
        ),
        
        # Bus header - Más prominente
        'bus_header': ParagraphStyle(
            'BusHeader',
            parent=styles['Heading2'],
            fontSize=16,
            fontName='Helvetica-Bold',
            textColor=Colors.BUS_HEADER_TEXT,
            spaceAfter=4,
            spaceBefore=8,
        ),
        'bus_stats': ParagraphStyle(
            'BusStats',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=Colors.TEXT_MUTED,
            alignment=TA_RIGHT,
        ),
        
        # Ruta
        'route_title': ParagraphStyle(
            'RouteTitle',
            parent=styles['Heading3'],
            fontSize=10,
            fontName='Helvetica-Bold',
            spaceAfter=4,
            spaceBefore=2,
        ),
        'route_type_badge': ParagraphStyle(
            'RouteTypeBadge',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
        ),
        
        # Horario de ruta
        'route_time': ParagraphStyle(
            'RouteTime',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=Colors.TEXT_DARK,
            spaceAfter=4,
        ),
        
        # Paradas
        'stop_time': ParagraphStyle(
            'StopTime',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Courier-Bold',
            textColor=Colors.TEXT_DARK,
        ),
        'stop_name': ParagraphStyle(
            'StopName',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=Colors.TEXT_DARK,
        ),
        'stop_school': ParagraphStyle(
            'StopSchool',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=Colors.SCHOOL_TEXT,
        ),
        
        # Link Google Maps
        'maps_link': ParagraphStyle(
            'MapsLink',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=Colors.LINK_BLUE,
            alignment=TA_LEFT,
        ),
        
        # Resumen
        'summary': ParagraphStyle(
            'Summary',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            textColor=Colors.TEXT_DARK,
            spaceAfter=4,
        ),
        'summary_bold': ParagraphStyle(
            'SummaryBold',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=Colors.TEXT_DARK,
            spaceAfter=4,
        ),
        
        # Tabla
        'table_header': ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=Colors.TABLE_HEADER_TEXT,
            alignment=TA_CENTER,
        ),
        'table_cell': ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=Colors.TEXT_DARK,
            alignment=TA_CENTER,
        ),
        'table_cell_left': ParagraphStyle(
            'TableCellLeft',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=Colors.TEXT_DARK,
            alignment=TA_LEFT,
        ),
        
        # Pie de página
        'footer': ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            textColor=Colors.TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }
    
    return custom_styles


# =============================================================================
# ELEMENTOS VISUALES MEJORADOS
# =============================================================================

def create_header(day_name: Optional[str]) -> Table:
    """Create the page header with title and day."""
    styles = create_styles()
    title = "TUTTI - Horario de Flota"
    day_text = day_name if day_name else "Horario"
    
    data = [
        [
            Paragraph(f"&#128652; <b>{title}</b>", styles['page_header']),
            Paragraph(f"&#128197; <b>{day_text.upper()}</b>", styles['page_header_right'])
        ]
    ]
    
    header_table = Table(data, colWidths=[6 * inch, 3 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), Colors.HEADER_BG),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (0, 0), 15),
        ('RIGHTPADDING', (-1, 0), (-1, 0), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    return header_table


def create_bus_header(
    bus_id: str,
    num_routes: int,
    total_duration: int = 0,
    min_capacity_needed: int = 0,
) -> Table:
    """Create a bus header section with improved styling."""
    styles = create_styles()
    route_text = f"{num_routes} ruta{'s' if num_routes != 1 else ''}"
    duration_text = f" | Duración total: {format_duration(total_duration)}" if total_duration > 0 else ""
    capacity_text = f" | Min plazas: {int(min_capacity_needed)}P" if int(min_capacity_needed or 0) > 0 else ""
    
    data = [
        [
            Paragraph(f"&#128652; <b>BUS {bus_id}</b>", styles['bus_header']),
            Paragraph(f"{route_text}{duration_text}{capacity_text}", styles['bus_stats'])
        ]
    ]
    
    bus_table = Table(data, colWidths=[6 * inch, 3 * inch])
    bus_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), Colors.BUS_HEADER_BG),
        ('LINEABOVE', (0, 0), (-1, -1), 3, Colors.HEADER_BG),
        ('LINEBELOW', (0, 0), (-1, -1), 1, Colors.BUS_HEADER_BORDER),
        ('LEFTPADDING', (0, 0), (0, 0), 12),
        ('RIGHTPADDING', (-1, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    return bus_table


def create_google_maps_box(maps_link: Optional[str]) -> Optional[Table]:
    """
    Create a visual box with Google Maps link.
    
    Args:
        maps_link: Google Maps URL
        
    Returns:
        Table element or None if no link
    """
    if not maps_link:
        return None
    
    styles = create_styles()
    
    # Create link text
    link_text = f'<a href="{maps_link}" color="{Colors.LINK_BLUE.hexval()}">&#128205; Ver ruta completa en Google Maps</a>'
    
    data = [
        [Paragraph(link_text, styles['maps_link'])]
    ]
    
    box = Table(data, colWidths=[8 * inch])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), Colors.LINK_BG),
        ('BOX', (0, 0), (-1, -1), 1.5, Colors.LINK_BLUE),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 6),
    ]))
    
    return box


def create_route_card(item: Dict[str, Any], route_num: int) -> Table:
    """Create a visual card for a route with all stops."""
    styles = create_styles()
    
    # Determine route type and colors
    route_type = item.get('type', '')
    if route_type == 'entry':
        bg_color = Colors.ENTRY_BG
        bg_alt = Colors.ENTRY_BG_ALT
        text_color = Colors.ENTRY_TEXT
        border_color = Colors.ENTRY_BORDER
        header_bg = Colors.ENTRY_DARK
        type_label = "ENTRADA"
        type_icon = "&#10132;"  # Flecha derecha
    elif route_type == 'exit':
        bg_color = Colors.EXIT_BG
        bg_alt = Colors.EXIT_BG_ALT
        text_color = Colors.EXIT_TEXT
        border_color = Colors.EXIT_BORDER
        header_bg = Colors.EXIT_DARK
        type_label = "SALIDA"
        type_icon = "&#11013;"  # Flecha izquierda
    else:
        bg_color = colors.HexColor('#f3f4f6')
        bg_alt = colors.HexColor('#e5e7eb')
        text_color = Colors.TEXT_DARK
        border_color = Colors.CARD_BORDER
        header_bg = Colors.TABLE_HEADER_BG
        type_label = "RUTA"
        type_icon = "&#128739;"
    
    school_name = item.get('school_name') or item.get('route_id', 'Desconocido')
    start_time = format_time(item.get('start_time', ''))
    end_time = format_time(item.get('end_time', ''))
    duration = calculate_route_duration(item.get('start_time'), item.get('end_time'))
    
    # Route header with badge
    header_data = [
        [
            Paragraph(f"{type_icon} <b>RUTA {route_num}</b>", styles['route_title']),
            Paragraph(f"<b>{type_label}</b>", styles['route_type_badge']),
        ]
    ]
    
    header_table = Table(header_data, colWidths=[5 * inch, 1.5 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), header_bg),
        ('BACKGROUND', (1, 0), (1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, -1), Colors.TEXT_LIGHT),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 10),
        ('RIGHTPADDING', (1, 0), (1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # School and time info
    info_data = [
        [
            Paragraph(f"&#127979; <b>{school_name}</b>", styles['route_title']),
            Paragraph(f"&#9201; <b>{start_time} - {end_time}</b> ({duration} min)", styles['route_time']),
        ]
    ]
    
    info_table = Table(info_data, colWidths=[3.5 * inch, 3 * inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 10),
        ('RIGHTPADDING', (1, 0), (1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Build stops list
    stops = item.get('stops', [])
    stops_data = []
    
    if stops:
        base_start = item.get('start_time')
        
        for i, stop in enumerate(stops):
            stop_name = stop.get('name', 'Parada sin nombre')
            time_offset = stop.get('time_from_start', 0)
            # Convertir segundos a minutos si el valor es grande
            if time_offset > 100:
                time_offset = time_offset / 60
            stop_time = add_minutes(base_start, int(time_offset))
            
            # Check if this is the last stop (school)
            is_last = (i == len(stops) - 1)
            
            if is_last:
                icon = "&#127979;"  # School icon
                stop_style_time = styles['stop_school']
                stop_style_name = styles['stop_school']
                row_bg = Colors.SCHOOL_BG
            else:
                icon = "&#128205;"  # Pin icon
                stop_style_time = styles['stop_time']
                stop_style_name = styles['stop_name']
                row_bg = bg_color if i % 2 == 0 else bg_alt
            
            # Time and name cell
            time_para = Paragraph(f"<b>{stop_time}</b>", stop_style_time)
            name_para = Paragraph(f"{icon} {stop_name}", stop_style_name)
            
            # Add connection indicator
            if not is_last:
                conn = Paragraph("&#8595;", styles['stop_name'])
            else:
                conn = Paragraph("&#10004; <i>Llegada</i>", styles['stop_school'])
            
            stops_data.append([time_para, name_para, conn])
            
            # Add background color
    else:
        stops_data.append([
            Paragraph("Sin paradas registradas", styles['stop_name']),
            '',
            ''
        ])
    
    # Create stops table
    if stops_data:
        stops_table = Table(stops_data, colWidths=[0.7 * inch, 4.3 * inch, 1 * inch])
        stops_styles = [
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, -1), 8),
            ('LEFTPADDING', (1, 0), (1, -1), 5),
            ('RIGHTPADDING', (2, 0), (2, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        
        # Add alternating backgrounds
        for i in range(len(stops_data)):
            is_last_stop = (i == len(stops_data) - 1)
            if is_last_stop:
                stops_styles.append(('BACKGROUND', (0, i), (-1, i), Colors.SCHOOL_BG))
            else:
                bg = bg_color if i % 2 == 0 else bg_alt
                stops_styles.append(('BACKGROUND', (0, i), (-1, i), bg))
        
        stops_table.setStyle(TableStyle(stops_styles))
    else:
        stops_table = Paragraph("Sin datos de paradas", styles['stop_name'])
    
    # Assemble card content
    card_data = [
        [header_table],
        [info_table],
        [stops_table],
    ]
    
    card = Table(card_data, colWidths=[6.5 * inch])
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('BOX', (0, 0), (-1, -1), 1.5, border_color),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 8),
    ]))
    
    return card


def create_positioning_card(
    current_item: Dict[str, Any],
    next_item: Dict[str, Any],
    current_route_num: int,
) -> Table:
    """Create a compact visual card for positioning time between two routes."""
    styles = create_styles()

    positioning_minutes = get_positioning_minutes(next_item)
    available_window = calculate_route_duration(
        current_item.get('end_time'),
        next_item.get('start_time'),
    )
    margin = available_window - positioning_minutes

    if margin < 0:
        status_color = Colors.ALERT_RED
        status_bg = Colors.ALERT_RED_BG
        status_text = "RIESGO"
    elif margin <= 5:
        status_color = Colors.ALERT_AMBER
        status_bg = Colors.ALERT_AMBER_BG
        status_text = "AJUSTADO"
    else:
        status_color = Colors.ALERT_GREEN
        status_bg = Colors.ALERT_GREEN_BG
        status_text = "OK"

    left_style = ParagraphStyle(
        'PositioningLeft',
        parent=styles['table_cell_left'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=Colors.TEXT_DARK,
    )
    right_style = ParagraphStyle(
        'PositioningRight',
        parent=styles['table_cell'],
        fontName='Courier-Bold',
        fontSize=8,
        alignment=TA_RIGHT,
        textColor=status_color,
    )

    link_text = (
        f"&#10230; <b>R{current_route_num} &#8594; R{current_route_num + 1}</b> "
        f"({format_time(current_item.get('end_time'))} &#8594; {format_time(next_item.get('start_time'))})"
    )
    metrics_text = (
        f"Posicionamiento {positioning_minutes}m | Ventana {available_window}m | "
        f"Margen {margin:+d}m | {status_text}"
    )

    card = Table(
        [[Paragraph(link_text, left_style), Paragraph(metrics_text, right_style)]],
        colWidths=[4.3 * inch, 2.2 * inch],
    )
    card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), status_bg),
        ('BOX', (0, 0), (-1, -1), 1, status_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 8),
        ('RIGHTPADDING', (1, 0), (1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    return card


def create_bus_summary_table(bus_id: str, items: List[Dict[str, Any]]) -> Table:
    """
    Create a summary table for a bus (similar to Excel client view).
    
    Columns: #, Origen, Destino, H.Inicio, H.Fin, Duración, Tipo
    """
    styles = create_styles()
    
    ordered_items = sort_schedule_items_by_time(items)

    # Header row
    data = [
        [
            Paragraph("#", styles['table_header']),
            Paragraph("Origen", styles['table_header']),
            Paragraph("Destino", styles['table_header']),
            Paragraph("H.Inicio", styles['table_header']),
            Paragraph("H.Fin", styles['table_header']),
            Paragraph("Duración", styles['table_header']),
            Paragraph("Posic.", styles['table_header']),
            Paragraph("Tipo", styles['table_header']),
        ]
    ]
    
    # Data rows
    total_duration = 0
    total_positioning = 0
    route_row_indices: List[int] = []
    transition_row_indices: List[int] = []

    transition_text_style = ParagraphStyle(
        'TransitionRowText',
        parent=styles['table_cell_left'],
        fontName='Helvetica-Oblique',
        fontSize=7,
        textColor=Colors.TEXT_MUTED,
        alignment=TA_LEFT,
    )

    for i, item in enumerate(ordered_items, 1):
        stops = item.get('stops', [])
        origin = stops[0].get('name', 'N/A') if stops else 'N/A'
        destination = stops[-1].get('name', 'N/A') if stops else item.get('school_name', 'N/A')
        
        start_time = format_time(item.get('start_time', ''))
        end_time = format_time(item.get('end_time', ''))
        duration = calculate_route_duration(item.get('start_time'), item.get('end_time'))
        total_duration += duration
        positioning_minutes = get_positioning_minutes(item) if i > 1 else 0
        if i > 1:
            total_positioning += positioning_minutes
        
        route_type = item.get('type', '')
        if route_type == 'entry':
            type_text = "ENTRADA"
            type_color = Colors.ENTRY_TEXT
            type_bg = Colors.ENTRY_BG
        elif route_type == 'exit':
            type_text = "SALIDA"
            type_color = Colors.EXIT_TEXT
            type_bg = Colors.EXIT_BG
        else:
            type_text = "RUTA"
            type_color = Colors.TEXT_DARK
            type_bg = colors.HexColor('#f3f4f6')
        
        row = [
            Paragraph(str(i), styles['table_cell']),
            Paragraph(origin[:30], styles['table_cell_left']),
            Paragraph(destination[:30], styles['table_cell_left']),
            Paragraph(start_time, styles['table_cell']),
            Paragraph(end_time, styles['table_cell']),
            Paragraph(f"{duration}m", styles['table_cell']),
            Paragraph("--" if i == 1 else f"{positioning_minutes}m", styles['table_cell']),
            Paragraph(type_text, ParagraphStyle(
                'TypeBadge',
                parent=styles['table_cell'],
                textColor=type_color,
                backColor=type_bg,
                fontName='Helvetica-Bold',
            )),
        ]
        route_row_indices.append(len(data))
        data.append(row)

        if i < len(ordered_items):
            next_item = ordered_items[i]
            available_window = calculate_route_duration(
                item.get('end_time'),
                next_item.get('start_time'),
            )
            required_positioning = get_positioning_minutes(next_item)
            margin = available_window - required_positioning

            if margin < 0:
                status = "RIESGO"
            elif margin <= 5:
                status = "AJUSTADO"
            else:
                status = "OK"

            transition_text = (
                f"R{i} -> R{i + 1} | "
                f"{format_time(item.get('end_time'))} -> {format_time(next_item.get('start_time'))} | "
                f"Ventana {available_window}m | Posicionamiento {required_positioning}m | "
                f"Margen {margin:+d}m ({status})"
            )
            transition_row = [
                Paragraph("", styles['table_cell']),
                Paragraph(transition_text, transition_text_style),
                Paragraph("", styles['table_cell']),
                Paragraph("", styles['table_cell']),
                Paragraph("", styles['table_cell']),
                Paragraph("", styles['table_cell']),
                Paragraph("", styles['table_cell']),
                Paragraph("", styles['table_cell']),
            ]
            transition_row_indices.append(len(data))
            data.append(transition_row)
    
    # Total row
    data.append([
        Paragraph("", styles['table_cell']),
        Paragraph("<b>TOTAL</b>", styles['table_cell_left']),
        Paragraph("", styles['table_cell']),
        Paragraph("", styles['table_cell']),
        Paragraph("", styles['table_cell']),
        Paragraph(f"<b>{format_duration(total_duration)}</b>", styles['table_cell']),
        Paragraph(f"<b>{total_positioning}m</b>", styles['table_cell']),
        Paragraph("", styles['table_cell']),
    ])

    # Create table
    table = Table(
        data,
        colWidths=[
            0.35 * inch,
            1.55 * inch,
            1.55 * inch,
            0.85 * inch,
            0.85 * inch,
            0.75 * inch,
            0.75 * inch,
            0.8 * inch,
        ],
    )
    
    table_styles = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), Colors.TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), Colors.TABLE_HEADER_TEXT),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -2), 0.5, Colors.TABLE_BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, Colors.TABLE_HEADER_BG),
        
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), Colors.TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, -1), (-1, -1), Colors.TABLE_HEADER_TEXT),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, Colors.TABLE_HEADER_BG),
        
        # Padding
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    
    # Alternating colors for route rows only
    for route_idx, row_i in enumerate(route_row_indices, 1):
        bg = Colors.TABLE_EVEN if route_idx % 2 == 0 else Colors.TABLE_ODD
        table_styles.append(('BACKGROUND', (0, row_i), (-1, row_i), bg))

    # Inter-route rows with compact shared message
    for row_i in transition_row_indices:
        table_styles.extend([
            ('SPAN', (1, row_i), (7, row_i)),
            ('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor('#eef2ff')),
            ('LINEABOVE', (0, row_i), (-1, row_i), 0.4, Colors.CARD_BORDER),
            ('LINEBELOW', (0, row_i), (-1, row_i), 0.4, Colors.CARD_BORDER),
            ('TOPPADDING', (0, row_i), (-1, row_i), 3),
            ('BOTTOMPADDING', (0, row_i), (-1, row_i), 3),
        ])
    
    table.setStyle(TableStyle(table_styles))
    
    return table


def create_summary_table(schedule: List[Dict[str, Any]]) -> Table:
    """Create summary statistics table."""
    styles = create_styles()
    
    # Calculate statistics
    total_buses = len(schedule)
    total_routes = sum(len(bus.get('items', [])) for bus in schedule)
    total_entries = sum(
        sum(1 for item in bus.get('items', []) if item.get('type') == 'entry')
        for bus in schedule
    )
    total_exits = sum(
        sum(1 for item in bus.get('items', []) if item.get('type') == 'exit')
        for bus in schedule
    )
    
    # Summary data
    summary_data = [
        [
            Paragraph(f"&#128652; <b>Buses:</b> {total_buses}", styles['summary_bold']),
            Paragraph(f"&#128204; <b>Rutas:</b> {total_routes}", styles['summary_bold']),
            Paragraph(f"&#10132; <b>Entradas:</b> {total_entries}", styles['summary_bold']),
            Paragraph(f"&#11013; <b>Salidas:</b> {total_exits}", styles['summary_bold']),
        ]
    ]
    
    summary_table = Table(summary_data, colWidths=[2.25 * inch] * 4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), Colors.TABLE_EVEN),
        ('BOX', (0, 0), (-1, -1), 1, Colors.CARD_BORDER),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 6),
    ]))
    
    return summary_table


# =============================================================================
# FUNCIÓN PRINCIPAL - MEJORADA
# =============================================================================

def generate_schedule_pdf(
    schedule: List[Dict[str, Any]], 
    day_name: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate a professional PDF report from a bus schedule.
    
    Includes:
    - Summary table per bus (Excel-like)
    - Google Maps link for each bus route
    """
    buffer = io.BytesIO()
    
    # Document setup - landscape for better layout
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    
    elements: List[Any] = []
    styles = create_styles()
    
    # =========================================================================
    # PÁGINA 1: Resumen General
    # =========================================================================
    
    # Header
    elements.append(create_header(day_name))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Summary stats
    elements.append(create_summary_table(schedule))
    elements.append(Spacer(1, 0.3 * inch))
    
    # Leyenda
    legend_data = [
        [
            Paragraph("&#9679; <b>Entradas</b> (azul)", ParagraphStyle('Legend', parent=styles['summary'], textColor=Colors.ENTRY_TEXT)),
            Paragraph("&#9679; <b>Salidas</b> (naranja)", ParagraphStyle('Legend', parent=styles['summary'], textColor=Colors.EXIT_TEXT)),
            Paragraph("&#9679; <b>Colegio</b> (verde)", ParagraphStyle('Legend', parent=styles['summary'], textColor=Colors.SCHOOL_TEXT)),
            Paragraph("&#128205; <b>Ver ruta en Google Maps</b>", ParagraphStyle('Legend', parent=styles['summary'], textColor=Colors.LINK_BLUE)),
        ]
    ]
    legend_table = Table(legend_data, colWidths=[2 * inch] * 4)
    legend_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(legend_table)
    elements.append(Spacer(1, 0.2 * inch))
    
    # =========================================================================
    # PÁGINAS POR BUS: Tabla Resumen + Detalle + Google Maps
    # =========================================================================
    
    for bus_idx, bus in enumerate(schedule):
        bus_id = bus.get('bus_id', 'Bus desconocido')
        items = sort_schedule_items_by_time(bus.get('items', []))
        num_routes = len(items)
        
        if bus_idx > 0:
            elements.append(PageBreak())
        
        # Calculate total duration
        total_duration = sum(
            calculate_route_duration(item.get('start_time'), item.get('end_time'))
            for item in items
        )
        min_capacity_needed = get_bus_min_capacity_needed(items)
        
        # Bus header
        elements.append(create_bus_header(bus_id, num_routes, total_duration, min_capacity_needed))
        elements.append(Spacer(1, 0.15 * inch))
        
        # Summary table (Excel-like view)
        elements.append(Paragraph("<b>Resumen de Rutas</b>", styles['summary_bold']))
        elements.append(Spacer(1, 0.05 * inch))
        elements.append(create_bus_summary_table(bus_id, items))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Collect all stops for Google Maps
        all_stops = []
        for item in items:
            stops = item.get('stops', [])
            all_stops.extend(stops)
        
        # Google Maps link
        maps_link = generate_google_maps_link(all_stops)
        maps_box = create_google_maps_box(maps_link)
        if maps_box:
            elements.append(Paragraph("<b>Verificación de Ruta</b>", styles['summary_bold']))
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(maps_box)
            elements.append(Spacer(1, 0.2 * inch))
        
        # Nota: Se elimina intencionalmente la sección "Detalle de Paradas"
        # para mantener el PDF compacto y operativo.
    
    # =========================================================================
    # PÁGINA FINAL: Pie de página
    # =========================================================================
    
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=Colors.CARD_BORDER))
    elements.append(Spacer(1, 0.1 * inch))
    elements.append(Paragraph(
        f"Documento generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - Tutti Bus Route Optimizer",
        styles['footer']
    ))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
