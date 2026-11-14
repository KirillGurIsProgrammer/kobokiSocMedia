#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    # Make the development server reachable by devices on the local network.
    # An explicitly supplied address/port is always respected.
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        has_addrport = any(not arg.startswith("-") for arg in sys.argv[2:])
        if not has_addrport:
            sys.argv.append(os.getenv("DJANGO_RUNSERVER_ADDRESS", "0.0.0.0:8000"))
        # Keep static assets available in this development server even when
        # DEBUG is supplied as False by the process environment.
        if "--insecure" not in sys.argv and "--nostatic" not in sys.argv:
            sys.argv.append("--insecure")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
