# Water Quality Dashboard (hackathon prototype)

Streamlit dashboard to explore water-quality measurements against reference thresholds, with plain-language
AI explanations. Runs out of the box on a **synthetic demo dataset** - no external API needed.

> The bundled data is invented and the bundled thresholds are **illustrative, not regulatory limits**.
> Nothing here says water is safe or unsafe.

## Setup
```bash
# inside your project folder, with your virtual environment active
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env   (then edit; .env is git-ignored)
streamlit run app.py
```
The app works without an API key; only the **Explain My Results** button needs one.

## Configuration (environment variables, `.env`, or `.streamlit/secrets.toml`)
| Name | Purpose |
|---|---|
| `OPENAI_API_KEY` | enables AI summaries |
| `OPENAI_MODEL` | model name (falls back to `DEFAULT_MODEL` in `src/ai_summary.py`) |
| `LIVE_DATA_URL`, `LIVE_DATA_API_KEY` | optional: a JSON endpoint you trust that returns records with the required fields |

## Project layout
- `app.py` - UI only (sidebar, tabs, wiring)
- `src/threshold_validation.py` - deterministic status logic (Within / Below / Above / Missing / Cannot assess)
- `src/data_loader.py` - CSV/live loading and data-quality validation
- `src/analysis.py` - filters, metrics, statistics, AI payload
- `src/visualizations.py` - Plotly charts and the Folium map
- `src/ai_summary.py` - OpenAI call (the only provider-specific function is `_call_model`)
- `data/` - sample measurements and threshold CSVs; `tests/` - unit tests

## Using your own thresholds
Upload a CSV with columns `parameter, minimum_value, maximum_value, unit, reference_name, source_organization,
source_url, applicability_notes` (blank min or max = one-sided). Add `is_verified` (true/false) if some rows
are unverified. Units must match the measurement unit exactly - nothing is converted.

## Tests
```bash
python -m pytest
```

## Demo script
1. Overview: note demo banners, assessed vs cannot-assess counts.
2. Map: click Demo Site B (mixed results), read the popup, view its chart.
3. Analytics: pick *Nitrate*, see the limit line, regional counts, gaps for missing data.
4. Untick "Use illustrative demo thresholds" - everything becomes "Cannot assess", as it should.
5. AI Insights: press *Explain My Results* (with a key), then expand "Exactly what is sent".
6. Details: download the filtered CSV.
