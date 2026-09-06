from flask import Flask, request, jsonify
import os
import secrets
import string

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

DATABASE_URL = os.getenv("DATABASE_URL")


# ==========================================
# 데이터베이스 연결
# ==========================================

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL 환경변수가 설정되지 않았습니다.")

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


# ==========================================
# 데이터베이스 초기화
# ==========================================

def initialize_database():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

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

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transactions_user_id
            ON transactions (roblox_user_id)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS driving_licenses (
                roblox_user_id TEXT PRIMARY KEY,
                has_driving_license BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS server_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT NOT NULL DEFAULT 'CLOSED',
                priority_rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO server_status (id, mode, priority_rank)
            VALUES (1, 'CLOSED', NULL)
            ON CONFLICT (id) DO NOTHING
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS server_access_logs (
                id BIGSERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                roblox_user_id TEXT NOT NULL,
                roblox_name TEXT NOT NULL,
                mode TEXT,
                required_rank INTEGER,
                group_rank INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_server_access_logs_id
            ON server_access_logs (id)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                id BIGSERIAL PRIMARY KEY,
                verification_code TEXT UNIQUE NOT NULL,
                roblox_user_id TEXT UNIQUE,
                verified BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verification_code
            ON verification_codes (verification_code)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verification_roblox_user_id
            ON verification_codes (roblox_user_id)
            """
        )

        # ==================================
        # Discord 숫자 고유번호 테이블
        # ==================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS roblox_unique_numbers (
                roblox_user_id TEXT PRIMARY KEY,
                unique_number INTEGER UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()
        print("[Bank API] 데이터베이스 초기화 완료")

    except Exception as error:
        print("[Bank API] 데이터베이스 초기화 실패:", error)
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# Render/Gunicorn처럼 모듈 import 방식으로 실행되어도 테이블 생성
try:
    initialize_database()
except Exception as error:
    print("[Bank API] 시작 시 DB 초기화 실패:", error)


# ==========================================
# 유저 생성
# ==========================================

def ensure_user(roblox_user_id):
    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users (roblox_user_id, balance, account_balance)
            VALUES (%s, 0, 0)
            ON CONFLICT (roblox_user_id) DO NOTHING
            """,
            (roblox_user_id,)
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
    return bool(data) and data.get("api_key") == API_KEY


def check_get_api_key():
    return request.args.get("api_key") == API_KEY


# ==========================================
# 숫자 확인
# ==========================================

def parse_amount(value):
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return None

    if amount <= 0:
        return None

    return amount


# ==========================================
# 8자리 인증 코드 생성
# ==========================================

def generate_verification_code():
    characters = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(characters) for _ in range(8))


# ==========================================
# 유저 잔액 조회
# ==========================================

def get_user_balance(roblox_user_id):
    roblox_user_id = str(roblox_user_id)
    ensure_user(roblox_user_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )

        user = cursor.fetchone()

        if not user:
            return {"balance": 0, "account_balance": 0}

        return {
            "balance": int(user["balance"]),
            "account_balance": int(user["account_balance"])
        }
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 기본 페이지
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "service": "Roblox Bank API",
        "database": "PostgreSQL Connected"
    })


# ==========================================
# 고유번호 시스템
# ==========================================

@app.route("/verification/generate", methods=["POST"])
def generate_code():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        verification_code = None

        for _ in range(10):
            new_code = generate_verification_code()
            cursor.execute(
                "SELECT id FROM verification_codes WHERE verification_code = %s",
                (new_code,)
            )
            if not cursor.fetchone():
                verification_code = new_code
                break

        if not verification_code:
            return jsonify({"success": False, "error": "고유번호 생성에 실패했습니다."}), 500

        cursor.execute(
            """
            INSERT INTO verification_codes (verification_code, verified)
            VALUES (%s, FALSE)
            """,
            (verification_code,)
        )
        connection.commit()

        print("[고유번호] 생성 완료:", verification_code)

        return jsonify({
            "success": True,
            "verification_code": verification_code
        })

    except Exception as error:
        if connection:
            connection.rollback()
        print("[고유번호] 생성 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/verification/link", methods=["POST"])
