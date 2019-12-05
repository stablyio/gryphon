import pyximport; pyximport.install()

from gryphon.lib.exchange.binance import BinanceBTCUSDTExchange
from gryphon.tests.environment.exchange_wrappers.auth_methods import ExchangeAuthMethodsTests


class TestBinanceBTCUSDTAuthMethods(ExchangeAuthMethodsTests):
    def setUp(self):
        self.exchange = BinanceBTCUSDTExchange()
