from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Discord 봇에서 전송한 잔액 저장
balances = {}

# API 보안키
API_KEY = os.getenv("API_KEY", "CHANGE_THIS_SECRET_KEY")


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "Roblox Bank API"
    })


# Discord 봇 → Render API
# 현금 / 계좌 잔액 저장 및 업데이트
@app.route("/update_balance", methods=["POST"])
def update_balance():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "데이터가 없습니다."
        }), 400

    # API 키 확인
    if data.get("api_key") != API_KEY:
        return jsonify({
            "success": False,
            "error": "API 키가 올바르지 않습니다."
        }), 403

    roblox_user_id = str(data.get("roblox_user_id"))

    # 현금
    balance = data.get("balance")

    # 계좌
    account_balance = data.get("account_balance")

    if not roblox_user_id:
        return jsonify({
            "success": False,
            "error": "roblox_user_id가 없습니다."
        }), 400

    # 처음 저장하는 유저라면 기본값 생성
    if roblox_user_id not in balances:
        balances[roblox_user_id] = {
            "balance": 0,
            "account_balance": 0
        }

    # 현금 업데이트
    if balance is not None:
        balances[roblox_user_id]["balance"] = int(balance)

    # 계좌 업데이트
    if account_balance is not None:
        balances[roblox_user_id]["account_balance"] = int(account_balance)

    return jsonify({
        "success": True,
        "roblox_user_id": roblox_user_id,
        "balance": balances[roblox_user_id]["balance"],
        "account_balance": balances[roblox_user_id]["account_balance"]
    })


# Roblox 게임 → 잔액 조회
@app.route("/balance/<roblox_user_id>", methods=["GET"])
def get_balance(roblox_user_id):

    roblox_user_id = str(roblox_user_id)

    # 저장된 정보 없으면 0원
    user_data = balances.get(
        roblox_user_id,
        {
            "balance": 0,
            "account_balance": 0
        }
    )

    return jsonify({
        "success": True,
        "roblox_user_id": roblox_user_id,
        "balance": user_data["balance"],
        "account_balance": user_data["account_balance"]
    })


# 서버 실행
if __name__ == "__main__":

    port = int(os.getenv("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
