#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aegis Runner Stateless Worker Entrance
Cloud-Native P2P Worker Process
"""
import asyncio
import signal
import sys

from src.runner.main import main, signal_handler


def run_worker():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Aegis Runner Worker] 进程安全退出")
    except Exception as exc:
        print(f"\n[Aegis Runner Worker] 异常退出: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run_worker()
