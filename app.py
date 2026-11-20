import streamlit as st
import os
import time
import glob
import subprocess
import asyncio
import yt_dlp
import edge_tts
from google import genai

st.set_page_config(page_title="AI Transcript & Myanmar Narrator Pro", layout="wide")

# ==================== CLEANUP & HELPERS ====================

def cleanup_files():
    for pattern in ["source_media*", "narrator_output_*.mp3"]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except Exception:
                pass

def compress_for_ai(input_path, out_path="source_media_fast.mp4"):
    """AI ဆီ ပို့ရာတွင် Connection မပြတ်ဘဲ အမြန်ဆုံးဖြစ်စေရန် 360p + 1fps သို့ ချုံ့ပေးခြင်း"""
    ext = os.path.splitext(input_path)[1].lower()
    if ext in [".mp3", ".m4a", ".wav"]:
        return input_path

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=-2:360,fps=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32",
        "-c:a", "aac", "-b:a", "64k",
        out_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        try:
            os.remove(input_path)
        except Exception:
            pass
        return out_path
    return input_path

def download_media_from_link(url, out_base="source_media_raw"):
    """Link မှ ဗီဒီယိုဆွဲထုတ်ပြီး AI ဖတ်ရန် အမြန်ဆုံး ချုံ့ပေးခြင်း"""
    ydl_opts = {
        'outtmpl': f'{out_base}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    files = glob.glob(f"{out_base}.*")
    if not files or os.path.getsize(files[0]) < 1000:
        raise Exception("Link မှ ဖိုင်ဆွဲထုတ်၍ မရပါ။ အောက်တွင် ဖိုင်တိုက်ရိုက် Upload တင်၍ စမ်းကြည့်ပါ။")
    
    return compress_for_ai(files[0])

def analyze_and_translate_with_gemini(api_key, media_path, script_style):
    """Gemini AI ဖြင့် အသံနှင့် ဗီဒီယိုပုံရိပ်များကို နားလည်ပြီး Transcript နှင့် မြန်မာ Recap Script ထုတ်ပေးခြင်း"""
    client = genai.Client(api_key=api_key)
    uploaded_file = client.files.upload(file=media_path)

    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)

    style_instruction = {
        "ပုံမှန် ဇာတ်လမ်းပြောပြပုံစံ (Natural Storyteller)": "သဘာဝကျကျ ဇာတ်လမ်းတစ်ပုဒ်ကို ကြည့်ရှုသူ စိတ်ဝင်စားအောင် ပြန်ပြောပြနေတဲ့ Narrator စတိုင်နဲ့ ရေးပေးပါ။",
        "TikTok/Shorts Viral စတိုင် (သွက်လက်တက်ကြွ)": "ပထမ ၃ စက္ကန့်မှာတင် ကြည့်ရှုသူ ဆွဲဆောင်နိုင်မယ့် Hook စကားလုံးနဲ့ စပြီး ခပ်သွက်သွက် စိတ်လှုပ်ရှားစရာကောင်းအောင် ပြန်ပြောပြတဲ့ စတိုင်နဲ့ ရေးပေးပါ။",
        "သည်းထိတ်ရင်ဖို / လျှို့ဝှက်ဆန်းကြယ် (Horror/Mystery)": "ကြောက်စရာကောင်းပြီး လျှို့ဝှက်ဆန်းကြယ်တဲ့ အငွေ့အသက်ပါအောင် ဆွဲဆောင်မှုရှိရှိ ပြန်ပြောပြတဲ့ စတိုင်နဲ့ ရေးပေးပါ။",
        "တိုက်ရိုက် ဘာသာပြန် (Direct Translation)": "မူရင်းစကားပြော အဓိပ္ပာယ်အတိုင်း အတိအကျ မြန်မာလို ပြန်ဆိုပေးပါ။"
    }.get(script_style, "")

    prompt = f"""
    သင်သည် ကျွမ်းကျင်သော Video Transcriber နှင့် Myanmar Movie Recap Scriptwriter တစ်ဦးဖြစ်သည်။
    ပူးတွဲပါ ဗီဒီယို/အသံဖိုင်ကို သေချာစစ်ဆေးပြီး အောက်ပါ အပိုင်း (၂) ပိုင်းကို တိကျစွာ ထုတ်ပေးပါ-

    1. မူရင်းဘာသာစကားဖြင့် စာသားအပြည့်အစုံ (Original Transcript):
       - ဖိုင်ထဲတွင် စကားပြောသံ ပါဝင်ပါက ပြောထားသည့် မူရင်းဘာသာစကားအတိုင်း စာသားအပြည့်အစုံ ရေးပေးပါ။
       - စကားပြောသံ လုံးဝမပါဘဲ ဗီဒီယိုမြင်ကွင်းနှင့် တေးဂီတသက်သက် ဖြစ်နေပါက ဗီဒီယိုထဲတွင် ဖြစ်ပျက်နေသည့် ဇာတ်ကွက်အကျဉ်းကို အင်္ဂလိပ်ဘာသာဖြင့် ရေးပေးပါ။

    2. မြန်မာဘာသာဖြင့် အသံသွင်းဖတ်ပြရန် အသင့်ဖြစ်မည့် စာသား (Myanmar Script):
       - စကားပြောသံပါပါက ထိုစကားပြောကို အခြေခံ၍လည်းကောင်း၊ စကားပြောမပါပါက ဗီဒီယိုထဲက ဇာတ်ကွက်များကို ကြည့်၍လည်းကောင်း မြန်မာလို ဇာတ်လမ်းပြန်ပြောပြပေးပါ။
       - စတိုင်လမ်းညွှန်ချက်: {style_instruction}
       - အရေးကြီးချက်: စာသားများကို Text-to-Speech (TTS) ဖြင့် ပြန်ဖတ်မည်ဖြစ်သောကြောင့် အကွင်းအကွက်များ (ဥပမာ- [ရယ်သံ]၊ (သက်ပြင်းချလျက်))၊ ဇယားများ လုံးဝ မထည့်ပါနှင့်။ ဖတ်ပြရမည့် မြန်မာစာသား သီးသန့်ကိုသာ ပုဒ်ဖြတ်ပုဒ်ရပ် (၊ ။) မှန်ကန်စွာဖြင့် ရေးသားပေးပါ။

    အဖြေကို အောက်ပါ Tag များကြားတွင် တိတိကျကျ ထည့်ပေးပါ-
    [ORIG_START]
    (မူရင်းစာသား ဤနေရာတွင်ထည့်ပါ)
    [ORIG_END]

    [MM_START]
    (မြန်မာစာသား ဤနေရာတွင်ထည့်ပါ)
    [MM_END]
    """

    response = None
