from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = Field(..., alias="MONGO_URI")
    model_name: str = Field(..., alias="MODEL_NAME")
    model_api_key: str = Field(..., alias="MODEL_API_KEY")
    model_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    model_extra_headers: dict[str, str] | None = Field(default=None, alias="MODEL_EXTRA_HEADERS")

    # OpenAI base URL by default; override via OPENAI_BASE_URL for alternatives (e.g., Gemini-compatible proxy)
    # Cloudinary
    cloudinary_url: str | None = Field(default=None, alias="CLOUDINARY_URL")
    cloudinary_api_key: str | None = Field(default=None, alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str | None = Field(default=None, alias="CLOUDINARY_API_SECRET")
    cloudinary_cloud_name: str | None = Field(default=None, alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_base_folder: str = Field(default="airr-poc", alias="CLOUDINARY_BASE_FOLDER")

    # LibreOffice
    libreoffice_path: str | None = Field(default=None, alias="LIBREOFFICE_PATH")

    # Microsoft Graph / Office 365
    graph_tenant_id: str = Field(..., alias="GRAPH_TENANT_ID")
    graph_client_id: str = Field(..., alias="GRAPH_CLIENT_ID")
    graph_client_secret: str = Field(..., alias="GRAPH_CLIENT_SECRET")
    graph_client_secret_id: str | None = Field(default=None, alias="GRAPH_CLIENT_SECRET_ID")
    graph_drive_id: str = Field(..., alias="GRAPH_DRIVE_ID")
    graph_base_url: str = Field(default="https://graph.microsoft.com/v1.0", alias="GRAPH_BASE_URL")

    # Conversion backend selector
    converter_backend: str = Field(default="libreoffice", alias="CONVERTER_BACKEND")

    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        populate_by_name = True


settings = Settings()
