# gromacs-trajectory-displayer

Interactive Streamlit dashboard for displaying and exploring GROMACS molecular dynamics trajectories

gromacs-trajectory-displayer is designed to be simple and extensible, focusing on fast, clear visual inspection of molecular dynamics trajectories and basic exploratory workflows. It works with common GROMACS formats and provides an interactive UI for quick analysis and export of parsed data.

Features
- Upload and display .xvg or .txt trajectory files from GROMACS
- Interactive Plotly visualizations (Line, Scatter, Area charts)
- Adjust chart options: markers, downsampling, column selection
- View frame count, time range, and summary statistics (mean, min, max)
- Export parsed data as CSV for downstream analysis
- Dark theme optimized for data visualization
- Minimal, extensible codebase so additional importers, viewers, or analysis modules can be added

Quick start
1. Install Python 3.8+
2. Clone and setup

   git clone https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer.git
   cd gromacs-trajectory-displayer

3. Create a virtual environment

   python -m venv venv
   source venv/bin/activate        # macOS/Linux
   # or
   venv\Scripts\activate         # Windows

4. Install dependencies

   pip install -r requirements.txt

5. Run

   streamlit run app.py

The app will open at http://localhost:8501

Usage
- Click "Upload a GROMACS .xvg file" in the sidebar
- Select your .xvg or .txt file
- Customize visualization:
  - Choose chart type (Line, Scatter, Area)
  - Toggle data point markers
  - Downsample data for faster rendering
  - Select which columns to plot
- View statistics and download the parsed data as CSV

Supported formats
- .xvg (XMGrace / GROMACS plot format)
  - Native GROMACS output format. Includes header lines:
    - Lines beginning with `#` are comments and are skipped
    - Lines beginning with `@` are plot directives (axis labels, legends) and are parsed or skipped
    - Data lines: whitespace-separated numeric values
- .txt (plain text)
  - Same structure as .xvg but with a .txt extension

Example file format

```
# GROMACS trajectory output
@ title "Potential Energy"
@ xaxis label "Time (ps)"
@ yaxis label "Energy (kJ/mol)"
@ s0 legend "Total"

0.00     -412345.678
0.01     -412300.123
0.02     -412280.456
```

Dependencies
- streamlit (1.32.0) - Web framework
- pandas (2.2.1) - Data tables
- numpy (1.26.4) - Numerical operations
- plotly (5.19.0) - Interactive charts

System requirements
- Python 3.8 or higher
- 512 MB RAM minimum (2 GB recommended for large files)
- ~500 MB disk space for dependencies
- Modern web browser

Troubleshooting

"Module not found" errors

- Activate the virtual environment: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

Slow rendering with large files

- Use the "Display every Nth frame" slider to downsample visualization
- Try values of 5–10 for files with >50k frames
- Note: the full dataset is still used for summary statistics unless otherwise indicated

File upload fails

- Verify the file is a valid .xvg or .txt file
- Ensure the file contains numeric data in columns
- Confirm headers (if present) start with `#` or `@`

"Address already in use" error

- Wait 1–2 minutes for the previous Streamlit server to time out, or run on another port:

  streamlit run app.py --server.port 8502

Installation details

See docs/INSTALLATION.md for:
- Platform-specific instructions (Windows, macOS, Linux)
- Docker setup
- Development installation
- Common issues and fixes

Contributing

See CONTRIBUTING.md for guidelines on:
- Reporting issues
- Contributing code
- Testing changes
- Code style standards

Publication information

See docs/PUBLICATION.md for:
- Research context and motivation
- Technical specifications
- Performance metrics
- Validation and testing
- F1000 submission details

License

MIT License. See LICENSE file.

Citation

```
@software{singh2026gromacs,
  title={GROMACS Trajectory Displayer},
  author={Singh, Ayushman},
  year={2026},
  url={https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer}
}
```
