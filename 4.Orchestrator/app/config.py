from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "sahyog-orchestrator"

    agent1_base_url: str = "http://127.0.0.1:8001"
    agent2_base_url: str = "http://127.0.0.1:8002"
    agent3_base_url: str = "http://127.0.0.1:8003"
    agent5_base_url: str = "http://127.0.0.1:8004"
    agent6_base_url: str = "http://127.0.0.1:8006"
    agent7_base_url: str = "http://127.0.0.1:8007"
    agent8_base_url: str = "http://127.0.0.1:8008"
    agent9_base_url: str = "http://127.0.0.1:8009"

    # Must match Agent 1's WEBHOOK_SECRET - used to sign requests to it.
    agent1_webhook_secret: str = "dev-secret-123"

    # Same repo-wide internal-services secret already configured for
    # 3.Triage and route <-> 5.ULB Dispatch <-> 6/7/8/9 - the Admin Portal
    # acts as a trusted internal caller on the human admin's behalf once
    # they've passed admin_portal_password below.
    internal_service_token: str = ""

    # Required, no default. Protects /admin/* in this service - a separate
    # trust boundary from internal_service_token, same separation every
    # other service in this repo uses between HTTPBasic admin actions and
    # X-Internal-Token service-to-service calls.
    admin_portal_password: str = ""

    # Agent 2's vision call alone can take minutes on a cold-loaded local
    # model (Ollama unloads idle models after ~5 min by default).
    request_timeout_seconds: float = 240.0

    # S2 doesn't estimate how many people are affected yet; use a neutral
    # default until that signal exists.
    default_population_impact: float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
