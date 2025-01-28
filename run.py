"""
Main bot module

@Developer: Stan
@AppVersion: 3.1.1
@ModuleVersion: 3.1.1
@PythonVersion: 3.13

"""

import sys
from datetime import datetime
from os import getenv, PathLike
from os.path import abspath, dirname, join
from time import sleep
from typing import Any, Callable, Literal, Mapping, Self, Collection

import ccxt
from ccxt.base.errors import InvalidOrder
from ccxt import Exchange
from dotenv import load_dotenv

from config import Color
from predict import PredictionApp


class App:
    """
    Main bot logic.

    """
    SUPPORTED_EXCHANGES: Collection[str] = ccxt.exchanges

    def __init__(
            self: Self,
            env_file_path: str,
            prediction_api: Callable[[Any], str]
    ) -> None:
        """

        :param env_file_path: filename of .env file to use for app
        :param prediction_api: function
        """

        # Check for '<something>.env' file
        load_dotenv(dotenv_path=env_file_path)

        self.EXCHANGE_NAME: str = getenv("DEFAULT_EXCHANGE_NAME")

        if self.EXCHANGE_NAME in self.SUPPORTED_EXCHANGES:
            self.EXCHANGE_API_KEY: str = getenv("EXCHANGE_API_KEY")
            self.EXCHANGE_SECRET: str = getenv("EXCHANGE_SECRET")
            self.EXCHANGE_PASSWORD: str = getenv("EXCHANGE_PASSPHRASE")

            # Exchange fee per transaction (0.1% = 0.001)
            self.FEE: float = float(getenv("DEFAULT_EXCHANGE_FEE"))

        else:
            sys.exit(f"No valid exchange name provided\n"
                     f"Valid options:\n\t(`kucoin`, )"
                     f"\nActual name provided: {self.EXCHANGE_NAME}")

        self.ALGORITHM_TRUST_PERCENTAGE: float = float(getenv("ALGORITHM_TRUST_PERCENTAGE"))
        self.DATA_VECTOR_LENGTH: int = int(getenv("DATA_VECTOR_LENGTH"))
        self.PREMIUM: float = float(getenv("PREMIUM_OVER_EXCHANGE_FEES")) + self.FEE
        self.MIN_TRANSACTION_VALUE_IN_BASE: float = float(getenv("MIN_TRANSACTION_VALUE_IN_BASE"))

        # Timeframe of data
        self.TIMEFRAME: str = getenv("TIMEFRAME")

        # Times it takes to cancel open orders
        self.CANCEL_ORDER_LIMIT: int = int(getenv("CANCEL_ORDER_LIMIT")) or 3
        self.cancel_order_counter: int = 0

        # Times to retry after failure
        self.RETRIES_BEFORE_SLEEP_LIMIT: int = int(getenv("RETRIES_BEFORE_SLEEP_LIMIT")) or 4
        self.retries_before_sleep_counter: int = 0

        # Optimal sleep time also works
        self.BASE_SLEEP_TIME: int = int(getenv("BASE_SLEEP_TIME")) or \
                                    min(max(self.DATA_VECTOR_LENGTH // 2, self.CANCEL_ORDER_LIMIT), 5) * 60

        # Instantiate the Exchange class
        self.exchange: Exchange = getattr(ccxt, self.EXCHANGE_NAME)()

        # Set sandbox mode to True or False (currently, True is not supported on kucoin)
        self.exchange.set_sandbox_mode(enabled=False)

        # Set your API keys
        self.exchange.apiKey = self.EXCHANGE_API_KEY
        self.exchange.secret = self.EXCHANGE_SECRET
        self.exchange.password = self.EXCHANGE_PASSWORD  # it's called `passphrase` on KuCoin

        # Set the symbol you want to trade on KuCoin
        self.SYMBOL: str = getenv("TRADING_PAIR")
        pair_lst: list = self.SYMBOL.split("/")
        self.PAIR_ITEM1: str = pair_lst[0]
        self.PAIR_ITEM2: str = pair_lst[1]

        self.predict_up_or_down: Callable[[Any], str] = prediction_api

    def order(self: Self,
              order_type: Literal["market", "limit"],
              buy_or_sell: Literal["buy", "sell"],
              amount: float,
              price: float = None) -> Mapping[str, Any]:
        """
        Create order of either buy or sell

        :param order_type:
        :param buy_or_sell:
        :param amount:
        :param price:
        :return:
        """
        try:
            transaction_cost: float = round(amount * float(price), 2)
            print(f"\t[INFO]\t⭐️ {Color.ITALIC}Trying to {buy_or_sell} {self.PAIR_ITEM1} with "
                  f"total transaction value ≈ {transaction_cost} {self.PAIR_ITEM2}.{Color.END}")
            if amount > self.MIN_TRANSACTION_VALUE_IN_BASE:
                order_id: Mapping[str, Any] = self.exchange.create_order(
                    symbol=self.SYMBOL,
                    type=order_type,
                    side=buy_or_sell,
                    amount=amount,
                    price=price
                )
            else:
                raise ValueError("\t[INFO]\t⛔️ Won't process order (transaction too small).\n")

        except InvalidOrder as error:
            print(f"\t[ERROR]\tInvalid order:\n\t\t{error}.\n")
            return {}

        except ValueError as error:
            print(error)
            return {}

        else:

            print(f"[ACTION DONE]\t🤝 Place a limit {Color.BOLD}{buy_or_sell} order{Color.END}"
                  f" of {Color.BOLD}{self.PAIR_ITEM1.lower()}{amount}{Color.END} x"
                  f" {self.PAIR_ITEM2.lower()}{price} ≈ {self.PAIR_ITEM2.lower()}{transaction_cost}")
            return order_id

    def prepare_order(self: Self) -> tuple[float | None, float | None, float | None, float | None]:
        """

        :return: (price_buy, price_sell, amount_buy, amount_sell) or tuple of Nones
        """

        # Fetch the current ticker information for the symbol
        print("\n\t[INFO]\tFetch the current info for the symbol.")

        # Get current balance
        balance = self.exchange.fetch_balance()
        base_asset_balance = balance[self.PAIR_ITEM1]["free"]
        quote_asset_balance = balance[self.PAIR_ITEM2]["free"]
        print(f"\t[INFO]\t💰 {self.PAIR_ITEM1} balance: {base_asset_balance}")
        print(f"\t[INFO]\t💵 {self.PAIR_ITEM2} balance: {quote_asset_balance}")

        try:
            orderbook: Mapping[str, Any] = self.exchange.fetch_order_book(symbol=self.SYMBOL)
            bid: Any = orderbook["bids"][0][0] if len(orderbook["bids"]) > 0 else None
            ask: Any = orderbook["asks"][0][0] if len(orderbook["asks"]) > 0 else None
            if not ask:
                raise Exception("Ask price is None")
            if not bid:
                raise Exception("Bid price is None")

        except BaseException as error:
            print(f"\t[WARNING]\t...Retrying because of some error:\n\t\t{error}.\n")
            self.retries_before_sleep_counter += 1
            if self.retries_before_sleep_counter == self.RETRIES_BEFORE_SLEEP_LIMIT:
                self.retries_before_sleep_counter = 0
                self.global_sleep()
            return None, None, None, None

        # Check the current bid and ask prices
        bid: float = float(bid)
        ask: float = float(ask)
        print(f"\t[INFO]\tBid {Color.ITALIC}≈ {round(bid, 4)} {self.PAIR_ITEM2}{Color.END}"
              f", Ask {Color.ITALIC}≈ {round(ask, 4)} {self.PAIR_ITEM2}{Color.END}\n")

        # Price is ALWAYS in quote asset (2nd item in trading pair `1st/2nd`)
        mean_price: float = (ask + bid) / 2
        price_buy: float = mean_price * (1 - self.PREMIUM)
        price_sell: float = mean_price * (1 + self.PREMIUM)
        # price_buy = price_sell = mean_price
        # price_buy: float = ask
        # price_sell: float = bid

        # Calculate how much of quote asset is about to be spent on a buy order
        amount_to_buy_in_quote_asset: float = self.ALGORITHM_TRUST_PERCENTAGE * quote_asset_balance

        # By CCXT rules, 'amount' variable for all '...order' methods
        # is ALWAYS in base asset (1st item in trading pair `1st/2nd`)
        amount_buy: float = amount_to_buy_in_quote_asset / price_buy
        amount_sell: float = self.ALGORITHM_TRUST_PERCENTAGE * base_asset_balance

        return price_buy, price_sell, amount_buy, amount_sell

    def main(self: Self, infinite_loop_condition: bool) -> None:
        """
        Main bot cycle logic.

        :param infinite_loop_condition: bool value
        :return: None
        """

        print(f"\t[INFO]\t🏦 Exchange: `{self.EXCHANGE_NAME}`.\n"
              "\t[INFO]\t💼 Algorithm trust percentage (reinvestment rate): "
              f"{Color.DARKCYAN}{self.ALGORITHM_TRUST_PERCENTAGE * 100}%{Color.END}.\n"
              "\t[INFO]\t📈 Algorithm premium: "
              f"{Color.DARKCYAN}{round(self.PREMIUM * 100, 4)}%{Color.END}.\n"
              "\t[INFO]\t📉 Lower limit: "
              f"{Color.DARKCYAN}{self.MIN_TRANSACTION_VALUE_IN_BASE} {self.PAIR_ITEM1}{Color.END}.\n\n"
              f"\t[INFO]\t🚀 Started algorithm with pair `{self.SYMBOL}`.")

        while infinite_loop_condition:
            try:
                # Market Data Print
                current_time = datetime.now()
                print(f"\n\t[INFO]\t⌚️ {Color.BOLD}Current time:"
                      f" {current_time.strftime('%B %d, %Y %I:%M:%S %p')}{Color.END}")

                # Check if there are any open orders
                print("\t[INFO]\t👀 Checking for open orders")
                open_orders = self.exchange.fetch_open_orders(self.SYMBOL)
                if not open_orders:
                    print("\t[INFO]\t🟢 No open orders.")

                    data: Any = self.exchange.fetch_ohlcv(
                        self.SYMBOL, self.TIMEFRAME, limit=self.DATA_VECTOR_LENGTH)
                    print("\t[INFO]\t📊 Got data: "
                          f"({self.DATA_VECTOR_LENGTH} x {self.TIMEFRAME}).")

                    try:
                        # Check if it is bullish up or bearish down before buying
                        prediction_main: Any = self.predict_up_or_down(data)
                        # prediction_support: Any = self.predict_up_or_down(data)
                        if prediction_main:
                            print("\t[AI]\t🤖 Got prediction.")

                        else:
                            print("\t[AI]\t🤖 Could not get prediction.")
                            self.retries_before_sleep_counter += 1
                            if self.retries_before_sleep_counter == self.RETRIES_BEFORE_SLEEP_LIMIT:
                                self.retries_before_sleep_counter = 0
                                self.global_sleep()
                            continue

                        # If bullish
                        if prediction_main == "up":
                            print(f"\t[AI]\t🤖 Is {Color.GREEN}bullish{Color.END} on {self.PAIR_ITEM1}.")

                            price_buy, _, amount_buy, _ = self.prepare_order()
                            if amount_buy is None:
                                continue

                            # Place a limit buy order
                            order_id: Mapping[str, Any] = self.order(
                                order_type="limit",
                                buy_or_sell="buy",
                                amount=amount_buy,
                                price=price_buy
                            )

                        # If bearish
                        elif prediction_main == "down":
                            print(f"\t[AI]\t🤖 Is {Color.RED}bearish{Color.END} on {self.PAIR_ITEM1}.")

                            _, price_sell, _, amount_sell = self.prepare_order()
                            if amount_sell is None:
                                continue

                            # Place a limit sell order
                            order_id: Mapping[str, Any] = self.order(
                                order_type="limit",
                                buy_or_sell="sell",
                                amount=amount_sell,
                                price=price_sell
                            )

                        # If indecisive
                        elif prediction_main == "hold":
                            print(f"\t[AI]\t🤖 Is {Color.PURPLE}hold{Color.END} on {self.PAIR_ITEM1}.")
                            print("\t[INFO]\t😎 Doing nothing.")

                        else:
                            self.global_sleep()
                            continue

                        if "order_id" in locals():
                            if bool(order_id):
                                print(f"[ORDER]:\t{order_id}.\n")
                            del order_id

                    except BaseException as error:
                        self.retries_before_sleep_counter += 1
                        if self.retries_before_sleep_counter == self.RETRIES_BEFORE_SLEEP_LIMIT:
                            self.retries_before_sleep_counter = 0
                            self.default_sleep_message(error, "ProbablyAIButCouldBeAnything")
                            self.global_sleep()
                        continue

                else:
                    print("\t[INFO]\t🛑 There are open orders.")

                    self.cancel_order_counter += 1
                    print(f"\t[INFO]\t💪🏻 {Color.ITALIC}Current open orders counter:{Color.END}"
                          f" {Color.BOLD}{Color.DARKCYAN}{self.cancel_order_counter}{Color.END}.")

                    if self.cancel_order_counter == self.CANCEL_ORDER_LIMIT:
                        self.cancel_order_counter = 0
                        for order in open_orders:
                            order_id_to_cancel: str = order.get("id")
                            self.exchange.cancel_order(order_id_to_cancel)
                            print(f"[ACTION DONE]\t☑️ {Color.BOLD}Order"
                                  f" cancelled{Color.END} with id: {order_id_to_cancel}")
                        continue

                self.global_sleep()

            except KeyboardInterrupt:
                print("[END]\tEND `main` module on KeyboardInterrupt.")
                break

            except ccxt.NetworkError as error:
                self.default_sleep_message(error, "NetworkError")
                self.global_sleep()
                continue

            except ccxt.ExchangeError as error:
                self.default_sleep_message(error, "ExchangeError")
                self.global_sleep()
                continue

            except Exception as error:
                self.default_sleep_message(error, "Some other")
                self.global_sleep()
                continue

        print("[END]\t👋🏻 END `main` module.")

    def global_sleep(self: Self) -> None:
        print(f"\t[INFO]\t🙈 Pause for {self.BASE_SLEEP_TIME} seconds.")
        sleep(self.BASE_SLEEP_TIME)

    def default_sleep_message(self: Self, error: Any, tag: str) -> None:
        print(f"\t[ERROR]\t🙈 Retrying after sleep ({self.BASE_SLEEP_TIME} seconds). "
              f"{tag} exception:\n\t\t{error}.\n")


if __name__ == "__main__":
    PREDICTION_ENVIRONMENT_FILENAME: str = "pandas.env"
    MAIN_ENVIRONMENT_FILENAME: str = "main.env"
    print("[START]\tSTARTED `main` module.")

    # Paths
    current_path: str | PathLike = dirname(abspath(__file__))
    predictions_env_path: str | PathLike = join(current_path, PREDICTION_ENVIRONMENT_FILENAME)
    main_trading_env_path: str | PathLike = join(current_path, MAIN_ENVIRONMENT_FILENAME)

    # Predictions
    prediction_app: PredictionApp = PredictionApp(env_file_path=predictions_env_path)
    prediction_function: Callable[[Any], str] = prediction_app.predict_up_or_down

    # Main logic
    kucoin_trading_bot: App = App(env_file_path=main_trading_env_path, prediction_api=prediction_function)
    sys.exit(kucoin_trading_bot.main(infinite_loop_condition=True))
