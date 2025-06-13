from fastapi import FastAPI, Security, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
import yfinance as yf
import pandas as pd
import os

app = FastAPI()

# Retrieve the API key from environment
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")


def recs_to_records(recs: pd.DataFrame):
    """
    Serialize full yfinance recommendations DataFrame to list of dicts:
    fields: date, firm, to_grade, from_grade
    """
    if recs is None or recs.empty:
        return []
    # Reset index to turn the Date index into a column
    df = recs.reset_index()
    # Build rename map based on case-insensitive matching
    col_map = {}
    # Original index column becomes 'date'
    idx_col = df.columns[0]
    col_map[idx_col] = 'date'
    for col in df.columns[1:]:
        lc = col.lower().replace('_', ' ').strip()
        if lc == 'firm':
            col_map[col] = 'firm'
        elif 'to grade' in lc.replace('\n',' '):
            col_map[col] = 'to_grade'
        elif 'from grade' in lc.replace('\n',' '):
            col_map[col] = 'from_grade'
    df = df.rename(columns=col_map)
    # Ensure the four columns exist
    required = ['date', 'firm', 'to_grade', 'from_grade']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing rec columns after rename: {missing}")
    return df[required].to_dict(orient="records")

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {
        "status": "YFinance API is live",
        "endpoints": [
            "/quote/{symbol}",
            "/quotes?symbols=...",
            "/recommendation/{symbol}",
            "/recommendations?symbols=..."
        ]
    }

@app.get("/quote/{symbol}", dependencies=[Depends(verify_api_key)])
def get_quote(symbol: str):
    """
    Return ticker.info for a single symbol.
    """
    try:
        return yf.Ticker(symbol).info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quotes", dependencies=[Depends(verify_api_key)])
def get_quotes(symbols: str = Query(..., description="Comma-separated list of tickers")):
    """
    Batch-fetch ticker.info for multiple symbols.
    Returns dict: symbol -> info dict.
    """
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols provided")
    tickers = yf.Tickers(" ".join(syms))
    result = {}
    for s in syms:
        t = tickers.tickers.get(s)
        result[s] = t.info if t else {"error": "Ticker not found"}
    return result

@app.get("/recommendation/{symbol}", dependencies=[Depends(verify_api_key)])
def get_recommendation(symbol: str):
    """
    Return full recommendation history for one symbol.
    """
    try:
        recs = yf.Ticker(symbol).recommendations
        return recs_to_records(recs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations", dependencies=[Depends(verify_api_key)])
def get_recommendations(symbols: str = Query(..., description="Comma-separated list of tickers")):
    """
    Batch-fetch full recommendation histories for multiple symbols.
    Returns dict: symbol -> list of rec record dicts.
    """
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols provided")
    result = {}
    for s in syms:
        try:
            recs = yf.Ticker(s).recommendations
            result[s] = recs_to_records(recs)
        except HTTPException as he:
            result[s] = {"error": he.detail}
        except Exception as e:
            result[s] = {"error": str(e)}
    return result
