# main.py
# FastAPI application for serving Yahoo Finance data and raw analyst recommendation histories

from fastapi import FastAPI, Security, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
import yfinance as yf
import pandas as pd
import os

app = FastAPI(
    title="YFinance Dynamic API",
    description="Flexible endpoints mapping to yfinance.Ticker attributes and methods",
    version="1.0.0"
)

# API key configuration
API_KEY = os.getenv("API_KEY")  # Set this environment variable
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def verify_api_key(api_key: str = Depends(Security(api_key_header))):
    """
    Verify that the provided X-API-KEY header matches the expected API key.
    """
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")


def serialize(obj):
    """
    Convert pandas DataFrame or Series to Python-native structures.
    Otherwise, return the object as-is.
    """
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index()
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        s = obj.where(pd.notnull(obj), None)
        return s.to_dict()
    return obj

@app.get("/data/{method}", dependencies=[Depends(verify_api_key)])
def get_data(
    method: str,
    symbols: str = Query(None, description="Comma-separated list of tickers, e.g. AAPL,INFY.NS"),
    symbol: str = Query(None, description="Single ticker override, e.g. AAPL")
):
    """
    Dynamic endpoint to fetch any attribute or zero-arg method on yfinance.Ticker.

    - If `symbol` provided, queries a single ticker.
    - Otherwise, `symbols` (comma-separated) for bulk.
    - Maps each symbol to getattr(ticker, method) or ticker.method().
    """
    # Determine list of symbols
    if symbol:
        sym_list = [symbol.strip()]
    elif symbols:
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    else:
        raise HTTPException(status_code=400, detail="Must provide either `symbol` or `symbols` query parameter.")

    results = {}
    for sym in sym_list:
        try:
            ticker = yf.Ticker(sym)
            # Retrieve attribute or method
            if not hasattr(ticker, method):
                raise AttributeError(f"Ticker has no attribute '{method}'")
            attr = getattr(ticker, method)
            # Call if callable (no args), else return attribute
            data = attr() if callable(attr) else attr
            results[sym] = serialize(data)
        except AttributeError as ae:
            results[sym] = {"error": str(ae)}
        except Exception as e:
            results[sym] = {"error": str(e)}
    return results

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    """
    Health-check and dynamic endpoint info.
    """
    return {
        "status": "YFinance Dynamic API is live",
        "dynamic_endpoint": "/data/{method}?symbols=... or &symbol=...",
        "note": "`method` corresponds to any yfinance.Ticker property or zero-arg method"
    }
