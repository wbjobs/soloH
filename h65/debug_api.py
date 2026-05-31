#!/usr/bin/env python
import urllib.request
import json

BASE_URL = "http://localhost:8000/api/v1"

def make_request(method, endpoint, data=None):
    url = BASE_URL + endpoint
    headers = {"Content-Type": "application/json"}
    if method == "GET":
        req = urllib.request.Request(url, method="GET", headers=headers)
    else:
        body = json.dumps(data).encode() if data else b"{}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

data = {
    "name": "Debug Test",
    "auction_type": "smr",
    "min_price": 10.0,
    "max_price": 500.0,
    "bid_increment": 5.0,
    "max_rounds": 30,
    "activity_rule": True,
    "num_items": 2,
    "num_bidders": 2,
    "bidder_strategies": ["truthful", "truthful"]
}

auction = make_request("POST", "/auctions?seed=500", data)
auction_id = auction["id"]

print("Auction created, ID:", auction_id)
print("Items:")
for item in auction["items"]:
    print(f'  {item["id"]}: {item["name"]}, reserve={item["reserve_price"]}')

print("\nBidders:")
for bidder in auction["bidders"]:
    print(f'  {bidder["id"]}: {bidder["name"]}, strategy={bidder["strategy_name"]}')
    for val in bidder.get("valuations", []):
        print(f'    item {val["item_id"]}: base_value={val["base_value"]}')

# Step 1
step_result = make_request("POST", f"/auctions/{auction_id}/step")
print("\nStep 1 result:", json.dumps(step_result, indent=2))

# Get state
state = make_request("GET", f"/auctions/{auction_id}/state")
print("\nState keys:", list(state.keys()))
print("State:", json.dumps(state, indent=2)[:800])
