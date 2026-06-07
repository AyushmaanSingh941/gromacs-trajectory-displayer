streamlit>=1.38
pandas>=2.0
numpy>=1.24
plotly>=5.20
scipy>=1.11
kaleido>=0.2.1
reportlab>=4.0
pytest>=7.4

# NOTE on kaleido: newer kaleido (v1+) needs a local Chrome install to
# render PNG/SVG/PDF exports. After installing requirements, run:
#     plotly_get_chrome
# once, or the export buttons in the app will show a friendly error
# instead of crashing. Everything else (markdown report, CSV export,
# on-screen charts) works fine without it.
