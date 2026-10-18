"""
Process and Network Monitor MCP Server (converted from uoltrtxt/read-1.3)
- Reference Repository: https://github.com/uoltrtxt/read-1.3
- Official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- psutil Documentation: https://psutil.readthedocs.io/
"""

from typing import Any, Dict, List, Optional
import psutil
from mcp.server.fastmcp import FastMCP

# MCP 서버 초기화
mcp = FastMCP("process-network-monitor")


def _safe_process_name(pid: Optional[int]) -> str:
    """PID로부터 프로세스 이름을 안전하게 조회합니다."""
    if not pid:
        return "<system>"
    try:
        return psutil.Process(pid).name() or "<unknown>"
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "<ended>"


@mcp.tool()
def list_processes(
    name_filter: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    현재 실행 중인 프로세스 목록(PID, 프로세스 이름, 메모리 사용량 MB)을 반환합니다.

    Args:
        name_filter: 프로세스 이름에 포함될 검색어 (선택 사항, 대소문자 무시)
        limit: 반환할 최대 프로세스 개수 (기본값: 100)
    """
    results: List[Dict[str, Any]] = []
    keyword = name_filter.lower().strip() if name_filter else None

    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            name = info.get("name") or "<unknown>"
            if keyword and keyword not in name.lower():
                continue

            mem_info = info.get("memory_info")
            mem_mb = round(mem_info.rss / (1024 * 1024), 2) if mem_info else 0.0

            results.append(
                {
                    "pid": info.get("pid"),
                    "name": name,
                    "memory_mb": mem_mb,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # 메모리 사용량(MB) 기준 내림차순 정렬 후 상위 limit개 반환
    results.sort(key=lambda x: x["memory_mb"], reverse=True)
    return results[: max(1, limit)]


@mcp.tool()
def get_process_detail(pid: int) -> Dict[str, Any]:
    """
    특정 PID 프로세스의 상세 자원 사용량(CPU, 메모리), 실행 파일 경로 및 네트워크 연결 정보를 조회합니다.
    기존 app.py의 on_proc_select 분석 데이터를 MCP 도구 형태로 제공합니다.

    Args:
        pid: 조회할 프로세스 ID (PID)
    """
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            name = p.name()
            status = p.status()
            cpu_percent = p.cpu_percent(interval=None)
            mem_mb = round(p.memory_info().rss / (1024 * 1024), 2)

            try:
                exe_path = p.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                exe_path = "<access_denied>"

            try:
                cmdline = p.cmdline()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmdline = []

            try:
                connections = [
                    {
                        "local_address": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-",
                        "remote_address": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-",
                        "status": c.status,
                    }
                    for c in p.net_connections(kind="inet")
                ]
            except (psutil.AccessDenied, psutil.ZombieProcess):
                connections = []

        return {
            "pid": pid,
            "name": name,
            "status": status,
            "cpu_percent": cpu_percent,
            "memory_mb": mem_mb,
            "exe": exe_path,
            "cmdline": cmdline,
            "connections": connections,
        }
    except psutil.NoSuchProcess:
        return {"error": f"PID {pid} 프로세스를 찾을 수 없습니다."}
    except psutil.AccessDenied:
        return {"error": f"PID {pid} 프로세스에 접근 권한이 없습니다. (관리자/루트 권한 필요)"}


@mcp.tool()
def list_network_connections(
    kind: str = "inet",
    status_filter: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    현재 활성화된 네트워크 연결(IP, 포트, 상태, 연결된 프로세스 PID 및 이름)을 조회합니다.

    Args:
        kind: 네트워크 종류 ('inet', 'inet4', 'inet6', 'tcp', 'udp' 등, 기본값: 'inet')
        status_filter: 연결 상태 필터 (예: 'ESTABLISHED', 'LISTEN', 선택 사항)
        limit: 반환할 최대 연결 개수 (기본값: 100)
    """
    connections: List[Dict[str, Any]] = []
    target_status = status_filter.upper().strip() if status_filter else None

    try:
        raw_conns = psutil.net_connections(kind=kind)
    except psutil.AccessDenied:
        return [
            {
                "error": "네트워크 연결 목록 조회 권한이 부족합니다. 관리자(Windows) 또는 sudo(macOS/Linux) 권한으로 실행해 주세요."
            }
        ]
    except ValueError as exc:
        return [{"error": f"지원하지 않는 kind 값입니다 ({kind}): {exc}"}]

    for conn in raw_conns:
        if target_status and conn.status != target_status:
            continue

        local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
        remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        pname = _safe_process_name(conn.pid)

        connections.append(
            {
                "pid": conn.pid,
                "process_name": pname,
                "local_address": local_addr,
                "remote_address": remote_addr,
                "status": conn.status,
            }
        )
        if len(connections) >= max(1, limit):
            break

    return connections


@mcp.prompt()
def analyze_process_prompt(pid: int, lang: str = "ko") -> str:
    """
    특정 PID의 프로세스 정보를 수집하여 역할, 작성 언어, 리소스 및 네트워크 상태를 분석하는 프롬프트를 생성합니다.

    Args:
        pid: 분석할 프로세스 ID (PID)
        lang: 언어 설정 ('ko' 또는 'en', 기본값: 'ko')
    """
    detail = get_process_detail(pid)
    if "error" in detail:
        return detail["error"]

    if lang == "en":
        return (
            f"Process '{detail['name']}' (PID {detail['pid']})\n"
            f"- Executable: {detail['exe']}\n"
            f"- Function: What does this program do?\n"
            f"- Language: What programming language is it likely written in?\n"
            f"- Resources: CPU {detail['cpu_percent']}%, Memory {detail['memory_mb']:.1f}MB\n"
            f"- Network Connections: {len(detail['connections'])} active connections"
        )

    return (
        f"프로세스 '{detail['name']}' (PID {detail['pid']})\n"
        f"- 실행 경로: {detail['exe']}\n"
        f"- 역할: 무엇을 하는 프로그램인가?\n"
        f"- 언어: 어떤 언어로 작성되었을까?\n"
        f"- 자원: CPU {detail['cpu_percent']}%, 메모리 {detail['memory_mb']:.1f}MB 사용\n"
        f"- 네트워크 연결: 활성 연결 {len(detail['connections'])}개"
    )


if __name__ == "__main__":
    # 표준 입출력(stdio) 전송 방식으로 MCP 서버 실행
    mcp.run()
