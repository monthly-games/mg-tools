#!/usr/bin/env python3
"""
공통 유틸리티 모듈
"""

import sys
from rich.console import Console


def get_console() -> Console:
    """Windows 호환 콘솔 생성"""
    if sys.platform == "win32":
        # Windows에서 Unicode 문자 문제 방지
        return Console(force_terminal=True, legacy_windows=True, no_color=False)
    return Console()


# 전역 콘솔 인스턴스
console = get_console()


# Unicode safe symbols
CHECK = "[OK]"
CROSS = "[FAIL]"
ARROW = "->"
