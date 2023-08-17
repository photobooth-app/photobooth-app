#!/usr/bin/python3
"""
Photobooth Cli application start script
"""
import argparse


def cli():
    parser = argparse.ArgumentParser(
        "photobooth-app",
        description="photobooth-app - Create your own photobooth!",
    )
    parser.add_argument(
        "-i",
        "--init",
        help="Initialize current folder as datafolder.",
        required=False,
        dest="init",
        action="store_true",
    )
    args = parser.parse_args()

    if args.init:
        print("init current directory as working directory")
        print("TODO: will be implemented later. Use to avoid messing file system with accidentally created workdirs")
    else:
        from photobooth import __main__ as booth_main

        booth_main.main()


if __name__ == "__main__":
    cli()
