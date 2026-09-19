from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "audio-agent"
    webhook_secret: str = "change-me"

    # Comma-separated list of origins allowed to call this service from a
    # browser (CORS). Defaults to the local citizen-portal dev server; a
    # real deployment overrides this to the real frontend domain instead.
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    asr_confidence_threshold: float = 0.60
    temp_audio_dir: str = "./tmp_audio"
    local_audio_dir: str = "./local_audio"

    ffmpeg_executable: str = "ffmpeg"

    # Bhashini pipeline (translation + TTS). Auth is a single Authorization
    # header using bhashini_ulca_api_key - found empirically, this deployment
    # rejects the generic userID+ulcaApiKey header pair Bhashini's public
    # sample code uses. bhashini_user_id is kept only for reference (the
    # "Udyat Key" as issued) - it is not sent in any request.
    bhashini_user_id: str = ""
    bhashini_ulca_api_key: str = ""
    bhashini_pipeline_id: str = "64392f96daac500b55c543cd"
    bhashini_config_url: str = (
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    )

    # Self-hosted Santali ASR/translation/TTS (see app/services/santali_local.py
    # and santali-voice-service/ at the repo root) - Bhashini has no Santali
    # model at all, so this one language is served by a small containerized
    # service instead, reached over plain HTTP like any other internal call.
    santali_voice_service_url: str = "http://localhost:8100"

    # Object storage (MinIO / any S3-compatible endpoint) - uploaded citizen
    # audio is persisted here (bucket "sahyog-audio") in addition to the
    # local_audio_dir temp copy this service already keeps around for
    # ffmpeg/faster-whisper to read. See app/media/object_storage.py and
    # "3.Triage and route/schema_003_media_objects.sql". DATABASE_URL is
    # optional here - this service has no other reason to talk to Postgres;
    # leave it blank to still get durable object storage without a
    # media_objects row (the pipeline falls back to threading the object
    # storage URL through raw_evidence instead - see README).
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_base_url: str = "http://localhost:9000"
    s3_access_key: str = "sahyog"
    s3_secret_key: str = "sahyog-dev-secret"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False
    s3_bucket_audio: str = "sahyog-audio"
    s3_bucket_images: str = "sahyog-images"
    database_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
