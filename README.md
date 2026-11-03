# AquaInsight - Water Quality Assessment

A beginner-friendly Streamlit dashboard for exploring water-quality measurements
against CPCB Designated Best Use criteria.

## Run locally

```powershell
cd Water_Q_Assesment
python -m pip install -r requirements.txt
streamlit run app.py
```

The initial app uses a small illustrative dataset so that every page works
immediately. Replace `demo_data()` in `app.py` with cleaned laboratory data
before using the dashboard for real decisions. Missing and non-applicable
measurements are kept separate from exceedances.

## Pages

- Overview: headline metrics, status counts, exceedances and recent samples
- Regional Analysis: compare average readings across monitoring locations
- Parameter Analysis: inspect a parameter over time
- CPCB Comparison: view class-specific criteria and sample-level status
- Trends: compare multiple parameters across sampling dates
- Reports: download filtered CSV and Excel results