"""地下停车场：具名场景受控准备 / 同 ROM 零内存写入重放。

默认只重放 --state，不跳剧情。--prepare 才会显式启用受控 scene4B/event15
夹具（准备早期分支、最终敌人 HP=1、玩家 HP=200；不是自然流程）。
只接受匹配 ROM CRC32 侧车的状态，输出目录必须不存在。失败也保留清单。
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def check_inputs(rom, state, out):
    """Fail before running Mesen or creating any output on invalid inputs."""
    rom, state, out = (Path(x).resolve() for x in (rom, state, out))
    if out.exists():
        raise ValueError("输出目录已存在；请选择新的隔离目录")
    if not rom.is_file() or not state.is_file():
        raise ValueError("ROM 或状态文件不存在")
    sidecar = state.with_suffix(".json")
    if not sidecar.is_file():
        raise ValueError("状态缺少同批 ROM CRC32 侧车；不能猜测版本或跨版载入")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    data = rom.read_bytes()
    crc = f"{zlib.crc32(data):08X}"
    if not isinstance(metadata, dict) or metadata.get("rom_crc32") != crc:
        raise ValueError("状态与 ROM 身份不匹配；禁止跨版重放")
    if metadata.get("rom_sha256") not in (None, hashlib.sha256(data).hexdigest()):
        raise ValueError("状态侧车的 ROM SHA-256 不匹配")
    saved_state = metadata.get("checkpoint")
    if isinstance(saved_state, dict) and saved_state.get("sha256") not in (None, fingerprint(state)["sha256"]):
        raise ValueError("即时存档已改变，不再匹配其指纹侧车")
    if len(data) not in (0x100000, 0x200000):
        raise ValueError("只支持本项目无外部头的 1 MiB / 2 MiB LoROM")
    # Validate ORIGINAL consumers; do not treat these addresses as generic SNES.
    for offset, expected in (
        (0x1F703, bytes.fromhex("AD 74 03")),
        (0x7328, bytes.fromhex("AD 01 03 CD 00 1C 90 03 8D 00 1C 60")),
        (0x174C2, bytes.fromhex("4B AB 9C AC 08 9C AD 08 AD 1E 03 C9 0F")),
        (0x1769C, bytes.fromhex("A2 02 BD 01 0E 10 0C BD 31 13 F0 07 BD 03 03 29 10 F0 07")),
        (0x38DE7, bytes.fromhex("AD 25 1D 29 02 F0 1B A2 00 BD 01 0E 10 07 BD 2C 1D 29 E0 D0 0B")),
        (0x2361E, bytes.fromhex("BE BA 73 1C")),
        (0x239A1, bytes.fromhex("43 03 0B 00 53 01 64 14 43 03 0B 00 54 01")),
        (0x239D4, bytes.fromhex("63 95 62 94")),
    ):
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"原场景消费者已改变，不能沿用探针地址: ROM {offset:06X}")
    protected = {str(x): fingerprint(x) for x in (rom, state, sidecar)}
    return rom, state, out, crc, protected


def resolve_mesen(path):
    # Resolve relative to the caller BEFORE subprocess changes cwd to ROOT.
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Mesen 可执行文件不存在")
    return path


def mesen_timeouts(frames):
    """Mesen has its OWN 100s default; give it an explicit bounded deadline.

    The subprocess deadline must be longer so a slow test can stop/release
    its isolated emulator cleanly. A timeout is not evidence of a game hang.
    """
    if frames < 1:
        raise ValueError("帧数必须是正数")
    core_seconds = max(120, (frames + 9) // 10)
    return core_seconds, core_seconds + 30


def completion_frame(log, requested, bounded):
    saved = re.search(r"^SAVED frames=(\d+)$", log, re.MULTILINE)
    actual = int(saved[1]) if saved else None
    valid = (actual is not None and 0 < actual <= requested + 2) if bounded else (actual is not None and requested <= actual <= requested + 2)
    return actual, valid


def write_manifest(out, manifest):
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True, help="同 ROM / 同批 CRC32 侧车的即时存档")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mesen", default=r"F:\emulators\mesen2\Mesen.exe")
    p.add_argument("--prepare", action="store_true", help="显式受控跳剧情；默认不启用、不改内存")
    p.add_argument("--prepare-frames", type=int, default=10000)
    p.add_argument("--frames", type=int, default=1200)
    p.add_argument("--input", default="", help="普通控制器输入，如 100-180:right")
    p.add_argument("--shots", default="300,450,650")
    p.add_argument("--auto-dialogue", action="store_true")
    p.add_argument("--enter", action="store_true", help="完成 event15 后用普通按键走到右门")
    p.add_argument("--expect", choices=("capture", "advance"), default="capture")
    a = p.parse_args()
    if a.frames < 1 or a.prepare_frames < 1:
        p.error("帧数必须是正数")
    try:
        rom, state, out, crc, protected = check_inputs(a.rom, a.state, a.out)
        a.mesen = resolve_mesen(a.mesen)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    state_metadata = json.loads(state.with_suffix(".json").read_text(encoding="utf-8"))
    scripts = [ROOT / "hw" / "mesen_garage_probe.lua"]
    if a.prepare:
        scripts.append(ROOT / "hw" / "mesen_garage_jump.lua")
    protected.update({str(x): fingerprint(x) for x in scripts})
    protected[str(Path(__file__).resolve())] = fingerprint(Path(__file__).resolve())
    protected[str(a.mesen)] = fingerprint(a.mesen)
    env = dict(os.environ, PYTHONUTF8="1", AUTO_FIGHT="", AUTO_DIALOGUE="",
               GARAGE_STAGE="", GARAGE_CPU2="", GARAGE_ENTER="", GARAGE_EXPECT_ENTRY="", PLAY_STOP_POLICE="")
    out.mkdir(parents=True)
    manifest = {
        "rom_crc32": crc, "rom_sha256": fingerprint(rom)["sha256"],
        "status": "running", "expectation": a.expect,
        "emulator": {"path": str(a.mesen), **fingerprint(a.mesen)},
        "scope": "controlled preparation + input-only replay" if a.prepare else "input-only replay from supplied same-ROM checkpoint",
        "preparation": {"enabled": a.prepare, "changes": "earlier event branches/maps/positions; final enemy starting HP=1, player HP=200" if a.prepare else "none",
                        "not_proven": ["natural quest completion", "normal enemy strength / exact180 XP", "Riki CPU context", "the reported user bug is repaired"]},
        "checkpoint_provenance": {
            "sidecar_scope": state_metadata.get("scope", "not specified; no natural-story claim"),
            "controlled_preparation": state_metadata.get("controlled_preparation"),
            "source_state": state_metadata.get("source_state"),
            "note": "input-only continuation does not turn an upstream controlled fixture into natural-mainline acceptance",
        },
        "inputs_unchanged": protected,
        "steps": [], "errors": [],
    }
    write_manifest(out, manifest)

    namespace = "garage-" + crc.lower() + "-" + hashlib.sha256(str(out).encode("utf-8")).hexdigest()[:8]

    def run(tag, checkpoint, script, frames, environment, inputs="", shots="30", bounded=False):
        file_tag = namespace + "-" + tag
        step = {"tag": tag, "file_tag": file_tag, "frames_max" if bounded else "frames_requested": frames,
                "state": str(checkpoint), "script": str(script), "input": inputs}
        manifest["steps"].append(step)
        # Both phases use a native-main-loop snapshot boundary. Saving can
        # occur one frame after the endFrame target, so record the ACTUAL count
        # and permit at most two snapshot-grace frames; never fabricate a count.
        directory = out / tag
        directory.mkdir()
        copied_rom = directory / (file_tag + ".smc")
        shutil.copy2(rom, copied_rom)
        play_env = dict(environment, PLAY_OUT=directory.as_posix(), PLAY_TAG=file_tag,
                        PLAY_FRAMES=str(frames), PLAY_SHOTS=shots, PLAY_INPUT=inputs,
                        PLAY_STATE=checkpoint.as_posix(), PLAY_SRAM="", PLAY_TRACE="",
                        PLAY_STOP_POLICE="1" if bounded else "")
        core_timeout, process_timeout = mesen_timeouts(frames)
        step["mesen_timeout_seconds"] = core_timeout
        step["process_timeout_seconds"] = process_timeout
        command = [str(a.mesen), "--testRunner", str(script), str(copied_rom),
                   "--doNotSaveSettings", f"--timeout={core_timeout}"]
        try:
            result = subprocess.run(command, cwd=ROOT, env=play_env, check=False,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8",
                                    timeout=process_timeout,
                                    creationflags=0x08000000 if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            text = exc.stdout or ""
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            result = subprocess.CompletedProcess(command, 124, text + "\nMESEN TIMEOUT\n")
        (out / (tag + "-runner.log")).write_text(result.stdout, encoding="utf-8")
        step["runner_exit"] = result.returncode
        logpath = out / tag / (file_tag + ".log")
        log = logpath.read_text(encoding="utf-8") if logpath.exists() else ""
        actual, saved = completion_frame(log, frames, bounded)
        step["actual_frames"] = actual
        step["snapshot_grace_frames"] = 2
        step["saved"] = saved
        proof = re.search(r"^SCENE_PROOF (.+)$", log, re.MULTILINE)
        if proof:
            step["scene_proof"] = proof[1]
            manifest["scene_proof"] = proof[1]
        abi = re.search(r"^NATIVE_MENU_ABI_PROOF (.+)$", log, re.MULTILINE)
        if abi:
            step["native_menu_abi_proof"] = abi[1]
        if result.returncode != 0 or not step["saved"]:
            raise RuntimeError(f"{tag} 没有完成预期消费者；失败日志已保留")
        return log

    ok = False
    try:
        checkpoint = state
        if a.prepare:
            log = run("prepare", state, ROOT / "hw" / "mesen_garage_jump.lua", a.prepare_frames,
                      env, shots="4500,5500,7500", bounded=True)
            if not re.search(r"^FIXTURE_PROOF finalBattle=true police0153=true .*luaWritesAfterStop=0;", log, re.MULTILINE):
                raise RuntimeError("受控准备缺少 final-KO / 停止内存写入的消费者证据")
            manifest["preparation"]["proof"] = next(x for x in log.splitlines() if x.startswith("FIXTURE_PROOF"))
            for c in (out / "prepare").glob(namespace + "-prepare-*.state"):
                c.with_suffix(".json").write_text(json.dumps({
                    "rom_crc32": crc, "rom_sha256": manifest["rom_sha256"],
                    "checkpoint": fingerprint(c), "scope": manifest["scope"],
                    "controlled_preparation": True,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            checkpoint = out / "prepare" / (namespace + "-prepare-msg-0153.state")
            if not checkpoint.is_file():
                raise RuntimeError("未取得原警方对话0153检查点")
        replay_env = dict(env, AUTO_DIALOGUE="1" if a.auto_dialogue or a.prepare else "",
                          GARAGE_ENTER="1" if a.enter or a.prepare else "",
                          GARAGE_EXPECT_ENTRY="1" if a.expect == "advance" else "")
        log = run("replay", checkpoint, ROOT / "hw" / "mesen_garage_probe.lua", a.frames,
                  replay_env, a.input, a.shots)
        proof = re.search(r"^SCENE_PROOF (.+)$", log, re.MULTILINE)
        if not proof:
            raise RuntimeError("缺少实际消费者 SCENE_PROOF；跑完帧数不是通过")
        manifest["scene_proof"] = proof[1]
        if a.expect == "advance" and "result=PASS" not in proof[1]:
            raise RuntimeError("原开门判定 / 进入4C断言失败")
        ok = True
    except Exception as exc:
        manifest["errors"].append(str(exc))
    finally:
        for name, before in protected.items():
            try:
                unchanged = fingerprint(Path(name)) == before
            except OSError:
                unchanged = False
            if not unchanged:
                ok = False
                manifest["errors"].append(f"受保护输入被改变: {name}")
        manifest["status"] = ("pass" if a.expect == "advance" else "captured") if ok else "fail"
        write_manifest(out, manifest)
    print(f"{manifest['status'].upper()} ROM={crc}: {out / 'manifest.json'}")
    for message in manifest["errors"]:
        print(message, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
