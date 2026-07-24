import requests

API_KEY = "api-key-kling-oL2-T2PMjl3B17QV8mmqc6EDxeegmiuTiX7q8cazId8"

url = "https://api-singapore.klingai.com/image-to-video/kling-2.5-turbo"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "contents": [
        {
            "type": "prompt",
            "text": "A girl sat on the train, looking out the window with a melancholic expression, her head swaying with the train."
        },
        {
            "type": "first_frame",
            "url": "https://p2-kling.klingai.com/kcdn/cdn-kcdn112452/kling-tob-release_note/image_25.png"
        }
    ],
    "settings": {
        "resolution": "1080p",
        "duration": 5
    },
    "options": {
        "callback_url": "https://xxx/callback",
        "external_task_id": "",
        "watermark_info": {
            "enabled": True
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

print("Status Code:", response.status_code)
print(response.json())