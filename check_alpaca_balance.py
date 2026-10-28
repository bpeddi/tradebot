"""Check Alpaca paper trading account balance using credentials from .env."""
import os
import sys
import requests

def load_env(path=".env"):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def main():
    env = load_env()
    api_key = env.get("ALPACA_API_KEY") or os.environ.get("ALPACA_API_KEY")
    secret_key = env.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    endpoint = (env.get("ALPACA_END_POINT") or os.environ.get("ALPACA_END_POINT")
                or "https://paper-api.alpaca.markets/v2")

    if not api_key or not secret_key:
        print("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env", file=sys.stderr)
        sys.exit(1)

    url = endpoint.rstrip("/") + "/account"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }

    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        print(f"Request failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    print("Connected to Alpaca paper account successfully.")
    print(f"Account ID:      {data.get('account_number')}")
    print(f"Status:          {data.get('status')}")
    print(f"Equity:          {data.get('equity')}")
    print(f"Cash:            {data.get('cash')}")
    print(f"Buying Power:    {data.get('buying_power')}")
    print(f"Portfolio Value: {data.get('portfolio_value')}")


if __name__ == "__main__":
    main()
