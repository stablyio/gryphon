import pyximport; pyximport.install()

from gryphon.lib.exchange.binance import (
    BinanceBTCUSDTExchange,
    BinanceBTCUSDSExchange,
)
from gryphon.tests.environment.exchange_wrappers.live_orders import LiveOrdersTest


# class TestBinanceBTCUSDTLiveOrders(LiveOrdersTest):
#     def __init__(self):
#         # Binance has fences around where you can set prices and amounts
#         # https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#percent_price
#         self.order1_price_amount = '3000'
#         self.order2_price_amount = '3001'
#         self.order_volume = '.004'
#         self.sleep_time = 1
    
#     def setUp(self):
#         self.exchange = BinanceBTCUSDTExchange()

class TestBinanceBTCUSDSLiveOrders(LiveOrdersTest):
    def __init__(self):
        # Binance has fences around where you can set prices and amounts
        # https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#percent_price
        self.order1_price_amount = '3000'
        self.order2_price_amount = '3001'
        self.order_volume = '.004'
        self.sleep_time = 2
    
    def setUp(self):
        self.exchange = BinanceBTCUSDSExchange()
