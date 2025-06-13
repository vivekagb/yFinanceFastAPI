from fastapi import FastAPI, Security, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
import yfinance as yf
import pandas as pd
import os

app = FastAPI()

# API key setup
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")

def recs_to_records(recs: pd.DataFrame):
    """Serialize the full recommendations DataFrame to a list of dicts."""
    if recs is None or recs.empty:
        return []
    df = recs.reset_index().rename(
        columns={df.index.name or "index": "date", "Firm": "firm", "To Grade": "to_grade", "From Grade": "from_grade"}
    )
    # keep only those four columns
    return df[["date", "firm", "to_grade", "from_grade"]].to_dict(orient="records")

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
    """Return ticker.info for a single symbol (no aggregation)."""
    try:
        return yf.Ticker(symbol).info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quotes", dependencies=[Depends(verify_api_key)])
def get_quotes(symbols: str = Query(..., description="Comma-separated list of tickers")):
    """Batch-fetch ticker.info for multiple symbols (no aggregation)."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols provided")
    tickers = yf.Tickers(" ".join(syms))
    out = {}
    for s in syms:
        t = tickers.tickers.get(s)
        out[s] = t.info if t else {"error": "Ticker not found"}
    return out

@app.get("/recommendation/{symbol}", dependencies=[Depends(verify_api_key)])
def get_recommendation(symbol: str):
    """Return the full, raw history of recommendations for one symbol."""
    try:
        return recs_to_records(yf.Ticker(symbol).recommendations)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations", dependencies=[Depends(verify_api_key)])
def get_recommendations(symbols: str = Query(..., description="Comma-separated list of tickers")):
    """Batch-fetch raw recommendation histories for multiple symbols."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No symbols provided")
    out = {}
    for s in syms:
        try:
            out[s] = recs_to_records(yf.Ticker(s).recommendations)
        except Exception as e:
            out[s] = {"error": str(e)}
    return out
