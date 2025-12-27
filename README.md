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

## 시작하기

### 1. 환경 설정

> **Note**: 배포 시 환경변수는 GitHub Actions CI/CD를 통해 자동으로 `.env` 파일에 주입됩니다.  
> 필요한 Secrets/Variables는 [gitsecrets.md](./gitsecrets.md)를 참고하세요.

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

# 서버 실행
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
| POST   | `/api/test/queue`     | 테스트용 RabbitMQ 메시지 발행       |
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
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "create",
  "message": "캐릭터 설명 텍스트"
}
```

### 이미지 편집 태스크

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "projectId": "project-uuid",
  "action": "edit",
  "imageUrl": "기존 이미지 S3 URL",
  "editRequest": "편집 요청 내용"
}
```

### 콜백 응답 (Spring으로 전송)

```json
{
  "jobId": "job-uuid",
  "characterId": "char-uuid",
  "status": "completed",
  "imageUrl": "https://cloudfront.net/media/character_xxx.png"
}
```

## 환경 변수

| 변수명                          | 설명                         | 기본값                 |
| ------------------------------- | ---------------------------- | ---------------------- |
| **AWS S3**                      |                              |                        |
| `AWS_REGION`                    | 기본 AWS 리전                | `ap-northeast-2`       |
| `AWS_S3_BUCKET_NAME`            | S3 버킷 이름                 | (필수)                 |
| `CLOUDFRONT_URL`                | CloudFront 도메인            | (옵션)                 |
| **AWS Bedrock**                 |                              |                        |
| `AWS_BEDROCK_DEFAULT_REGION`    | Bedrock 리전                 | `us-east-1`            |
| `AWS_BEDROCK_ACCESS_KEY_ID`     | Bedrock 전용 액세스 키       | (필수)                 |
| `AWS_BEDROCK_SECRET_ACCESS_KEY` | Bedrock 전용 시크릿 키       | (필수)                 |
| **Gemini**                      |                              |                        |
| `GEMINI_API_KEY`                | Gemini API 키                | (필수 - 이미지 편집용) |
| **RabbitMQ (외부)**             |                              |                        |
| `RABBITMQ_IMAGE_HOST`           | RabbitMQ 호스트 (Private IP) | `localhost`            |
| `RABBITMQ_IMAGE_PORT`           | RabbitMQ 포트                | `5672`                 |
| `RABBITMQ_IMAGE_USER`           | RabbitMQ 사용자              | `guest`                |
| `RABBITMQ_IMAGE_PASSWORD`       | RabbitMQ 비밀번호            | `guest`                |
| `RABBITMQ_IMAGE_VHOST`          | RabbitMQ VHost               | `stolink`              |
| `RABBITMQ_IMAGE_QUEUE`          | 이미지 큐 이름               | `stolink.image.queue`  |
| **Spring Callback**             |                              |                        |
| `ALB_DNS_NAME`                  | Spring ALB DNS 이름          | (필수)                 |

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
│   │   ├── prompt_service.py      # 프롬프트 엔지니어링
│   │   ├── image_service.py       # 이미지 생성/편집
│   │   ├── s3_service.py          # S3 업로드
│   │   └── callback_service.py    # Spring Boot 콜백
│   ├── consumers/
│   │   └── image_consumer.py      # RabbitMQ 컨슈머
│   ├── graph/
│   │   └── image_graph.py         # LangGraph 워크플로우
│   └── schemas/
│       └── image_task.py          # Pydantic 스키마
├── .github/
│   └── workflows/
│       ├── deploy.yml             # main 브랜치 배포
│       └── deploytest.yml         # deploytest 브랜치 배포
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── gitsecrets.md                  # GitHub Secrets/Variables 문서
```

## CI/CD

GitHub Actions를 통해 자동 배포됩니다:

- **main** 브랜치 → 운영 EC2
- **deploytest** 브랜치 → 테스트 EC2

### 배포 흐름

1. pytest 테스트 실행
2. Docker 이미지 빌드 (GHCR 푸시)
3. SSM으로 EC2에 배포

## 관련 프로젝트

- **Spring Boot Backend**: 메인 API 서버
- **AI Analysis Worker**: LangGraph 기반 스토리 분석
