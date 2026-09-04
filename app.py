from flask import Flask, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)


# ==========================================
# 데이터 저장
# ==========================================

# 유저별 현금 / 계좌 잔액
balances = {}

# 유저별 거래내역
transactions = {}


# ==========================================
# API 보안키
# ==========================================

API_KEY = os.getenv(
    "API_KEY",
    "CHANGE_THIS_SECRET_KEY"
)


# ==========================================
# 기본 페이지
# ==========================================

@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "service": "Roblox Bank API"
    })


# ==========================================
# 유저 데이터 생성
# ==========================================

def ensure_user(user_id):

    user_id = str(user_id)

    if user_id not in balances:

        balances[user_id] = {
            "balance": 0,
            "account_balance": 0
        }


    if user_id not in transactions:

        transactions[user_id] = []


# ==========================================
# 거래내역 추가
# ==========================================

def add_transaction(
    user_id,
    transaction_type,
    amount,
    message
):

    user_id = str(user_id)

    ensure_user(user_id)


    transaction = {

        "type": transaction_type,

        "amount": int(amount),

        "message": message,

        "time": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    }


    # 최신 거래가 위로 오도록 추가
    transactions[user_id].insert(
        0,
        transaction
    )


    # 최대 50개까지만 저장
    if len(transactions[user_id]) > 50:

        transactions[user_id] = (
            transactions[user_id][:50]
        )


# ==========================================
# Discord 봇 → API
# 현금 / 계좌 잔액 업데이트
# ==========================================

@app.route(
    "/update_balance",
    methods=["POST"]
)
def update_balance():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # API 키 확인

    if data.get("api_key") != API_KEY:

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = str(
        data.get("roblox_user_id")
    )


    if not roblox_user_id:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    ensure_user(
        roblox_user_id
    )


    # 현금

    balance = data.get(
        "balance"
    )


    # 계좌

    account_balance = data.get(
        "account_balance"
    )


    # 현금 업데이트

    if balance is not None:

        balances[
            roblox_user_id
        ]["balance"] = int(balance)


    # 계좌 업데이트

    if account_balance is not None:

        balances[
            roblox_user_id
        ]["account_balance"] = int(
            account_balance
        )


    return jsonify({

        "success": True,

        "roblox_user_id":
        roblox_user_id,

        "balance":
        balances[
            roblox_user_id
        ]["balance"],

        "account_balance":
        balances[
            roblox_user_id
        ]["account_balance"]

    })


# ==========================================
# 잔액 조회
# ==========================================

@app.route(
    "/balance/<roblox_user_id>",
    methods=["GET"]
)
def get_balance(
    roblox_user_id
):

    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    return jsonify({

        "success": True,

        "roblox_user_id":
        roblox_user_id,

        "balance":
        balances[
            roblox_user_id
        ]["balance"],

        "account_balance":
        balances[
            roblox_user_id
        ]["account_balance"]

    })


# ==========================================
# 출금
# 계좌 → 현금
# ==========================================

@app.route(
    "/withdraw",
    methods=["POST"]
)
def withdraw():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # API 키 확인

    if data.get("api_key") != API_KEY:

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    user_id = str(
        data.get("roblox_user_id")
    )


    amount = int(
        data.get("amount", 0)
    )


    if amount <= 0:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    ensure_user(
        user_id
    )


    # 계좌 잔액 부족

    if balances[
        user_id
    ]["account_balance"] < amount:

        return jsonify({

            "success": False,

            "error":
            "계좌 잔액이 부족합니다."

        })


    # 계좌 차감

    balances[
        user_id
    ]["account_balance"] -= amount


    # 현금 증가

    balances[
        user_id
    ]["balance"] += amount


    # 거래내역 추가

    add_transaction(

        user_id,

        "withdraw",

        amount,

        f"{amount:,}원 출금"

    )


    return jsonify({

        "success": True,

        "balance":
        balances[
            user_id
        ]["balance"],

        "account_balance":
        balances[
            user_id
        ]["account_balance"]

    })


# ==========================================
# 입금
# 현금 → 계좌
# ==========================================

@app.route(
    "/deposit",
    methods=["POST"]
)
def deposit():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # API 키 확인

    if data.get("api_key") != API_KEY:

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    user_id = str(
        data.get("roblox_user_id")
    )


    amount = int(
        data.get("amount", 0)
    )


    if amount <= 0:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    ensure_user(
        user_id
    )


    # 현금 부족

    if balances[
        user_id
    ]["balance"] < amount:

        return jsonify({

            "success": False,

            "error":
            "보유 현금이 부족합니다."

        })


    # 현금 차감

    balances[
        user_id
    ]["balance"] -= amount


    # 계좌 증가

    balances[
        user_id
    ]["account_balance"] += amount


    # 거래내역 추가

    add_transaction(

        user_id,

        "deposit",

        amount,

        f"{amount:,}원 입금"

    )


    return jsonify({

        "success": True,

        "balance":
        balances[
            user_id
        ]["balance"],

        "account_balance":
        balances[
            user_id
        ]["account_balance"]

    })


# ==========================================
# 송금
# 송금자 계좌 → 받는 사람 계좌
# ==========================================

@app.route(
    "/transfer",
    methods=["POST"]
)
def transfer():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # API 키 확인

    if data.get("api_key") != API_KEY:

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    sender_id = str(
        data.get("sender_id")
    )


    receiver_id = str(
        data.get("receiver_id")
    )


    amount = int(
        data.get("amount", 0)
    )


    if amount <= 0:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    if sender_id == receiver_id:

        return jsonify({

            "success": False,

            "error":
            "자기 자신에게 송금할 수 없습니다."

        })


    ensure_user(
        sender_id
    )

    ensure_user(
        receiver_id
    )


    # 송금자 계좌 잔액 부족

    if balances[
        sender_id
    ]["account_balance"] < amount:

        return jsonify({

            "success": False,

            "error":
            "계좌 잔액이 부족합니다."

        })


    # 송금자 계좌 차감

    balances[
        sender_id
    ]["account_balance"] -= amount


    # 받는 사람 계좌 증가

    balances[
        receiver_id
    ]["account_balance"] += amount


    # ======================================
    # 거래내역 저장
    # ======================================

    add_transaction(

        sender_id,

        "transfer_sent",

        amount,

        f"{amount:,}원 송금"

    )


    add_transaction(

        receiver_id,

        "transfer_received",

        amount,

        f"{amount:,}원 입금 받음"

    )


    return jsonify({

        "success": True,

        "sender_account_balance":
        balances[
            sender_id
        ]["account_balance"],

        "receiver_account_balance":
        balances[
            receiver_id
        ]["account_balance"]

    })


# ==========================================
# 거래내역 조회
# ==========================================

@app.route(
    "/transactions/<roblox_user_id>",
    methods=["GET"]
)
def get_transactions(
    roblox_user_id
):

    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    return jsonify({

        "success": True,

        "transactions":
        transactions[
            roblox_user_id
        ]

    })


# ==========================================
# 서버 실행
# ==========================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            5000
        )
    )


    app.run(

        host="0.0.0.0",

        port=port

    )
