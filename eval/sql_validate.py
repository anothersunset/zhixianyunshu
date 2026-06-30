"""SQL syntax validator using sqlglot. Called from Java backend via ProcessBuilder.
Outputs JSON: {"valid": true/false, "error": "..."}
"""
import sys
import json
import sqlglot

def validate(sql: str, dialect: str = "postgres") -> dict:
    if not sql.strip():
        return {"valid": False, "error": "Empty SQL"}
    try:
        # RAISE 模式：遇到语法错误直接抛异常
        parsed = sqlglot.parse(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)

        # 额外检查：结果是否为空
        if not parsed:
            return {"valid": False, "error": "sqlglot returned empty parse tree"}
        return {"valid": True, "error": None}
    except Exception as e:
        msg = str(e)
        # 提取核心错误信息，去掉颜色码等
        msg = msg.replace("\x1b[4m", "").replace("\x1b[0m", "")
        return {"valid": False, "error": msg[:300]}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"valid": False, "error": "usage: sql_validate.py <sql_string> [dialect]"}))
        sys.exit(1)
    sql = sys.argv[1]
    dialect = sys.argv[2] if len(sys.argv) > 2 else "postgres"
    result = validate(sql, dialect)
    print(json.dumps(result, ensure_ascii=True))
