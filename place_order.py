"""Place a market order on Alpaca using credentials from .env."""
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
    if len(sys.argv) != 4:
        print("Usage: python place_order.py SYMBOL QTY SIDE", file=sys.stderr)
        sys.exit(1)

    symbol, qty, side = sys.argv[1], sys.argv[2], sys.argv[3]

    env = load_env()
    api_key = env.get("ALPACA_API_KEY")
    secret_key = env.get("ALPACA_SECRET_KEY")
    endpoint = env.get("ALPACA_END_POINT", "https://paper-api.alpaca.markets/v2")

    if not api_key or not secret_key:
        print("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in .env", file=sys.stderr)
        sys.exit(1)

    url = endpoint.rstrip("/") + "/orders"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "Content-Type": "application/json",
    }
    body = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }

    resp = requests.post(url, headers=headers, json=body, timeout=10)

    if resp.status_code not in (200, 201):
        print(f"Order failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    print("Order submitted.")
    print(f"Order ID:     {data.get('id')}")
    print(f"Symbol:       {data.get('symbol')}")
    print(f"Qty:          {data.get('qty')}")
    print(f"Side:         {data.get('side')}")
    print(f"Type:         {data.get('type')}")
    print(f"Time in force:{data.get('time_in_force')}")
    print(f"Status:       {data.get('status')}")
    print(f"Submitted at: {data.get('submitted_at')}")


if __name__ == "__main__":
    main()
