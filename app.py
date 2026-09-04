from flask import Flask, request, jsonify
import os
import sqlite3
from threading import Lock

app = Flask(__name__)

# ==============================
# API 보안키
# ==============================

API_KEY = os.getenv("API_KEY", "CHANGE_THIS_SECRET_KEY")

# SQLite 데이터베이스
DB_PATH = os.getenv("DB_PATH", "bank.db")

# 거래 중 데이터 충돌 방지
db_lock = Lock()


# ==============================
# 데이터베이스 연결
# ==============================

def get_db():

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


# ==============================
# 데이터베이스 초기화
# ==============================

def init_db():

    with db_lock:

        db = get_db()

        cursor = db.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                roblox_user_id TEXT PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                account_balance INTEGER NOT NULL DEFAULT 0
            )
        """)

        db.commit()

        db.close()


init_db()


# ==============================
# 유저 데이터 생성
# ==============================

def ensure_user(db, roblox_user_id):

    cursor = db.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO balances
        (
            roblox_user_id,
            balance,
            account_balance
        )
        VALUES (?, 0, 0)
    """, (str(roblox_user_id),))

    db.commit()


# ==============================
# 유저 잔액 가져오기
# ==============================

def get_user_data(db, roblox_user_id):

    ensure_user(
        db,
        roblox_user_id
    )

    cursor = db.cursor()

    cursor.execute("""
        SELECT
            balance,
            account_balance
        FROM balances
        WHERE roblox_user_id = ?
    """, (str(roblox_user_id),))

    row = cursor.fetchone()

    return {
        "balance": int(row["balance"]),
        "account_balance": int(
            row["account_balance"]
        )
    }


# ==============================
# 홈페이지
# ==============================

@app.route("/")
def home():

    return jsonify({
        "status": "online",
        "service": "Roblox Bank API"
    })


# ==============================
# Discord 봇 → 잔액 업데이트
# ==============================

@app.route(
    "/update_balance",
    methods=["POST"]
)
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


    roblox_user_id = str(
        data.get("roblox_user_id")
    )

    if not roblox_user_id:

        return jsonify({
            "success": False,
            "error": "roblox_user_id가 없습니다."
        }), 400


    balance = data.get("balance")

    account_balance = data.get(
        "account_balance"
    )


    try:

        with db_lock:

            db = get_db()

            ensure_user(
                db,
                roblox_user_id
            )

            updates = []

            values = []


            # 현금 업데이트

            if balance is not None:

                balance = int(balance)

                if balance < 0:

                    db.close()

                    return jsonify({
                        "success": False,
                        "error": "현금은 음수가 될 수 없습니다."
                    }), 400


                updates.append(
                    "balance = ?"
                )

                values.append(
                    balance
                )


            # 계좌 업데이트

            if account_balance is not None:

                account_balance = int(
                    account_balance
                )

                if account_balance < 0:

                    db.close()

                    return jsonify({
                        "success": False,
                        "error": "계좌 잔액은 음수가 될 수 없습니다."
                    }), 400


                updates.append(
                    "account_balance = ?"
                )

                values.append(
                    account_balance
                )


            if updates:

                values.append(
                    roblox_user_id
                )

                cursor = db.cursor()

                cursor.execute(
                    f"""
                    UPDATE balances
                    SET {", ".join(updates)}
                    WHERE roblox_user_id = ?
                    """,
                    values
                )

                db.commit()


            user_data = get_user_data(
                db,
                roblox_user_id
            )

            db.close()


        return jsonify({

            "success": True,

            "roblox_user_id":
                roblox_user_id,

            "balance":
                user_data["balance"],

            "account_balance":
                user_data["account_balance"]

        })


    except ValueError:

        return jsonify({
            "success": False,
            "error": "잔액 값이 올바르지 않습니다."
        }), 400


    except Exception as error:

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==============================
# Roblox 게임 → 잔액 조회
# ==============================