def link_verification():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    verification_code = data.get("verification_code")
    roblox_user_id = data.get("roblox_user_id")

    if not verification_code:
        return jsonify({"success": False, "error": "고유번호가 없습니다."}), 400

    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    verification_code = str(verification_code).strip().upper()
    roblox_user_id = str(roblox_user_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT verification_code, verified
            FROM verification_codes
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        existing_user = cursor.fetchone()

        if existing_user and existing_user["verified"]:
            connection.rollback()
            return jsonify({
                "success": False,
                "error": "이미 다른 고유번호와 연동된 Roblox 계정입니다."
            }), 400

        cursor.execute(
            """
            SELECT id, verification_code, roblox_user_id, verified
            FROM verification_codes
            WHERE verification_code = %s
            FOR UPDATE
            """,
            (verification_code,)
        )
        code_data = cursor.fetchone()

        if not code_data:
            connection.rollback()
            return jsonify({"success": False, "error": "존재하지 않는 고유번호입니다."}), 404

        if code_data["verified"]:
            connection.rollback()
            return jsonify({"success": False, "error": "이미 사용된 고유번호입니다."}), 400

        cursor.execute(
            """
            UPDATE verification_codes
            SET roblox_user_id = %s,
                verified = TRUE,
                verified_at = CURRENT_TIMESTAMP
            WHERE verification_code = %s
            """,
            (roblox_user_id, verification_code)
        )
        connection.commit()

        print("[고유번호] 연동 완료:", roblox_user_id, verification_code)

        return jsonify({
            "success": True,
            "verified": True,
            "roblox_user_id": roblox_user_id,
            "verification_code": verification_code
        })

    except Exception as error:
        if connection:
            connection.rollback()
        print("[고유번호] 연동 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/verification/<roblox_user_id>", methods=["GET"])
def check_verification(roblox_user_id):
    if not check_get_api_key():
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT verification_code, roblox_user_id, verified, verified_at
            FROM verification_codes
            WHERE roblox_user_id = %s
              AND verified = TRUE
            """,
            (roblox_user_id,)
        )
        verification_data = cursor.fetchone()

        if not verification_data:
            return jsonify({
                "success": True,
                "roblox_user_id": roblox_user_id,
                "verified": False
            })

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "verified": True
        })

    except Exception as error:
        print("[고유번호] 확인 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/verification/check", methods=["POST"])
def verification_check():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT verification_code, verified
            FROM verification_codes
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        verification_data = cursor.fetchone()

        if not verification_data:
            return jsonify({
                "success": True,
                "roblox_user_id": roblox_user_id,
                "verified": False
            })

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "verified": bool(verification_data["verified"])
        })

    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/verification/unlink", methods=["POST"])
def unlink_verification():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE verification_codes
            SET roblox_user_id = NULL,
                verified = FALSE,
                verified_at = NULL
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        affected_rows = cursor.rowcount
        connection.commit()

        if affected_rows == 0:
            return jsonify({
                "success": False,
                "error": "연동 정보를 찾을 수 없습니다."
            }), 404

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "verified": False
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Discord 숫자 고유번호 저장 / 수정
# ==========================================

@app.route("/sync_unique_number", methods=["POST"])
def sync_unique_number():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    unique_number = data.get("unique_number")

    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    if unique_number is None:
        return jsonify({"success": False, "error": "unique_number가 없습니다."}), 400

    try:
        roblox_user_id = str(roblox_user_id)
        unique_number = int(unique_number)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "고유번호는 숫자여야 합니다."}), 400

    if unique_number <= 0:
        return jsonify({"success": False, "error": "고유번호는 1 이상이어야 합니다."}), 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT roblox_user_id
            FROM roblox_unique_numbers
            WHERE unique_number = %s
              AND roblox_user_id != %s
            """,
            (unique_number, roblox_user_id)
        )
        existing = cursor.fetchone()

        if existing:
            connection.rollback()
            return jsonify({
                "success": False,
                "error": "이미 다른 Roblox 계정에서 사용 중인 고유번호입니다."
            }), 409

        cursor.execute(
            """
            INSERT INTO roblox_unique_numbers
                (roblox_user_id, unique_number, updated_at)
            VALUES
                (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (roblox_user_id)
            DO UPDATE SET
                unique_number = EXCLUDED.unique_number,
                updated_at = CURRENT_TIMESTAMP
            """,
            (roblox_user_id, unique_number)
        )

        connection.commit()

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "unique_number": unique_number
        })

    except Exception as error:
        if connection:
            connection.rollback()
        print("[고유번호] Render 동기화 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Discord 숫자 고유번호 삭제
# ==========================================

@app.route("/delete_unique_number/<roblox_user_id>", methods=["POST"])
def delete_unique_number(roblox_user_id):
    data = request.get_json(silent=True) or {}

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM roblox_unique_numbers WHERE roblox_user_id = %s",
            (roblox_user_id,)
        )
        connection.commit()

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "deleted": cursor.rowcount > 0
        })

    except Exception as error:
        if connection:
            connection.rollback()
        print("[고유번호] Render 삭제 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Roblox 숫자 고유번호 조회
# ==========================================

@app.route("/unique-number/<roblox_user_id>", methods=["GET"])
def get_unique_number(roblox_user_id):
    if not check_get_api_key():
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT unique_number
            FROM roblox_unique_numbers
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        data = cursor.fetchone()

        if not data:
            return jsonify({
                "success": True,
                "registered": False,
                "roblox_user_id": roblox_user_id,
                "unique_number": None
            })

        return jsonify({
            "success": True,
            "registered": True,
            "roblox_user_id": roblox_user_id,
            "unique_number": int(data["unique_number"])
        })

    except Exception as error:
        print("[고유번호] 조회 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Discord 봇 잔액 동기화
# ==========================================

@app.route("/update_balance", methods=["POST"])
def update_balance():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")

    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    roblox_user_id = str(roblox_user_id)
    ensure_user(roblox_user_id)

    balance = data.get("balance")
    account_balance = data.get("account_balance")

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if balance is not None:
            try:
                balance = int(balance)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "잔액이 올바르지 않습니다."}), 400

            if balance < 0:
                return jsonify({"success": False, "error": "잔액은 음수가 될 수 없습니다."}), 400

            cursor.execute(
                """
                UPDATE users
                SET balance = %s, updated_at = CURRENT_TIMESTAMP
                WHERE roblox_user_id = %s
                """,
                (balance, roblox_user_id)
            )

        if account_balance is not None:
            try:
                account_balance = int(account_balance)
            except (TypeError, ValueError):
                return jsonify({"success": False, "error": "계좌 잔액이 올바르지 않습니다."}), 400

            if account_balance < 0:
                return jsonify({"success": False, "error": "계좌 잔액은 음수가 될 수 없습니다."}), 400

            cursor.execute(
                """
                UPDATE users
                SET account_balance = %s, updated_at = CURRENT_TIMESTAMP
                WHERE roblox_user_id = %s
                """,
                (account_balance, roblox_user_id)
            )

        connection.commit()

        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        user = cursor.fetchone()

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "balance": int(user["balance"]),
            "account_balance": int(user["account_balance"])
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 잔액 조회
# ==========================================

