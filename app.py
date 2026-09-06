from flask import Flask, request, jsonify
import os

import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)


# ==========================================
# 환경변수
# ==========================================

API_KEY = os.getenv(
    "API_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)


# ==========================================
# 데이터베이스 연결
# ==========================================

def get_db_connection():

    if not DATABASE_URL:

        raise Exception(
            "DATABASE_URL 환경변수가 설정되지 않았습니다."
        )


    connection = psycopg2.connect(

        DATABASE_URL,

        cursor_factory=RealDictCursor

    )


    return connection


# ==========================================
# 데이터베이스 초기화
# ==========================================

def initialize_database():

    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        # ==================================
        # 유저 잔액 테이블
        # ==================================

        cursor.execute(

            """
            CREATE TABLE IF NOT EXISTS users (

                roblox_user_id TEXT PRIMARY KEY,

                balance BIGINT NOT NULL DEFAULT 0,

                account_balance BIGINT NOT NULL DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
            """

        )


        # ==================================
        # 거래내역 테이블
        # ==================================

        cursor.execute(

            """
            CREATE TABLE IF NOT EXISTS transactions (

                id BIGSERIAL PRIMARY KEY,

                roblox_user_id TEXT NOT NULL,

                transaction_type TEXT NOT NULL,

                amount BIGINT NOT NULL,

                message TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
            """

        )


        # ==================================
        # 거래내역 조회 인덱스
        # ==================================

        cursor.execute(

            """
            CREATE INDEX IF NOT EXISTS
            idx_transactions_user_id

            ON transactions
            (
                roblox_user_id
            )
            """

        )


        # ==================================
        # 운전면허 테이블
        # ==================================

        cursor.execute(

            """
            CREATE TABLE IF NOT EXISTS driving_licenses (

                roblox_user_id TEXT PRIMARY KEY,

                has_driving_license BOOLEAN
                NOT NULL DEFAULT FALSE,

                updated_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP

            )
            """

        )


        connection.commit()


        print(
            "[Bank API] 데이터베이스 초기화 완료"
        )


    except Exception as error:

        print(
            "[Bank API] 데이터베이스 초기화 실패:",
            error
        )

        raise


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# 유저 생성
# ==========================================

def ensure_user(
    roblox_user_id
):

    roblox_user_id = str(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            INSERT INTO users
            (
                roblox_user_id,
                balance,
                account_balance
            )

            VALUES
            (
                %s,
                0,
                0
            )

            ON CONFLICT
            (
                roblox_user_id
            )

            DO NOTHING
            """,

            (
                roblox_user_id,
            )

        )


        connection.commit()


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# API 키 확인
# ==========================================

def check_api_key(data):

    return (

        data

        and

        data.get(
            "api_key"
        ) == API_KEY

    )


# ==========================================
# 숫자 확인
# ==========================================

def parse_amount(value):

    try:

        amount = int(
            value
        )


    except:

        return None


    if amount <= 0:

        return None


    return amount


# ==========================================
# 유저 잔액 조회
# ==========================================

def get_user_balance(
    roblox_user_id
):

    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s
            """,

            (
                roblox_user_id,
            )

        )


        user = cursor.fetchone()


        if not user:

            return {

                "balance": 0,

                "account_balance": 0

            }


        return {

            "balance":

            int(
                user["balance"]
            ),

            "account_balance":

            int(
                user["account_balance"]
            )

        }


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# 기본 페이지
# ==========================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({

        "status":
        "online",

        "service":
        "Roblox Bank API",

        "database":
        "PostgreSQL Connected"

    })


