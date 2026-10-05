"""No-ROM input safety contracts. These unit tests do NOT validate gameplay."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("garage_runner", ROOT / "tools/run_garage_story.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GarageRunnerSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        # Synthetic zeros + tiny ORIGINAL code signatures, NOT a commercial ROM.
        data = bytearray(0x100000)
        for off, hexdata in (
            (0x1F703, "AD 74 03"),
            (0x7328, "AD 01 03 CD 00 1C 90 03 8D 00 1C 60"),
            (0x174C2, "4B AB 9C AC 08 9C AD 08 AD 1E 03 C9 0F"),
            (0x1769C, "A2 02 BD 01 0E 10 0C BD 31 13 F0 07 BD 03 03 29 10 F0 07"),
            (0x38DE7, "AD 25 1D 29 02 F0 1B A2 00 BD 01 0E 10 07 BD 2C 1D 29 E0 D0 0B"),
            (0x2361E, "BE BA 73 1C"),
            (0x239A1, "43 03 0B 00 53 01 64 14 43 03 0B 00 54 01"),
            (0x239D4, "63 95 62 94"),
        ):
            value = bytes.fromhex(hexdata)
            data[off:off + len(value)] = value
        self.rom = self.base / "synthetic.sfc"
        self.rom.write_bytes(data)
        self.state = self.base / "synthetic.state"
        self.state.write_bytes(b"unit-test state, never loaded into Mesen")
        self.sidecar = self.state.with_suffix(".json")
        self.meta = {"rom_crc32": f"{zlib.crc32(data):08X}",
                     "rom_sha256": hashlib.sha256(data).hexdigest(),
                     "checkpoint": runner.fingerprint(self.state)}
        self.save_meta()
        self.out = self.base / "new-output"

    def save_meta(self):
        self.sidecar.write_text(json.dumps(self.meta), encoding="utf-8")

    def check(self):
        return runner.check_inputs(self.rom, self.state, self.out)

    def test_valid_identity_readonly_no_output_created(self):
        before = {p: p.read_bytes() for p in (self.rom, self.state, self.sidecar)}
        result = self.check()
        self.assertEqual(result[3], self.meta["rom_crc32"])
        self.assertFalse(self.out.exists())
        for path, value in before.items():
            self.assertEqual(path.read_bytes(), value)

    def test_changed_pause_capture_boundary_rejected(self):
        data = bytearray(self.rom.read_bytes())
        data[0x7333] ^= 1
        self.rom.write_bytes(data)
        self.meta['rom_crc32'] = f'{zlib.crc32(data):08X}'
        self.meta['rom_sha256'] = hashlib.sha256(data).hexdigest()
        self.save_meta()
        with self.assertRaisesRegex(ValueError, '007328'):
            self.check()

    def test_changed_companion_consumer_rejected(self):
        data = bytearray(self.rom.read_bytes())
        data[0x1769C] ^= 1
        self.rom.write_bytes(data)
        self.meta['rom_crc32'] = f'{zlib.crc32(data):08X}'
        self.meta['rom_sha256'] = hashlib.sha256(data).hexdigest()
        self.save_meta()
        with self.assertRaisesRegex(ValueError, '01769C'):
            self.check()

    def test_changed_all_actor_wait_rejected(self):
        data = bytearray(self.rom.read_bytes())
        data[0x38DE7] ^= 1
        self.rom.write_bytes(data)
        self.meta['rom_crc32'] = f'{zlib.crc32(data):08X}'
        self.meta['rom_sha256'] = hashlib.sha256(data).hexdigest()
        self.save_meta()
        with self.assertRaisesRegex(ValueError, '038DE7'):
            self.check()

    def test_missing_sidecar_rejected(self):
        self.sidecar.unlink()
        with self.assertRaisesRegex(ValueError, "CRC32"):
            self.check()
        self.assertFalse(self.out.exists())

    def test_cross_rom_crc_rejected(self):
        self.meta["rom_crc32"] = "NOTMATCH"
        self.save_meta()
        with self.assertRaisesRegex(ValueError, "身份不匹配"):
            self.check()

    def test_wrong_rom_sha_rejected(self):
        self.meta["rom_sha256"] = "0" * 64
        self.save_meta()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.check()

    def test_state_mutation_rejected(self):
        self.state.write_bytes(b"different state")
        with self.assertRaisesRegex(ValueError, "即时存档已改变"):
            self.check()

    def test_existing_output_preserved(self):
        self.out.mkdir()
        sentinel = self.out / "keep.txt"
        sentinel.write_bytes(b"do not overwrite")
        with self.assertRaisesRegex(ValueError, "输出目录已存在"):
            self.check()
        self.assertEqual(sentinel.read_bytes(), b"do not overwrite")

    def test_changed_consumer_signature_rejected(self):
        data = bytearray(self.rom.read_bytes())
        data[0x239D4] = 0
        self.rom.write_bytes(data)
        self.meta["rom_crc32"] = f"{zlib.crc32(data):08X}"
        self.meta["rom_sha256"] = hashlib.sha256(data).hexdigest()
        self.save_meta()
        with self.assertRaisesRegex(ValueError, "消费者已改变"):
            self.check()

    def test_relative_mesen_resolves_from_caller(self):
        old = Path.cwd()
        exe = self.base / "fake-Mesen.exe"
        exe.write_bytes(b"unit-only executable placeholder")
        try:
            os.chdir(self.base)
            self.assertEqual(runner.resolve_mesen(Path(exe.name)), exe.resolve())
        finally:
            os.chdir(old)

    def test_explicit_mesen_deadline_is_inside_process_deadline(self):
        for frames in (1, 1200, 5000, 16000):
            core, process = runner.mesen_timeouts(frames)
            self.assertGreaterEqual(core, 120)
            self.assertGreater(process, core)
        self.assertEqual(runner.mesen_timeouts(5000), (500, 530))
        with self.assertRaises(ValueError):
            runner.mesen_timeouts(0)
        source = (ROOT / "tools/run_garage_story.py").read_text(encoding="utf-8")
        self.assertIn('f"--timeout={core_timeout}"', source)
        self.assertIn('timeout=process_timeout', source)

    def test_menu_abi_probe_counts_actual_native_calls(self):
        source = (ROOT / "hw/mesen_garage_probe.lua").read_text(encoding="utf-8")
        self.assertIn('0x1F706,0x1F706', source)
        self.assertIn('0x1F70B,0x1F70B', source)
        self.assertIn('menuEntry.a&0xFFEF', source)
        self.assertIn("menuCalls==0 and 'UNEXERCISED'", source)
        self.assertIn("st['cpu.ps']~=flags", source)

    def test_capture_boundary_remains_reachable_in_start_overlay(self):
        source = (ROOT / "hw/mesen_garage_probe.lua").read_text(encoding="utf-8")
        self.assertIn('0x7333,0x7333', source)
        self.assertNotIn('0x7203,0x7203', source)

    def test_snapshot_grace_records_actual_without_fake_frame_count(self):
        self.assertEqual(runner.completion_frame("SAVED frames=1201\n", 1200, False), (1201, True))
        self.assertEqual(runner.completion_frame("SAVED frames=1203\n", 1200, False), (1203, False))
        self.assertEqual(runner.completion_frame("SAVED frames=1199\n", 1200, False), (1199, False))

    def test_early_preparation_requires_completion_marker(self):
        self.assertEqual(runner.completion_frame("SAVED frames=6701\n", 10000, True), (6701, True))
        self.assertEqual(runner.completion_frame("SHOT 6701\n", 10000, True), (None, False))
        self.assertEqual(runner.completion_frame("SAVED frames=0\n", 10000, True), (0, False))

    def test_replay_probe_has_no_injection_api(self):
        probe = (ROOT / "hw/mesen_garage_probe.lua").read_text(encoding="utf-8")
        for api in ("emu.write(", "emu.setState(", "emu.reset(", "emu.setRom("):
            self.assertNotIn(api, probe)
        self.assertIn("emu.setInput(key,0)", probe)
        self.assertIn("entered and gateAccepted>0", probe)
        self.assertIn("expect and not pass and 1 or 0", probe)


if __name__ == "__main__":
    unittest.main()
