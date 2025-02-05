import ccxt
import pandas as pd
import numpy as np
import json
import requests
from bs4 import BeautifulSoup
import time
import datetime
from pytz import timezone
import functions as func
import json

import os
import sys
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QToolTip
from PyQt5.QtCore import QTimer

form_class = uic.loadUiType("./Auto_Trader_GUI_final.ui")[0]
func.Set_Env()


class WindowClass(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Bitget: Auto Trading System - by.조성운 고수')

        prev_data = func.Load_prev_setting()
        self.Load_Setting(prev_data)
        self.tot_earned = float(self.T_profit.toPlainText())

        with open('./Data/UserInfo.json', 'r') as f:
            usrinfo = json.load(f)

        self.api_key = usrinfo['api_key']
        self.secret_key = usrinfo['secret_key']
        self.pw = usrinfo['pw']

        self.DWRate = func.dwrate()

        self.loginTimer = QTimer(self)
        self.timer = QTimer(self)
        self.DWtimer = QTimer(self)

        self.loginTimer.timeout.connect(self.LogIn)
        self.timer.timeout.connect(self.Load_RSI_n_PRICE)
        self.DWtimer.timeout.connect(self.GetDW)
        self.ck_box1.stateChanged.connect(self.CkBox)
        self.ck_box2.stateChanged.connect(self.CkBox)

        self.start_btn.clicked.connect(self.StartClick)
        self.reset_btn.clicked.connect(self.ResetClick)
        self.refresh_btn.clicked.connect(self.RefreshAccount)
        self.status = 0
        self.t_status = 0
        self.symbol = "BTC/USDT:USDT"

        self.munit = 0 #0:$, 1:won
        self.numf = 0 #0:wo , / 1:with ,

        self.period = 14
        self.lose_num = 0 #당일 이득 본 매매 횟수
        self.win_num = 0 #당일 손해 본 매매 수

        self.RSI_V = 0
        self.n_error = 0

        self.daily_earned = 0
        self.Set_ToolTip()
        self.LogIn()

    def LogIn(self):
        self.exchange = ccxt.bitget({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'password': self.pw,
            "options": {'defaultType': 'swap', 'adjustForTimeDifference': True},
            "enableRateLimit": True})
        self.market = self.exchange.load_markets()

    def Set_ToolTip(self):
        self.label_timeframe.setToolTip('캔들 길이: 1분봉~1주봉')
        self.label_period.setToolTip('RSI 길이')
        self.label_leverage.setToolTip('레버리지 1배~125배')
        self.label_threshold.setToolTip('매수 RSI 조건')
        self.label_cond.setToolTip('매수/매도 수익')
        self.label_cap.setToolTip('매매 사용 자본($)')
        self.label_mlose.setToolTip('일 최대 손절 횟수')
        self.label_target.setToolTip('일 목표 금액')
        self.label_stime.setToolTip('매매 시작 시간')
        self.label_etime.setToolTip('매매 종료 시간')

        self.label_oprice.setToolTip('매수 체결 가격')
        self.label_margin.setToolTip('마진 금액(매매 실사용 금액)')
        self.label_cprice.setToolTip('코인 현재 가격')
        self.label_return.setToolTip('현시점 기준 수익률(수수료 포함)')
        self.label_profit.setToolTip('현시점 기준 수익$(수수료 포함)')
        self.label_account.setToolTip('계좌 내 사용 가능 금액')

    def GetDW(self):
        self.DWRate = float(func.dwrate())

    def RefreshAccount(self):
        self.acc_money = round(func.get_balance(self.exchange),2)
        self.acc_money_txt.setText(self.SetNum(self.acc_money))
        self.RefreshWL()

    def CkBox(self):
        if self.ck_box1.isChecked():
            self.munit = 1
        elif not self.ck_box1.isChecked():
            self.munit = 0
        if self.ck_box2.isChecked():
            self.numf = 1
        elif not self.ck_box2.isChecked():
            self.numf = 0

    def SetNum(self, num):
        if self.munit == 0:
            if self.numf==1:
                if num<1:
                    return f"{num:.3f} $"
                num = format(num,",")
            num = str(num)+" $"
        else:
            n = int(num*self.DWRate)
            if self.numf==1:
                if n<1:
                    return f"{n} W"
                n = format(n,",")
            num = str(n)+" W"
        return num

    def Load_RSI_n_PRICE(self):
        try:
            rsi = func.get_RSI(self.exchange,tframe=self.tframe, period=self.period)
            self.RSI_V = rsi
            is_err = -1
        except:
            rsi = self.RSI_V
            is_err = 1

        if is_err == -1:
            if self.n_error >= 1:
                self.n_error += is_err
        else:
            self.n_error += is_err

        if self.n_error==10:
            print("ERROR: NETWORK_ERROR!")
        assert self.n_error<10, "ERROR: NETWORK_ERROR!"

        price = func.get_current_price(self.exchange)
        self.curr_RSI.setText(str(round(rsi,2)))
        self.curr_Price.setText(self.SetNum(round(price, 2)))

        ck_tvalid = func.ck_time(self.STime,self.ETime)

        if ck_tvalid<=0:
            self.Emergency_stop()
            if self.status == 1:
                self.change_status()
            return

        elif ck_tvalid==2:
            self.ResetClick()
            return

        elif ck_tvalid==1:
            if self.status == 0:
                self.change_status()

        if self.status == 1:
            if self.t_status==0 and self.daily_earned >= self.target and self.daily_earned!=0:
                self.Emergency_stop()
                return
            if rsi<=self.RSI_threshold and self.t_status==0:
                if self.lose_num < self.max_lose:
                    order_info = func.open_position(self.exchange, self.amount)
                    self.exchange.load_markets()
                    self.RefreshAccount()
                    self.t_status = 1
                    time.sleep(1)
                    prce,amt = self.parse_PA(order_info['id'])
                    self.save_log(action="BUY", lev=self.leverage, amount=amt, price=prce)
                else:
                    self.Emergency_stop()
                    return
            if self.t_status == 1:
                _,pos = func.ck_exist_pos(self.exchange)
                e_price = float(pos['entryPrice'])
                c_price = float(pos['markPrice'])
                leverage = int(pos['leverage'])
                margin = float(pos['info']['margin'])
                amount = float(pos['info']['total'])

                self.o_price.setText(self.SetNum(e_price))
                self.c_price.setText(self.SetNum(c_price))
                self.pos_margin.setText(self.SetNum(margin))

                c_ret = func.cal_PIR(e_price, c_price, leverage) * 100
                c_ern = c_ret/100 * margin * leverage

                self.c_return.setText(f"{c_ret:.2f}")
                self.c_earn.setText(self.SetNum(c_ern))

                if np.abs(c_ret) >= self.pm_cond:
                    order_info = func.close_position(self.exchange, amount)
                    self.exchange.load_markets()
                    self.t_status = 0
                    time.sleep(1)
                    prce, amt = self.parse_PA(order_info['id'])
                    earn = func.cal_PIR(e_price,prce,leverage)*margin*leverage
                    self.daily_earned += earn
                    self.tot_earned += earn
                    if earn<0:
                        self.lose_num += 1
                    else:
                        self.win_num += 1
                    self.RefreshAccount()
                    self.RefreshWL()
                    self.RefreshTradeInfo()
                    self.save_log(action="SELL", lev=self.leverage, amount=amt, price=prce, earned=f"{earn:.3f}")

    def RefreshTradeInfo(self):
        self.o_price.setText(' ')
        self.c_price.setText(' ')
        self.pos_margin.setText(' ')
        self.c_return.setText(' ')
        self.c_earn.setText(' ')

    def RefreshWL(self):
        self.win.setText(str(self.win_num))
        self.lose.setText(str(self.lose_num))
        self.D_profit.setText(self.SetNum(self.daily_earned))
        self.T_profit.setText(self.SetNum(self.tot_earned))

    def SetUp(self):
        self.period = int(self.period_txt.toPlainText())
        self.tframe = self.time_txt.currentText()
        self.leverage = int(self.lev_txt.value())
        self.RSI_threshold = float(self.rsi_threshold.toPlainText())
        self.pm_cond = float(self.cond_txt.toPlainText())
        self.capital = float(self.cap_txt.toPlainText())
        self.max_lose = int(self.maxlose_txt.toPlainText())
        self.target = float(self.target_txt.toPlainText())
        self.STime = self.stime_txt.toPlainText()
        self.ETime = self.etime_txt.toPlainText()

        curr_price = func.get_current_price(self.exchange)
        self.amount = func.cal_amount(self.capital*self.leverage, curr_price)

    def change_status(self):
        if self.status == 1:
            self.status = 0
            self.start_btn.setText("START")
            if self.start_btn.isChecked():
                self.start_btn.toggle()
        else:
            self.status = 1
            self.start_btn.setText("STOP")
            if not self.start_btn.isChecked():
                self.start_btn.toggle()

    def Emergency_stop(self):
        is_exist, pos = func.ck_exist_pos(self.exchange)
        if self.status == 1:
            self.change_status()
        if is_exist == 1:
            amt = float(pos['info']['available'])
            e_price = float(pos['entryPrice'])
            leverage = int(pos['leverage'])
            margin = float(pos['info']['margin'])
            order_info = func.close_position(self.exchange, amount=amt)
            self.t_status = 0
            self.exchange.load_markets()
            time.sleep(1)
            prce, amt = self.parse_PA(order_info['id'])
            earn = func.cal_PIR(e_price,prce,leverage)*margin*leverage
            self.daily_earned += earn
            self.RefreshAccount()
            self.RefreshWL()
            self.RefreshTradeInfo()
            self.save_log(action="SELL", lev=self.leverage, amount=amt, price=f"{prce:.1f}", earned=f"{earn:.3f}")

    def StartClick(self):
        if self.status == 1:
            reply = QMessageBox.question(self, "주의!", f"자동매매를 즉시 중단하시겠습니까?\n\n현재 보유중인 코인이 모두 매도됩니다.",
                                         QMessageBox.No | QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.Emergency_stop()
                self.timer.stop()
                self.DWtimer.stop()
                return
            else:
                self.start_btn.toggle()
                return

        self.LogIn()
        self.SetUp()
        self.loginTimer.start(1200000)  # 연결 유지 위해, 20분 단위 재로그인
        self.acc_money = round(func.get_balance(self.exchange), 2)

        ck_trade, _ = func.ck_exist_pos(self.exchange)

        if ck_trade == 0:
            if self.leverage*self.pm_cond>=100:
                reply = QMessageBox.question(self, "경고!", f"{self.leverage}배의 레버리지는 자산이 청산될 수 있습니다.\n\n 정말 그대로 진행하시겠습니까?", QMessageBox.No|QMessageBox.Yes , QMessageBox.No)
                if reply == QMessageBox.Yes:
                    pass
                else:
                    self.start_btn.toggle()
                    return
            if self.amount == 0:
                QMessageBox.critical(self, "ERROR Message", "<<< Account Error >>>\n\n최소 주문 수량을 만족할 수 없습니다.  계좌의 잔액이 충분한지 확인해주세요.\n\n선물 지갑의 잔액을 늘리거나 레버리지 배율을 높여 문제를 해결할 수 있습니다.")
                self.start_btn.toggle()
                return

            if self.lose_num == self.max_lose:
                QMessageBox.critical(self, "ERROR Message", f"<<< LoseNum Error >>>\n\n오늘의 최대 손실 횟수({self.max_lose}회)를 초과했습니다.")
                self.start_btn.toggle()
                return

            if self.capital > self.acc_money:
                QMessageBox.critical(self, "ERROR Message", f"<<< Balance Error >>>\n\n매매에 사용하시고자 하는 금액({self.capital} $)이 선물 지갑의 잔고({self.acc_money} $)보다 많습니다.\n\n계좌의 잔액을 확인해 주세요. ")
                self.start_btn.toggle()
                return

            if (not func.time_is_valid(self.STime)) or (not func.time_is_valid(self.ETime)):
                QMessageBox.critical(self, "ERROR Message", "<<< Format Error >>>\n\n시작시간/종료시간의 포맷을 제대로 확인해 주세요.")
                self.start_btn.toggle()
                return

        self.RefreshAccount()
        self.RSI_label.setText(f"RSI{self.period}")
        self.Load_RSI_n_PRICE()
        self.timer.start(2000)
        self.DWtimer.start(3600000) #1시간 단위 환율 자동 업데이트

        self.apply_leverage()
        self.change_status()
        self.Save_Setting()

        isExist,_ = func.ck_exist_pos(self.exchange)
        if isExist:
            self.t_status = 1

    def apply_leverage(self):
        set_margin_mode = self.exchange.set_margin_mode('crossed', symbol="BTC/USDT:USDT")
        self.exchange.set_leverage(self.leverage, symbol="BTC/USDT:USDT")

    def save_log(self, action, lev, amount, price, earned=None):
        action_t = func.get_time()
        log_msg = f"{action_t} [{action}] (x{lev}) {amount}BTC {price}($)"

        if action == "SELL":
            log_msg += f"   {earned}($)"
        self.textBrowser.append(log_msg)
        func.Save_Log_AS_EXCEL([action_t,action,lev,amount,price,earned])
        self.Save_Setting()
        self.RefreshAccount()

    def ResetClick(self):
        self.win_num = 0
        self.lose_num = 0
        self.daily_earned = 0
        self.RefreshWL()

    def Time():
        curr_t = func.get_time()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message', 'Are you sure to quit?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def parse_PA(self, id, symbol="BTC/USDT:USDT"):
        info = self.exchange.fetch_order_trades(id,symbol)[0]
        price, amount = info['price'], info['amount']
        return price, amount

    def Save_Setting(self):
        prev_data = {'timeframe':self.tframe,
                     'period':int(self.period),
                     'leverage':int(self.leverage),
                     'threshold':int(self.RSI_threshold),
                     'cond':self.pm_cond,
                     'capital':self.capital,
                     'max_lose': int(self.max_lose),
                     'target': int(self.target),
                     'sTime':self.STime,
                     'eTime':self.ETime,
                     'tot_earned':float(self.tot_earned)}
        func.Save_prev_setting(prev_data)

    def Load_Setting(self, prev_data):
        self.period_txt.setText(str(prev_data['period']))
        self.time_txt.setCurrentText(prev_data['timeframe'])
        self.lev_txt.setValue(int(prev_data['leverage']))
        self.rsi_threshold.setText(str(prev_data['threshold']))
        self.cond_txt.setText(str(prev_data['cond']))
        self.cap_txt.setText(str(prev_data['capital']))
        self.maxlose_txt.setText(str(prev_data['max_lose']))
        self.target_txt.setText(str(prev_data['target']))
        self.stime_txt.setText(prev_data['sTime'])
        self.etime_txt.setText(prev_data['eTime'])
        self.T_profit.setText(str(prev_data['tot_earned']))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = WindowClass()
    myWindow.show()
    app.exec_()