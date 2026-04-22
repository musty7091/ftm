from typing import Any

from sqlalchemy import text

from app.db.session import session_scope


def _safe_text(value: Any) -> str:
    if value is None:
        return "-"

    return str(value)


def _print_separator() -> None:
    print("-" * 120)


def main() -> None:
    print("FTM yetkisiz işlem denemeleri güvenlik raporu")
    print("=" * 120)
    print("")

    limit_input = input("Kaç kayıt gösterilsin? [50]: ").strip() or "50"

    if not limit_input.isdigit():
        print("Geçersiz limit. Varsayılan 50 kullanılacak.")
        limit = 50
    else:
        limit = int(limit_input)

    if limit <= 0:
        limit = 50

    with session_scope() as session:
        statement = text(
            """
            SELECT
                id,
                action,
                entity_type,
                entity_id,
                description,
                new_values
            FROM audit_logs
            WHERE action = 'PERMISSION_DENIED'
            ORDER BY id DESC
            LIMIT :limit
            """
        )

        rows = session.execute(statement, {"limit": limit}).mappings().all()

        if not rows:
            print("PERMISSION_DENIED kaydı bulunamadı.")
            return

        print(f"Toplam gösterilen kayıt: {len(rows)}")
        print("")

        for row in rows:
            new_values = row.get("new_values") or {}

            if isinstance(new_values, dict):
                username = new_values.get("username", "-")
                role = new_values.get("role", "-")
                required_permission = new_values.get("required_permission", "-")
                attempted_action = new_values.get("attempted_action", "-")
                details = new_values.get("details", {})
            else:
                username = "-"
                role = "-"
                required_permission = "-"
                attempted_action = "-"
                details = {}

            _print_separator()
            print(f"Log ID          : {_safe_text(row.get('id'))}")
            print(f"Action          : {_safe_text(row.get('action'))}")
            print(f"Kullanıcı       : {_safe_text(username)}")
            print(f"Rol             : {_safe_text(role)}")
            print(f"Gereken yetki   : {_safe_text(required_permission)}")
            print(f"Denenen işlem   : {_safe_text(attempted_action)}")
            print(f"Entity Type     : {_safe_text(row.get('entity_type'))}")
            print(f"Entity ID       : {_safe_text(row.get('entity_id'))}")
            print(f"Açıklama        : {_safe_text(row.get('description'))}")

            if isinstance(details, dict) and details:
                print("Detaylar        :")

                for key, value in details.items():
                    print(f"  - {key}: {_safe_text(value)}")

        _print_separator()


if __name__ == "__main__":
    main()