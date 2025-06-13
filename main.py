from fastapi import FastAPI
import yfinance as yf

app = FastAPI()

@app.get("/quote/{symbol}")
def get_quote(symbol: str):
    ticker = yf.Ticker(symbol)
    return ticker.info
