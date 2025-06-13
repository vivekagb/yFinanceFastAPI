from fastapi import FastAPI, Security, HTTPException, Depends
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
    return {"status": "YFinance API is live", "usage": "/quote/{symbol}"}

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
