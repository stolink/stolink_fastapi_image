# StoLink Image Worker

AWS Bedrock 기반 이미지 생성/편집 FastAPI 워커 서비스입니다. **LangGraph**를 사용하여 이미지 생성 워크플로우를 관리합니다.

## 기술 스택

- **FastAPI**: 비동기 웹 프레임워크
- **LangGraph**: 워크플로우 오케스트레이션
- **LangChain AWS**: Bedrock Claude 통합
- **AWS Bedrock**: AI 모델 서비스
  - Claude 3.5 Haiku: 프롬프트 엔지니어링
  - Amazon Nova Canvas: 이미지 생성
- **Google Gemini**: 이미지 편집 (gemini-2.5-flash-image)
- **RabbitMQ**: 메시지 큐 (외부 EC2 서버)
- **AWS S3**: 이미지 저장소
- **MinIO**: 로컬 S3 호환 스토리지 (개발용)

## 아키텍처

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Spring Boot    │──▶───│    RabbitMQ     │──▶───│  Image Worker   │
│   (via ALB)     │      │   (외부 EC2)    │      │    (FastAPI)    │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        ▲                                                  │
        │                                                  ▼
        │                                       ┌─────────────────────┐
        │                                       │   LangGraph State   │
        │                                       │       Graph         │
        │                                       └─────────────────────┘
        │                                                  │
        │          ┌───────────────────────────────────────┼───────────────────────────────────┐
        │          ▼                                       ▼                                   ▼
        │ ┌─────────────────┐                   ┌─────────────────┐                 ┌─────────────────┐
        │ │  Claude Haiku   │                   │   Nova Canvas   │                 │ Google Gemini   │
        │ │ (프롬프트 생성)  │                    │  (이미지 생성)   │                 │  (이미지 편집)  │
        │ └─────────────────┘                   └─────────────────┘                 └─────────────────┘
        │                                                  │
        │                                                  ▼
        │                                       ┌─────────────────┐
        │                                       │    S3 업로드     │
        │                                       └─────────────────┘
        │                                                  │
        └──────────── Callback (ALB) ──────────────────────┘
```

### LangGraph 워크플로우

```
┌─────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌───────────────┐
│  START  │──▶──│ generate_prompt  │──▶──│  create_image    │──▶──│ upload_to_s3  │──▶──END
└─────────┘     └──────────────────┘     │  (action=create) │     └───────────────┘
                         │               └──────────────────┘              ▲
                         │                                                 │
                         │               ┌──────────────────┐              │
                         └──────────▶────│   edit_image     │──────────────┘
                                         │  (action=edit)   │
                                         └──────────────────┘
```

### S3 경로 구조

이미지는 계층적 경로 구조로 S3에 저장됩니다:

```
media/{userId}/{projectId}/{characterId}/{prefix}_{timestamp}.png
```

예시:

```
media/user-123/project-456/char-789/character_20241229_103045.png
media/user-123/project-456/char-789/edited_20241229_103050.png
```

이 구조의 장점:

- **사용자별 데이터 격리**: 각 사용자의 데이터를 분리
- **프로젝트별 관리**: 프로젝트 단위로 이미지 그룹화
- **캐릭터 추적**: 특정 캐릭터의 모든 이미지 버전 추적
- **라이프사이클 관리**: S3 라이프사이클 규칙 적용 용이

## 시작하기

### 1. 환경 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# .env 파일에 실제 값 입력 (AWS, Gemini API 키 등)
```

> **Note**: 배포 시 환경변수는 GitHub Actions CI/CD를 통해 자동으로 `.env` 파일에 주입됩니다.  
> 필요한 Secrets/Variables는 [gitsecrets.md](./gitsecrets.md)를 참고하세요.

### 2. 로컬 개발 (Docker Compose)

로컬 개발 환경은 RabbitMQ와 MinIO(S3 에뮬레이터)를 포함합니다:

```bash
# RabbitMQ + MinIO 포함 빌드 및 실행
docker compose -f docker-compose.local.yml up --build -d

# 로그 확인
docker compose -f docker-compose.local.yml logs -f image-worker

# 중지
docker compose -f docker-compose.local.yml down

# 데이터 삭제 포함 중지
docker compose -f docker-compose.local.yml down -v
```