# ==========================================
# Discord 봇 잔액 동기화
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


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = data.get(
        "roblox_user_id"
    )


    if roblox_user_id is None:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    balance = data.get(
        "balance"
    )


    account_balance = data.get(
        "account_balance"
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        if balance is not None:

            balance = int(
                balance
            )


            if balance < 0:

                return jsonify({

                    "success": False,

                    "error":
                    "잔액은 음수가 될 수 없습니다."

                }), 400


            cursor.execute(

                """
                UPDATE users

                SET

                    balance = %s,

                    updated_at =
                    CURRENT_TIMESTAMP

                WHERE roblox_user_id = %s
                """,

                (

                    balance,

                    roblox_user_id

                )

            )


        if account_balance is not None:

            account_balance = int(
                account_balance
            )


            if account_balance < 0:

                return jsonify({

                    "success": False,

                    "error":
                    "계좌 잔액은 음수가 될 수 없습니다."

                }), 400


            cursor.execute(

                """
                UPDATE users

                SET

                    account_balance = %s,

                    updated_at =
                    CURRENT_TIMESTAMP

                WHERE roblox_user_id = %s
                """,

                (

                    account_balance,

                    roblox_user_id

                )

            )


        connection.commit()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s
            """,

            (
                roblox_user_id,
            )

        )


        user = cursor.fetchone()


        return jsonify({

            "success": True,

            "roblox_user_id":
            roblox_user_id,

            "balance":
            int(
                user["balance"]
            ),

            "account_balance":
            int(
                user["account_balance"]
            )

        })


    except Exception as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


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

    user = get_user_balance(
        roblox_user_id
    )


    return jsonify({

        "success": True,

        "roblox_user_id":
        str(
            roblox_user_id
        ),

        "balance":
        user["balance"],

        "account_balance":
        user["account_balance"]

    })


# ==========================================
# 운전면허 조회
# Roblox 게임에서 사용
# ==========================================

@app.route(
    "/driving-license/<roblox_user_id>",
    methods=["GET"]
)
def get_driving_license(
    roblox_user_id
):

    api_key = request.args.get(
        "api_key"
    )


    if api_key != API_KEY:

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = str(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            SELECT

                has_driving_license

            FROM driving_licenses

            WHERE roblox_user_id = %s
            """,

            (
                roblox_user_id,
            )

        )


        license_data = cursor.fetchone()


        if not license_data:

            return jsonify({

                "success": True,

                "roblox_user_id":
                roblox_user_id,

                "has_driving_license":
                False

            })


        return jsonify({

            "success": True,

            "roblox_user_id":
            roblox_user_id,

            "has_driving_license":

            bool(
                license_data[
                    "has_driving_license"
                ]
            )

        })


    except Exception as error:

        print(

            "[Bank API] 운전면허 조회 오류:",
            error

        )


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# 운전면허 지급
# ==========================================

