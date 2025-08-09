import re
import time
import importlib
import warnings
from typing import List
from kokoro import KPipeline
import numpy as np
import soundfile as sf
from loguru import logger
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS
from app.services.config import device

# Suppress PyTorch warnings
warnings.filterwarnings("ignore")

LANGUAGE_CONFIG = {
    "en-us": {
        "lang_code": "a",
        "international": False,
        "iso639_1": "en",
    },
    "en": {
        "lang_code": "a",
        "international": False,
        "iso639_1": "en",
    },
    "en-gb": {
        "lang_code": "b",
        "international": False,
        "iso639_1": "en",
    },
    "es": {"lang_code": "e", "international": True, "iso639_1": "es"},
    "fr": {"lang_code": "f", "international": True, "iso639_1": "fr"},
    "hi": {"lang_code": "h", "international": True, "iso639_1": "hi"},
    "it": {"lang_code": "i", "international": True, "iso639_1": "it"},
    "pt": {"lang_code": "p", "international": True, "iso639_1": "pt"},
    "ja": {"lang_code": "j", "international": True, "iso639_1": "ja"},
    "zh": {"lang_code": "z", "international": True, "iso639_1": "zh"},
}
LANGUAGE_VOICE_CONFIG = {
    "en-us": [
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ],
    "en-gb": [
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    ],
    "zh": [
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoxiao",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ],
    "es": ["ef_dora", "em_alex", "em_santa"],
    "fr": ["ff_siwis"],
    "it": ["if_sara", "im_nicola"],
    "pt": ["pf_dora", "pm_alex", "pm_santa"],
    "hi": ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"],
}

LANGUAGE_VOICE_MAP = {}
for lang, voices in LANGUAGE_VOICE_CONFIG.items():
    for voice in voices:
        if lang in LANGUAGE_CONFIG:
            LANGUAGE_VOICE_MAP[voice] = LANGUAGE_CONFIG[lang]
        else:
            print(f"Warning: Language {lang} not found in LANGUAGE_CONFIG")


class TTS:
    def break_text_into_sentences(self, text, lang_code) -> List[str]:
        """
        Advanced sentence splitting with better handling of abbreviations and edge cases.
        """
        if not text or not text.strip():
            return []

        # Language-specific sentence boundary patterns
        patterns = {
            "a": r"(?<=[.!?])\s+(?=[A-Z_])",  # English
            "e": r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑÜ¿¡_])",  # Spanish - allow inverted punctuation after boundaries
            "f": r"(?<=[.!?])\s+(?=[A-ZÁÀÂÄÇÉÈÊËÏÎÔÖÙÛÜŸ_])",  # French
            "h": r"(?<=[।!?])\s+",  # Hindi: Split after devanagari danda
            "i": r"(?<=[.!?])\s+(?=[A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß_])",  # Italian
            "p": r"(?<=[.!?])\s+(?=[A-ZÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝ_])",  # Portuguese
            "z": r"(?<=[。！？])",  # Chinese: Split after Chinese punctuation
        }

        # Common abbreviations that shouldn't trigger sentence breaks
        abbreviations = {
            "a": {
                "Mr.",
                "Mrs.",
                "Ms.",
                "Dr.",
                "Prof.",
                "Sr.",
                "Jr.",
                "Inc.",
                "Corp.",
                "Ltd.",
                "Co.",
                "etc.",
                "vs.",
                "eg.",
                "i.e.",
                "e.g.",
                "Vol.",
                "Ch.",
                "Fig.",
                "No.",
                "p.",
                "pp.",
            },  # English
            "e": {
                "Sr.",
                "Sra.",
                "Dr.",
                "Dra.",
                "Prof.",
                "etc.",
                "pág.",
                "art.",
                "núm.",
                "cap.",
                "vol.",
            },  # Spanish
            "f": {
                "M.",
                "Mme.",
                "Dr.",
                "Prof.",
                "etc.",
                "art.",
                "p.",
                "vol.",
                "ch.",
                "fig.",
                "n°",
            },  # French
            "h": {"श्री", "श्रीमती", "डॉ.", "प्रो.", "etc.", "पृ.", "अध."},  # Hindi
            "i": {
                "Sig.",
                "Sig.ra",
                "Dr.",
                "Prof.",
                "ecc.",
                "pag.",
                "art.",
                "n.",
                "vol.",
                "cap.",
                "fig.",
            },  # Italian
            "p": {
                "Sr.",
                "Sra.",
                "Dr.",
                "Dra.",
                "Prof.",
                "etc.",
                "pág.",
                "art.",
                "n.º",
                "vol.",
                "cap.",
            },  # Portuguese
            "z": {"先生", "女士", "博士", "教授", "等等", "第", "页", "章"},  # Chinese
        }

        abbrevs = abbreviations.get(lang_code, set())

        # Protect abbreviations by temporarily replacing them
        protected_text = text
        replacements = {}
        for i, abbrev in enumerate(abbrevs):
            placeholder = f"__ABBREV_{i}__"
            protected_text = protected_text.replace(abbrev, placeholder)
            replacements[placeholder] = abbrev

        # Apply the regex splitting
        pattern = patterns.get(lang_code, patterns["a"])
        sentences = re.split(pattern, protected_text.strip())

        # Restore abbreviations and clean up
        restored_sentences = []
        for sentence in sentences:
            for placeholder, original in replacements.items():
                sentence = sentence.replace(placeholder, original)
            sentence = sentence.strip()
            if sentence:
                restored_sentences.append(sentence)

        return restored_sentences if restored_sentences else [text.strip()]

    def kokoro_international(
        self, text: str, output_path: str, voice: str, lang_code: str, speed=1
    ) -> tuple[str, List[dict], float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
        if not lang_code:
            raise ValueError(f"Voice '{voice}' not found in LANGUAGE_VOICE_MAP")
        start = time.time()
        context_logger = logger.bind(
            voice=voice,
            speed=speed,
            text_length=len(text),
        )
        context_logger.debug("Starting TTS generation (international) with kokoro")
        sentences = self.break_text_into_sentences(text, lang_code)
        context_logger.debug(
            "Text split into sentences",
            sentences=sentences,
            num_sentences=len(sentences),
        )

        # generate the audio for each sentence
        audio_data = []
        captions = []
        full_audio_length = 0
        pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device)
        for sentence in sentences:
            context_logger.debug(
                "Processing sentence",
                sentence=sentence,
                voice=voice,
                speed=speed,
            )
            generator = pipeline(sentence, voice=voice, speed=speed)

            for i, result in enumerate(generator):
                context_logger.debug(
                    "Generated audio for sentence",
                )
                data = result.audio
                audio_length = len(data) / 24000
                audio_data.append(data)
                # since there are no tokens, we can just use the sentence as the text
                captions.append(
                    {
                        "text": sentence,
                        "start_ts": full_audio_length,
                        "end_ts": full_audio_length + audio_length,
                    }
                )
                full_audio_length += audio_length

        context_logger = context_logger.bind(
            execution_time=time.time() - start,
            audio_length=full_audio_length,
            speedup=full_audio_length / (time.time() - start),
        )
        context_logger.debug(
            "TTS generation (international) completed with kokoro",
        )

        audio_data = np.concatenate(audio_data)
        audio_data = np.column_stack((audio_data, audio_data))
        sf.write(output_path, audio_data, 24000, format="WAV")
        return captions, full_audio_length

    def kokoro_english(
        self, text: str, output_path: str, voice="af_heart", speed=1
    ) -> tuple[str, List[dict], float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
        if not lang_code:
            raise ValueError(f"Voice '{voice}' not found in LANGUAGE_VOICE_MAP")
        if lang_code != "a":
            raise NotImplementedError(
                f"TTS for language code '{lang_code}' is not implemented."
            )
        start = time.time()

        context_logger = logger.bind(
            voice=voice,
            speed=speed,
            text_length=len(text),
            device=device.type,
        )

        context_logger.debug("Starting TTS generation with kokoro")
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        pipeline = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=device.type)

        generator = pipeline(text, voice=voice, speed=speed)

        captions = []
        audio_data = []
        full_audio_length = 0
        for _, result in enumerate(generator):
            data = result.audio
            audio_length = len(data) / 24000
            audio_data.append(data)
            if result.tokens:
                tokens = result.tokens
                for t in tokens:
                    if t.start_ts is None or t.end_ts is None:
                        if captions:
                            captions[-1]["text"] += t.text
                            captions[-1]["end_ts"] = full_audio_length + audio_length
                        continue
                    try:
                        captions.append(
                            {
                                "text": t.text,
                                "start_ts": full_audio_length + t.start_ts,
                                "end_ts": full_audio_length + t.end_ts,
                            }
                        )
                    except Exception as e:
                        logger.error(
                            "Error processing token: {}, Error: {}",
                            t,
                            e,
                        )
                        raise ValueError(f"Error processing token: {t}, Error: {e}")
            full_audio_length += audio_length

        audio_data = np.concatenate(audio_data)
        audio_data = np.column_stack((audio_data, audio_data))
        sf.write(output_path, audio_data, 24000, format="WAV")
        context_logger.bind(
            execution_time=time.time() - start,
            audio_length=full_audio_length,
            speedup=full_audio_length / (time.time() - start),
            youtube_channel="https://www.youtube.com/"
        ).debug(
            "TTS generation completed with kokoro",
        )
        return captions, full_audio_length

    def kokoro(
        self, text: str, output_path: str, voice="af_heart", speed=1
    ) -> tuple[str, List[dict], float]:
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or whitespace")
        lang_code = LANGUAGE_VOICE_MAP.get(voice, {}).get("lang_code")
        if not lang_code:
            raise ValueError(f"Voice '{voice}' not found in LANGUAGE_VOICE_MAP")
        if lang_code == "a":
            return self.kokoro_english(text, output_path, voice, speed)
        else:
            return self.kokoro_international(text, output_path, voice, lang_code, speed)

    def chatterbox(
        self,
        text: str,
        output_path: str,
        sample_audio_path: str = None,
        exaggeration=0.5,
        cfg_weight=0.5,
        temperature=0.8,
    ):
        start = time.time()
        context_logger = logger.bind(
            text_length=len(text),
            sample_audio_path=sample_audio_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            model="ChatterboxTTS",
            language="en-US",
            device=device.type,
        )
        context_logger.debug("starting TTS generation with Chatterbox")
        model = ChatterboxTTS.from_pretrained(device=device.type)

        if sample_audio_path:
            wav = model.generate(
                text,
                audio_prompt_path=sample_audio_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )
        else:
            wav = model.generate(
                text,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                temperature=temperature,
            )

        if wav.dim() == 2 and wav.shape[0] == 1:
            wav = wav.repeat(2, 1)
        elif wav.dim() == 1:
            wav = wav.unsqueeze(0).repeat(2, 1)

        audio_length = wav.shape[1] / model.sr
        ta.save(output_path, wav, model.sr)
        context_logger.bind(
            execution_time=time.time() - start,
            audio_length=audio_length,
            speedup=audio_length / (time.time() - start),
            youtube_channel="https://www.youtube.com/"
        ).debug(
            "TTS generation with Chatterbox completed",
        )

    def valid_kokoro_voices(self, lang_code = None) -> List[str]:
        """
        Returns a list of valid voices for the given language code.
        If no language code is provided, returns all voices.
        """
        if lang_code:
            return LANGUAGE_VOICE_CONFIG.get(lang_code, [])
        else:
            return [
                voice for voices in LANGUAGE_VOICE_CONFIG.values() for voice in voices
            ]



