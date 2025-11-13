from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = Field(..., alias="MONGO_URI")
    model_name: str = Field(..., alias="MODEL_NAME")
    model_api_key: str = Field(..., alias="MODEL_API_KEY")

    # Gemini-compatible OpenAI endpoint
    openai_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/openai/v1",
        alias="OPENAI_BASE_URL",
    )

    # Cloudinary
    cloudinary_url: str | None = Field(default=None, alias="CLOUDINARY_URL")
    cloudinary_api_key: str | None = Field(default=None, alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str | None = Field(default=None, alias="CLOUDINARY_API_SECRET")
    cloudinary_cloud_name: str | None = Field(default=None, alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_base_folder: str = Field(default="airr-poc", alias="CLOUDINARY_BASE_FOLDER")

    # LibreOffice
    libreoffice_path: str | None = Field(default=None, alias="LIBREOFFICE_PATH")

    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        populate_by_name = True


settings = Settings()