@app.route(
    "/driving-license/grant",
    methods=["POST"]
)
def grant_driving_license():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = data.get(
        "roblox_user_id"
    )


    if roblox_user_id is None:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    roblox_user_id = str(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            INSERT INTO driving_licenses

            (
                roblox_user_id,

                has_driving_license,

                updated_at
            )

            VALUES
            (
                %s,

                TRUE,

                CURRENT_TIMESTAMP
            )

            ON CONFLICT
            (
                roblox_user_id
            )

            DO UPDATE SET

                has_driving_license = TRUE,

                updated_at =
                CURRENT_TIMESTAMP
            """,

            (
                roblox_user_id,
            )

        )


        connection.commit()


        return jsonify({

            "success": True,

            "roblox_user_id":
            roblox_user_id,

            "has_driving_license":
            True

        })


    except Exception as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# 운전면허 제거
# ==========================================

@app.route(
    "/driving-license/revoke",
    methods=["POST"]
)
def revoke_driving_license():

    data = request.get_json()


    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = data.get(
        "roblox_user_id"
    )


    if roblox_user_id is None:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    roblox_user_id = str(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            INSERT INTO driving_licenses

            (
                roblox_user_id,

                has_driving_license,

                updated_at
            )

            VALUES
            (
                %s,

                FALSE,

                CURRENT_TIMESTAMP
            )

            ON CONFLICT
            (
                roblox_user_id
            )

            DO UPDATE SET

                has_driving_license = FALSE,

                updated_at =
                CURRENT_TIMESTAMP
            """,

            (
                roblox_user_id,
            )

        )


        connection.commit()


        return jsonify({

            "success": True,

            "roblox_user_id":
            roblox_user_id,

            "has_driving_license":
            False

        })


    except Exception as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


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


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = data.get(
        "roblox_user_id"
    )


    if roblox_user_id is None:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    amount = parse_amount(
        data.get("amount")
    )


    if amount is None:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s

            FOR UPDATE
            """,

            (
                roblox_user_id,
            )

        )


        user = cursor.fetchone()


        if user["account_balance"] < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        cursor.execute(

            """
            UPDATE users

            SET

                balance =
                balance + %s,

                account_balance =
                account_balance - %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s
            """,

            (

                amount,

                amount,

                roblox_user_id

            )

        )


        cursor.execute(

            """
            INSERT INTO transactions

            (
                roblox_user_id,

                transaction_type,

                amount,

                message
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,

            (

                roblox_user_id,

                "withdraw",

                amount,

                f"{amount:,}원 출금"

            )

        )


        connection.commit()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s
            """,

            (
                roblox_user_id,
            )

        )


        updated_user = cursor.fetchone()


        return jsonify({

            "success": True,

            "balance":
            int(
                updated_user["balance"]
            ),

            "account_balance":
            int(
                updated_user["account_balance"]
            )

        })


    except Exception as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


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


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    roblox_user_id = data.get(
        "roblox_user_id"
    )


    if roblox_user_id is None:

        return jsonify({

            "success": False,

            "error":
            "roblox_user_id가 없습니다."

        }), 400


    amount = parse_amount(
        data.get("amount")
    )


    if amount is None:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    roblox_user_id = str(
        roblox_user_id
    )


    ensure_user(
        roblox_user_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s

            FOR UPDATE
            """,

            (
                roblox_user_id,
            )

        )


        user = cursor.fetchone()


        if user["balance"] < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "보유 현금이 부족합니다."

            })


        cursor.execute(

            """
            UPDATE users

            SET

                balance =
                balance - %s,

                account_balance =
                account_balance + %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s
            """,

            (

                amount,

                amount,

                roblox_user_id

            )

        )


        cursor.execute(

            """
            INSERT INTO transactions

            (
                roblox_user_id,

                transaction_type,

                amount,

                message
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,

            (

                roblox_user_id,

                "deposit",

                amount,

                f"{amount:,}원 입금"

            )

        )


        connection.commit()


        cursor.execute(

            """
            SELECT

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id = %s
            """,

            (
                roblox_user_id,
            )

        )


        updated_user = cursor.fetchone()


        return jsonify({

            "success": True,

            "balance":
            int(
                updated_user["balance"]
            ),

            "account_balance":
            int(
                updated_user["account_balance"]
            )

        })


    except Exception as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


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


    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    sender_id = data.get(
        "sender_id"
    )


    receiver_id = data.get(
        "receiver_id"
    )


    if sender_id is None or receiver_id is None:

        return jsonify({

            "success": False,

            "error":
            "송금 대상 정보가 없습니다."

        }), 400


    amount = parse_amount(
        data.get("amount")
    )


    if amount is None:

        return jsonify({

            "success": False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    sender_id = str(
        sender_id
    )

    receiver_id = str(
        receiver_id
    )


    if sender_id == receiver_id:

        return jsonify({

            "success": False,

            "error":
            "자기 자신에게 송금할 수 없습니다."

        }), 400


    ensure_user(
        sender_id
    )

    ensure_user(
        receiver_id
    )


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        first_id = min(
            sender_id,
            receiver_id
        )

        second_id = max(
            sender_id,
            receiver_id
        )


        cursor.execute(

            """
            SELECT

                roblox_user_id,

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id
            IN (%s, %s)

            ORDER BY roblox_user_id

            FOR UPDATE
            """,

            (

                first_id,

                second_id

            )

        )


        users = cursor.fetchall()


        user_map = {

            row[
                "roblox_user_id"
            ]: row

            for row in users

        }


        sender = user_map.get(
            sender_id
        )


        if not sender:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "송금자 정보를 찾을 수 없습니다."

            })


        if sender[
            "account_balance"
        ] < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        cursor.execute(

            """
            UPDATE users

            SET

                account_balance =
                account_balance - %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s
            """,

            (

                amount,

                sender_id

            )

        )


        cursor.execute(

            """
            UPDATE users

            SET

                account_balance =
                account_balance + %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s
            """,

            (

                amount,

                receiver_id

            )

        )


        cursor.execute(

            """
            INSERT INTO transactions

            (
                roblox_user_id,

                transaction_type,

                amount,

                message
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,

            (

                sender_id,

                "transfer_sent",

                amount,

                f"{amount:,}원 송금"

            )

        )


        cursor.execute(

            """
            INSERT INTO transactions

            (
                roblox_user_id,

                transaction_type,

                amount,

                message
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,

            (

                receiver_id,

                "transfer_received",

                amount,

                f"{amount:,}원 송금 받음"

            )

        )


        connection.commit()


        cursor.execute(

            """
            SELECT

                roblox_user_id,

                account_balance

            FROM users

            WHERE roblox_user_id
            IN (%s, %s)
            """,

            (

                sender_id,

                receiver_id

            )

        )


        updated_users = cursor.fetchall()


        updated_map = {

            row[
                "roblox_user_id"
            ]: row

            for row in updated_users

        }


        return jsonify({

            "success": True,

            "sender_account_balance":

            int(
                updated_map[
                    sender_id
                ][
                    "account_balance"
                ]
            ),

            "receiver_account_balance":

            int(
                updated_map[
                    receiver_id
                ][
                    "account_balance"
                ]
            )

        })


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] 송금 오류:",
            error

        )


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


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


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(

            """
            SELECT

                id,

                transaction_type,

                amount,

                message,

                created_at

            FROM transactions

            WHERE roblox_user_id = %s

            ORDER BY id DESC

            LIMIT 100
            """,

            (
                roblox_user_id,
            )

        )


        rows = cursor.fetchall()


        transaction_list = []


        for row in rows:

            transaction_list.append({

                "id":
                row["id"],

                "type":
                row[
                    "transaction_type"
                ],

                "amount":
                int(
                    row["amount"]
                ),

                "message":
                row["message"],

                "time":
                row[
                    "created_at"
                ].strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            })


        return jsonify({

            "success": True,

            "transactions":
            transaction_list

        })


    except Exception as error:

        print(

            "[Bank API] 거래내역 조회 오류:",
            error

        )


        return jsonify({

            "success": False,

            "error":
            str(error)

        }), 500


    finally:

        if cursor:

            cursor.close()


        if connection:

            connection.close()


# ==========================================
# 서버 실행
# ==========================================

if __name__ == "__main__":

    initialize_database()


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
