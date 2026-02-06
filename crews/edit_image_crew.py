import logging
import re
import boto3
import replicate
import requests
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from crewai import Crew, Agent, Task
from crewai.project import CrewBase, task, agent, crew
from starlette.concurrency import run_in_threadpool

from app.config import get_settings

logger = logging.getLogger(__name__)

# Constants
S3_FOLDER_PREFIX = "geminiImages"
FILENAME_EXT = "png"
DEFAULT_EXPIRATION = 3600  # 1 hour


@CrewBase
class EditImagePromptMakerCrew:
    """
    이미지 편집용 프롬프트를 만드는 CrewAI 에이전트
    사용자의 편집 요청을 분석하여 Google Nano Banana 모델에 최적화된 프롬프트 생성
    """
    
    @agent
    def image_edit_prompt_maker_agent(self) -> Agent:
        return Agent(
            role="이미지 편집 프롬프트 전문가",
            goal="사용자의 편집 요청을 정확히 분석하여, 정체성은 유지하면서 요청된 변경 사항이 확실히 반영되도록 프롬프트를 작성한다.",
            backstory="""당신은 이미지 편집 프롬프트 전문가입니다.
            요청 유형에 따라 변경 강도를 조절합니다:
            - 소품/색상 변경: 최소한의 변경만 적용
            - 노화/상처 등 외모 변화: 정체성은 유지하되 요청된 변화는 눈에 띄게 적용
            사용자가 변경을 요청해도 '얼굴 형태, 눈코입의 위치, 조명 방향, 정적인 자세'는 절대로 건드리지 않습니다. 
            **노화 요청 시 'significantly aged', 'deep wrinkles', 'distinct gray hair', 'mature skin texture' 같이 변화가 확실히 느껴지는 강한 명시적 키워드를 반드시 포함합니다.**""",
            llm="gemini/gemini-2.5-flash",
            verbose=False,
        )

    @task
    def make_edit_prompt_task(self) -> Task:
        return Task(
            agent=self.image_edit_prompt_maker_agent(),
            description="""사용자의 편집 요청('{edit_request}')을 분석하여 Google Nano Banana 모델에 최적화된 영어 프롬프트를 작성하세요.

            [요청 유형별 처리 가이드라인]
            
            1. 소품/색상 변경 (옷, 배경, 액세서리 등):
               - 얼굴, 자세, 정체성은 99% 보존
               - 제한: 변경 사항은 요청한 소품이나 색상 등에만 한정 (e.g., 'only change the shirt color')
               - 'strictly maintain original facial features, only change [요청 항목]' 사용
            
            2. 노화/젊어짐 (나이 변화): 
            - 정체성과 자세는 완벽히 유지하되, **'확실하고 눈에 띄는' 노화 효과를 적용**해야 합니다.
            - 노화 프롬프트 필수 강화 요소 (반드시 포함):
                * **'visibly older appearance'** (눈에 띄게 나이 든 외모)
                * **'deep and prominent crow's feet wrinkles around eyes'** (깊고 뚜렷한 눈가 주름)
                * **'pronounced forehead lines and deeper nasolabial folds'** (뚜렷한 이마 주름과 깊어진 팔자 주름)
                * **'distinct graying hair mixed with original hair color' or 'salt and pepper hair'** (원래 머리색과 섞인 뚜렷한 흰머리/반백발)
                * **'mature, weathered skin texture with slight sagging'** (성숙하고 풍파를 겪은, 약간 처진 피부 질감)
                - 예시: **'same person significantly aged by 10 years, with deep prominent crow's feet and forehead wrinkles, distinct graying hair at temples and crown (salt and pepper look), pronounced nasolabial folds, mature weathered skin texture, maintain exact identity and pose'**
                
            3. 상처/흉터 추가:
               - 정체성 유지하면서 요청된 부위에 상처 추가
               - 'same person with a realistic [scar type] on [location], maintain identity'
            
            [필수 키워드]
            - 모든 프롬프트에 'same person, maintain identity' 포함
            - 노화 요청 시 **'significantly aged', 'deep wrinkles', 'gray hair'** 등 명시적이고 강한 노화 키워드 포함""",
            expected_output="""Google Nano Banana 모델용 영어 편집 프롬프트. 요청 유형에 맞게 변경 허용 범위를 조절하세요. (프롬프트 결과물만 출력하세요.)""",
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.image_edit_prompt_maker_agent()],
            tasks=[self.make_edit_prompt_task()],
            verbose=False,
        )



