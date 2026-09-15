# Phase C: Real AI Provider + FFmpeg Integration

> 状态：Superseded，历史方案。当前 Provider 与 FFmpeg 模块虽已起草，但主执行数据流尚未贯通。后续任务以 `2026-09-15-company-delivery-plan.md` 的 Epic E2、E4、E5 为准。

## Overview

Replace mock handlers with real AI providers (Ollama, OpenAI, ComfyUI) and FFmpeg video processing. Add asset management, configuration system, and provider registry.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Configuration                        │
│  (backend/app/config.py - Pydantic Settings)           │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 Provider Registry                        │
│  (backend/app/providers/__init__.py)                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │   Ollama    │ │   OpenAI    │ │   ComfyUI   │      │
│  │  (Text)     │ │ (Text+Img)  │ │ (Img+Video) │      │
│  └─────────────┘ └─────────────┘ └─────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Service Layer                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │   FFmpeg    │ │   Asset     │ │   Event     │      │
│  │   Service   │ │   Manager   │ │   Bus       │      │
│  └─────────────┘ └─────────────┘ └─────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Real Handlers                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │  TextInput  │ │  Storyboard │ │ TextToImage  │      │
│  │  (LLM)     │ │  (LLM)      │ │ (Provider)   │      │
│  └─────────────┘ └─────────────┘ └─────────────┘      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │ ImageToVideo│ │ VideoConcat │ │   Output    │      │
│  │ (Provider)  │ │ (FFmpeg)    │ │ (Asset)     │      │
│  └─────────────┘ └─────────────┘ └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

## Files to Create

### 1. Configuration System

**`backend/app/config.py`** - Pydantic Settings
```python
- ProviderType enum: ollama | openai | comfyui | mock
- ProviderConfig: api_url, api_key, model, extra_params
- Settings class:
  - DEFAULT_LLM_PROVIDER: ProviderType
  - DEFAULT_IMAGE_PROVIDER: ProviderType
  - DEFAULT_VIDEO_PROVIDER: ProviderType
  - providers: dict[str, ProviderConfig]
  - ASSET_DIR: str (default: "data/assets")
  - FFMPEG_PATH: str (default: "ffmpeg")
  - WORKER_POLL_INTERVAL: float
- Load from .env file + environment variables
```

### 2. Provider Abstraction Layer

**`backend/app/providers/__init__.py`** - Provider registry
```python
- register_provider(name, provider)
- get_provider(name) -> BaseProvider
- list_providers() -> list[str]
```

**`backend/app/providers/base.py`** - Abstract base class
```python
class BaseProvider(ABC):
    name: str
    supported_capabilities: list[str]  # "text" | "image" | "video"

    async def generate_text(self, prompt: str, config: dict) -> str
    async def generate_image(self, prompt: str, config: dict) -> bytes
    async def generate_video(self, image_path: str, prompt: str, config: dict) -> bytes
    async def health_check() -> bool
```

**`backend/app/providers/mock_provider.py`** - Mock for testing
```python
class MockProvider(BaseProvider):
    - Returns fake data with configurable delays
    - Useful for development and testing
```

**`backend/app/providers/ollama_provider.py`** - Local LLM
```python
class OllamaProvider(BaseProvider):
    - Uses httpx.AsyncClient
    - POST /api/generate for text generation
    - POST /api/chat for conversational text
    - Supports model selection from config
    - Config: api_url, model, temperature, max_tokens
```

**`backend/app/providers/openai_provider.py`** - OpenAI API
```python
class OpenAIProvider(BaseProvider):
    - Uses httpx.AsyncClient
    - POST /v1/chat/completions for text (GPT-4)
    - POST /v1/images/generations for images (DALL-E 3)
    - Config: api_key, model, image_model, size, quality
```

**`backend/app/providers/comfyui_provider.py`** - ComfyUI API
```python
class ComfyUIProvider(BaseProvider):
    - Uses httpx.AsyncClient
    - POST /prompt for workflow execution
    - WebSocket /ws for progress tracking
    - GET /view for image retrieval
    - Config: api_url, workflow_id, checkpoint, sampler
    - Supports img2vid workflows
```

### 3. Service Layer

**`backend/app/services/ffmpeg.py`** - FFmpeg wrapper
```python
class FFmpegService:
    async def concatenate_videos(
        self, video_paths: list[str], output_path: str,
        callback: Callable | None = None
    ) -> str
    - Uses asyncio.create_subprocess_exec
    - Progress callback via stderr parsing
    - Returns output path

    async def image_to_video(
        self, image_path: str, output_path: str,
        duration: float = 4.0, fps: int = 24,
        width: int = 1920, height: int = 1080
    ) -> str
    - Ken Burns effect (zoom/pan)
    - Returns output path

    async def get_video_info(self, video_path: str) -> dict
    - Returns duration, resolution, codec, etc.
```

**`backend/app/services/asset_manager.py`** - File storage
```python
class AssetManager:
    def __init__(self, asset_dir: str = "data/assets")
    
    def save_asset(self, data: bytes, filename: str, category: str = "") -> str
    - Saves to {asset_dir}/{category}/{filename}
    - Returns relative path

    def get_asset_path(self, relative_path: str) -> str
    - Returns absolute path

    def get_asset_url(self, relative_path: str) -> str
    - Returns URL for serving (e.g., /assets/...)

    def delete_asset(self, relative_path: str) -> bool
    - Removes file

    def cleanup_old_assets(self, max_age_days: int = 7) -> int
    - Deletes files older than max_age_days
    - Returns count of deleted files

    def list_assets(self, category: str = "") -> list[dict]
    - Lists all assets with metadata
```

