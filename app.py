from flask import Flask, request, jsonify
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


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
        sslmode="require"
    )


    return connection


# ==========================================
# 데이터베이스 초기화
# ==========================================

def initialize_database():

    connection = None

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

                created_at TIMESTAMP WITH TIME ZONE
                DEFAULT CURRENT_TIMESTAMP,

                updated_at TIMESTAMP WITH TIME ZONE
                DEFAULT CURRENT_TIMESTAMP

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

                message TEXT NOT NULL,

                created_at TIMESTAMP WITH TIME ZONE
                DEFAULT CURRENT_TIMESTAMP

            )

            """

        )


        # 거래내역 검색 속도 향상

        cursor.execute(

            """

            CREATE INDEX IF NOT EXISTS
            idx_transactions_user_id

            ON transactions (
                roblox_user_id,
                created_at DESC
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

        raise error


    finally:

        if connection:

            connection.close()


# ==========================================
# API 키 확인
# ==========================================

def check_api_key(data):

    if not data:

        return False


    return data.get(
        "api_key"
    ) == API_KEY


# ==========================================
# 유저 생성
# ==========================================

def ensure_user(
    cursor,
    user_id
):

    user_id = str(
        user_id
    )


    cursor.execute(

        """

        INSERT INTO users (

            roblox_user_id

        )

        VALUES (

            %s

        )

        ON CONFLICT (
            roblox_user_id
        )

        DO NOTHING

        """,

        (
            user_id,
        )

    )


# ==========================================
# 유저 잔액 가져오기
# ==========================================

def get_user_balance(
    cursor,
    user_id
):

    user_id = str(
        user_id
    )


    ensure_user(
        cursor,
        user_id
    )


    cursor.execute(

        """

        SELECT

            balance,

            account_balance

        FROM users

        WHERE roblox_user_id = %s

        """,

        (
            user_id,
        )

    )


    result = cursor.fetchone()


    if not result:

        return {

            "balance": 0,

            "account_balance": 0

        }


    return {

        "balance":
        int(result[0]),

        "account_balance":
        int(result[1])

    }


# ==========================================
# 거래내역 저장
# ==========================================

def add_transaction(

    cursor,

    user_id,

    transaction_type,

    amount,

    message

):

    cursor.execute(

        """

        INSERT INTO transactions (

            roblox_user_id,

            transaction_type,

            amount,

            message

        )

        VALUES (

            %s,

            %s,

            %s,

            %s

        )

        """,

        (

            str(user_id),

            str(transaction_type),

            int(amount),

            str(message)

        )

    )


# ==========================================
# 기본 페이지
# ==========================================

@app.route("/")
def home():

    return jsonify({

        "status":
        "online",

        "service":
        "Roblox Bank API",

        "database":
        "PostgreSQL"

    })


# ==========================================
# Discord 봇 → 잔액 업데이트
# ==========================================

@app.route(

    "/update_balance",

    methods=["POST"]

)
def update_balance():

    data = request.get_json()


    # ==============================
    # 데이터 확인
    # ==============================

    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # ==============================
    # API 키 확인
    # ==============================

    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    # ==============================
    # Roblox User ID
    # ==============================

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


    # ==============================
    # 잔액 데이터
    # ==============================

    balance = data.get(
        "balance"
    )

    account_balance = data.get(
        "account_balance"
    )


    # ==============================
    # 데이터베이스 연결
    # ==============================

    connection = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        ensure_user(

            cursor,

            roblox_user_id

        )


        # ==========================
        # 현금 업데이트
        # ==========================

        if balance is not None:

            balance = int(
                balance
            )


            if balance < 0:

                raise ValueError(
                    "현금은 음수가 될 수 없습니다."
                )


            cursor.execute(

                """

                UPDATE users

                SET

                    balance = %s,

                    updated_at =
                    CURRENT_TIMESTAMP

                WHERE
                    roblox_user_id = %s

                """,

                (

                    balance,

                    roblox_user_id

                )

            )


        # ==========================
        # 계좌 업데이트
        # ==========================

        if account_balance is not None:

            account_balance = int(
                account_balance
            )


            if account_balance < 0:

                raise ValueError(
                    "계좌 잔액은 음수가 될 수 없습니다."
                )


            cursor.execute(

                """

                UPDATE users

                SET

                    account_balance = %s,

                    updated_at =
                    CURRENT_TIMESTAMP

                WHERE
                    roblox_user_id = %s

                """,

                (

                    account_balance,

                    roblox_user_id

                )

            )


        # ==========================
        # 변경사항 저장
        # ==========================

        connection.commit()


        # 최신 잔액 조회

        user_data = get_user_balance(

            cursor,

            roblox_user_id

        )


        return jsonify({

            "success":
            True,

            "roblox_user_id":
            roblox_user_id,

            "balance":
            user_data["balance"],

            "account_balance":
            user_data[
                "account_balance"
            ]

        })


    except ValueError as error:

        if connection:

            connection.rollback()


        return jsonify({

            "success":
            False,

            "error":
            str(error)

        }), 400


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] update_balance 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "데이터베이스 오류가 발생했습니다."

        }), 500


    finally:

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

    connection = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        user_data = get_user_balance(

            cursor,

            roblox_user_id

        )


        connection.commit()


        return jsonify({

            "success":
            True,

            "roblox_user_id":
            str(
                roblox_user_id
            ),

            "balance":
            user_data[
                "balance"
            ],

            "account_balance":
            user_data[
                "account_balance"
            ]

        })


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] balance 조회 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "잔액을 불러오지 못했습니다."

        }), 500


    finally:

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


    # ==============================
    # 데이터 확인
    # ==============================

    if not data:

        return jsonify({

            "success": False,

            "error":
            "데이터가 없습니다."

        }), 400


    # ==============================
    # API 키 확인
    # ==============================

    if not check_api_key(data):

        return jsonify({

            "success": False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    # ==============================
    # 데이터 가져오기
    # ==============================

    user_id = str(

        data.get(
            "roblox_user_id"
        )

    )


    try:

        amount = int(

            data.get(
                "amount",
                0
            )

        )


    except:

        amount = 0


    if amount <= 0:

        return jsonify({

            "success":
            False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    connection = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        ensure_user(

            cursor,

            user_id

        )


        # ==================================
        # 행 잠금
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

                user_id,

            )

        )


        user_data = cursor.fetchone()


        cash_balance = int(
            user_data[0]
        )

        account_balance = int(
            user_data[1]
        )


        # 계좌 잔액 부족

        if account_balance < amount:

            connection.rollback()


            return jsonify({

                "success":
                False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        # ==============================
        # 계좌 차감
        # ==============================

        new_account_balance = (

            account_balance
            -
            amount

        )


        # ==============================
        # 현금 증가
        # ==============================

        new_cash_balance = (

            cash_balance
            +
            amount

        )


        cursor.execute(

            """

            UPDATE users

            SET

                balance = %s,

                account_balance = %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s

            """,

            (

                new_cash_balance,

                new_account_balance,

                user_id

            )

        )


        # ==============================
        # 거래내역
        # ==============================

        add_transaction(

            cursor,

            user_id,

            "withdraw",

            amount,

            f"{amount:,}원 출금"

        )


        connection.commit()


        return jsonify({

            "success":
            True,

            "balance":
            new_cash_balance,

            "account_balance":
            new_account_balance

        })


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] 출금 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "출금 처리 중 오류가 발생했습니다."

        }), 500


    finally:

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

            "success":
            False,

            "error":
            "데이터가 없습니다."

        }), 400


    if not check_api_key(data):

        return jsonify({

            "success":
            False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    user_id = str(

        data.get(
            "roblox_user_id"
        )

    )


    try:

        amount = int(

            data.get(
                "amount",
                0
            )

        )


    except:

        amount = 0


    if amount <= 0:

        return jsonify({

            "success":
            False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    connection = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        ensure_user(

            cursor,

            user_id

        )


        # ==================================
        # 행 잠금
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

                user_id,

            )

        )


        user_data = cursor.fetchone()


        cash_balance = int(
            user_data[0]
        )

        account_balance = int(
            user_data[1]
        )


        # 현금 부족

        if cash_balance < amount:

            connection.rollback()


            return jsonify({

                "success":
                False,

                "error":
                "보유 현금이 부족합니다."

            })


        new_cash_balance = (

            cash_balance
            -
            amount

        )


        new_account_balance = (

            account_balance
            +
            amount

        )


        cursor.execute(

            """

            UPDATE users

            SET

                balance = %s,

                account_balance = %s,

                updated_at =
                CURRENT_TIMESTAMP

            WHERE roblox_user_id = %s

            """,

            (

                new_cash_balance,

                new_account_balance,

                user_id

            )

        )


        # 거래내역

        add_transaction(

            cursor,

            user_id,

            "deposit",

            amount,

            f"{amount:,}원 입금"

        )


        connection.commit()


        return jsonify({

            "success":
            True,

            "balance":
            new_cash_balance,

            "account_balance":
            new_account_balance

        })


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] 입금 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "입금 처리 중 오류가 발생했습니다."

        }), 500


    finally:

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

            "success":
            False,

            "error":
            "데이터가 없습니다."

        }), 400


    if not check_api_key(data):

        return jsonify({

            "success":
            False,

            "error":
            "API 키가 올바르지 않습니다."

        }), 403


    sender_id = str(

        data.get(
            "sender_id"
        )

    )


    receiver_id = str(

        data.get(
            "receiver_id"
        )

    )


    try:

        amount = int(

            data.get(
                "amount",
                0
            )

        )


    except:

        amount = 0


    if amount <= 0:

        return jsonify({

            "success":
            False,

            "error":
            "올바른 금액을 입력해주세요."

        }), 400


    if sender_id == receiver_id:

        return jsonify({

            "success":
            False,

            "error":
            "자기 자신에게 송금할 수 없습니다."

        })


    connection = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        # 두 유저 생성

        ensure_user(

            cursor,

            sender_id

        )

        ensure_user(

            cursor,

            receiver_id

        )


        # ==================================
        # 데드락 방지를 위한 정렬
        # ==================================

        first_id = min(

            sender_id,

            receiver_id

        )

        second_id = max(

            sender_id,

            receiver_id

        )


        # 두 유저 행 잠금

        cursor.execute(

            """

            SELECT

                roblox_user_id,

                balance,

                account_balance

            FROM users

            WHERE roblox_user_id IN (

                %s,

                %s

            )

            ORDER BY roblox_user_id

            FOR UPDATE

            """,

            (

                first_id,

                second_id

            )

        )


        rows = cursor.fetchall()


        users_data = {}


        for row in rows:

            users_data[
                str(row[0])
            ] = {

                "balance":
                int(row[1]),

                "account_balance":
                int(row[2])

            }


        sender_data = users_data[
            sender_id
        ]

        receiver_data = users_data[
            receiver_id
        ]


        # 송금자 계좌 부족

        if (

            sender_data[
                "account_balance"
            ]

            <

            amount

        ):

            connection.rollback()


            return jsonify({

                "success":
                False,

                "error":
                "계좌 잔액이 부족합니다."

            })


        # ==============================
        # 새로운 잔액
        # ==============================

        new_sender_account = (

            sender_data[
                "account_balance"
            ]

            -

            amount

        )


        new_receiver_account = (

            receiver_data[
                "account_balance"
            ]

            +

            amount

        )


        # ==============================
        # 송금자 업데이트
        # ==============================

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

                new_sender_account,

                sender_id

            )

        )


        # ==============================
        # 받는 사람 업데이트
        # ==============================

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

                new_receiver_account,

                receiver_id

            )

        )


        # ==============================
        # 거래내역
        # ==============================

        add_transaction(

            cursor,

            sender_id,

            "transfer_sent",

            amount,

            f"{amount:,}원 송금"

        )


        add_transaction(

            cursor,

            receiver_id,

            "transfer_received",

            amount,

            f"{amount:,}원 송금 받음"

        )


        # ==============================
        # 모든 작업 저장
        # ==============================

        connection.commit()


        return jsonify({

            "success":
            True,

            "sender_account_balance":
            new_sender_account,

            "receiver_account_balance":
            new_receiver_account

        })


    except Exception as error:

        if connection:

            connection.rollback()


        print(

            "[Bank API] 송금 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "송금 처리 중 오류가 발생했습니다."

        }), 500


    finally:

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

    connection = None


    try:

        connection = get_db_connection()


        cursor = connection.cursor(
            cursor_factory=
            psycopg2.extras.RealDictCursor
        )


        # 최대 50개

        cursor.execute(

            """

            SELECT

                transaction_type AS type,

                amount,

                message,

                created_at

            FROM transactions

            WHERE roblox_user_id = %s

            ORDER BY created_at DESC

            LIMIT 50

            """,

            (

                str(
                    roblox_user_id
                ),

            )

        )


        rows = cursor.fetchall()


        transaction_list = []


        for row in rows:

            created_at = row[
                "created_at"
            ]


            # 시간 문자열 변환

            if created_at:

                time_text = (
                    created_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

            else:

                time_text = ""


            transaction_list.append({

                "type":
                row["type"],

                "amount":
                int(
                    row["amount"]
                ),

                "message":
                row["message"],

                "time":
                time_text

            })


        return jsonify({

            "success":
            True,

            "transactions":
            transaction_list

        })


    except Exception as error:

        print(

            "[Bank API] 거래내역 조회 오류:",

            error

        )


        return jsonify({

            "success":
            False,

            "error":
            "거래내역을 불러오지 못했습니다."

        }), 500


    finally:

        if connection:

            connection.close()


# ==========================================
# 서버 시작 시 DB 초기화
# ==========================================

initialize_database()


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
