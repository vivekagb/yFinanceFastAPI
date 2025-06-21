from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader, APIKey
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
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
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")
    return api_key

def serialize(obj):
    """
    Convert Python objects into JSON-serializable primitives.
    """
    # Basic primitives
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # dict → recurse
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    # list/tuple → list
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]
    # DataFrame → list of dicts
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index().where(pd.notnull(obj), None)
        return df.to_dict(orient="records")
    # Series → dict
    if isinstance(obj, pd.Series):
        return obj.where(pd.notnull(obj), None).to_dict()
    # Fallback JSON encoder
    try:
        return jsonable_encoder(obj)
    except Exception:
        return str(obj)

@app.get("/data/{method}")
async def get_data(
    method: str,
    symbols: str = Query(None, description="Comma-separated tickers"),
    symbol: str = Query(None, description="Single ticker override"),
    api_key: APIKey = Depends(verify_api_key)
):
    """
    Dynamic endpoint to fetch nested attributes/methods on yfinance.Ticker.
    Use dot-notation to access properties of returned objects.
    E.g. `/data/get_funds_data.sector_weightings` for fund weights.
    """
    # Build list of tickers
    if symbol:
        tickers = [symbol]
    elif symbols:
        tickers = [s.strip() for s in symbols.split(",") if s.strip()]
    else:
        raise HTTPException(status_code=400, detail="Provide `symbol` or `symbols` parameter.")

    results = {}
    for sym in tickers:
        try:
            ticker = yf.Ticker(sym)
            # Navigate nested parts
            parts = method.split('.')
            current = ticker
            for part in parts:
                if not hasattr(current, part):
                    raise AttributeError(f"'{type(current).__name__}' object has no attribute '{part}'")
                attr = getattr(current, part)
                current = attr() if callable(attr) else attr
            # Serialize final object
            results[sym] = serialize(current)
        except Exception as e:
            results[sym] = {"error": str(e)}

    return JSONResponse(content=jsonable_encoder(results))

@app.get("/")
async def root(api_key: APIKey = Depends(verify_api_key)):
    return JSONResponse(content=jsonable_encoder({
        "status": "YFinance Dynamic API is live",
        "usage": "GET /data/{method}?symbol=XXX or symbols=XXX,YYY",
        "note": "Use dot-notation e.g., get_funds_data.sector_weightings"
    }))
