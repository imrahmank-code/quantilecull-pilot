import urllib.request
import urllib.error

url = "https://quantilecull-pilot.onrender.com/latest-version"
print(f"Requesting {url}...")
try:
    with urllib.request.urlopen(url) as response:
        print("Status Code:", response.status)
        print("Headers:\n", response.headers)
        print("Body:\n", response.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Headers:\n", e.headers)
    try:
        body = e.read().decode()
        print("Body:\n", body[:1000])
    except Exception as ex:
        print("Could not read body:", ex)
except Exception as e:
    print("General Error:", e)
