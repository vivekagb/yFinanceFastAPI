from fastapi import FastAPI, Security, HTTPException, Depends, Query
from fastapi.security.api_key import APIKeyHeader
import yfinance as yf
import os

app = FastAPI()

# Retrieve the API key from environment variable
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

# Dependency to verify API key
async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {"status": "YFinance API is live", "usage": "/quote/{symbol} or /quotes?symbols=AAPL,INFY"}

@app.get("/quote/{symbol}", dependencies=[Depends(verify_api_key)])
def get_quote(symbol: str):
    """
    Fetch and return information for the given symbol using yfinance.
    """
    try:
        ticker = yf.Ticker(symbol)
        return ticker.info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quotes", dependencies=[Depends(verify_api_key)])
def get_quotes(
    symbols: str = Query(..., description="Comma-separated list of tickers, e.g. AAPL,INFY.NS,RELIANCE.BO")
):
    """
    Batch-fetch info for multiple symbols at once.
    Returns a dict mapping each symbol to its yfinance.info (or an error message).
    """
    # Clean and split the symbols list
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    try:
        # Use yfinance.Tickers to fetch all in one go
        tickers = yf.Tickers(" ".join(symbol_list))
        result = {}
        for sym in symbol_list:
            try:
                info = tickers.tickers[sym].info or {}
                result[sym] = info
            except Exception as ex:
                # capture individual symbol errors
                result[sym] = {"error": str(ex)}
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch fetch failed: {e}")