if __name__ == "__main__":
    import os
    import sys
    import pathlib
    from datetime import datetime

    # make logs visible for the smoke tests
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    def ok(msg: str):
        print(f"[OK] {msg}")

    def run_sentence_split_tests():
        tts = TTS()

        # English
        en_text = (
            "Dr. Smith arrived at 10 a.m. sharp. He spoke briefly about AI. "
            "Then he left; everyone applauded!"
        )
        en_sent = tts.break_text_into_sentences(en_text, lang_code="a")
        assert isinstance(en_sent, list) and len(en_sent) >= 2, "EN: expected multiple sentences"
        # Reconstruct with a space (pattern splits on boundary + spaces)
        en_recon = " ".join(en_sent)
        assert "".join(en_recon.split()) == "".join(en_text.split()), "EN: reconstruction mismatch"
        ok(f"Sentence split (EN): {len(en_sent)} sentences")

        # Chinese
        zh_text = "今天的会议很顺利。大家讨论了模型部署！最后确定了时间表？好的，我们开始吧。"
        zh_sent = tts.break_text_into_sentences(zh_text, lang_code="z")
        assert isinstance(zh_sent, list) and len(zh_sent) >= 2, "ZH: expected multiple sentences"
        # Chinese pattern keeps punctuation; no spaces should be introduced
        zh_recon = "".join(zh_sent)
        assert zh_recon == zh_text, "ZH: reconstruction mismatch"
        ok(f"Sentence split (ZH): {len(zh_sent)} sentences")

    def run_voice_map_tests():
        # basic checks on voice lists
        assert "af_heart" in LANGUAGE_VOICE_CONFIG.get("en-us", []), "Missing EN voice"
        assert "zf_xiaobei" in LANGUAGE_VOICE_CONFIG.get("zh", []), "Missing ZH voice"
        zh_voices = TTS().valid_kokoro_voices("zh")
        assert len(zh_voices) >= 4, "Expected several ZH voices"
        ok(f"Voice map: {len(zh_voices)} Chinese voices available")

    def run_kokoro_smoke():
        if os.environ.get("RUN_KOKORO_SMOKE", "1") not in ("1", "true", "True"):
            print("[SKIP] Kokoro smoke test disabled via RUN_KOKORO_SMOKE")
            return

        tts = TTS()
        out_root = pathlib.Path("./output/test_runs")
        out_root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # EN (af_heart)
        en_text = "Hello, this is a quick Kokoro English test."
        en_wav = out_root / f"kokoro_en_{ts}.wav"
        captions_en, length_en = tts.kokoro(en_text, str(en_wav), voice="af_heart", speed=1.0)
        assert en_wav.exists(), "Kokoro EN: output file not created"
        info_en = ta.info(str(en_wav))
        assert info_en.num_frames > 0 and info_en.sample_rate == 24000, "Kokoro EN: invalid WAV"
        ok(f"Kokoro EN: {info_en.num_channels}ch @ {info_en.sample_rate} Hz, {info_en.num_frames} frames")

        # ZH (zf_xiaobei)
        #zh_text = "你好！这是一次快速的 Kokoro 中文测试。"
        zh_text = ('美国人没来日本的时候，日本没有民主选举，民众吃不饱穿不暖，农家子弟男要当兵女要当妓，农民没有土地，武士阶级高人一等。'
            '整个日本配给制，吃点好的都要被举报。日本节节败退，但新闻报道却一直是大获全胜。'
            #'结果美国人来了以后：1946年10月11日，麦克阿瑟向币原首相口头传达了五大改革指令。'
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
        zh_wav = out_root / f"kokoro_zh_{ts}.wav"
        #captions_zh, length_zh = tts.kokoro(zh_text, str(zh_wav), voice="zf_xiaobei", speed=1.0)
        #captions_zh, length_zh = tts.kokoro(zh_text, str(zh_wav), voice="zm_yunjian", speed=1.0)
        captions_zh, length_zh = tts.kokoro(zh_text, str(zh_wav), voice="zm_yunxi", speed=1.0)
        assert zh_wav.exists(), "Kokoro ZH: output file not created"
        info_zh = ta.info(str(zh_wav))
        assert info_zh.num_frames > 0 and info_zh.sample_rate == 24000, "Kokoro ZH: invalid WAV"
        ok(f"Kokoro ZH: {info_zh.num_channels}ch @ {info_zh.sample_rate} Hz, {info_zh.num_frames} frames")

    def run_chatterbox_smoke():
        if os.environ.get("RUN_CHATTERBOX_SMOKE", "0") not in ("1", "true", "True"):
            print("[SKIP] Chatterbox smoke test disabled (set RUN_CHATTERBOX_SMOKE=1 to enable)")
            return

        try:
            prompt_path = os.environ.get("CHATTERBOX_PROMPT")
            if prompt_path and not os.path.exists(prompt_path):
                logger.warning(f"CHATTERBOX_PROMPT set but not found: {prompt_path}")
                prompt_path = None

            tts = TTS()
            out_root = pathlib.Path("./output/test_runs")
            out_root.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_wav = out_root / f"chatterbox_{ts}.wav"

            sample_text = (
                "This is a brief Chatterbox smoke test. "
                "We are verifying audio generation and saving."
            )
            tts.chatterbox(
                text=sample_text,
                output_path=str(out_wav),
                sample_audio_path=prompt_path,
                exaggeration=0.5,
                cfg_weight=0.5,
                temperature=0.7,
            )
            assert out_wav.exists(), "Chatterbox: output file not created"
            info = ta.info(str(out_wav))
            assert info.num_frames > 0 and info.sample_rate > 0, "Chatterbox: invalid WAV"
            ok(f"Chatterbox: {info.num_channels}ch @ {info.sample_rate} Hz, {info.num_frames} frames")
        except Exception as e:
            # do not crash entire test suite if chatterbox deps/weights aren’t available
            logger.exception("Chatterbox smoke test failed (non-fatal)")

    def check_and_warn_deps(pkgs):
        missing = []
        for pkg in pkgs:
            try:
                importlib.import_module(pkg)
            except ImportError:
                missing.append(pkg)
        if missing:
            print("\n[ERROR] Missing required packages: " + ", ".join(missing))
            print("Run: pip install " + " ".join(missing))
            sys.exit(1)

    # Kokoro 依赖检测
    check_and_warn_deps(["kokoro", "ordered_set", "soundfile", "torchaudio", "numpy", "pypinyin", "cn2an", "jieba"])

    print("Running inline tests...\n")
    try:
        run_sentence_split_tests()
        run_voice_map_tests()
        run_kokoro_smoke()
        run_chatterbox_smoke()
        print("\nAll inline tests finished ✅")
    except Exception:
        print("\nInline test FAILED ❌")
        import traceback as _tb
        _tb.print_exc()
        sys.exit(1)
