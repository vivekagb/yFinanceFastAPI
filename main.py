# main.py
# FastAPI application with dynamic yfinance.Ticker method mapping

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader, APIKey
import yfinance as yf
import pandas as pd
import os

app = FastAPI(
    title="YFinance Dynamic API",
    description="Flexible endpoints mapping to yfinance.Ticker attributes and methods",
    version="1.0.0"
)

# API key configuration
API_KEY_NAME = "X-API-KEY"
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: APIKey = Depends(api_key_header)):
    """
    Dependency to verify the API key header.
    """
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")
    return api_key


def serialize(obj):
    """
    Convert pandas DataFrame or Series to Python-native structures.
    Otherwise return the object as-is.
    """
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index()
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
    if isinstance(obj, pd.Series):
        s = obj.where(pd.notnull(obj), None)
        return s.to_dict()
    return obj

@app.get("/data/{method}")
async def get_data(
    method: str,
    symbols: str = Query(None, description="Comma-separated tickers"),
    symbol: str = Query(None, description="Single ticker override"),
    api_key: APIKey = Depends(verify_api_key)
):
    """
    Dynamic endpoint to fetch any attribute or zero-arg method on yfinance.Ticker.
    """
    # Determine symbols list
    if symbol:
        sym_list = [symbol]
    elif symbols:
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    else:
        raise HTTPException(status_code=400, detail="Provide `symbol` or `symbols` parameter.")

    results = {}
    for sym in sym_list:
        try:
            ticker = yf.Ticker(sym)
            if not hasattr(ticker, method):
                raise AttributeError(f"Ticker has no attribute '{method}'")
            attr = getattr(ticker, method)
            data = attr() if callable(attr) else attr
            results[sym] = serialize(data)
        except AttributeError as ae:
            results[sym] = {"error": str(ae)}
        except Exception as e:
            results[sym] = {"error": str(e)}
    return results

@app.get("/")
async def root(api_key: APIKey = Depends(verify_api_key)):
    """
    Health-check and dynamic endpoint info.
    """
    return {
        "status": "YFinance Dynamic API is live",
        "dynamic_endpoint": "/data/{method}?symbols=... or &symbol=...",
        "note": "`method` corresponds to any yfinance.Ticker property or zero-arg method"
    }
