"""Produce a Precision-Synced 1920x1080 Broadcast Demo Video (.mp4) (~3 min 15 sec)
where EVERY voiceover sentence matches EXACTLY what is visible on screen!

Key Audio-UI Synchronization Engine:
- Reads exact Playwright event timestamps from `scratch/demo_clips_v2/clip_markers.json`.
- Trims initial page-load/auth setup (`t_start_trim`) so ZERO white loading screens ever appear.
- Compresses ONLY the LLM waiting/spinner interval (`t_think_start .. t_answer_ready`) into a
  snappy 3.2s visual beat showing the live SSE Thinking progress badges.
- Plays the actual rendered answer (English grounded answer + Eligibility Cards + Official Links,
  FULL Hindi Devanagari answer text + Hindi Devanagari Follow-Ups + Listen button, 0.04s PII block,
  HITL Confirm Modal + MOEDU Ticket, Admin Trace Waterfall + Admin Benchmark Evals) cleanly at
  natural ~1.0x pace synchronized directly with the neural Indian-English voiceover!
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = PROJECT_ROOT / "docs" / "assets"
DIAG_DIR = PROJECT_ROOT / "docs" / "diagrams"
WORK_DIR = Path(
    r"C:\Users\Raj Gandhi\.gemini\antigravity\brain\658d51c5-0985-498e-a8ec-f39d8e5b7604\scratch\video_studio_v2"
)
CLIPS_DIR = Path(
    r"C:\Users\Raj Gandhi\.gemini\antigravity\brain\658d51c5-0985-498e-a8ec-f39d8e5b7604\scratch\demo_clips_v2"
)
OUT_MP4 = PROJECT_ROOT / "docs" / "deliverables" / "JanSahayak_AI_EndToEnd_Demo_Video.mp4"

VOICE = "en-IN-PrabhatNeural"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080


def _font(size: int, bold: bool = False):
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for fp in candidates:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def _probe_duration(path: Path) -> float:
    cmd = [FFMPEG, "-i", str(path)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            part = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = part.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 10.0


async def _synth_audio(text: str, out_mp3: Path) -> float:
    try:
        comm = edge_tts.Communicate(text, VOICE, rate="+7%")
        await comm.save(str(out_mp3))
    except Exception as exc:
        print(f"      [TTS fallback -> gTTS en-IN] ({exc.__class__.__name__})")
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", tld="co.in", slow=False)
        tts.save(str(out_mp3))
    return _probe_duration(out_mp3)


def _render_slide_frame(
    out_png: Path,
    kicker: str,
    title: str,
    subtitle: str,
    main_img: Path | None,
    dark: bool = False,
    footer_badge: str = "",
) -> Path:
    bg_col = (11, 34, 57) if dark else (248, 250, 252)
    img = Image.new("RGB", (W, H), bg_col)
    draw = ImageDraw.Draw(img)

    if dark and main_img and main_img.exists():
        cover = Image.open(main_img).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
        img.paste(cover, (0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([96, 120, 845, 178], radius=14, fill=(234, 88, 12))
        draw.text((126, 134), kicker.upper(), font=_font(26, bold=True), fill=(255, 255, 255))
        draw.text((96, 225), title, font=_font(76, bold=True), fill=(255, 255, 255))
        draw.rectangle([96, 430, 320, 440], fill=(251, 191, 36))
        draw.text((96, 475), subtitle, font=_font(34, bold=False), fill=(226, 232, 240))
        draw.rounded_rectangle([96, 860, 1824, 980], radius=18, fill=(19, 51, 84), outline=(51, 85, 122), width=2)
        draw.text((130, 898), footer_badge, font=_font(28, bold=True), fill=(251, 191, 36))
    else:
        draw.rectangle([0, 0, W, 12], fill=(234, 88, 12))
        draw.rectangle([0, 12, W, 152], fill=(255, 255, 255))
        draw.line([(0, 152), (W, 152)], fill=(226, 232, 240), width=2)
        draw.text((76, 26), kicker.upper(), font=_font(22, bold=True), fill=(234, 88, 12))
        draw.text((76, 62), title, font=_font(44, bold=True), fill=(11, 34, 57))
        if main_img and main_img.exists():
            im = Image.open(main_img).convert("RGB")
            max_w, max_h = 1760, 780
            scale = min(max_w / im.width, max_h / im.height)
            nw, nh = int(im.width * scale), int(im.height * scale)
            im = im.resize((nw, nh), Image.Resampling.LANCZOS)
            px = (W - nw) // 2
            py = 176 + (max_h - nh) // 2
            draw.rounded_rectangle([px - 6, py - 6, px + nw + 6, py + nh + 6], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
            img.paste(im, (px, py))
        draw.rectangle([0, 988, W, H], fill=(11, 34, 57))
        draw.text((76, 1014), subtitle, font=_font(27, bold=True), fill=(251, 191, 36))

    img.save(out_png)
    return out_png


def _render_overlay_bar(out_png: Path, step_pill: str, caption: str) -> Path:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H - 84, W, H], fill=(11, 34, 57, 236))
    draw.rectangle([0, H - 88, W, H - 84], fill=(234, 88, 12, 255))
    pill_w = max(210, len(step_pill) * 14 + 46)
    draw.rounded_rectangle([38, H - 66, 38 + pill_w, H - 18], radius=10, fill=(234, 88, 12, 255))
    draw.text((58, H - 56), step_pill, font=_font(22, bold=True), fill=(255, 255, 255, 255))
    draw.text((62 + pill_w, H - 58), caption, font=_font(26, bold=True), fill=(248, 250, 252, 255))
    img.save(out_png)
    return out_png


def _build_still_segment(frame_png: Path, audio_mp3: Path, dur: float, out_mp4: Path) -> None:
    total_dur = dur + 0.50
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-t", f"{total_dur:.2f}", "-i", str(frame_png),
        "-i", str(audio_mp3),
        "-vf", f"scale=1920:1080,fps=30,fade=t=in:st=0:d=0.30,fade=t=out:st={max(0.2, total_dur-0.30):.2f}:d=0.30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-af", "apad=pad_dur=0.50",
        "-t", f"{total_dur:.2f}",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _build_synced_live_segment(
    clip_webm: Path,
    marker: dict[str, float],
    overlay_png: Path,
    audio_mp3: Path,
    audio_dur: float,
    out_mp4: Path,
) -> None:
    """Surgically pace a recorded browser clip using its exact Playwright event timestamps:
    - Part A (t_start_trim -> t_think_start): login / profile / typing at crisp pace
    - Part B (t_think_start -> t_answer_ready): compress long LLM spinner wait cleanly to ~3.2s!
    - Part C (t_answer_ready -> end): actual rendered answer, cards, Devanagari text, localized
      follow-ups, HITL modal & receipt paced naturally to fill the remaining narration time!
    """
    raw_dur = _probe_duration(clip_webm)
    target_dur = audio_dur + 0.50
    t0 = max(0.0, min(marker.get("t_start_trim", 0.0), raw_dur - 2.0))

    has_think = (
        "t_think_start" in marker
        and "t_answer_ready" in marker
        and marker["t_answer_ready"] - marker["t_think_start"] > 4.2
    )

    if has_think:
        t1 = min(marker["t_think_start"], raw_dur - 1.5)
        t2 = min(marker["t_answer_ready"], raw_dur - 1.0)
        d_a = max(0.5, t1 - t0)
        d_b = max(0.5, t2 - t1)
        d_c = max(1.0, raw_dur - t2)

        # Allocate clean target durations matching narration structure!
        tgt_b = 3.2  # Crisp 3.2s live SSE Thinking progress beat!
        rem = max(4.0, target_dur - tgt_b)
        # Keep typing snappy (slightly accelerated if long), give generous real-time focus to the Answer (Part C)!
        tgt_a = min(rem * 0.42, max(3.5, d_a / 1.35))
        tgt_c = max(3.0, rem - tgt_a)

        pts_a = tgt_a / d_a
        pts_b = tgt_b / d_b
        pts_c = tgt_c / d_c

        vf = (
            f"[0:v]split=3[va][vb][vc];"
            f"[va]trim=start={t0:.2f}:end={t1:.2f},setpts=(PTS-STARTPTS)*{pts_a:.4f}[sa];"
            f"[vb]trim=start={t1:.2f}:end={t2:.2f},setpts=(PTS-STARTPTS)*{pts_b:.4f}[sb];"
            f"[vc]trim=start={t2:.2f},setpts=(PTS-STARTPTS)*{pts_c:.4f}[sc];"
            f"[sa][sb][sc]concat=n=3:v=1:a=0,"
            f"scale=1920:992:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(992-ih)/2:color=#0B2239,"
            f"fps=30[base];"
            f"[base][1:v]overlay=0:0,"
            f"tpad=stop_mode=clone:stop_duration=10,"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.2, target_dur-0.25):.2f}:d=0.25[v]"
        )
    else:
        # Clean continuous clip (e.g. Privacy instant 0.04s block or Admin Trace + Eval tour)
        eff_dur = max(1.0, raw_dur - t0)
        pts = max(0.65, min(1.80, target_dur / eff_dur))
        vf = (
            f"[0:v]trim=start={t0:.2f},setpts=(PTS-STARTPTS)*{pts:.4f},"
            f"scale=1920:992:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(992-ih)/2:color=#0B2239,"
            f"fps=30[base];"
            f"[base][1:v]overlay=0:0,"
            f"tpad=stop_mode=clone:stop_duration=10,"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.2, target_dur-0.25):.2f}:d=0.25[v]"
        )

    cmd = [
        FFMPEG, "-y",
        "-i", str(clip_webm),
        "-i", str(overlay_png),
        "-i", str(audio_mp3),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-af", "apad=pad_dur=0.50",
        "-t", f"{target_dur:.2f}",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


SCENES = [
    {
        "id": "01_intro",
        "kind": "still",
        "dark": True,
        "img": ASSET_DIR / "ppt_hero_cover.jpg",
        "kicker": "IIT Kharagpur Executive PG  •  Track B Capstone",
        "title": "JanSahayak AI\nCitizen Welfare Copilot",
        "subtitle": "649 Central Schemes  •  7 Indian Languages  •  HITL CPGRAMS Action\nEngineered strictly on Qwen3-8B + bge-small-en-v1.5 — zero fine-tuning.",
        "footer": "100% Gold Hit@5  •  88.3% vs 19% Judge Accuracy (p<0.001)  •  20/20 Red-Team  •  ~₹67 / 1,000 Tasks",
        "narration": (
            "India runs six hundred and forty nine Central Government welfare schemes across fifty one ministries, "
            "yet millions lose entitlements to English portals, hidden exclusions, and complex CPGRAMS grievance forms. "
            "Meet JanSahayak AI — our multilingual, voice-first Agentic Hybrid RAG copilot, built strictly on IIT Kharagpur's "
            "Track B small-model stack: Qwen 3, 8 billion parameters, and BGE Small embeddings, with zero fine-tuning."
        ),
    },
    {
        "id": "02_citizen_discovery",
        "kind": "live",
        "marker_key": "clip_01",
        "clip": CLIPS_DIR / "clip_01_citizen_discovery.webm",
        "pill": "LIVE DEMO 1/5",
        "caption": "Citizen Login & Profile -> Hybrid RAG + Deterministic Eligibility Rules + Citations & Follow-Ups",
        "narration": (
            "Signing in as Priya Sharma, a nineteen-year-old OBC engineering student, her profile loads automatically. "
            "When she asks which central scholarships she qualifies for, the live thinking indicator streams each LangGraph step. "
            "First, Priya sees a grounded answer with official citations; scrolling down reveals her deterministic eligibility verdict, "
            "a ready-to-use document checklist, direct myScheme links, and three one-tap suggested follow-up questions."
        ),
    },
    {
        "id": "03_hindi_multilingual",
        "kind": "live",
        "marker_key": "clip_02",
        "clip": CLIPS_DIR / "clip_02_hindi_multilingual.webm",
        "pill": "LIVE DEMO 2/5",
        "caption": "Hindi Devanagari Query -> English-Pivot Hybrid RAG -> Grounded Devanagari Reply & Follow-Ups",
        "narration": (
            "Switching the interface to Hindi, Priya asks for college scholarships in Devanagari script. "
            "JanSahayak pivots her query into English for unified hybrid retrieval across all six hundred and forty nine schemes, "
            "then renders a clear, cited Hindi Devanagari response — followed by official scheme links, "
            "localized Hindi follow-up questions in Devanagari, and one-click voice audio read-aloud."
        ),
    },
    {
        "id": "04_privacy_guardrail",
        "kind": "live",
        "marker_key": "clip_03",
        "clip": CLIPS_DIR / "clip_03_privacy_guardrail.webm",
        "pill": "LIVE DEMO 3/5",
        "caption": "DPDP Act 2023 PII Masking + Prompt-Injection Shield (0.04s Block, 0 LLM Tokens)",
        "narration": (
            "Now watch our privacy and safety guardrail in action. When a user enters a twelve-digit Aadhaar number "
            "alongside a prompt-injection attack trying to expose internal instructions, our deterministic DPDP shield "
            "blocks it in forty milliseconds — redacting the Aadhaar number before a single token ever reaches Qwen 3."
        ),
    },
    {
        "id": "05_hitl_grievance",
        "kind": "live",
        "marker_key": "clip_04",
        "clip": CLIPS_DIR / "clip_04_hitl_grievance.webm",
        "pill": "LIVE DEMO 4/5",
        "caption": "CPGRAMS Action: <=2,000-Char Draft + Code-Gated HITL Confirm + Live MOEDU Ticket",
        "narration": (
            "When Priya reports a delayed PM-USP scholarship installment, the agent routes her complaint to the Ministry of Education, "
            "drafts a formal grievance strictly under two thousand characters, and pauses inside a mandatory Human-in-the-Loop modal. "
            "Only after Priya clicks Confirm does it register her live CPGRAMS sandbox ticket with an official pgportal handoff packet."
        ),
    },
    {
        "id": "06_admin_observability",
        "kind": "live",
        "marker_key": "clip_05",
        "clip": CLIPS_DIR / "clip_05_admin_observability.webm",
        "pill": "LIVE DEMO 5/5",
        "caption": "Admin RBAC: Masked-PII Execution Trace Waterfall -> Live Benchmark Evals Dashboard",
        "narration": (
            "Switching to the Administrator portal unlocks complete LLMOps observability. "
            "Notice the blocked Aadhaar prompt stored safely as masked digits in forty milliseconds with zero tokens, "
            "alongside per-node span timings, Planner JSON, and Critic audits. Clicking Benchmark Evals opens our synchronized "
            "evaluation dashboard featuring ROUGE, BLEU, BERTScore, retrieval ablations, and independent Gemini judging."
        ),
    },
    {
        "id": "07_architecture",
        "kind": "still",
        "dark": False,
        "img": DIAG_DIR / "clean_01_system_architecture.png",
        "kicker": "Track B Small-Model Engineering Architecture",
        "title": "7-Stage LangGraph + ReAct Reflector Loop & Deterministic Tools",
        "subtitle": "5 Pydantic Tools  •  Max 2 Reflector Rounds  •  18 Code-Enforced DPDP Defenses  •  Single-Worker Shared-VM Safe",
        "narration": (
            "Under the hood, JanSahayak runs a seven-stage LangGraph pipeline with a bounded ReAct Reflector loop, "
            "five Pydantic-validated tools, section-aware four hundred and forty token chunking, and eighteen code-enforced privacy defenses."
        ),
    },
    {
        "id": "08_evals_and_vision",
        "kind": "still",
        "dark": False,
        "img": DIAG_DIR / "clean_04_synced_eval_benchmarks.png",
        "kicker": "Zero-Leakage Benchmarks & Population-Scale India Vision",
        "title": "Verified Statistical Proof & DPI-Ready Sustainability (~₹67 / 1K Tasks)",
        "subtitle": "88.3% vs 19% Gold QA (p<0.001)  •  81.2% 80-Task Loop (100% Eligibility)  •  20/20 Red-Team  •  Bhashini & DigiLocker Ready",
        "narration": (
            "On sixty zero-leakage gold questions with FAQ chunks excluded, hybrid RAG jumps from nineteen percent for vanilla Qwen 3 "
            "to eighty eight point three percent on Gemini judging, with McNemar p under zero point zero zero one. "
            "Trace-driven fixes lifted our eighty-task Reflector loop to eighty one point two percent completion and one hundred percent "
            "on eligibility and refusals — at just sixty seven rupees per thousand tasks. "
            "Ready to plug into Bhashini, DigiLocker, and Common Service Centres, JanSahayak AI puts India's welfare schemes "
            "in every citizen's voice. Thank you."
        ),
    },
]


async def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    markers = json.loads((CLIPS_DIR / "clip_markers.json").read_text(encoding="utf-8"))
    seg_files: list[Path] = []

    for sc in SCENES:
        sid = sc["id"]
        mp3_path = WORK_DIR / f"{sid}.mp3"
        print(f"[TTS] Synthesizing {sid}...")
        dur = await _synth_audio(sc["narration"], mp3_path)
        print(f"      -> {dur:.2f}s voiceover")

        seg_mp4 = WORK_DIR / f"seg_{sid}.mp4"
        if sc["kind"] == "still":
            frame_png = WORK_DIR / f"frame_{sid}.png"
            _render_slide_frame(
                frame_png,
                kicker=sc["kicker"],
                title=sc["title"],
                subtitle=sc["subtitle"],
                main_img=sc["img"],
                dark=sc.get("dark", False),
                footer_badge=sc.get("footer", ""),
            )
            _build_still_segment(frame_png, mp3_path, dur, seg_mp4)
        else:
            clip_path = sc["clip"]
            assert clip_path.exists(), f"Missing live clip: {clip_path}"
            ov_png = WORK_DIR / f"overlay_{sid}.png"
            _render_overlay_bar(ov_png, sc["pill"], sc["caption"])
            _build_synced_live_segment(
                clip_path,
                markers[sc["marker_key"]],
                ov_png,
                mp3_path,
                dur,
                seg_mp4,
            )

        seg_dur = _probe_duration(seg_mp4)
        seg_files.append(seg_mp4)
        print(f"[SEG OK] {seg_mp4.name} ({seg_dur:.2f}s)")

    concat_txt = WORK_DIR / "concat_list.txt"
    concat_txt.write_text(
        "\n".join(f"file '{str(p).replace(chr(92), '/')}'" for p in seg_files),
        encoding="utf-8",
    )
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c", "copy", "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    final_dur = _probe_duration(OUT_MP4)
    print(f"[FINAL SYNCED VIDEO OK] {OUT_MP4} | {final_dur:.1f}s ({final_dur/60:.2f} min) | {OUT_MP4.stat().st_size:,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
