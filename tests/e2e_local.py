"""End-to-end check without network: a synthetic clip with three scenes and a sidecar caption file, plus a silent
clip, go through the real pipeline (ffmpeg frames, caption parsing, alignment, README, manifest, index, search).

Run: uv run python tests/e2e_local.py
"""
import json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ctxr import cli  # noqa: E402


def clip(path, audio=True):
    scenes = ["testsrc2=size=640x360:rate=25:duration=8", "smptebars=size=640x360:rate=25:duration=8", "mandelbrot=size=640x360:rate=25"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", scenes[0], "-f", "lavfi", "-i", scenes[1], "-t", "8", "-f", "lavfi", "-i", scenes[2]]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=24"]
    cmd += ["-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]"] + (["-map", "3:a", "-c:a", "aac"] if audio else []) + \
           ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        demo = td / "my demo.mp4"
        clip(demo)
        (td / "my demo.srt").write_text("1\n00:00:00,500 --> 00:00:07,000\nWelcome to the local demo.\n\n"
                                        "2\n00:00:08,000 --> 00:00:15,000\nThis is the second scene.\n\n"
                                        "3\n00:00:16,000 --> 00:00:23,000\nAnd the third one ends here.\n")
        silent = td / "silent.mp4"
        clip(silent, audio=False)
        out = td / "out"
        rc = subprocess.run([sys.executable, "-m", "ctxr.cli", str(demo), str(silent), "--out", str(out), "--cooldown", "0"],
                            cwd=Path(__file__).resolve().parents[1] / "src", capture_output=True, text=True)
        print(rc.stdout.strip().splitlines()[-1] if rc.stdout.strip() else rc.stderr[-500:])
        assert rc.returncode == 0, rc.stderr[-2000:]

        folders = sorted(p for p in out.iterdir() if p.is_dir())
        assert len(folders) == 2, folders
        demo_dir = next(p for p in folders if "my-demo" in p.name)
        m = json.loads((demo_dir / "manifest.json").read_text())
        assert m["platform"] == "Local" and m["transcript_source"] == "captions", m
        assert [f["t"] for f in m["frames"]] == [0.0, 8.0, 16.0], [f["t"] for f in m["frames"]]
        assert [s["text"] for f in m["frames"] for s in f["segments"]] == \
               ["Welcome to the local demo.", "This is the second scene.", "And the third one ends here."]
        assert (demo_dir / "frames" / m["frames"][1]["file"]).stat().st_size > 1000
        readme = (demo_dir / "README.md").read_text()
        assert "### 00:08" in readme and "This is the second scene." in readme and "[watch]" not in readme, readme[:400]
        assert not list(out.glob("*.mp4")) and not list(out.glob(".tmp-*")), "download leftovers"

        s = json.loads((next(p for p in folders if "silent" in p.name) / "manifest.json").read_text())
        assert s["transcript_source"] == "none" and s["frames"] and all(not f["segments"] for f in s["frames"]), s["transcript_source"]

        assert (out / "INDEX.md").read_text().count("| 20") == 2
        hits = cli.search(out, "second scene")
        assert len(hits) == 1 and hits[0]["t"] == 8.0 and hits[0]["frame"].endswith("0002_00m08s.jpg"), hits
        print("e2e ok: local clip with sidecar captions, silent clip, index and search")


if __name__ == "__main__":
    main()
