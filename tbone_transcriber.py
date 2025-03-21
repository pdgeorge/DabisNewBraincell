import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
device = torch.device("cuda") if torch.cuda.is_available() else "cpu"

stt_checkpoint = "distil-whisper/distil-large-v3"
stt_model = AutoModelForSpeechSeq2Seq.from_pretrained(stt_checkpoint, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True)
stt_model.to(device)
stt_processor = AutoProcessor.from_pretrained(stt_checkpoint)

stt_pipeline = pipeline(
    "automatic-speech-recognition",
    model=stt_model,
    tokenizer=stt_processor.tokenizer,
    feature_extractor=stt_processor.feature_extractor,
    max_new_tokens=128,
    torch_dtype=torch_dtype,
    device=device
)

def transcriber(files):
    transcribed_array = []
    transcribed = {}
    for file in files:
        data = stt_pipeline(file, generate_kwargs={"max_new_tokens": 256}, return_timestamps=False)
        transcribed["msg_user"] = file[:-4]
        transcribed["msg_msg"] = data["text"]
        # print("===============================")
        # print(f"tbone_transcriber: {transcribed["data"]=}")
        # print(f"tbone_transcriber: {transcribed=}")
        transcribed_array.append(transcribed)
        transcribed = {}
    return transcribed_array

def tester():
    files = [
        "WavTest1.wav",
        "WavTest2.wav"
    ]
    transcribed = transcriber(files)
    print(f"{transcribed=}")

if __name__ == "__main__":
    tester()