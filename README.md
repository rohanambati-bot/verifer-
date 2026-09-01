# VisionClick Agent

**VisionClick Agent** is an autonomous browser + computer-vision agent designed to observe video annotation tasks, perceive temporal action patterns in videos, reason over natural language statements, determine TRUE/FALSE correctness with verifiable evidence, select the corresponding 👍 or 👎 controls, verify every selection, and submit tasks on a local test platform.

---

## Architecture Overview

```
VisionClick Pipeline:
OBSERVE ➔ UNDERSTAND ➔ EXTRACT ➔ TEMPORAL ANALYSIS ➔ REASON ➔ COLLECT EVIDENCE ➔ CLASSIFY ➔ VERIFY ➔ ACT ➔ VERIFY ACTION ➔ SUBMIT ➔ RECORD RESULT ➔ NEXT TASK
```

```
visionclick-agent/
├── app/
│   ├── main.py                     # Agent orchestrator & continuous worker loop
│   ├── config.py                   # Pydantic configuration loader (YAML + Env)
│   ├── browser/
│   │   ├── controller.py           # Async Playwright Chromium manager
│   │   ├── page_detector.py        # Semantic DOM selector detector (no hard-coded coords)
│   │   ├── task_parser.py          # Structured task extraction from live DOM
│   │   └── action_executor.py      # Resilient clicker, DOM state verifier, submitter
│   ├── video/
│   │   ├── extractor.py            # Video metadata & frame extraction
│   │   ├── sampler.py              # Adaptive frame sampler & perceptual deduplication
│   │   ├── scene_detector.py       # Motion & scene transition segmenter
│   │   └── temporal.py             # Multi-frame temporal action reasoning pipeline
│   ├── vision/
│   │   ├── base.py                 # Abstract VisionProvider interface & Pydantic models
│   │   ├── local.py                # Local model integration stub & documentation
│   │   ├── mock.py                 # Fully functional ground-truth mock provider
│   │   ├── objects.py              # Object ontology & spatial relationships
│   │   └── hands.py                # Hand detection & hand-object interaction models
│   ├── reasoning/
│   │   ├── statement_parser.py     # NL statement predicate parser (extensible actions)
│   │   ├── action_reasoner.py      # Maps statements to required temporal evidence
│   │   ├── evidence.py             # Evidence collection, structuring & scoring engine
│   │   └── confidence.py           # Threshold routing & two-pass confidence manager
│   ├── decision/
│   │   ├── classifier.py           # TRUE/FALSE decision maker with full audit trail
│   │   └── verifier.py             # Second-pass verifier for low-confidence decisions
│   ├── database/
│   │   ├── models.py               # Pydantic models for 9 SQLite tables
│   │   ├── database.py             # aiosqlite async database connection & schema
│   │   └── repository.py           # CRUD repository & dashboard aggregations
│   ├── dashboard/
│   │   ├── server.py               # FastAPI backend with REST & live WebSockets
│   │   └── static/                 # Glassmorphism dark-mode UI (HTML/CSS/JS)
│   └── utils/
│       ├── logging.py              # Dual JSON & colorized human console logger
│       ├── timing.py               # Latency profiling & throughput metrics
│       └── retry.py                # Exponential backoff error recovery
├── demo/
│   ├── server/                     # Demo video annotation website (FastAPI)
│   ├── tasks/                      # Synthetic demo tasks definitions
│   ├── videos/                     # Synthetic test video generator & MP4 files
│   └── ground_truth/               # Benchmark ground truth
├── tests/
│   ├── unit/                       # Unit test suite
│   ├── integration/                # Database & API integration tests
│   └── e2e/                        # End-to-end autonomous pipeline test
├── benchmark/
│   ├── benchmark.py                # Benchmark runner against all tasks
│   └── metrics.py                  # Accuracy, Precision, Recall, F1 & latency metrics
├── config.yaml                     # Application settings
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── run.py                          # Unified CLI entry point
```

---

## Key Features

1. **Semantic Browser Automation**: Discovers buttons and video containers using ARIA attributes, button text, and semantic HTML without any hardcoded mouse coordinates.
2. **Temporal Video Processing**: Analyzes multi-frame motion and sequence patterns rather than single isolated frames.
3. **Structured Evidence Engine**: Every single decision is paired with temporal start/end timestamps and human-readable explanation reasoning.
4. **Two-Pass Confidence Verification**: Decisions scoring between 0.75 and 0.90 automatically trigger deep second-pass verification comparing beginning, middle, and end segments.
5. **Real-time Glassmorphism Dashboard**: Live WebSocket telemetry reporting status, video progress, accuracy, latency, and decision audit trails.
6. **Pluggable VisionProvider Interface**: Easily swap `MockVisionProvider` with local multimodal models (LLaVA, Florence-2, BLIP-2).

---

## Quickstart & Installation

### 1. Create Virtual Environment & Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Generate Synthetic Test Videos
```bash
python demo/videos/generate_videos.py
```

---

## Available Commands

| Command | Description |
|---|---|
| `python run.py --demo` | Launch the local demo annotation website on `http://127.0.0.1:3000` |
| `python run.py --dashboard` | Launch the real-time agent dashboard on `http://127.0.0.1:8000` |
| `python run.py --dry-run` | Run autonomous agent in safe dry-run mode (does not submit) |
| `python run.py --auto-submit` | Run autonomous agent with auto-submission enabled on local test URL |
| `python run.py --benchmark` | Run full benchmark suite and display precision/recall/F1 table |
| `python -m pytest` | Run all unit, integration, and E2E tests |

---

## Switching Vision Providers

To switch from `mock` to a local model (e.g. Florence-2, LLaVA, BLIP-2):

1. Open `config.yaml` and set:
   ```yaml
   vision:
     provider: local
   ```
2. Implement model inference in `app/vision/local.py` following the documented abstract methods:
   - `analyze_frame(frame)`
   - `analyze_frames(frames)`
   - `analyze_temporal_segment(frames, timestamps)`
   - `detect_hands(frame)`
   - `detect_objects(frame)`
3. The rest of the pipeline remains unchanged.

---

## Configuration (`config.yaml`)

```yaml
browser:
  headless: false
  slow_mo: 0

agent:
  dry_run: true
  auto_submit: false
  max_tasks: 10
  max_runtime_minutes: 60
  poll_interval: 2

vision:
  provider: mock
  sample_fps: 4
  high_confidence: 0.90
  review_threshold: 0.75

performance:
  workers: 4
  enable_cache: true
  adaptive_sampling: true

dashboard:
  host: 127.0.0.1
  port: 8000

demo:
  url: http://127.0.0.1:3000
```
