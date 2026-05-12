import os
import requests

API_URL = "https://router.huggingface.co/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {"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"}",
}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

response = query({
    "messages": [
        {
            "role": "user",
            "content": "que fut mon premier message"
        }
    ],
    "model": "deepseek-ai/DeepSeek-V4-Pro:novita"
})

print(response["choices"][0]["message"])