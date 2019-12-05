"""
https://github.com/binance-exchange/binance-official-api-docs
"""

import hashlib
import hmac
import time
# import decimal
from cdecimal import *

from gryphon.lib.exchange.consts import Consts
from gryphon.lib.exchange import exceptions
from gryphon.lib.exchange.exchange_api_wrapper import ExchangeAPIWrapper
from gryphon.lib.logger import get_logger
from gryphon.lib.models.exchange import Balance
from gryphon.lib.exchange import order_types
from gryphon.lib.money import Money


class BinanceExchangeAPIWrapper(ExchangeAPIWrapper):
    """A base class to implement support for binance.com
    This class is not intended to be instantiated itself and does not appear 
    as a supported exchange in gryphon.lib.exchange.exchange_factory.
    Instead, there are subclasses of this class for each currency pair that
    the exchange supports.
    """
    base_url = 'https://api.binance.com'
    order_type_to_binance_type = {order_types.LIMIT_ORDER: 'LIMIT', order_types.MARKET_ORDER: 'MARKET', order_types.POST_ONLY: 'LIMIT_MAKER'}
    binance_type_to_order_type = dict((v,k) for k,v in order_type_to_binance_type.iteritems())

    @staticmethod
    def signature(url_params, request_body, secret):
        """Signature of a url query string as required by Binance.
        Parameters
        ----------
        url_params : dict
            query string parameters from a url as given by a request object
        request_body : dict
            request body
        secret : str
            binance user secret for signing the query string
        Returns
        -------
        str
        """
        query_string = ""
        body_string = ""

        for key in url_params.keys():
            query_string += key + "=" + str(url_params[key]) + "&"
        query_string = query_string[:-1] # remove the last &
        for key in request_body.keys():
            body_string += key + "=" + str(request_body[key]) + "&"
        body_string = body_string[:-1] # remove the last &

        total_params = query_string + body_string

        return hmac.new(secret, total_params, hashlib.sha256).hexdigest()

    def __init__(self, session=None, configuration=None):
        super(BinanceExchangeAPIWrapper, self).__init__(session)

        self.credentials = None
        self.volume_currency = None
        self.currency = None
        self.symbol = None
        self.bid_string = 'BUY'
        self.ask_string = 'SELL'        

    def load_credentials(self):
        credentials = ['api_key', 'secret']
        if self.credentials is None:
            self.credentials = {
                credential: self._load_env('BINANCE_' + credential.upper())
                for credential in credentials
            }

    def auth_request(self, req_method, url, request_args):
        """Modify a request to add authentication header and query string.
        Overrides the not implemented method from the base class.
        For authenticated endpoints, Binance requires the api key in the
        request header and a timestamp and signature within the query string.
        """
        self.load_credentials()

        try:
            headers = request_args['headers']
        except KeyError:
            headers = request_args['headers'] = {}

        headers['X-MBX-APIKEY'] = self.credentials['api_key']

        try:
            url_params = request_args['params']
        except KeyError:
            url_params = request_args['params'] = {}

        try:
            request_body = request_args['data']
        except KeyError:
            request_body = request_args['data'] = {}

        timestamp = int(round(time.time() * 1000))
        url_params['timestamp'] = timestamp
        url_params['signature'] = self.signature(url_params, request_body, self.credentials['secret'])

##########################################################################################
# Public Endpoint Methods                                                                #
##########################################################################################
    def ping(self):
        """Establish basic connectivity to the exchange.
        This method is specific to the Binance exchange. It is not an
        implementation of any method from the parent class.
        """
        req = self.req(
            'get',
            '/api/v3/ping',
            no_auth=True
        )
        return self.resp(req)

    def get_ticker_req(self, verify=True):
        return self.req(
            'get',
            '/api/v3/ticker/24hr',
            no_auth=True,
            verify=verify,
            params={'symbol': self.symbol},
        )

    def get_ticker_resp(self, req):
        response = self.resp(req)
        return {
            'high': Money(response['highPrice'], self.currency),
            'low': Money(response['lowPrice'], self.currency),
            'last': Money(response['lastPrice'], self.currency),
            'volume': Money(response['volume'], self.volume_currency),
        }

    def _get_orderbook_from_api_req(self, verify=True):
        return self.req(
            'get',
            '/api/v3/depth',
            no_auth=True,
            verify=verify,
            params={'symbol': self.symbol},
        )

