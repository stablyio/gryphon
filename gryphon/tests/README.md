# Running tests
Export any environment variables needed for running the tests and then run using `nosetests`
```
export $(cat path/to/.env)
nosetests environment/exchange_wrappers/binance_auth.py
```
