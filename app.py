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
        data.get("api_key") == API_KEY
    )


# ==========================================
# 숫자 확인
# ==========================================

def parse_amount(value):

    try:

        amount = int(value)


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
#
# 주의:
# 이 기능은 외부 데이터로 잔액을
# 강제로 설정하는 기능입니다.
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


        # ==================================
        # 기존 잔액 잠금
        # ==================================

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


        # ==================================
        # 현금 업데이트
        # ==================================

        if balance is not None:

            try:

                balance = int(
                    balance
                )


            except:

                return jsonify({

                    "success": False,

                    "error":
                    "balance 값이 올바르지 않습니다."

                }), 400


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


        # ==================================
        # 계좌 업데이트
        # ==================================

        if account_balance is not None:

            try:

                account_balance = int(
                    account_balance
                )


            except:

                return jsonify({

                    "success": False,

                    "error":
                    "account_balance 값이 올바르지 않습니다."

                }), 400


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


        # 최신 데이터 조회

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


        print(
            "[Bank API] 잔액 업데이트 오류:",
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
# 출금
#
# 계좌 → 현금
# PostgreSQL에 즉시 저장
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

        data.get(
            "amount"
        )

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


        # ==================================
        # 유저 행 잠금
        # ==================================

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


        if not user:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "유저 정보를 찾을 수 없습니다."

            }), 404


        # ==================================
        # 계좌 잔액 확인
        # ==================================

        if int(
            user["account_balance"]
        ) < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        # ==================================
        # 계좌 감소
        # 현금 증가
        #
        # 같은 SQL 트랜잭션에서 저장
        # ==================================

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


        # ==================================
        # 거래내역 저장
        # ==================================

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


        # ==================================
        # 여기서 실제 영구 저장
        # ==================================

        connection.commit()


        # ==================================
        # 저장된 최신 잔액 조회
        # ==================================

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


        print(

            f"[Bank API] 출금 완료 | "
            f"{roblox_user_id} | "
            f"{amount:,}원"

        )


        return jsonify({

            "success": True,

            "message":
            f"{amount:,}원 출금 완료",

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


        print(

            "[Bank API] 출금 오류:",
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
# 입금
#
# 현금 → 계좌
# PostgreSQL에 즉시 저장
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

        data.get(
            "amount"
        )

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


        # ==================================
        # 유저 행 잠금
        # ==================================

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


        if not user:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "유저 정보를 찾을 수 없습니다."

            }), 404


        # ==================================
        # 현금 부족 확인
        # ==================================

        if int(
            user["balance"]
        ) < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "보유 현금이 부족합니다."

            })


        # ==================================
        # 현금 감소
        # 계좌 증가
        # ==================================

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


        # ==================================
        # 거래내역 영구 저장
        # ==================================

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


        # ==================================
        # 실제 PostgreSQL 영구 저장
        # ==================================

        connection.commit()


        # 최신 저장 데이터 조회

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


        print(

            f"[Bank API] 입금 완료 | "
            f"{roblox_user_id} | "
            f"{amount:,}원"

        )


        return jsonify({

            "success": True,

            "message":
            f"{amount:,}원 입금 완료",

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


        print(

            "[Bank API] 입금 오류:",
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
# 송금
#
# 송금자 계좌
# ↓
# 받는 사람 계좌
#
# 두 계좌를 하나의 트랜잭션으로 저장
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

        data.get(
            "amount"
        )

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


        # ==================================
        # 데드락 방지
        # ID 순서대로 잠금
        # ==================================

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


        receiver = user_map.get(
            receiver_id
        )


        if not sender or not receiver:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "유저 정보를 찾을 수 없습니다."

            }), 404


        # ==================================
        # 송금자 계좌 확인
        # ==================================

        if int(
            sender[
                "account_balance"
            ]
        ) < amount:

            connection.rollback()


            return jsonify({

                "success": False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        # ==================================
        # 송금자 계좌 감소
        # ==================================

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


        # ==================================
        # 받는 사람 계좌 증가
        # ==================================

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


        # ==================================
        # 송금자 거래내역
        # ==================================

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


        # ==================================
        # 받는 사람 거래내역
        # ==================================

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


        # ==================================
        # 모든 작업을 한 번에 영구 저장
        # ==================================

        connection.commit()


        # ==================================
        # 최신 잔액 조회
        # ==================================

        cursor.execute(

            """
            SELECT

                roblox_user_id,

                balance,

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


        sender_data = updated_map[
            sender_id
        ]

        receiver_data = updated_map[
            receiver_id
        ]


        print(

            f"[Bank API] 송금 완료 | "
            f"{sender_id} → "
            f"{receiver_id} | "
            f"{amount:,}원"

        )


        return jsonify({

            "success": True,

            "message":
            f"{amount:,}원 송금 완료",

            "sender_balance":
            int(
                sender_data[
                    "balance"
                ]
            ),

            "sender_account_balance":
            int(
                sender_data[
                    "account_balance"
                ]
            ),

            "receiver_balance":
            int(
                receiver_data[
                    "balance"
                ]
            ),

            "receiver_account_balance":
            int(
                receiver_data[
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

            created_at = row[
                "created_at"
            ]


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
                created_at.strftime(
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