last_err = None
for m_name in ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-2.0-flash"]:
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=m_name,
                contents=[uploaded_file, prompt]
            )
            break
        except Exception as e:
            last_err = e
            time.sleep(3)
    if response is not None:
        break
if response is None:
    raise last_err

    try:
        client.files.delete(name=uploaded_file.name)
    except Exception:
        pass

    text = (response.text or "").strip()
    orig_text = ""
    mm_text = ""

    if "[ORIG_START]" in text and "[ORIG_END]" in text:
        orig_text = text.split("[ORIG_START]")[1].split("[ORIG_END]")[0].strip()

    if "[MM_START]" in text and "[MM_END]" in text:
        mm_text = text.split("[MM_START]")[1].split("[MM_END]")[0].strip()

    if not orig_text and not mm_text:
        mm_text = text

    return orig_text, mm_text

async def _generate_tts_async(text, voice, rate, pitch, out_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)

def generate_narrator_audio(text, character_choice):
    ts = int(time.time())
    out_mp3 = f"narrator_output_{ts}.mp3"

    characters = {
        "👨 ကိုကျော် (ယောက်ျားလေး - တည်ငြိမ်လေးနက်သော Narrator အသံ)": {
            "voice": "my-MM-ThihaNeural",
            "rate": "+0%",
            "pitch": "+0Hz"
        },
        "👩 မလှလှ (မိန်းကလေး - ချိုသာသွက်လက်သော Narrator အသံ)": {
            "voice": "my-MM-NilarNeural",
            "rate": "+5%",
            "pitch": "+2Hz"
        },
        "⚡ သွက်လက်တက်ကြွ (TikTok/Shorts Viral စတိုင် - မြန်ဆန်သွက်လက်)": {
            "voice": "my-MM-ThihaNeural",
            "rate": "+18%",
            "pitch": "+4Hz"
        },
        "😱 သည်းထိတ်ရင်ဖို / လျှို့ဝှက်ဆန်းကြယ် (Horror/Mystery စတိုင် - နိမ့်ပြီးလေးနက်)": {
            "voice": "my-MM-ThihaNeural",
            "rate": "-8%",
            "pitch": "-8Hz"
        }
    }

    cfg = characters[character_choice]
    asyncio.run(_generate_tts_async(text, cfg["voice"], cfg["rate"], cfg["pitch"], out_mp3))
    return out_mp3

