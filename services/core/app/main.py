from fastapi import FastAPI

from app.usecases.lifecycle import go_to_sleep, wake_up

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/lifecycle/wake")
def wake() -> dict:
    return wake_up().model_dump()


@app.post("/lifecycle/sleep")
def sleep() -> dict:
    return go_to_sleep().model_dump()
