# StoLink Image Worker

AWS Bedrock 기반 이미지 생성/편집 FastAPI 워커 서비스입니다. **LangGraph**를 사용하여 이미지 생성 워크플로우를 관리합니다.

## 기술 스택

- **FastAPI**: 비동기 웹 프레임워크
- **LangGraph**: 워크플로우 오케스트레이션
- **LangChain AWS**: Bedrock Claude 통합
- **AWS Bedrock**: AI 모델 서비스
  - Claude 3.5 Haiku: 프롬프트 엔지니어링
  - Amazon Nova Canvas: 이미지 생성
  - Stability Image Search & Replace: 이미지 편집
- **RabbitMQ**: 메시지 큐
- **AWS S3**: 이미지 저장소

## 아키텍처

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Spring Boot    │──▶───│    RabbitMQ     │──▶───│  Image Worker   │
│    Backend      │      │  (image queue)  │      │    (FastAPI)    │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                                          │
                                                          ▼
                                               ┌─────────────────────┐
                                               │   LangGraph State   │
                                               │       Graph         │
                                               └─────────────────────┘
                                                          │
                         ┌────────────────────────────────┼────────────────────────────────┐
                         ▼                                ▼                                ▼
                ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
                │  Claude Haiku   │            │   Nova Canvas   │            │   Stability AI  │
                │ (프롬프트 생성)  │            │  (이미지 생성)  │            │  (이미지 편집)  │
                └─────────────────┘            └─────────────────┘            └─────────────────┘
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

## 시작하기

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 - AWS 자격 증명 입력
```

### 2. Docker로 실행

```bash
# 빌드 및 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f image-worker

# 상태 확인
docker-compose ps
```

### 3. 로컬 실행 (개발용)

```bash
# 의존성 설치
uv sync

# RabbitMQ 실행
docker-compose up -d rabbitmq

# 서버 실행
uv run uvicorn app.main:app --reload --port 8000
```

## API 엔드포인트

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | 헬스 체크 |
| GET | `/ready` | RabbitMQ 연결 상태 확인 |
| POST | `/api/image/generate` | 수동 이미지 생성 (테스트용) |
| POST | `/api/image/edit` | 수동 이미지 편집 (테스트용) |

### 수동 이미지 생성 예시

```bash
curl -X POST http://localhost:8000/api/image/generate \
  -H "Content-Type: application/json" \
  -d '{"message": "검은색 정장을 입은 20대 한국인 남성"}'
```

### 수동 이미지 편집 예시

```bash
curl -X POST http://localhost:8000/api/image/edit \
  -H "Content-Type: application/json" \
  -d '{
    "imageUrl": "https://your-bucket.s3.region.amazonaws.com/image.png",
    "editRequest": "이 인물이 10년 후 모습을 보여줘"
  }'
```

## RabbitMQ 메시지 형식

이미지 생성 태스크 메시지:

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "create",
  "message": "캐릭터 설명 텍스트",
  "callbackUrl": "http://localhost:8080/api/internal/ai/image/callback"
}
```

이미지 편집 태스크 메시지:

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "edit",
  "imageUrl": "기존 이미지 S3 URL",
  "editRequest": "편집 요청 내용",
  "callbackUrl": "http://localhost:8080/api/internal/ai/image/callback"
}
```

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 | (필수) |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | (필수) |
| `AWS_REGION` | Bedrock 리전 | `us-east-1` |
| `AWS_S3_BUCKET_NAME` | S3 버킷 이름 | (필수) |
| `AWS_S3_REGION` | S3 버킷 리전 | `ap-northeast-2` |
| `RABBITMQ_HOST` | RabbitMQ 호스트 | `localhost` |
| `RABBITMQ_IMAGE_QUEUE` | 이미지 큐 이름 | `stolink.image.queue` |
| `SPRING_CALLBACK_URL` | Spring Boot 콜백 URL | `http://localhost:8080/api/internal/ai/image/callback` |

## 프로젝트 구조

```
sto-link-image-backend/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── config/
│   │   └── settings.py            # 환경 설정
│   ├── api/
│   │   └── routes.py              # API 라우트
│   ├── services/
│   │   ├── bedrock_service.py     # AWS Bedrock 통합
│   │   ├── prompt_service.py      # 프롬프트 엔지니어링
│   │   ├── image_service.py       # 이미지 생성/편집
│   │   ├── s3_service.py          # S3 업로드
│   │   └── callback_service.py    # Spring Boot 콜백
│   ├── consumers/
│   │   └── image_consumer.py      # RabbitMQ 컨슈머
│   └── schemas/
│       └── image_task.py          # Pydantic 스키마
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## 관련 프로젝트

- **Spring Boot Backend**: 메인 API 서버
- **AI Analysis Worker**: LangGraph 기반 스토리 분석
