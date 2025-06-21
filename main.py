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
    Convert pandas DataFrame, Series, yfinance fund objects, or other types to serializable structures.
    """
    # DataFrame → list-of-dicts
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index().where(pd.notnull(obj), None)
        return df.to_dict(orient="records")

    # Series → dict
    if isinstance(obj, pd.Series):
        return obj.where(pd.notnull(obj), None).to_dict()

    # yfinance FundsData (has to_dict)
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            return obj.to_dict()
        except Exception:
            pass

    # NamedTuple-like (e.g., _asdict)
    if hasattr(obj, "_asdict") and callable(obj._asdict):
        try:
            return obj._asdict()
        except Exception:
            pass

    # Last-resort JSON encoding for numpy types, dataclasses, etc.
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
    Dynamic endpoint to fetch any attribute or zero-arg method on yfinance.Ticker.
    """
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
            raw = attr() if callable(attr) else attr
            results[sym] = serialize(raw)
        except AttributeError as ae:
            results[sym] = {"error": str(ae)}
        except Exception as e:
            results[sym] = {"error": str(e)}

    # Return a fully JSON-serializable response
    return JSONResponse(content=jsonable_encoder(results))


@app.get("/")
async def root(api_key: APIKey = Depends(verify_api_key)):
    """
    Health-check and dynamic endpoint info.
    """
    return JSONResponse(content=jsonable_encoder({
        "status": "YFinance Dynamic API is live",
        "dynamic_endpoint": "/data/{method}?symbols=... or &symbol=...",
        "note": "`method` corresponds to any yfinance.Ticker property or zero-arg method"
    }))