@app.route("/balance/<roblox_user_id>", methods=["GET"])
def get_balance(roblox_user_id):
    user = get_user_balance(roblox_user_id)

    return jsonify({
        "success": True,
        "roblox_user_id": str(roblox_user_id),
        "balance": user["balance"],
        "account_balance": user["account_balance"]
    })



# ==========================================
# Roblox RP 서버 상태 조회
# ==========================================

@app.route("/server/status", methods=["GET"])
def get_server_status():
    if request.args.get("api_key") != API_KEY:
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT mode, priority_rank, updated_at FROM server_status WHERE id = 1"
        )
        row = cursor.fetchone()

        if not row:
            return jsonify({
                "success": True,
                "mode": "CLOSED",
                "priority_rank": None
            })

        return jsonify({
            "success": True,
            "mode": row["mode"],
            "priority_rank": row["priority_rank"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
        })
    except Exception as error:
        print("[Bank API] 서버 상태 조회 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Roblox RP 서버 상태 변경
# ==========================================

@app.route("/server/state", methods=["POST"])
def set_server_state():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    mode = str(data.get("mode", "")).upper()
    if mode not in {"OPEN", "PRIORITY", "CLOSED"}:
        return jsonify({"success": False, "error": "mode는 OPEN, PRIORITY, CLOSED 중 하나여야 합니다."}), 400

    priority_rank = data.get("priority_rank")
    if mode == "PRIORITY":
        if priority_rank is None:
            return jsonify({"success": False, "error": "PRIORITY 상태에서는 priority_rank가 필요합니다."}), 400
        try:
            priority_rank = int(priority_rank)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "priority_rank는 숫자여야 합니다."}), 400
        if not 0 <= priority_rank <= 255:
            return jsonify({"success": False, "error": "priority_rank는 0~255 범위여야 합니다."}), 400
    else:
        priority_rank = None

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO server_status (id, mode, priority_rank, updated_at)
            VALUES (1, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id)
            DO UPDATE SET
                mode = EXCLUDED.mode,
                priority_rank = EXCLUDED.priority_rank,
                updated_at = CURRENT_TIMESTAMP
            """,
            (mode, priority_rank)
        )
        connection.commit()

        return jsonify({
            "success": True,
            "mode": mode,
            "priority_rank": priority_rank
        })
    except Exception as error:
        if connection:
            connection.rollback()
        print("[Bank API] 서버 상태 변경 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# Roblox RP 서버 입장 로그 저장
# ==========================================

@app.route("/server/access-log", methods=["POST"])
def create_server_access_log():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400
    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    event_type = str(data.get("event_type", "UNKNOWN"))[:64]
    roblox_user_id = str(data.get("roblox_user_id", ""))[:64]
    roblox_name = str(data.get("roblox_name", ""))[:128]
    mode = str(data.get("mode", ""))[:32] or None
    reason = str(data.get("reason", ""))[:500]
    try:
        required_rank = int(data["required_rank"]) if data.get("required_rank") is not None else None
    except (TypeError, ValueError):
        required_rank = None
    try:
        group_rank = int(data["group_rank"]) if data.get("group_rank") is not None else None
    except (TypeError, ValueError):
        group_rank = None

    if not roblox_user_id or not roblox_name:
        return jsonify({"success": False, "error": "roblox_user_id와 roblox_name이 필요합니다."}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO server_access_logs(
                event_type, roblox_user_id, roblox_name, mode,
                required_rank, group_rank, reason
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id, created_at
            """,
            (event_type, roblox_user_id, roblox_name, mode, required_rank, group_rank, reason)
        )
        row = cursor.fetchone()
        connection.commit()
        return jsonify({
            "success": True,
            "id": row["id"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None
        })
    except Exception as error:
        if connection:
            connection.rollback()
        print("[Bank API] 서버 입장 로그 저장 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/server/access-logs", methods=["GET"])
def get_server_access_logs():
    if request.args.get("api_key") != API_KEY:
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    try:
        since_id = int(request.args.get("since_id", "0"))
    except ValueError:
        since_id = 0
    try:
        limit = max(1, min(100, int(request.args.get("limit", "100"))))
    except ValueError:
        limit = 100

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, event_type, roblox_user_id, roblox_name, mode,
                   required_rank, group_rank, reason, created_at
            FROM server_access_logs
            WHERE id > %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (since_id, limit)
        )
        rows = cursor.fetchall()
        return jsonify({
            "success": True,
            "logs": [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "roblox_user_id": row["roblox_user_id"],
                    "roblox_name": row["roblox_name"],
                    "mode": row["mode"],
                    "required_rank": row["required_rank"],
                    "group_rank": row["group_rank"],
                    "reason": row["reason"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]
        })
    except Exception as error:
        print("[Bank API] 서버 입장 로그 조회 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 운전면허 조회
# ==========================================

@app.route("/driving-license/<roblox_user_id>", methods=["GET"])
def get_driving_license(roblox_user_id):
    if request.args.get("api_key") != API_KEY:
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT has_driving_license
            FROM driving_licenses
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        license_data = cursor.fetchone()

        if not license_data:
            return jsonify({
                "success": True,
                "roblox_user_id": roblox_user_id,
                "has_driving_license": False
            })

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "has_driving_license": bool(license_data["has_driving_license"])
        })

    except Exception as error:
        print("[Bank API] 운전면허 조회 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 운전면허 지급
# ==========================================

@app.route("/driving-license/grant", methods=["POST"])
def grant_driving_license():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO driving_licenses
                (roblox_user_id, has_driving_license, updated_at)
            VALUES (%s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (roblox_user_id)
            DO UPDATE SET
                has_driving_license = TRUE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (roblox_user_id,)
        )
        connection.commit()

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "has_driving_license": True
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 운전면허 제거
# ==========================================

@app.route("/driving-license/revoke", methods=["POST"])
def revoke_driving_license():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    roblox_user_id = str(roblox_user_id)
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO driving_licenses
                (roblox_user_id, has_driving_license, updated_at)
            VALUES (%s, FALSE, CURRENT_TIMESTAMP)
            ON CONFLICT (roblox_user_id)
            DO UPDATE SET
                has_driving_license = FALSE,
                updated_at = CURRENT_TIMESTAMP
            """,
            (roblox_user_id,)
        )
        connection.commit()

        return jsonify({
            "success": True,
            "roblox_user_id": roblox_user_id,
            "has_driving_license": False
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 출금: 계좌 -> 현금
# ==========================================

@app.route("/withdraw", methods=["POST"])
def withdraw():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    amount = parse_amount(data.get("amount"))
    if amount is None:
        return jsonify({"success": False, "error": "올바른 금액을 입력해주세요."}), 400

    roblox_user_id = str(roblox_user_id)
    ensure_user(roblox_user_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            FOR UPDATE
            """,
            (roblox_user_id,)
        )
        user = cursor.fetchone()

        if user["account_balance"] < amount:
            connection.rollback()
            return jsonify({"success": False, "error": "계좌 잔액이 부족합니다."}), 400

        cursor.execute(
            """
            UPDATE users
            SET balance = balance + %s,
                account_balance = account_balance - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE roblox_user_id = %s
            """,
            (amount, amount, roblox_user_id)
        )

        cursor.execute(
            """
            INSERT INTO transactions
                (roblox_user_id, transaction_type, amount, message)
            VALUES (%s, %s, %s, %s)
            """,
            (roblox_user_id, "withdraw", amount, f"{amount:,}원 출금")
        )
        connection.commit()

        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        updated_user = cursor.fetchone()

        return jsonify({
            "success": True,
            "balance": int(updated_user["balance"]),
            "account_balance": int(updated_user["account_balance"])
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 입금: 현금 -> 계좌
# ==========================================

@app.route("/deposit", methods=["POST"])
def deposit():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    roblox_user_id = data.get("roblox_user_id")
    if roblox_user_id is None:
        return jsonify({"success": False, "error": "roblox_user_id가 없습니다."}), 400

    amount = parse_amount(data.get("amount"))
    if amount is None:
        return jsonify({"success": False, "error": "올바른 금액을 입력해주세요."}), 400

    roblox_user_id = str(roblox_user_id)
    ensure_user(roblox_user_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            FOR UPDATE
            """,
            (roblox_user_id,)
        )
        user = cursor.fetchone()

        if user["balance"] < amount:
            connection.rollback()
            return jsonify({"success": False, "error": "보유 현금이 부족합니다."}), 400

        cursor.execute(
            """
            UPDATE users
            SET balance = balance - %s,
                account_balance = account_balance + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE roblox_user_id = %s
            """,
            (amount, amount, roblox_user_id)
        )

        cursor.execute(
            """
            INSERT INTO transactions
                (roblox_user_id, transaction_type, amount, message)
            VALUES (%s, %s, %s, %s)
            """,
            (roblox_user_id, "deposit", amount, f"{amount:,}원 입금")
        )
        connection.commit()

        cursor.execute(
            """
            SELECT balance, account_balance
            FROM users
            WHERE roblox_user_id = %s
            """,
            (roblox_user_id,)
        )
        updated_user = cursor.fetchone()

        return jsonify({
            "success": True,
            "balance": int(updated_user["balance"]),
            "account_balance": int(updated_user["account_balance"])
        })

    except Exception as error:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 송금
# ==========================================

@app.route("/transfer", methods=["POST"])
def transfer():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "데이터가 없습니다."}), 400

    if not check_api_key(data):
        return jsonify({"success": False, "error": "API 키가 올바르지 않습니다."}), 403

    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    if sender_id is None or receiver_id is None:
        return jsonify({"success": False, "error": "송금 대상 정보가 없습니다."}), 400

    amount = parse_amount(data.get("amount"))
    if amount is None:
        return jsonify({"success": False, "error": "올바른 금액을 입력해주세요."}), 400

    sender_id = str(sender_id)
    receiver_id = str(receiver_id)

    if sender_id == receiver_id:
        return jsonify({"success": False, "error": "자기 자신에게 송금할 수 없습니다."}), 400

    ensure_user(sender_id)
    ensure_user(receiver_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        first_id = min(sender_id, receiver_id)
        second_id = max(sender_id, receiver_id)

        cursor.execute(
            """
            SELECT roblox_user_id, balance, account_balance
            FROM users
            WHERE roblox_user_id IN (%s, %s)
            ORDER BY roblox_user_id
            FOR UPDATE
            """,
            (first_id, second_id)
        )
        users = cursor.fetchall()

        user_map = {row["roblox_user_id"]: row for row in users}
        sender = user_map.get(sender_id)

        if not sender:
            connection.rollback()
            return jsonify({"success": False, "error": "송금자 정보를 찾을 수 없습니다."}), 400

        if sender["account_balance"] < amount:
            connection.rollback()
            return jsonify({"success": False, "error": "계좌 잔액이 부족합니다."}), 400

        cursor.execute(
            """
            UPDATE users
            SET account_balance = account_balance - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE roblox_user_id = %s
            """,
            (amount, sender_id)
        )

        cursor.execute(
            """
            UPDATE users
            SET account_balance = account_balance + %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE roblox_user_id = %s
            """,
            (amount, receiver_id)
        )

        cursor.execute(
            """
            INSERT INTO transactions
                (roblox_user_id, transaction_type, amount, message)
            VALUES (%s, %s, %s, %s)
            """,
            (sender_id, "transfer_sent", amount, f"{amount:,}원 송금")
        )

        cursor.execute(
            """
            INSERT INTO transactions
                (roblox_user_id, transaction_type, amount, message)
            VALUES (%s, %s, %s, %s)
            """,
            (receiver_id, "transfer_received", amount, f"{amount:,}원 송금 받음")
        )
        connection.commit()

        cursor.execute(
            """
            SELECT roblox_user_id, account_balance
            FROM users
            WHERE roblox_user_id IN (%s, %s)
            """,
            (sender_id, receiver_id)
        )
        updated_users = cursor.fetchall()
        updated_map = {row["roblox_user_id"]: row for row in updated_users}

        return jsonify({
            "success": True,
            "sender_account_balance": int(updated_map[sender_id]["account_balance"]),
            "receiver_account_balance": int(updated_map[receiver_id]["account_balance"])
        })

    except Exception as error:
        if connection:
            connection.rollback()
        print("[Bank API] 송금 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 거래내역 조회
# ==========================================

@app.route("/transactions/<roblox_user_id>", methods=["GET"])
def get_transactions(roblox_user_id):
    roblox_user_id = str(roblox_user_id)
    ensure_user(roblox_user_id)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, transaction_type, amount, message, created_at
            FROM transactions
            WHERE roblox_user_id = %s
            ORDER BY id DESC
            LIMIT 100
            """,
            (roblox_user_id,)
        )
        rows = cursor.fetchall()

        transaction_list = []
        for row in rows:
            transaction_list.append({
                "id": row["id"],
                "type": row["transaction_type"],
                "amount": int(row["amount"]),
                "message": row["message"],
                "time": row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            })

        return jsonify({
            "success": True,
            "transactions": transaction_list
        })

    except Exception as error:
        print("[Bank API] 거래내역 조회 오류:", error)
        return jsonify({"success": False, "error": str(error)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ==========================================
# 서버 실행
# ==========================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
