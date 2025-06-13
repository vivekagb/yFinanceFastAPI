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

# Helper to serialize recommendations DataFrame
def recs_to_records(recs: pd.DataFrame):
    if recs is None or recs.empty:
        return []
    df = recs.copy()
    # reset index (date)
    df = df.reset_index()
    # ensure column names
    date_col = df.columns[0]
    df = df.rename(columns={date_col: "date", "Firm": "firm", "To Grade": "to_grade", "From Grade": "from_grade"})
    return df.to_dict(orient="records")

@app.get("/recommendation/{symbol}", dependencies=[Depends(verify_api_key)])
def get_recommendation(symbol: str):
    """
    Return the full history of analyst recommendations for a single symbol.
    """
    try:
        ticker = yf.Ticker(symbol)
        recs = ticker.recommendations
        return recs_to_records(recs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recommendations", dependencies=[Depends(verify_api_key)])
def get_recommendations(
    symbols: str = Query(..., description="Comma-separated list of tickers, e.g. AAPL,INFY.NS,RELIANCE.BO")
):
    """
    Batch-fetch the full recommendations history for multiple symbols.
    Returns a dict mapping each symbol to a list of recommendation records.
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    result = {}
    for sym in sym_list:
        try:
            ticker = yf.Ticker(sym)
            recs = ticker.recommendations
            result[sym] = recs_to_records(recs)
        except Exception as e:
            result[sym] = {"error": str(e)}
    return result

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {
        "status": "YFinance API is live",
        "usage": "/quote/{symbol}, /quotes?symbols=...",
        "recommendation": "/recommendation/{symbol}",
        "recommendations": "/recommendations?symbols=..."
    }

@app.get("/quote/{symbol}", dependencies=[Depends(verify_api_key)])
def get_quote(symbol: str):
    """
    Existing endpoint: fetch info for a single symbol.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info.copy()
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quotes", dependencies=[Depends(verify_api_key)])
def get_quotes(
    symbols: str = Query(..., description="Comma-separated list of tickers, e.g. AAPL,INFY.NS,RELIANCE.BO")
):
    """
    Existing bulk endpoint: batch-fetch info for multiple symbols.
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    tickers = yf.Tickers(" ".join(sym_list))
    result = {}
    for sym in sym_list:
        t = tickers.tickers.get(sym)
        if not t:
            result[sym] = {"error": "Ticker not found"}
            continue
        info = t.info.copy()
        result[sym] = info
    return result
