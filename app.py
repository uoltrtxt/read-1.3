import os, psutil, openai, threading
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk, scrolledtext

# 1) .env 로드 및 API 키 / 모델_NAME 검증
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("환경 변수 OPENAI_API_KEY를 설정해주세요.")
model_name = os.environ.get("OPENAI_MODEL", "o4-mini-2025-04-16")
openai.api_key = api_key

# --- GUI 초기화 ---
root = tk.Tk()
root.title("Process and Network Monitor")
root.geometry("800x600")
notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True)

# 탭 프레임 생성
frame_proc = ttk.Frame(notebook)
frame_net  = ttk.Frame(notebook)
notebook.add(frame_proc, text="실행중인 것들")
notebook.add(frame_net,  text="네트워크 정보")

# --- 탭1: 프로세스 목록 ---
proc_list   = tk.Listbox(frame_proc)
proc_list.pack(side='left', fill='both', expand=True, padx=5, pady=5)
proc_detail = scrolledtext.ScrolledText(frame_proc, width=50)
proc_detail.pack(side='right', fill='both', expand=True, padx=5, pady=5)

# --- 탭2: 네트워크 연결 목록 ---
net_list   = tk.Listbox(frame_net)
net_list.pack(side='left', fill='both', expand=True, padx=5, pady=5)
net_detail = scrolledtext.ScrolledText(frame_net, width=50)
net_detail.pack(side='right', fill='both', expand=True, padx=5, pady=5)

# 언어 선택 옵션
lang_var = tk.StringVar(value='ko')  # 'ko' or 'en'
lang_frame = ttk.Frame(root)
ttk.Radiobutton(lang_frame, text="한국어", variable=lang_var, value='ko').pack(side='left')
ttk.Radiobutton(lang_frame, text="English", variable=lang_var, value='en').pack(side='left')
lang_frame.pack(pady=5)

# 리스트 갱신 함수
def refresh_lists():
    proc_list.delete(0, tk.END)
    for proc in psutil.process_iter(['pid','name']):
        name = proc.info['name'] or "<unknown>"
        pid  = proc.info['pid']
        proc_list.insert('end', f"{name} (PID {pid})")

    net_list.delete(0, tk.END)
    for conn in psutil.net_connections(kind='inet'):
        l = f"{conn.laddr.ip}:{conn.laddr.port}"
        r = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        pname = None
        if conn.pid:
            try:
                pname = psutil.Process(conn.pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pname = "<ended>"
        net_list.insert('end', f"{pname} (PID {conn.pid}) {l} → {r} [{conn.status}]")

# 1초 주기 갱신
root.after(0, refresh_lists)
root.after(1000, lambda: root.after(1000, refresh_lists))

# 프로세스 선택 시 GPT 분석
def on_proc_select(event):
    sel = proc_list.curselection()
    if not sel:
        return
    pid = int(proc_list.get(sel[0]).split("PID")[1].split(")")[0])

    def task():
        try:
            p = psutil.Process(pid)
            info = {
                'name': p.name(),
                'pid': pid,
                'cpu': p.cpu_percent(interval=None),
                'mem': p.memory_info().rss / (1024*1024)
            }
            if lang_var.get() == 'ko':
                prompt = (
                    f"프로세스 '{info['name']}' (PID {pid})\n"
                    f"- 역할: 무엇을 하는 프로그램인가?\n"
                    f"- 언어: 어떤 언어로 작성되었을까?\n"
                    f"- 자원: CPU {info['cpu']}%, 메모리 {info['mem']:.1f}MB 사용"
                )
            else:
                prompt = (
                    f"Process '{info['name']}' (PID {pid})\n"
                    f"- Function: What does it do?\n"
                    f"- Language: Likely code language?\n"
                    f"- Resources: CPU {info['cpu']}%, Memory {info['mem']:.1f}MB"
                )

root.mainloop()




