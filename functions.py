import ccxt
import pandas as pd
import numpy as np
import json
import requests
from bs4 import BeautifulSoup
import time
import datetime
from pytz import timezone
import os

# 환율 파싱 함수(크롤링, 1시간 주기 업데이트)
def dwrate():
  response = requests.get("https://finance.naver.com/marketindex/")
  content = BeautifulSoup(response.content, 'html.parser')
  containers = content.find('span', {'class': 'value'})
  usd_krw = float(containers.text.replace(',',''))
  return usd_krw

# RSI 계산 함수
def rsi(ohlc: pd.DataFrame, period: int = 14):
    delta = ohlc["close"].diff()
    ups, downs = delta.copy(), delta.copy()
    ups[ups < 0] = 0
    downs[downs > 0] = 0

    AU = ups.ewm(com = period-1, min_periods = period).mean()
    AD = downs.abs().ewm(com = period-1, min_periods = period).mean()
    RS = AU/AD

    return pd.Series(100 - (100/(1 + RS)), name = "RSI")

# 선물 포지션 open 함수
def open_position(exchange, amount, side="long", symbol="BTC/USDT:USDT"):
  if side=="long":
    response = exchange.create_order(
    symbol=symbol,type='market',side='buy',amount=amount,
    params={'marketType': 'swap'})

  elif side=='short':
    response = exchange.create_order(
    symbol=symbol,type='market',side='sell',amount=amount,
    params={'marketType': 'swap'})

  return response

# 선물 포지션 close 함수
def close_position(exchange, amount, symbol="BTC/USDT:USDT"):
    try:
      response = exchange.create_order(
      symbol=symbol,type='market',side='sell',amount=amount,
      params={'marketType': 'swap', 'reduceOnly': True})

      return response
    except:
      pass

    try:
      response = exchange.create_order(
      symbol=symbol,type='market',side='buy',amount=amount,
      params={'marketType': 'swap', 'reduceOnly': True})

      return response
    except:
      pass

    return None

# 현재 한국 시간 파싱(로그 작성용)
def get_time():
  today = datetime.datetime.now(timezone('Asia/Seoul'))
  return str(today.date())+" "+":".join([f"{today.hour:02d}", f"{today.minute:02d}", f"{today.second:02d}"])

# 현재 비트코인(선물) 가격 가져오기
def get_current_price(exchange, symbol="BTC/USDT:USDT"):
  curr_price = exchange.fetch_ticker(symbol)['ask']
  return curr_price

# 실시간 RSI 검출(계산)
def get_RSI(exchange, tframe = "1m", symbol="BTC/USDT:USDT", period=14):
  klines = exchange.fetch_ohlcv(symbol, timeframe=tframe)
  df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'vol'])

  RSI = rsi(df, period=period).iloc[-1]
  return RSI

# 매매 상태 전환 함수
def ck_time(s_time, e_time):
  s_t = int(s_time.split(":")[0])*60+int(s_time.split(":")[1])
  e_t = int(e_time.split(":")[0])*60+int(e_time.split(":")[1])

  today = get_time()
  c_t = today.split(" ")[1].split(":")
  c_time = int(c_t[0])*60+int(c_t[1])

  if c_time >= 23*60+59: # 날짜 바뀌는 시간
    return 2
  if s_t<=c_time and c_time<e_t: # 매매 시간
    return 1
  elif c_time>=e_t: # 종료 시간
    return -1
  else: # 시작 전 시간
    return 0

# 기존 체결된 포지션이 있는지 확인하는 함수
def ck_exist_pos(exchange):
  positions = exchange.fetch_positions()
  for pos in positions:
    if pos['info']['available'] != '0':
      return 1,pos
  return 0,None

# 포지션 따른 수익률 계산 함수
def cal_PIR(e_price, c_price, leverage, pos="long"):
  delta = c_price - e_price
  f = 0.0004
  pm = 1 if (pos=="long") else -1
  RR = pm*((c_price/e_price-1)) - 2*f
  return RR # Return with trade-fee

# 최소 주문 금액에 맞춰 long 포지션 개설 가능한 주문량 구하는 함수

def cal_amount(money, curr_price, min_amount = 0.001):
  return min_amount*int(money/curr_price/min_amount)

# 매매시 해당 기록 로그로 남기는 함수
def save_log(Time, Pos, Price, Amount, Income):
  print(log)
  #~~~

# 현재 가용 잔고(선물지갑) 확인 함수
def get_balance(exchange):
  balance = exchange.fetch_balance()
  f_money = float(balance['info'][0]['maxTransferOut'])
  return f_money

def time_is_valid(timeformat):
  h,m = map(int,timeformat.split(":"))
  if h>=0 and h<=24 and m>=0 and m<60:
    return 1
  else:
    return 0

def Set_Env():
  fpath = "./Data/"
  fname = "UserInfo.json"
  fname2 = "PrevData.json"
  fname3 = "TradeLog.xlsx"
  try:
    os.mkdir(fpath)
  except:
    pass
  if not(os.path.exists(fpath+fname)):
    usr_info = {'api_key':'Insert_Your_Own_API_KEY_Here',
                'secret_key':'Insert_Your_Own_SECRET_KEY_Here',
                'pw':'Insert_Your_Own_PASSWORD_Here'}
    with open(fpath+fname, 'w') as f:
        json.dump(usr_info, f)

  if not(os.path.exists(fpath+fname2)):
    prev_data = { 'timeframe':'5m',
                  'period': 6,
                  'leverage': 1,
                  'threshold': 15,
                  'cond': 1.0,
                  'capital': 100,
                  'max_lose': 2,
                  'target': 80,
                  'sTime': "10:00",
                  'eTime': "22:00",
                  "tot_earned":0}
    with open(fpath+fname2, 'w') as f:
        json.dump(prev_data, f)

  if not (os.path.exists(fpath+fname3)):
    log_excel = pd.DataFrame(columns=["Time","Action","Leverage","Amount","Price","Earned"])
    log_excel.to_excel(fpath+fname3, index=False)

def Save_Log_AS_EXCEL(new_log):
    fpath = "./Data/"
    fname = "TradeLog.xlsx"

    log = pd.read_excel(fpath+fname)
    log.loc[len(log)] = new_log
    log.to_excel(fpath+fname,index=False)

def Save_prev_setting(prev_data):
    fpath = "./Data/"
    fname = "PrevData.json"
    with open(fpath+fname, 'w') as f:
        json.dump(prev_data, f)

def Load_prev_setting():
    fpath = "./Data/"
    fname = "PrevData.json"
    with open(fpath+fname, 'r') as f:
        prev_data = json.load(f)
    return prev_data