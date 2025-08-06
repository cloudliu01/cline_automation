import os
import json
import tempfile
import shutil
import time
import pathlib
import azure.cognitiveservices.speech as speechsdk
import time as time_module  
from datetime import datetime

def ms_to_vtt(ms: int) -> str:
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def make_word_boundary_handler(word_boundaries, text):
    def on_word_boundary(evt):
        start_ms = int(evt.audio_offset / 10_000)
        boundary_type = getattr(evt, "boundary_type", None)
        text_offset = getattr(evt, "text_offset", None)
        word_length = getattr(evt, "word_length", None)
        word = None
        if text_offset is not None and word_length is not None:
            try:
                word = text[text_offset:text_offset + word_length]
            except Exception:
                pass
        word_boundaries.append({
            "start_ms": start_ms,
            "text_offset": text_offset,
            "word_length": word_length,
            "word": word,
            "boundary_type": str(boundary_type) if boundary_type is not None else None
        })
    return on_word_boundary

def synthesize_speech(text: str, outdir='./output/audio', save_vtt=True) -> dict:
    speech_config = speechsdk.SpeechConfig(
        subscription=os.environ.get('AZURE_TTS_KEY'),
        endpoint=os.environ.get('AZURE_TTS_ENDPOINT')
    )
    speech_config.speech_synthesis_voice_name = 'zh-CN-XiaochenMultilingualNeural'
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
    )

    dt_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = dt_str
    timestamped_dir = pathlib.Path(outdir, base)
    timestamped_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmpfile:
        tmp_path = tmpfile.name

    word_boundaries = []
    handler = make_word_boundary_handler(word_boundaries, text)
    speech_synthesizer = None

    try:
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmp_path)
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        speech_synthesizer.synthesis_word_boundary.connect(handler)
        result = speech_synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_path = timestamped_dir / f'audio.mp3'
            shutil.copy(tmp_path, audio_path)

            json_path = timestamped_dir / f'words.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "text": text,
                    "items": word_boundaries
                }, f, ensure_ascii=False, indent=2)

            vtt_path = None
            if save_vtt:
                vtt_path = timestamped_dir / f'subtitle.vtt'
                lines = ["WEBVTT", ""]
                for i, item in enumerate(word_boundaries):
                    start = item["start_ms"]
                    end = (word_boundaries[i + 1]["start_ms"]
                           if i + 1 < len(word_boundaries) else start + 200)
                    text_token = item.get("word") or ""
                    lines.append(str(i + 1))
                    lines.append(f"{ms_to_vtt(start)} --> {ms_to_vtt(end)}")
                    lines.append(text_token)
                    lines.append("")
                with open(vtt_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))

            return {
                "audio_path": str(audio_path),
                "words_json_path": str(json_path),
                "vtt_path": str(vtt_path) if vtt_path else None
            }
        else:
            if result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                raise Exception(
                    f"TTS canceled: {cancellation_details.reason} - "
                    f"{getattr(cancellation_details, 'error_details', '')}"
                )
            raise Exception(f"TTS failed: {result.reason}")
    finally:
        # Ensure the synthesizer is closed before deleting the temp file!
        if speech_synthesizer is not None:
            speech_synthesizer.stop_speaking()
        # Wait up to 1 second for file to unlock (especially for Windows)
        for _ in range(10):
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                break
            except PermissionError:
                time_module.sleep(0.1)
        else:
            print(f"Warning: Could not remove temp file: {tmp_path}")


# 用法例子
if __name__ == "__main__":
    text = ('美国人没来日本的时候，日本没有民主选举，民众吃不饱穿不暖，农家子弟男要当兵女要当妓，农民没有土地，武士阶级高人一等。'
            '整个日本配给制，吃点好的都要被举报。日本节节败退，但新闻报道却一直是大获全胜。'
            '结果美国人来了以后：1946年10月11日，麦克阿瑟向币原首相口头传达了五大改革指令。'
            #'一，女性解放：从此日本女性有了女性参政议政的权利。'
            #'二，承认劳动者的组织权：从此劳动者可以组织工会，可以团结起来争取自己的权益。'
            #'三，教育民主化：军国教育天皇教育就此取消，学校可以自己选定教育课本和内容。'
            #'四，秘密警察的废除：再也没有半夜突然警察抄家带你去问话的恐惧。私权得以保护。'
            #'五，经济民主化：大财阀被分割，中小企业，手工业者，农民也得到了保障。'
            #'基于这五大改革指令，战前的治安维持法被废止，德田球一等政治犯思想犯被释放，日本共产党终于可以日本公开成立，并组织劳动者。'
            #'虽然麦克阿瑟一生反共，但民主化却更重视。事实上直到朝鲜战争爆发，美军日本大本营才开始压制日本左翼政党，但这种压制也比二战时候日本军国主义要柔和的多。'
            #'经济民主化还让大财阀解体，从此一家独大的情况很长时间不再出现，资本被分散到各个中小企业，这成为了日本之后高度经济发展时期的基础。'
            #'优秀的技术者不在集中于财阀工厂里，在各自行业的小公司发挥作用，索尼等这类企业才得以成长。'
            #'土地改革，强制将大地主的田地没收，然后分给农民，日本版的“打土豪分田地”。旧日本地主，地方大名没落，农民开始真正掌握土地，大大刺激了农民的积极性，日本战后很快就解决粮食不足问题'
    )
    result = synthesize_speech(text)
    print("Audio:", result["audio_path"])
    print("Words JSON:", result["words_json_path"])
    print("VTT:", result["vtt_path"])
