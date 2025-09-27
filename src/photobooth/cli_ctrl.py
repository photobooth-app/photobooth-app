import argparse
import sys
from importlib.metadata import version
from pathlib import Path


def handle_service(args):
    print(f"Service command: {args.action}")


def handle_backup(args):
    print(f"Backup command: {args.action}")


def handle_maintenance(args):
    print(f"Maintenance command: {args.action}")


def handle_info(args):
    print(f"Info command: {args.action}")

    print("✨ Welcome to photobooth-ctrl ✨")
    print(f"photobooth directory: {Path(__file__).parent.resolve()}")
    print(f"working directory: {Path.cwd().resolve()}")
    print(f"app version started: {version('photobooth-app')}")


def main(args=None):
    parser = argparse.ArgumentParser(prog="photobooth-ctrl", description="Photobooth Management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Service subcommands
    service_parser = subparsers.add_parser("service", help="Manage services")
    service_parser.add_argument(
        "action",
        choices=["install", "uninstall", "start", "stop", "status"],
        nargs="?",
        default="status",
        help="Service action",
    )
    service_parser.set_defaults(func=handle_service)

    # Backup subcommands
    backup_parser = subparsers.add_parser("backup", help="Manage backups")
    backup_parser.add_argument(
        "action",
        choices=["create", "restore"],
        help="Backup action",
    )
    backup_parser.set_defaults(func=handle_backup)

    # Maintenance subcommands
    maintenance_parser = subparsers.add_parser("maintenance", help="Toggle maintenance mode")
    maintenance_parser.add_argument(
        "action",
        choices=["on", "off"],
        help="Maintenance mode",
    )
    maintenance_parser.set_defaults(func=handle_maintenance)

    # Info subcommands
    info_parser = subparsers.add_parser("info", help="Info")
    info_parser.add_argument(
        "action",
        choices=["version", "test123"],
    )
    info_parser.set_defaults(func=handle_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main(args=sys.argv[1:]))  # for testing