### 4. Real Handlers

**`backend/app/handlers/real_handlers.py`** - Real implementations
```python
class RealTextInputHandler:
    - Uses LLM provider to process prompt
    - Returns structured text output

class RealStoryboardHandler:
    - Uses LLM provider to generate structured storyboard
    - Parses JSON response into scene list
    - Validates scene structure

class RealTextToImageHandler:
    - Uses image provider to generate images
    - Saves to asset manager
    - Returns asset path

class RealImageToVideoHandler:
    - Uses video provider or FFmpeg
    - Saves to asset manager
    - Returns asset path

class RealVideoConcatHandler:
    - Uses FFmpeg service to concatenate videos
    - Saves to asset manager
    - Returns final video path

class RealOutputHandler:
    - Finalizes assets
    - Generates download URLs
    - Returns completion info
```

### 5. Handler Registry

**`backend/app/handlers/__init__.py`** - Updated
```python
- register_handlers(use_mock: bool = True)
- get_handler(kind: str) -> NodeHandler
- Switch between mock and real handlers based on config
```

### 6. Configuration API

**`backend/app/api/config.py`** - REST endpoints
```python
GET  /api/config/providers - List available providers
GET  /api/config/settings  - Get current settings (no secrets)
PUT  /api/config/settings  - Update settings
POST /api/config/test-provider - Test provider connection
```

---

## Implementation Order

### Phase C1: Core Infrastructure (Priority 1)
1. `backend/app/config.py` - Configuration system
2. `backend/app/providers/__init__.py` - Provider registry
3. `backend/app/providers/base.py` - Abstract base class
4. `backend/app/providers/mock_provider.py` - Mock provider
5. `backend/app/services/asset_manager.py` - File storage
6. `backend/app/services/ffmpeg.py` - FFmpeg wrapper

### Phase C2: Provider Implementations (Priority 2)
7. `backend/app/providers/ollama_provider.py` - Ollama LLM
8. `backend/app/providers/openai_provider.py` - OpenAI API
9. `backend/app/providers/comfyui_provider.py` - ComfyUI API

### Phase C3: Real Handlers (Priority 3)
10. `backend/app/handlers/real_handlers.py` - Real handler implementations
11. `backend/app/handlers/__init__.py` - Updated handler registry

### Phase C4: Integration (Priority 4)
12. `backend/app/api/config.py` - Configuration API
13. Update `backend/app/main.py` - Wire everything together
14. Update handlers registration

### Phase C5: Testing (Priority 5)
15. `backend/tests/providers/test_mock_provider.py`
16. `backend/tests/providers/test_ollama_provider.py`
17. `backend/tests/providers/test_openai_provider.py`
18. `backend/tests/services/test_asset_manager.py`
19. `backend/tests/services/test_ffmpeg.py`
20. `backend/tests/handlers/test_real_handlers.py`
21. `backend/tests/api/test_config.py`

---

## Key Design Decisions

### 1. Provider Selection
- Each node type can use a different provider
- Default providers can be set globally
- Per-node override via config

### 2. Asset Storage
- Flat directory structure: `data/assets/{category}/{uuid}.{ext}`
- Categories: `images`, `videos`, `final`
- No database for assets (filesystem only)
- Cleanup based on file age

### 3. FFmpeg Integration
- Use asyncio subprocess for non-blocking
- Parse stderr for progress updates
- Support common formats: mp4, webm, mov

### 4. Error Handling
- Provider failures → task fails (with retry option)
- FFmpeg failures → task fails
- Asset save failures → task fails
- All errors logged and emitted via event bus

### 5. Configuration
- Pydantic Settings for validation
- Environment variables for secrets
- .env file for local development
- API for runtime changes (non-sensitive)

---

## Dependencies to Add

**backend/requirements.txt** additions:
```
httpx>=0.27.0          # Async HTTP client for providers
python-dotenv>=1.0.0   # Environment variable loading
pydantic-settings>=2.0 # Settings management
```

**Note:** No ffmpeg-python needed - using subprocess directly for more control.

---

## Testing Strategy

### Unit Tests
- Mock provider with mock HTTP responses
- Asset manager with temp directories
- FFmpeg service with mock subprocess
- Configuration with test values

### Integration Tests
- End-to-end with mock providers
- Real provider connections (optional, requires services)
- FFmpeg with real video files (small test files)

### Test Markers
- `@pytest.mark.mock` - Uses mock providers only
- `@pytest.mark.integration` - Requires real services
- `@pytest.mark.slow` - Long-running tests

---

## Migration Notes

### Existing Code Updates
1. `backend/app/handlers/base.py` → Keep as fallback
2. `backend/app/handlers/__init__.py` → Add provider-aware registry
3. `backend/app/engine/worker.py` → No changes needed
4. `backend/app/main.py` → Add provider initialization

### Backward Compatibility
- Mock handlers remain available
- Configuration defaults to mock providers
- No breaking changes to existing API

---

## Success Criteria

1. ✅ Configuration system loads from .env
2. ✅ Providers register and can be retrieved
3. ✅ Mock provider works for all node types
4. ✅ Real handlers use providers correctly
5. ✅ FFmpeg concatenates videos
6. ✅ Asset manager stores and retrieves files
7. ✅ All existing tests still pass
8. ✅ New tests cover Phase C code
9. ✅ Configuration API works
10. ✅ No regressions in Phase A/B functionality