# ==================== STREAMLIT UI ====================

st.title("🎙️ AI Transcript & Myanmar Narrator Studio")
st.caption("Video Link / File Upload ➔ Original Transcript ➔ မြန်မာပြန် Recap Script ➔ Character ၄ မျိုး Narrator အသံဖိုင်")

with st.sidebar:
    st.header("🔑 AI စနစ် ချိတ်ဆက်မှု")
    api_key = st.text_input("Google AI Studio API Key ထည့်ပါ:", type="password", placeholder="AIzaSy...")
    st.caption("အခမဲ့ Key ကို aistudio.google.com တွင် ရယူနိုင်ပါသည်။")
    st.markdown("---")
    if st.button("🗑️ ဖိုင်အဟောင်းများ ရှင်းလင်းမည်", use_container_width=True):
        cleanup_files()
        st.session_state.clear()
        st.success("✅ ရှင်းလင်းပြီးပါပြီ!")
        st.rerun()

if "orig_transcript" not in st.session_state:
    st.session_state.orig_transcript = ""
if "mm_script" not in st.session_state:
    st.session_state.mm_script = ""
if "final_audio" not in st.session_state:
    st.session_state.final_audio = None
if "show_editor" not in st.session_state:
    st.session_state.show_editor = False

# ==================== STEP 1: INPUT SOURCE ====================
st.header("၁။ Video Link (သို့မဟုတ်) ဖိုင်ထည့်သွင်းပြီး မြန်မာပြန် ထုတ်ယူခြင်း")

input_mode = st.radio("📥 ထည့်သွင်းမည့် နည်းလမ်း ရွေးချယ်ပါ:", ["🔗 Video Link ထည့်မည်", "📁 ဖုန်း/စက်ထဲမှ ဗီဒီယို သို့မဟုတ် အသံဖိုင် တင်မည်"], horizontal=True)

col1, col2 = st.columns([2, 1])
with col1:
    if input_mode == "🔗 Video Link ထည့်မည်":
        video_url = st.text_input("YouTube / TikTok / RedNote Link ထည့်ပါ:", placeholder="https://...")
        uploaded_local_file = None
    else:
        uploaded_local_file = st.file_uploader("ဗီဒီယို (MP4/MOV) သို့မဟုတ် အသံဖိုင် (MP3/M4A) ရွေးပါ:", type=["mp4", "mov", "mkv", "mp3", "m4a", "wav"])
        video_url = ""

with col2:
    script_style = st.selectbox(
        "📝 မြန်မာပြန် ရေးသားမည့် စတိုင်:",
        [
            "ပုံမှန် ဇာတ်လမ်းပြောပြပုံစံ (Natural Storyteller)",
            "TikTok/Shorts Viral စတိုင် (သွက်လက်တက်ကြွ)",
            "သည်းထိတ်ရင်ဖို / လျှို့ဝှက်ဆန်းကြယ် (Horror/Mystery)",
            "တိုက်ရိုက် ဘာသာပြန် (Direct Translation)"
        ]
    )

if st.button("✨ Transcript ထုတ်ပြီး မြန်မာလို ပြန်ပေးမည်", use_container_width=True):
    if not api_key.strip():
        st.warning("⚠️ ဘယ်ဘက်ဘေး (သို့မဟုတ် အပေါ်ဘယ်ဘက် >> ခလုတ်) ထဲတွင် Google AI Studio API Key အရင်ထည့်ပေးပါခင်ဗျာ။")
    elif input_mode == "🔗 Video Link ထည့်မည်" and not video_url.strip():
        st.warning("⚠️ ကျေးဇူးပြု၍ Video Link အရင်ထည့်ပေးပါခင်ဗျာ။")
    elif input_mode != "🔗 Video Link ထည့်မည်" and uploaded_local_file is None:
        st.warning("⚠️ ကျေးဇူးပြု၍ ဗီဒီယို သို့မဟုတ် အသံဖိုင် အရင်ရွေးချယ်ပေးပါခင်ဗျာ။")
    else:
        cleanup_files()
        st.session_state.final_audio = None
        media_path = ""

        if input_mode == "🔗 Video Link ထည့်မည်":
            with st.spinner("⏳ အဆင့် (၁/၂): Link မှ ဗီဒီယိုဆွဲထုတ်ပြီး အမြန်ဆုံးဖြစ်အောင် ချုံ့ပေးနေပါသည်..."):
                try:
                    media_path = download_media_from_link(video_url.strip())
                except Exception as e:
                    st.error(f"❌ {e}")
                    st.stop()
        else:
            with st.spinner("⏳ အဆင့် (၁/၂): တင်ထားသော ဖိုင်ကို AI အတွက် ပြင်ဆင်ပေးနေပါသည်..."):
                ext = os.path.splitext(uploaded_local_file.name)[1]
                raw_local = f"source_media_raw{ext}"
                with open(raw_local, "wb") as f:
                    f.write(uploaded_local_file.read())
                media_path = compress_for_ai(raw_local)

        with st.spinner("🧠 အဆင့် (၂/၂): AI ဖြင့် စာသား/ဇာတ်ကွက်ဖတ်ပြီး မြန်မာပြန် Script ရေးသားနေပါသည်..."):
            try:
                orig, mm = analyze_and_translate_with_gemini(api_key.strip(), media_path, script_style)
                st.session_state.orig_transcript = orig
                st.session_state.mm_script = mm
                st.session_state.show_editor = True
                st.success("✅ Transcript နှင့် မြန်မာပြန် Script အောင်မြင်စွာ ထုတ်ပြီးပါပြီ!")
            except Exception as e:
                st.error(f"❌ AI စာသားပြန်ဆိုရာတွင် Error ဖြစ်ပွားပါသည်: {e}")

