import uvicorn

from app import create_app
from config import settings
from core.logging import configure_logging

configure_logging()
app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)

