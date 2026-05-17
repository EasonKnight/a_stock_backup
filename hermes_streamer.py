#!/usr/bin/env python
"""Hermes 输出实时转发器 — 管道读取 + 逐行 flush 到文件"""
import sys, os, subprocess, tempfile

prompt = sys.argv[1] if len(sys.argv) > 1 else ""

# 用 PIPE 读取，每行 flush
tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
tmp_path = tmp.name
tmp.close()

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

proc = subprocess.Popen(
    ["hermes", "-z", prompt],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NO_WINDOW,
    env=env, bufsize=0,
)

with open(tmp_path, "a", encoding="utf-8") as f:
    for raw in iter(lambda: proc.stdout.read(1), b""):
        f.write(raw.decode("utf-8", errors="replace"))
        f.flush()

proc.wait()

# 写完成信号
with open(tmp_path + ".done", "w") as f:
    f.write("1")

# 输出路径供主程序读取
print(tmp_path, flush=True)
