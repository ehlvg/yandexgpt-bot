import asyncio
from .config import YC_FOLDER_ID, YC_API_KEY, YANDEXGPT_MODEL, GPT_TEMPERATURE
from yandex_cloud_ml_sdk import YCloudML

SDK = YCloudML(folder_id=YC_FOLDER_ID, auth=YC_API_KEY)

async def generate_reply(history):
    loop = asyncio.get_event_loop()
    def _call():
        result = (
            SDK.models.completions(YANDEXGPT_MODEL)
            .configure(temperature=GPT_TEMPERATURE)
            .run(history)
        )
        return result[0].text if result else "(empty response)"
    return await loop.run_in_executor(None, _call)

async def generate_image(description: str) -> bytes:
    loop = asyncio.get_event_loop()
    def _generate():
        model = SDK.models.image_generation("yandex-art")
        model = model.configure(width_ratio=1, height_ratio=1)
        operation = model.run_deferred(description)
        result = operation.wait()
        return result.image_bytes
    return await loop.run_in_executor(None, _generate) 