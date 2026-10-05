"""受控跳到梅田部队战后，再以零 WRAM 写入重放原事件。

只接受有 ROM CRC32 侧车的同构建走廊即时存档。原 ROM、输入状态、SRAM 和
日常 Mesen 配置不修改。输出目录必须不存在，避免覆盖已有证据。
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]

def fingerprint(path):
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True, help="同 ROM、菜单已关闭的走廊检查点")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expect", choices=("stall", "advance"), required=True)
    p.add_argument("--mesen", default=r"F:\emulators\mesen2\Mesen.exe")
    a = p.parse_args()
    rom, state, out = a.rom.resolve(), a.state.resolve(), a.out.resolve()
    crc = f"{zlib.crc32(rom.read_bytes()):08X}"
    metadata = json.loads(state.with_suffix(".json").read_text(encoding="utf-8"))
    if metadata["rom_crc32"] != crc:
        p.error("状态与 ROM 身份不匹配；禁止跨版重放")
    if out.exists():
        p.error("输出目录已存在，请选择新的隔离目录")
    out.mkdir(parents=True)
    protected = {str(x): fingerprint(x) for x in (rom, state, state.with_suffix(".json"))}
    runner = ROOT / "tools" / "run_mesen_play.py"
    env = dict(os.environ, STORY_EXPECT=a.expect, PYTHONUTF8="1")

    def run(tag, checkpoint, script, frames):
        subprocess.run([sys.executable, str(runner), "--mesen", a.mesen,
                        "--rom", str(rom), "--state", str(checkpoint),
                        "--tag", tag, "--frames", str(frames),
                        "--shots", "1000,1500,2000,4000", "--script", str(script),
                        "--out", str(out / tag)], env=env, cwd=ROOT, check=True)

    run("jump", state, ROOT / "hw" / "mesen_umeda_jump.lua", 4700)
    checkpoint = out / "jump" / "jump-msg-00C4.state"
    for c in (out / "jump").glob("jump-msg-*.state"):
        c.with_suffix(".json").write_text(json.dumps({
            "rom_crc32": crc, "rom_sha256": protected[str(rom)]["sha256"],
            "checkpoint": fingerprint(c),
            "scope": "controlled event08 jump; not natural quest progression"
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    run("continue", checkpoint, ROOT / "hw" / "mesen_umeda_continue.lua", 4000)
    log = (out / "continue" / "continue.log").read_text(encoding="utf-8")
    if f"PASS controlled original event08 continuation expectation={a.expect}" not in log:
        raise AssertionError("缺少真实消费者断言的完成标志")
    result = re.search(r"^RESULT (.+)$", log, re.MULTILINE)
    if not result:
        raise AssertionError("缺少运行结果")
    for name, old in protected.items():
        if fingerprint(Path(name)) != old:
            raise AssertionError(f"输入被修改: {name}")
    scripts = [ROOT / "hw" / name for name in
               ("mesen_umeda_jump.lua", "mesen_umeda_continue.lua")]
    manifest = {"rom_crc32": crc, "inputs_unchanged": protected,
                "expectation": a.expect, "status": "pass", "result": result[1],
                "scripts": {str(x): fingerprint(x) for x in scripts},
                "scope": "controlled original event08; zero memory writes during continuation; not full playthrough"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {a.expect} ROM={crc}: {out / 'manifest.json'}")

if __name__ == "__main__":
    main()
