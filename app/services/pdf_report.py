"""PDF Report Generator for Backtest Results"""

import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.services.backtester import BacktestSummary, TradeResult


def generate_backtest_pdf(summary: BacktestSummary) -> io.BytesIO:
    """Backtest natijasini PDF formatda yaratish"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.darkblue
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        alignment=TA_LEFT,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.darkblue
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
    )
    
    elements = []
    
    # Title
    elements.append(Paragraph("📊 BACKTEST HISOBOTI", title_style))
    elements.append(Spacer(1, 5*mm))
    
    # Info section
    info_data = [
        ["Symbol:", summary.symbol],
        ["Signal TF:", summary.signal_timeframe],
        ["Execution TF:", summary.execution_timeframe],
        ["Davr:", f"{summary.period_start.strftime('%d.%m.%Y')} - {summary.period_end.strftime('%d.%m.%Y')}"],
        ["Yaratilgan:", summary.created_at.strftime('%d.%m.%Y %H:%M')],
        ["Session ID:", summary.session_id],
    ]
    
    info_table = Table(info_data, colWidths=[80, 200])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.darkblue),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Summary Statistics
    elements.append(Paragraph("📈 UMUMIY STATISTIKA", subtitle_style))
    
    # Profit color
    profit_color = colors.green if summary.total_profit_percent >= 0 else colors.red
    
    stats_data = [
        ["Jami signallar:", str(summary.total_signals), "Win rate:", f"{summary.win_rate:.1f}%"],
        ["LONG signallar:", str(summary.long_signals), "Profit factor:", f"{summary.profit_factor:.2f}"],
        ["SHORT signallar:", str(summary.short_signals), "Jami profit:", f"{summary.total_profit_percent:.2f}%"],
        ["", "", "", ""],
        ["Yutiqlar (wins):", str(summary.wins), "Avg profit:", f"{summary.average_profit:.2f}%"],
        ["Yutqazishlar:", str(summary.losses), "Avg loss:", f"{summary.average_loss:.2f}%"],
        ["Partial wins:", str(summary.partial_wins), "Max profit:", f"{summary.max_profit:.2f}%"],
        ["Timeouts:", str(summary.timeouts), "Max loss:", f"{summary.max_loss:.2f}%"],
    ]
    
    stats_table = Table(stats_data, colWidths=[90, 60, 80, 70])
    stats_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.darkblue),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.darkblue),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.95)),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 5*mm))
    
    # TP Statistics
    elements.append(Paragraph("🎯 TAKE PROFIT STATISTIKASI", subtitle_style))
    
    tp_data = [
        ["TP Level", "Hits", "Foiz"],
        ["TP1 (40%)", str(summary.tp1_hits), f"{(summary.tp1_hits/max(summary.total_signals,1)*100):.1f}%"],
        ["TP2 (30%)", str(summary.tp2_hits), f"{(summary.tp2_hits/max(summary.total_signals,1)*100):.1f}%"],
        ["TP3 (30%)", str(summary.tp3_hits), f"{(summary.tp3_hits/max(summary.total_signals,1)*100):.1f}%"],
    ]
    
    tp_table = Table(tp_data, colWidths=[100, 80, 80])
    tp_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.6)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(tp_table)
    elements.append(Spacer(1, 10*mm))

    # Strategy Performance
    if summary.strategy_performance:
        elements.append(Paragraph("🧩 STRATEGIYA PERFORMANCE", subtitle_style))

        perf_data = [["Strategiya", "Signals", "WinRate", "Profit", "PF", "Weight"]]
        for perf in summary.strategy_performance:
            perf_data.append([
                perf.name,
                str(perf.total_signals),
                f"{perf.win_rate:.1f}%",
                f"{perf.total_profit_percent:.2f}%",
                f"{perf.profit_factor:.2f}",
                f"{perf.current_weight:.2f}->{perf.suggested_weight:.2f}",
            ])

        perf_table = Table(perf_data, colWidths=[90, 45, 55, 55, 40, 70])
        perf_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.5, 0.4)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(perf_table)
        elements.append(Spacer(1, 10*mm))

        # Weight breakdown
        elements.append(Paragraph("⚙️ WEIGHT BREAKDOWN (DEBUG)", subtitle_style))
        wb_data = [["Strategiya", "Base", "Perf", "Regime", "Stability", "Corr", "Actual"]]
        for perf in summary.strategy_performance:
            wb_data.append([
                perf.name,
                f"{perf.base_weight:.2f}",
                f"{perf.perf_weight:.2f}",
                f"{perf.regime_mult:.2f}",
                f"{perf.stability_weight:.2f}",
                f"{perf.corr_penalty:.2f}",
                f"{perf.actual_weight:.2f}",
            ])
        wb_table = Table(wb_data, colWidths=[90, 40, 40, 45, 55, 45, 45])
        wb_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.3, 0.3, 0.3)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(wb_table)
        elements.append(Spacer(1, 10*mm))
    
    # All Trades Table
    if summary.trades:
        elements.append(Paragraph("📋 BARCHA SIGNALLAR", subtitle_style))
        
        # Header
        trades_header = ["#", "Ochilish", "Yopilish", "Yo'n", "Entry", "Exit", "SL", "TP1", "TP2", "TP3", "Natija", "Profit%"]
        trades_data = [trades_header]
        
        for i, trade in enumerate(summary.trades, 1):
            # Result indicator - PARTIAL uchun qaysi TP lar hit bo'lganini ko'rsatish
            if trade.result == "TP3":
                result_text = "✅ TP3"
            elif trade.result == "TP2":
                result_text = "✅ TP2"
            elif trade.result == "TP1":
                result_text = "✅ TP1"
            elif trade.result == "PARTIAL":
                # PARTIAL - qaysi TP lar hit bo'lgani va SL qayerda
                tp_hits = []
                if trade.tp1_hit:
                    tp_hits.append("T1")
                if trade.tp2_hit:
                    tp_hits.append("T2")
                
                sl_info = ""
                if trade.sl_hit and trade.sl_hit_at:
                    if trade.sl_hit_at == "BREAKEVEN":
                        sl_info = "→BE"
                    elif trade.sl_hit_at == "TP1":
                        sl_info = "→T1"
                    else:
                        sl_info = "→SL"
                
                result_text = f"{'+'.join(tp_hits)}{sl_info}" if tp_hits else "PARTIAL"
            elif trade.result == "SL":
                result_text = "❌ SL"
            else:
                result_text = "⏱ TIMEOUT"
            
            # Direction indicator
            direction = "🟢L" if trade.direction == "LONG" else "🔴S"
            
            # Exit price
            exit_price_str = f"{trade.exit_price:.2f}" if trade.exit_price else "-"
            
            # Exit time
            exit_time_str = trade.exit_time.strftime('%d.%m %H:%M') if trade.exit_time else "-"
            
            # Profit formatting
            profit_str = f"{trade.total_profit_percent:+.2f}%"
            
            trades_data.append([
                str(i),
                trade.signal_time.strftime('%d.%m %H:%M'),
                exit_time_str,
                direction,
                f"{trade.entry_price:.2f}",
                exit_price_str,
                f"{trade.stop_loss:.2f}" if trade.stop_loss else "-",
                f"{trade.take_profit_1:.2f}" if trade.take_profit_1 else "-",
                f"{trade.take_profit_2:.2f}" if trade.take_profit_2 else "-",
                f"{trade.take_profit_3:.2f}" if trade.take_profit_3 else "-",
                result_text,
                profit_str,
            ])
            
        
        # Adjust column widths for A4 - soddalashtirilgan jadval
        col_widths = [18, 55, 55, 25, 55, 55, 55, 55, 55, 55, 70, 45]
        
        trades_table = Table(trades_data, colWidths=col_widths)
        
        # Table styling
        table_style = [
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.4, 0.6)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Row colors based on result
        for i, trade in enumerate(summary.trades, 1):
            if trade.total_profit_percent > 0:
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.Color(0.9, 1.0, 0.9)))
            elif trade.total_profit_percent < 0:
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.Color(1.0, 0.9, 0.9)))
            else:
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.Color(1.0, 1.0, 0.9)))
        
        trades_table.setStyle(TableStyle(table_style))
        elements.append(trades_table)
    
    # Footer
    elements.append(Spacer(1, 15*mm))
    footer_text = f"Trading Signals Bot | Backtest Report | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    elements.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey
    )))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer


def get_pdf_filename(summary: BacktestSummary) -> str:
    """PDF fayl nomini yaratish"""
    return (
        f"backtest_{summary.symbol}_"
        f"{summary.signal_timeframe}_"
        f"{summary.period_start.strftime('%Y%m%d')}-"
        f"{summary.period_end.strftime('%Y%m%d')}.pdf"
    )
