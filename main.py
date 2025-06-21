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
    Convert Python objects into JSON-serializable primitives:
    - Native types (str, int, float, bool, None)
    - dict, list, tuple (recursive)
    - pandas DataFrame / Series
    - yfinance FundsData and other objects with __dict__
    """
    # Native Python primitives
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    # dict → recurse
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}

    # list/tuple → recurse into list
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]

    # pandas DataFrame → list of dicts
    if isinstance(obj, pd.DataFrame):
        df = obj.reset_index()
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")

    # pandas Series → dict
    if isinstance(obj, pd.Series):
        s = obj.where(pd.notnull(obj), None)
        return s.to_dict()

    # Objects with __dict__ (e.g., yfinance FundsData)
    if hasattr(obj, "__dict__"):
        result = {}
        for k, v in obj.__dict__.items():
            if k.startswith("_"):
                continue
            # include only basic or known collections
            if isinstance(v, (str, int, float, bool)) or v is None or isinstance(v, (dict, list, tuple, pd.DataFrame, pd.Series)):
                result[k] = serialize(v)
        if result:
            return result

    # Namedtuple-like with _asdict()
    if hasattr(obj, "_asdict") and callable(obj._asdict):
        try:
            return serialize(obj._asdict())
        except Exception:
            pass

    # Fallback to jsonable_encoder (handles numpy, datetime, dataclass, etc.)
    try:
        return jsonable_encoder(obj)
    except Exception:
        # Last resort: string form
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
    # Build list of tickers
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

    # Return JSON-serializable response
    return JSONResponse(content=jsonable_encoder(results))

@app.get("/")
async def root(api_key: APIKey = Depends(verify_api_key)):
    """
    Health-check and dynamic endpoint info.
    """
    info = {
        "status": "YFinance Dynamic API is live",
        "dynamic_endpoint": "/data/{method}?symbols=... or &symbol=...",
        "note": "`method` corresponds to any yfinance.Ticker property or zero-arg method"
    }
    return JSONResponse(content=jsonable_encoder(info))