**로컬 서비스:**

| 서비스           | URL                    | 인증                  |
| ---------------- | ---------------------- | --------------------- |
| Image Worker API | http://localhost:8000  | -                     |
| RabbitMQ 관리 UI | http://localhost:15672 | guest/guest           |
| MinIO Console    | http://localhost:9001  | minioadmin/minioadmin |

> **Note**: 생성된 이미지는 MinIO Console → `stolink-test` 버킷에서 확인할 수 있습니다.

### 3. 로컬 실행 (Docker 없이)

```bash
# 의존성 설치
uv sync

# 서버 실행 (별도로 RabbitMQ 필요)
uv run uvicorn app.main:app --reload --port 8000
```

## API 엔드포인트

| Method | Path                  | Description                         |
| ------ | --------------------- | ----------------------------------- |
| GET    | `/`                   | 서비스 정보                         |
| GET    | `/health`             | 헬스 체크 (RabbitMQ 연결 상태 포함) |
| GET    | `/ready`              | RabbitMQ 연결 확인                  |
| POST   | `/api/image/generate` | 수동 이미지 생성 (RabbitMQ 우회)    |
| POST   | `/api/image/edit`     | 수동 이미지 편집 (RabbitMQ 우회)    |
| POST   | `/upload`             | S3 이미지 업로드                    |

### 수동 이미지 생성 예시

```bash
curl -X POST http://localhost:8000/api/image/generate \
  -H "Content-Type: application/json" \
  -d '{"message": "검은색 정장을 입은 20대 한국인 남성"}'
```

### RabbitMQ 큐 테스트

```bash
curl -X POST http://localhost:8000/api/test/queue \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create",
    "message": "검은색 정장을 입은 20대 한국인 남성",
    "projectId": "test-project"
  }'
```

## RabbitMQ 메시지 형식

### 이미지 생성 태스크

```json
{
  "jobId": "job-uuid",
  "userId": "user-uuid",
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "create",
  "message": "캐릭터 설명 텍스트",
  "callbackUrl": "http://alb-dns/api/internal/ai/image/callback"
}
```

### 이미지 편집 태스크

```json
{
  "jobId": "job-uuid",
  "userId": "user-uuid",
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "edit",
  "imageUrl": "기존 이미지 S3 URL = media/{userId}/{projectId}/{characterId}/{timestamp}.png",
  "editRequest": "편집 요청 내용",
  "callbackUrl": "http://alb-dns/api/internal/ai/image/callback"
}
```

### 콜백 응답 (Spring으로 전송)

> **Note**: `callbackUrl`이 메시지에 필수로 포함되어야 합니다. 없으면 콜백이 스킵됩니다.

> **Retry Policy**: 콜백 전송 실패 시 **지수 백오프**로 최대 3회 재시도합니다 (1초 → 2초 → 4초).
>
> - 4xx 클라이언트 에러: 재시도 안함
> - 5xx 서버 에러 / 타임아웃: 재시도 수행

성공 시:

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "status": "SUCCESS",
  "imageUrl": "https://cloudfront.net/media/user-123/project-456/char-789/character_xxx.png"
}
```

실패 시:

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "status": "FAILED",
  "error": "에러 메시지"
}
```

## 환경 변수