##########################################################################################
# Authorised Endpoint Methods                                                            #
##########################################################################################

    def get_balance_req(self):
        return self.req(
            'get',
            'api/v3/account',
        )

    def get_balance_resp(self, req):
        raw_balances = self.resp(req)

        volume_currency_available = None
        price_currency_available = None

        for raw_balance in raw_balances:
            if raw_balance['currency'] == self.volume_currency:
                volume_currency_available = Money(
                    raw_balance['available'],
                    self.volume_currency,
                )
            elif raw_balance['currency'] == self.currency:
                price_currency_available = Money(
                    raw_balance['available'],
                    self.currency,
                )
        
        if volume_currency_available == None or price_currency_available == None:
            raise exceptions.ExchangeAPIErrorException(
                self,
                'missing expected balances',
            )
        
        balance = Balance()
        balance[self.volume_currency] = volume_currency_available
        balance[self.currency] = price_currency_available

        return balance

    def get_open_orders_req(self):
        return self.req(
            'get',
            '/api/v3/openOrders',
            params={'symbol': self.symbol},
        )

    def get_open_orders_resp(self, req):
        response = self.resp(req)
        return [
            {
                'mode': self._order_mode_to_const(order['side']),
                'id': str(order['orderId']),
                'price': Money(order['price'], self.currency),
                'type': self.binance_type_to_order_type[order['type']],
                'volume': Money(order['origQty'], self.volume_currency),
                'volume_remaining': Money(order['origQty'], self.volume_currency) - Money(order['executedQty'], self.volume_currency),
            }
            for order in response
        ]

    def place_order_req(self, mode, volume, price, order_type=order_types.LIMIT_ORDER):
        side = self._order_mode_from_const(mode)

        price = price.round_to_decimal_places(
            self.price_decimal_precision,
        )

        volume = volume.round_to_decimal_places(
            self.volume_decimal_precision,
        )

        payload = {
            'symbol': self.symbol,
            'side': side,
            'quantity': str(volume.amount),
            'price': str(price.amount),
            'type': self.order_type_to_binance_type[order_type],
        }

        if self.order_type_to_binance_type[order_type] == 'LIMIT':
            payload['timeInForce'] = 'GTC'

        return self.req(
            'post', 
            '/api/v3/order', 
            data=payload,
        )

    def place_order_resp(self, req):
        response = self.resp(req)

        try:
            order_id = str(response['orderId'])

            return {'success': True, 'order_id': order_id}
        except KeyError:
            raise exceptions.ExchangeAPIErrorException(
                self,
                'response does not contain an order id',
            )

    def get_order_details_req(self, order_id):
        return self.req(
            'get',
            '/api/v3/order',
            params={
                'symbol': self.symbol,
                'orderId': order_id,
            },
        )

    def get_order_details_resp(self, req):
        response = self.resp(req)

        volume_amount = Money(response['origQty'], self.volume_currency)
        executed_volume_amount = Money(response['executedQty'], self.volume_currency)
        price = Money(response['price'], self.currency) 
        # Cannot multiple Money * Money, we need to know the unit, so we use the currency unit and a Decimal
        price_currency_amount = price * Decimal(response['executedQty']) 
        result = {
            'id': str(response['orderId']),
            'time_created': int(response['time']),
            'mode': self._order_mode_to_const(response['side']),
            'type': self.binance_type_to_order_type[response['type']],
            self.volume_currency.lower() + '_total': volume_amount,
            self.currency.lower()+ '_total': price_currency_amount,
            # 'trades': [], # Binance does not split orders into trades, just partial fill quantities
        }
        return result

    def cancel_order_req(self, order_id):
        payload = {
            'symbol': self.symbol,
            'orderId': order_id,
        }
        print(payload)

        return self.req(
            'delete', 
            '/api/v3/order', 
            data=payload,
        )

    def cancel_order_resp(self, req):
        response = self.resp(req)

        if response['status'] == 'CANCELED':
            return {'success': True}
        else:
            raise exceptions.ExchangeAPIErrorException(
                self,
                'canceled order does not have canceled status',
            )

    '''
    Binance does not publish an endpoint for querying multiple IDs, so we send multiple requests
    '''
    def get_multi_order_details_req(self, order_ids):
        reqs = []
        for order_id in order_ids:
            reqs.append(self.get_order_details_req(order_id))
        return reqs

    def get_multi_order_details_resp(self, reqs):
        orders_by_id = {}
        for req in reqs:
            order = self.get_order_details_resp(req)
            orders_by_id[order['id']] = order
        return orders_by_id

class BinanceBTCUSDTExchange(BinanceExchangeAPIWrapper):

    def __init__(self, session=None, configuration=None):
        super(BinanceBTCUSDTExchange, self).__init__(session)

        # Configured
        self.currency = 'USDT'
        self.volume_currency = 'BTC'
        self.price_decimal_precision = 8
        self.volume_decimal_precision = 6

        # Auto set
        self.symbol = self.volume_currency + self.currency
        self.name = 'BINANCE_' + self.volume_currency + '_' + self.currency
        self.friendly_name = 'Binance ' + self.volume_currency + '-' + self.currency

        if configuration:
            self.configure(configuration)

class BinanceBTCUSDSExchange(BinanceExchangeAPIWrapper):

    def __init__(self, session=None, configuration=None):
        super(BinanceBTCUSDSExchange, self).__init__(session)

        # Configured
        self.currency = 'USDS'
        self.volume_currency = 'BTC'
        self.price_decimal_precision = 8
        self.volume_decimal_precision = 6

        # Auto set
        self.symbol = self.volume_currency + self.currency
        self.name = 'BINANCE_' + self.volume_currency + '_' + self.currency
        self.friendly_name = 'Binance ' + self.volume_currency + '-' + self.currency

        if configuration:
            self.configure(configuration)