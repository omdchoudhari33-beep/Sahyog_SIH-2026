from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "audio-agent"
    webhook_secret: str = "change-me"
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
