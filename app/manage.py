"""Hand out roles. No endpoint can do this; this script is the way.

Run it inside the app container:

    python -m manage grant-role alice-smith admin
    python -m manage revoke-role alice-smith admin
    python -m manage seed-roles

Running one twice is fine (nothing changes, exit 0). An unknown user exits 1.
"""

import argparse
import sys

import crud
from database.database import Base, SessionLocal, engine
from database.models import User
from sqlalchemy import select


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manage", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "seed-roles", help=f"make sure the roles exist: {', '.join(crud.ROLE_NAMES)}"
    )
    for name in ("grant-role", "revoke-role"):
        sub = commands.add_parser(name)
        sub.add_argument("display_name")
        sub.add_argument("role", choices=crud.ROLE_NAMES)
    args = parser.parse_args(argv)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if args.command == "seed-roles":
            crud.seed_auth(db, None, None)
            print(f"roles present: {', '.join(crud.ROLE_NAMES)}")
            return 0

        user = db.scalar(select(User).where(User.display_name == args.display_name))
        if user is None:
            print(f"no user named {args.display_name!r}", file=sys.stderr)
            return 1
        change = crud.grant_role if args.command == "grant-role" else crud.revoke_role
        changed = change(db, user, args.role)
        db.commit()
        granting = args.command == "grant-role"
        if changed:
            print(
                f"{'granted' if granting else 'revoked'} {args.role} "
                f"{'to' if granting else 'from'} {user.display_name}"
            )
        else:
            print(
                f"{user.display_name} {'already had' if granting else 'did not have'} "
                f"{args.role}; nothing changed"
            )
        print(f"roles now: {', '.join(sorted(r.name for r in user.roles)) or '(none)'}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
