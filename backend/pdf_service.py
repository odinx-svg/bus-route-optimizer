from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from typing import List, Dict
import io

def generate_schedule_pdf(schedule: List[Dict]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Title
    elements.append(Paragraph("Tutti Bus Schedule Optimization", title_style))
    elements.append(Spacer(1, 0.25 * inch))
    
    # Summary
    total_buses = len(schedule)
    total_routes = sum(len(bus['items']) for bus in schedule)
    summary_text = f"Total Buses: {total_buses} | Total Routes Covered: {total_routes}"
    elements.append(Paragraph(summary_text, normal_style))
    elements.append(Spacer(1, 0.5 * inch))
    
    for bus in schedule:
        # Bus Header
        bus_id = bus.get('bus_id', 'Unknown Bus')
        elements.append(Paragraph(f"Bus: {bus_id}", heading_style))
        
        # Table Data
        data = [['Start Time', 'End Time', 'Route ID', 'Type', 'Shift (min)']]
        
        for item in bus.get('items', []):
            shift = item.get('time_shift_minutes', 0)
            shift_str = f"+{shift}" if shift > 0 else str(shift)
            
            row = [
                item.get('start_time', ''),
                item.get('end_time', ''),
                str(item.get('route_id', '')),
                item.get('type', ''),
                shift_str
            ]
            data.append(row)
            
        # Table Style
        table = Table(data, colWidths=[1.5*inch, 1.5*inch, 3*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.indigo),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.5 * inch))
        
        # Optional: Page break after every few buses or just let it flow?
        # Let's let it flow for now.
        
    doc.build(elements)
    buffer.seek(0)
    return buffer