| 변수명                          | 설명                        | 기본값                      |
| ------------------------------- | --------------------------- | --------------------------- |
| **AWS S3**                      |                             |                             |
| `AWS_REGION`                    | 기본 AWS 리전               | `ap-northeast-2`            |
| `AWS_S3_BUCKET_NAME`            | S3 버킷 이름                | (필수)                      |
| `S3_ENDPOINT_URL`               | S3 엔드포인트 (MinIO용)     | (로컬: `http://minio:9000`) |
| `S3_ACCESS_KEY_ID`              | S3 전용 액세스 키 (MinIO용) | (옵션, aws\_\* 오버라이드)  |
| `S3_SECRET_ACCESS_KEY`          | S3 전용 시크릿 키 (MinIO용) | (옵션, aws\_\* 오버라이드)  |
| `CLOUDFRONT_URL`                | CloudFront 도메인           | (옵션)                      |
| **AWS Bedrock**                 |                             |                             |
| `AWS_BEDROCK_DEFAULT_REGION`    | Bedrock 리전                | `us-east-1`                 |
| `AWS_BEDROCK_ACCESS_KEY_ID`     | Bedrock 전용 액세스 키      | (필수)                      |
| `AWS_BEDROCK_SECRET_ACCESS_KEY` | Bedrock 전용 시크릿 키      | (필수)                      |
| **Gemini**                      |                             |                             |
| `GEMINI_API_KEY`                | Gemini API 키               | (필수 - 이미지 편집용)      |
| **RabbitMQ**                    |                             |                             |
| `RABBITMQ_HOST`                 | RabbitMQ 호스트             | `localhost`                 |
| `RABBITMQ_PORT`                 | RabbitMQ 포트               | `5672`                      |
| `RABBITMQ_USER`                 | RabbitMQ 사용자             | `guest`                     |
| `RABBITMQ_PASSWORD`             | RabbitMQ 비밀번호           | `guest`                     |
| `RABBITMQ_VHOST`                | RabbitMQ VHost              | `stolink`                   |
| `RABBITMQ_IMAGE_QUEUE`          | 이미지 큐 이름              | `stolink.image.queue`       |

## 프로젝트 구조

```
stolink_fastapi_image/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── config/
│   │   └── settings.py            # 환경 설정
│   ├── api/
│   │   └── routes.py              # API 라우트
│   ├── services/
│   │   ├── bedrock_service.py     # AWS Bedrock (Claude, Nova Canvas)
│   │   ├── gemini_service.py      # Google Gemini 이미지 편집
│   │   ├── prompt_service.py      # 프롬프트 엔지니어링 (LLM 주입 가능)
│   │   ├── image_service.py       # 이미지 생성/편집
│   │   ├── s3_service.py          # S3 업로드 (계층적 경로)
│   │   └── callback_service.py    # Spring Boot 콜백 (지수 백오프 재시도)
│   ├── consumers/
│   │   └── image_consumer.py      # RabbitMQ 컨슈머
│   ├── graph/
│   │   └── image_graph.py         # LangGraph 워크플로우
│   └── schemas/
│       └── image_task.py          # Pydantic 스키마
├── test/                          # 개발용 Jupyter 테스트
│   ├── image_generation_test.ipynb        # 이미지 생성 테스트
│   ├── image_generation_gemini_test.ipynb # Gemini 편집 테스트
│   └── integration_test_with_s3.ipynb     # S3 통합 테스트
├── tests/                         # pytest 자동화 테스트
│   └── test_health.py             # 헬스체크 테스트
├── .github/
│   └── workflows/
│       ├── deploy.yml             # main 브랜치 배포
│       └── deploy_dev.yml         # dev 브랜치 배포
├── .env.example                   # 환경변수 예제
├── Dockerfile
├── docker-compose.yml             # 운영 배포용
├── docker-compose.local.yml       # 로컬 개발용 (RabbitMQ + MinIO 포함)
├── pyproject.toml
└── gitsecrets.md                  # GitHub Secrets/Variables 문서
```

## CI/CD

GitHub Actions를 통해 자동 배포됩니다:

- **main** 브랜치 → 운영 EC2
- **deploy_dev** 브랜치 → 테스트 EC2

### 배포 흐름

1. pytest 테스트 실행
2. Docker 이미지 빌드 (GHCR 푸시)
3. SSM으로 EC2에 배포

## 테스트

`PromptService`는 LLM 주입을 지원하여 단위 테스트 시 mock을 사용할 수 있습니다:

```python
from unittest.mock import Mock
from app.services.prompt_service import PromptService

mock_llm = Mock()
mock_llm.invoke.return_value.content = "test prompt"

service = PromptService(llm=mock_llm)
result = service.create_character_prompt("test")
```

## 관련 프로젝트

- **Spring Boot Backend**: 메인 API 서버
- **AI Analysis Worker**: LangGraph 기반 스토리 분석
