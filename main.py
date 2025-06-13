# main.py
from fastapi import FastAPI, Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
import yfinance as yf
import os

app = FastAPI()
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

@app.get("/", dependencies=[Depends(verify_api_key)])
def root():
    return {"status": "live"}

@app.get("/quote/{symbol}", dependencies=[Depends(verify_api_key)])
def get_quote(symbol: str):
    ticker = yf.Ticker(symbol)
    return ticker.info