# Transcript & Myanmar Script ပြသခြင်း
if st.session_state.show_editor:
    st.markdown("---")
    c_orig, c_mm = st.columns(2)
    with c_orig:
        st.subheader("📄 မူရင်း Transcript / ဇာတ်ကွက်အကျဉ်း")
        st.text_area("မူရင်းစာသား:", value=st.session_state.orig_transcript, height=250, key="orig_box")
    with c_mm:
        st.subheader("🇲🇲 မြန်မာပြန် Script (လိုအပ်ပါက ပြင်ဆင်နိုင်သည်)")
        edited_mm_script = st.text_area("အသံသွင်းမည့် မြန်မာစာသား:", value=st.session_state.mm_script, height=250, key="mm_box")

    # ==================== STEP 2: NARRATOR VOICE GENERATION ====================
    st.markdown("---")
    st.header("၂။ Narrator Character ရွေးချယ်ပြီး အသံသွင်းခြင်း")

    selected_char = st.radio(
        "🎙️ အသံသွင်းမည့် Narrator Character (၄) မျိုးထဲမှ တစ်မျိုး ရွေးချယ်ပါ:",
        [
            "👨 ကိုကျော် (ယောက်ျားလေး - တည်ငြိမ်လေးနက်သော Narrator အသံ)",
            "👩 မလှလှ (မိန်းကလေး - ချိုသာသွက်လက်သော Narrator အသံ)",
            "⚡ သွက်လက်တက်ကြွ (TikTok/Shorts Viral စတိုင် - မြန်ဆန်သွက်လက်)",
            "😱 သည်းထိတ်ရင်ဖို / လျှို့ဝှက်ဆန်းကြယ် (Horror/Mystery စတိုင် - နိမ့်ပြီးလေးနက်)"
        ]
    )

    if st.button("🔊 ရွေးချယ်ထားသော Character ဖြင့် အသံသွင်းမည်", use_container_width=True):
        if not edited_mm_script.strip():
            st.warning("⚠️ အသံသွင်းရန် မြန်မာစာသား မရှိသေးပါ။")
        else:
            with st.spinner("🎙️ Narrator အသံသွင်းပေးနေပါသည် (စက္ကန့်အနည်းငယ်သာ ကြာပါမည်)..."):
                try:
                    mp3_path = generate_narrator_audio(edited_mm_script.strip(), selected_char)
                    st.session_state.final_audio = mp3_path
                    st.success("🎉 အသံသွင်းခြင်း အောင်မြင်ပါပြီ!")
                except Exception as e:
                    st.error(f"❌ အသံသွင်းရာတွင် Error ဖြစ်ပွားပါသည်: {e}")

# Final Audio Download ပြသခြင်း
if st.session_state.final_audio and os.path.exists(st.session_state.final_audio):
    st.markdown("---")
    st.subheader("🎧 ထွက်ရှိလာသော Narrator အသံဖိုင်")
    st.audio(st.session_state.final_audio)
    with open(st.session_state.final_audio, "rb") as af:
        st.download_button(
            "💾 အသံဖိုင် (MP3) ဒေါင်းလုဒ်ရယူရန်",
            af,
            file_name="Myanmar_Narrator_Voice.mp3",
            mime="audio/mp3",
            use_container_width=True
        )