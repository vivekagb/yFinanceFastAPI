from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader, APIKey
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from yfinance import Tickers
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
        df = obj.reset_index()
        # replace NaN with None so JSON nulls are used
        df = df.where(pd.notnull(df), None)
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

    # Batch-load all tickers in one go
    batch = Tickers(" ".join(tickers))

    # Dynamically navigate into the desired attribute/method on the batch object
    parts = method.split('.')
    current = batch
    for part in parts:
        if not hasattr(current, part):
            raise HTTPException(
                status_code=400,
                detail=f"'{type(current).__name__}' object has no attribute '{part}'"
            )
        current = getattr(current, part)
        current = current() if callable(current) else current

    results = {}
    # If it's a DataFrame with a MultiIndex (ticker as level 0), split per symbol
    if isinstance(current, pd.DataFrame) and isinstance(current.index, pd.MultiIndex):
        for sym in tickers:
            try:
                sub_df = current.xs(sym, level=0)
                results[sym] = serialize(sub_df)
            except KeyError:
                results[sym] = {"error": f"No data found for {sym}"}
    else:
        # Fallback: same result for every ticker
        serial = serialize(current)
        for sym in tickers:
            results[sym] = serial

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/")
async def root(api_key: APIKey = Depends(verify_api_key)):
    return JSONResponse(content=jsonable_encoder({
        "status": "YFinance Dynamic API is live",
        "usage": "GET /data/{method}?symbol=XXX or symbols=XXX,YYY",
        "note": "Use dot-notation e.g., get_funds_data.sector_weightings"
    }))
