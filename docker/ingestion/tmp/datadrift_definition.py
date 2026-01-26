import base64
import json
import os

import requests


def main():
    api_base = "http://openmetadata-server:8585/api/v1"
    encoded_password = base64.b64encode(os.environ["OM_ADMIN_PWD"].encode("utf-8")).decode("utf-8")
    login_payload = {"email": os.environ["OM_ADMIN_EMAIL"], "password": encoded_password}

    print("登入並嘗試獲取jwt token...")

    token = requests.post(f"{api_base}/users/login", json=login_payload).json()["accessToken"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    uri = f"{api_base}/dataQuality/testDefinitions/name/datadrift"  # 確認test definition是否存在
    response = requests.get(uri, headers=headers)
    if response.status_code in [200, 201]:
        print("Test Definition 已存在，作業將會結束...")
    else:
        print("Test Definition 不存在，嘗試建立...")

        uri = f"{api_base}/dataQuality/testDefinitions"
        with open("/tmp/datadrift_definition.json", "r", encoding="utf-8") as f:
            body = json.load(f)
        response = requests.put(uri, headers=headers, json=body)

        if response.status_code in [200, 201]:
            print("Success:", response.json())
        else:
            print(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    main()