class ImageEditingError(Exception):
    def __init__(self, message, error_code, fallback_url=None):
        self.message = message
        self.error_code = error_code
        self.fallback_url = fallback_url
        super().__init__(message)


class EditImageService:
    """
    이미지 편집 서비스
    - Replicate의 Google Nano Banana 모델을 사용하여 이미지 편집
    - S3에서 이미지를 불러오고 편집 후 다시 S3에 업로드
    """
    
    def __init__(self):
        self.settings = get_settings()
        # S3 클라이언트 초기화 (명시적 인증 정보 및 s3v4 서명 버전 사용)
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            region_name=self.settings.aws_region,
            config=boto3.session.Config(signature_version='s3v4')
        )

    async def edit_image(self, image_url: str, edit_request: str, user_id: str = "default") -> str:
        """
        기존 이미지를 편집
        
        Args:
            image_url: 편집할 원본 이미지의 S3 URL
            edit_request: 사용자의 편집 요청 텍스트
            user_id: 사용자 ID (S3 경로 구분용)
            
        Returns:
            편집된 이미지의 S3 URL
        """
        # CrewAI로 편집 프롬프트 생성 (블로킹 I/O이므로 스레드 풀에서 실행)
        edit_crew = EditImagePromptMakerCrew().crew()
        kickoff_result = await run_in_threadpool(edit_crew.kickoff, inputs={"edit_request": edit_request})
        
        # CrewAI 결과 추출 (딕셔너리 형태의 결과에서 태스크 출력물만 가져옴)
        enhanced_prompt = kickoff_result.raw
        if isinstance(enhanced_prompt, dict):
            enhanced_prompt = enhanced_prompt.get('make_edit_prompt_task', '')
            
        if not enhanced_prompt:
            logger.error("프롬프트 생성 결과가 비어있습니다.")
            raise ImageEditingError(
                message="프롬프트 생성에 실패했습니다. 요청 내용을 확인 후 다시 시도해주세요.",
                error_code="ERR_PROMPT_GENERATION_FAILED"
            )
        
        # S3 URL을 Presigned URL로 변환 (Replicate이 접근할 수 있도록)
        presigned_url = await self._get_presigned_url(image_url)
        
        logger.debug(f"원본 S3 URL: {image_url}")
        logger.debug(f"Presigned URL: {presigned_url[:100]}...")
        logger.debug(f"프롬프트: {enhanced_prompt[:200]}...")
        
        # Nano Banana 모델로 이미지 편집 (재시도 로직 적용, 스레드 풀에서 실행)
        try:
            output_list = await run_in_threadpool(
                self._call_replicate_with_retry,
                {
                    "prompt": enhanced_prompt,
                    "image_input": [presigned_url],
                    "output_format": FILENAME_EXT
                }
            )
            
            # Replicate 결과 유효성 검증 (보통 URL 문자열 리스트를 반환)
            if not output_list or not isinstance(output_list, list) or not output_list[0]:
                raise ImageEditingError(
                    message="이미지 편집 결과가 유효하지 않습니다. 다시 시도해 주세요.",
                    error_code="ERR_IMG_OUTPUT_INVALID"
                )
            
            edited_image_url = str(output_list[0])
            
        except ImageEditingError:
            raise
        except Exception as e:
            # 3회 실패 후 Graceful Error 처리
            logger.error(f"이미지 편집 최종 실패: {e}")
            raise ImageEditingError(
                message="현재 이미지 서버 사용량이 많아 작업을 완료할 수 없습니다. 잠시 후 다시 시도해주세요.",
                error_code="ERR_IMG_NANO_TIMEOUT",
                fallback_url=image_url # 원본 이미지 URL 반환
            )
        
        # S3에 업로드하고 URL 반환
        return await self._upload_to_s3(edited_image_url, "edited", user_id)

    @retry(
        retry=retry_if_exception_type((replicate.exceptions.ModelError, replicate.exceptions.ReplicateError, requests.exceptions.RequestException)),
        wait=wait_exponential(multiplier=1, min=2, max=10), # 2^n wait (2s, 4s, 8s)
        stop=stop_after_attempt(3), # Max 3 tries
        reraise=True,
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING)
    )
    def _call_replicate_with_retry(self, input_data):
        return replicate.run("google/nano-banana", input=input_data)

    async def _get_presigned_url(self, s3_url: str) -> str:
        """
        S3 URL에서 버킷과 키를 추출하여 Presigned URL 생성 (1시간 유효)
        """
        return await run_in_threadpool(self._sync_get_presigned_url, s3_url)

    def _sync_get_presigned_url(self, s3_url: str) -> str:
        """
        동기 방식의 Presigned URL 생성 로직
        """
        match = re.match(r'https://([^.]+)\.s3\.([^.]+)\.amazonaws\.com/(.+)', s3_url)
        if not match:
            logger.error(f"S3 URL 형식이 올바르지 않아 Presigned URL 생성을 실패했습니다: {s3_url}")
            raise ImageEditingError(
                message="원본 이미지 URL 형식이 올바르지 않습니다.",
                error_code="ERR_INVALID_S3_URL_FORMAT"
            )

        bucket = match.group(1)
        region = match.group(2)
        key = match.group(3)
        
        try:
            # 현재 클라이언트의 리전과 동일하면 재사용, 아니면 리전별 임시 클라이언트 생성
            if region == self.settings.aws_region:
                client = self.s3_client
            else:
                client = boto3.client(
                    's3',
                    aws_access_key_id=self.settings.aws_access_key_id,
                    aws_secret_access_key=self.settings.aws_secret_access_key,
                    region_name=region,
                    config=boto3.session.Config(signature_version='s3v4')
                )
            
            presigned_url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=DEFAULT_EXPIRATION
            )
            return presigned_url
        except Exception as e:
            logger.error(f"Presigned URL 생성 중 오류 발생: {e}")
            return s3_url

    async def _upload_to_s3(self, url: str, prefix: str, user_id: str) -> str:
        """
        URL에서 이미지를 다운로드하여 S3에 업로드
        """
        return await run_in_threadpool(self._sync_upload_to_s3, url, prefix, user_id)

    def _sync_upload_to_s3(self, url: str, prefix: str, user_id: str) -> str:
        """
        동기 방식의 S3 업로드 로직
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            file_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{FILENAME_EXT}"
            s3_key = f"{S3_FOLDER_PREFIX}/{user_id}/{file_name}"
            
            self.s3_client.put_object(
                Bucket=self.settings.aws_s3_bucket_name,
                Key=s3_key,
                Body=response.content,
                ContentType=f'image/{FILENAME_EXT}'
            )
            
            return f"https://{self.settings.aws_s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"
            
        except requests.exceptions.RequestException as e:
            logger.error(f"이미지 다운로드 실패 ({url}): {e}")
            raise ImageEditingError("편집된 이미지를 다운로드하는 데 실패했습니다.", "ERR_DOWNLOAD_FAILED")
        except Exception as e:
            logger.error(f"S3 업로드 실패: {e}")
            raise ImageEditingError("편집된 파일을 저장소에 업로드하는 데 실패했습니다.", "ERR_S3_UPLOAD_FAILED")
