import json
import requests

def chat(messages, model, json_format=False, options={"num_ctx": 66536}):
    url = "http://localhost:11434/api/chat"
    data = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options
    }
    if json_format:
        data["format"] = "json"
    timeout = 2000
    try:
        res = requests.post(url, json=data, timeout=timeout)
        s = json.loads(res.text)["message"]["content"]
        return s
    except requests.exceptions.Timeout:
        print("time out")
        return "err"
    except Exception:
        return "err"