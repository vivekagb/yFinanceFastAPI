from fastapi import FastAPI
import yfinance as yf

app = FastAPI()

@app.get("/")
def root():
    return {"status": "YFinance API is live", "usage": "/quote/{symbol}"}

@app.get("/quote/{symbol}")
def get_quote(symbol: str):
    ticker = yf.Ticker(symbol)
    return ticker.info
