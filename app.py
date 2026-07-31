from flask import Flask, request, jsonify
import requests
import json
import time

app = Flask(__name__)

# External API configuration
API_KEY = "R-BOTS72EJ"
BASE_URL = "https://r-bots-num-2-info-api.co08.art/info"
MAX_RETRIES = 3
RETRY_DELAY = 1

# Credit object – every response mein included
CREDIT = {
    "owner": "@DG_DRIFT",
    "main_channel": "@DGDRIFT",
    "likes_group": "@DGDRIFTFF",
    "apis_channel": "@driftfreeapis"
}

# Custom exceptions
class APIError(Exception): pass
class InvalidNumberError(APIError): pass
class RateLimitError(APIError): pass
class ServerError(APIError): pass

def fetch_with_retry(number):
    if not number or not number.strip():
        raise InvalidNumberError("Phone number cannot be empty.")
    url = f"{BASE_URL}?key={API_KEY}&num={number}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise APIError("Invalid JSON response from server.")
            if data.get("status") == "error" or data.get("error"):
                error_msg = data.get("message") or data.get("error") or "Unknown API error"
                if "invalid" in error_msg.lower() or "not found" in error_msg.lower():
                    raise InvalidNumberError(error_msg)
                elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                    raise RateLimitError(error_msg)
                else:
                    raise APIError(error_msg)
            return data
        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES:
                raise APIError("Request timed out after multiple retries.")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
        except requests.exceptions.ConnectionError:
            if attempt == MAX_RETRIES:
                raise APIError("Network connection error.")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 0
            if status in (400, 401, 403, 404):
                if status in (401, 403):
                    raise APIError("Invalid API key or permission denied.")
                elif status == 404:
                    raise InvalidNumberError("Number not found or invalid endpoint.")
                else:
                    raise APIError(f"Client error (HTTP {status})")
            elif 500 <= status < 600:
                if attempt == MAX_RETRIES:
                    raise ServerError(f"Server error (HTTP {status}) after retries.")
                time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
            else:
                raise APIError(f"HTTP error {status}")
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                raise APIError(f"Request failed: {e}")
            time.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
    return None

def get_number_info(number):
    try:
        data = fetch_with_retry(number)
        if not data or data.get("found", 0) == 0:
            return [], 0, None
        return data.get("data", []), data.get("found", 0), None
    except (InvalidNumberError, RateLimitError, ServerError, APIError) as e:
        return [], 0, str(e)
    except Exception as e:
        return [], 0, f"Unexpected error: {e}"

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "API is running! Use /number?num=YOUR_NUMBER",
        "credit": CREDIT
    }), 200

@app.route('/number', methods=['GET'])
def lookup_number():
    num = request.args.get('num')
    if not num:
        return jsonify({
            "error": "Missing 'num' parameter",
            "credit": CREDIT
        }), 400
    records, found, error = get_number_info(num)
    if error:
        return jsonify({
            "error": error,
            "credit": CREDIT
        }), 404 if "not found" in error.lower() else 500
    if found == 0:
        return jsonify({
            "found": 0,
            "data": [],
            "credit": CREDIT
        }), 200
    return jsonify({
        "found": found,
        "data": records,
        "credit": CREDIT
    }), 200

# Vercel automatically uses 'app' – no if __name__ block needed.