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
# 잔액 저장/업데이트
@app.route("/update_balance", methods=["POST"])
def update_balance():

    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if data.get("api_key") != API_KEY:
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = str(data.get("roblox_user_id"))
    balance = data.get("balance")

    if not roblox_user_id or balance is None:
        return jsonify({
            "success": False,
            "error": "roblox_user_id 또는 balance가 없습니다."
        }), 400

    balances[roblox_user_id] = int(balance)

    return jsonify({
        "success": True,
        "roblox_user_id": roblox_user_id,
        "balance": balances[roblox_user_id]
    })


# Roblox 게임 → 잔액 조회
@app.route("/balance/<roblox_user_id>", methods=["GET"])
def get_balance(roblox_user_id):

    balance = balances.get(str(roblox_user_id), 0)

    return jsonify({
        "success": True,
        "roblox_user_id": str(roblox_user_id),
        "balance": balance
    })


# 서버 실행
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