@app.route(
    "/balance/<roblox_user_id>",
    methods=["GET"]
)
def get_balance(roblox_user_id):

    try:

        with db_lock:

            db = get_db()

            user_data = get_user_data(
                db,
                roblox_user_id
            )

            db.close()


        return jsonify({

            "success": True,

            "roblox_user_id":
                str(roblox_user_id),

            "balance":
                user_data["balance"],

            "account_balance":
                user_data["account_balance"]

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500


# ==============================
# ATM 출금
#
# 계좌 → 현금
# ==============================

@app.route(
    "/withdraw",
    methods=["POST"]
)
def withdraw():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "error": "데이터가 없습니다."
        }), 400


    if data.get("api_key") != API_KEY:

        return jsonify({
            "success": False,
            "error": "API 키가 올바르지 않습니다."
        }), 403


    roblox_user_id = str(
        data.get("roblox_user_id")
    )


    try:

        amount = int(
            data.get("amount", 0)
        )


    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "error": "금액이 올바르지 않습니다."
        }), 400


    if amount <= 0:

        return jsonify({
            "success": False,
            "error": "금액은 1원 이상이어야 합니다."
        }), 400


    try:

        with db_lock:

            db = get_db()

            user_data = get_user_data(
                db,
                roblox_user_id
            )


            # 계좌 잔액 부족

            if user_data["account_balance"] < amount:

                db.close()

                return jsonify({

                    "success": False,

                    "error":
                        "계좌 잔액이 부족합니다."

                }), 400


            new_account_balance = (
                user_data["account_balance"]
                - amount
            )


            new_balance = (
                user_data["balance"]
                + amount
            )


            cursor = db.cursor()

            cursor.execute("""
                UPDATE balances
                SET
                    balance = ?,
                    account_balance = ?
                WHERE roblox_user_id = ?
            """, (

                new_balance,

                new_account_balance,

                roblox_user_id

            ))


            db.commit()

            db.close()


        return jsonify({

            "success": True,

            "message":
                "출금이 완료되었습니다.",

            "balance":
                new_balance,

            "account_balance":
                new_account_balance

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500


# ==============================
# ATM 입금
#
# 현금 → 계좌
# ==============================

@app.route(
    "/deposit",
    methods=["POST"]
)
def deposit():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "error": "데이터가 없습니다."
        }), 400


    if data.get("api_key") != API_KEY:

        return jsonify({
            "success": False,
            "error": "API 키가 올바르지 않습니다."
        }), 403


    roblox_user_id = str(
        data.get("roblox_user_id")
    )


    try:

        amount = int(
            data.get("amount", 0)
        )


    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "error": "금액이 올바르지 않습니다."
        }), 400


    if amount <= 0:

        return jsonify({
            "success": False,
            "error": "금액은 1원 이상이어야 합니다."
        }), 400


    try:

        with db_lock:

            db = get_db()

            user_data = get_user_data(
                db,
                roblox_user_id
            )


            # 현금 부족

            if user_data["balance"] < amount:

                db.close()

                return jsonify({

                    "success": False,

                    "error":
                        "보유 현금이 부족합니다."

                }), 400


            new_balance = (
                user_data["balance"]
                - amount
            )


            new_account_balance = (
                user_data["account_balance"]
                + amount
            )


            cursor = db.cursor()

            cursor.execute("""
                UPDATE balances
                SET
                    balance = ?,
                    account_balance = ?
                WHERE roblox_user_id = ?
            """, (

                new_balance,

                new_account_balance,

                roblox_user_id

            ))


            db.commit()

            db.close()


        return jsonify({

            "success": True,

            "message":
                "입금이 완료되었습니다.",

            "balance":
                new_balance,

            "account_balance":
                new_account_balance

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500


# ==============================
# ATM 송금
#
# 내 계좌 → 상대 계좌
# ==============================

@app.route(
    "/transfer",
    methods=["POST"]
)
def transfer():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "error": "데이터가 없습니다."
        }), 400


    if data.get("api_key") != API_KEY:

        return jsonify({
            "success": False,
            "error": "API 키가 올바르지 않습니다."
        }), 403


    sender_id = str(
        data.get("sender_id")
    )

    receiver_id = str(
        data.get("receiver_id")
    )


    if sender_id == receiver_id:

        return jsonify({

            "success": False,

            "error":
                "자기 자신에게 송금할 수 없습니다."

        }), 400


    try:

        amount = int(
            data.get("amount", 0)
        )


    except (ValueError, TypeError):

        return jsonify({

            "success": False,

            "error":
                "금액이 올바르지 않습니다."

        }), 400


    if amount <= 0:

        return jsonify({

            "success": False,

            "error":
                "금액은 1원 이상이어야 합니다."

        }), 400


    try:

        with db_lock:

            db = get_db()


            # 두 유저 데이터 확인

            sender_data = get_user_data(
                db,
                sender_id
            )

            receiver_data = get_user_data(
                db,
                receiver_id
            )


            # 송금자 계좌 잔액 부족

            if (
                sender_data["account_balance"]
                < amount
            ):

                db.close()

                return jsonify({

                    "success": False,

                    "error":
                        "계좌 잔액이 부족합니다."

                }), 400


            new_sender_account = (
                sender_data["account_balance"]
                - amount
            )


            new_receiver_account = (
                receiver_data["account_balance"]
                + amount
            )


            cursor = db.cursor()


            # 송금자 계좌 감소

            cursor.execute("""
                UPDATE balances
                SET account_balance = ?
                WHERE roblox_user_id = ?
            """, (

                new_sender_account,

                sender_id

            ))


            # 수신자 계좌 증가

            cursor.execute("""
                UPDATE balances
                SET account_balance = ?
                WHERE roblox_user_id = ?
            """, (

                new_receiver_account,

                receiver_id

            ))


            db.commit()

            db.close()


        return jsonify({

            "success": True,

            "message":
                "송금이 완료되었습니다.",

            "sender_account_balance":
                new_sender_account,

            "receiver_account_balance":
                new_receiver_account

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "error":
                str(error)

        }), 500


# ==============================
# 서버 실행
# ==============================

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
