# Water Quality Observatory

An interactive descriptive-analysis dashboard for groundwater and surface-water observations in Bangalore Urban and Bangalore Rural. The application keeps each source CSV row as its own sample, preserves missing values, and links every value back to its dataset and source row. It does not use machine learning, forecasting, imputation, or fabricated measurements.

## Project architecture

- `water_quality/data.py` reads the original CSVs in `data/`, filters the two project districts at runtime, parses dates and values, retains blank measurement cells, and produces data-quality summaries.
- `water_quality/api.py` builds reusable filtered API responses for observations, statistics, stations, comparison, trends, biological summaries, heatmaps, standards assessment, and data quality.
- `water_quality/server.py` serves the JSON API and static dashboard with Python's standard library. There is no database.
- `web/index.html` is a responsive browser dashboard. Leaflet displays station measurements on OpenStreetMap tiles; Plotly renders charts. Both browser libraries are loaded from CDNs.
- `standards.json` contains configurable BIS and CPCB parameter criteria and their references.

The dashboard reads the original `data/` CSVs, rather than the earlier `cleaned_data_blr/` or `imputed_data_blr/` outputs. This retains sparse parameter columns and excludes the earlier dataset-wide imputation results. Source files are never modified.

## Run locally

Python 3.10 or newer is required. There are no Python package dependencies; `requirements.txt` is intentionally empty. The browser needs internet access to load Leaflet, Plotly, and OpenStreetMap tiles.

From this directory:

```bash
python3 -m water_quality.server
```

Then open <http://127.0.0.1:8000>. Stop the server with Ctrl+C.

## Dashboard features

- Overview cards for source rows, monitoring stations, water source, and parameter coverage.
- Separate groundwater and surface-water analysis, plus chemical, physical, and biological views.
- District and sample-date filters, parameter and station selectors, descriptive statistics, distributions, and historical observations.
- Parameter-specific point maps with value-scaled station markers, sample details, and dataset provenance. The map does not draw an interpolated surface.
- Source, district, station, category, agency, and date comparisons. Different units remain in separate groups.
- Parameter-level assessment profiles for groundwater screening against BIS IS 10500 and for CPCB surface-water Classes A–E. Surface-water class is never assumed. Results are not an overall safety declaration.
- Data-quality reporting for source rows, district scope, missing values, duplicate signatures, invalid coordinates, date parsing, and numeric parsing.

## API endpoints

All endpoints return JSON. Common filters include `water_source`, `category`, `parameter`, `parameter_key`, `station_id`, `station`, `district`, `location`, `start_date`, and `end_date`. Use `parameter_key` to select a particular parameter and unit together.

| Endpoint | Purpose |
|---|---|
| `GET /api/health/` | Server and loaded sample status |
| `GET /api/dashboard/overview/` | Overview totals and recent observations |
| `GET /api/water-sources/` | Source categories and record counts |
| `GET /api/parameters/` | Available parameters, units, categories, and dataset sources |
| `GET /api/stations/` | Filtered station locations and coverage |
| `GET /api/observations/?limit=100&offset=0` | Paginated observations |
| `GET /api/observations/{station_id}/` | Observations for a site |
| `GET /api/statistics/` | Count, mean, median, min, max, standard deviation, quartiles, missingness |
| `GET /api/heatmap/?water_source=...&parameter_key=...` | GeoJSON point measurements for the latest observation per station in the date range |
| `GET /api/comparison/?parameter_key=...&compare_by=water_source` | Unit-aware group summaries |
| `GET /api/trends/?parameter_key=...` | Actual time-stamped observations, without smoothing |
| `GET /api/standards/` | Configured criteria profiles |
| `GET /api/assessment/?profile=...` | Parameter-level criteria results |
| `GET /api/biological/` | Biological parameter and positive-value summaries |
| `GET /api/data-quality/` | Dataset-wise processing and quality report |

## Data scope and interpretation

The source directory currently has 16 CSVs. The dashboard includes the rows whose `District` is Bangalore Urban or Bangalore Rural and reports the number of statewide rows outside that scope. Parameter observations from separate files remain separate, even when station, date, and coordinates match; no cross-file sample merge is inferred. Dates are parsed from the source date strings while the original date and dataset filename remain available.

Blank cells and common null markers are kept as missing. They are not treated as zero. Statistics use numeric measurements only. A qualitative or malformed value is not coerced to a number. Invalid dates and coordinates remain in the data-quality report and are excluded only from views that require valid dates or map coordinates.

The available data does not identify every laboratory method needed to apply every reference criterion. Unsupported method comparisons (including BOD where the 5-day, 20°C method is not documented) are reported as not assessed. CPCB designated-use criteria are profile-specific. BIS screening is for drinking-water parameters only. Passing the available parameter checks cannot establish complete drinking-water safety.

## Validation

Run the automated checks from this directory:

```bash
python3 -m unittest discover -s tests -v
```

The checks cover CSV ingestion and district scoping, row provenance, missing-value behavior, descriptive statistics, API filtering and pagination, assessment outcomes, and loading the project datasets.

