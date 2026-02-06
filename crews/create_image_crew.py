# 이미지 생성 서비스 : 사용자의 텍스트 요청을 분석하여 새로운 이미지 생성
# nano_banana 프로젝트에서 이관됨

import os
import boto3
import replicate
import requests
from datetime import datetime
from crewai import Crew, Agent, Task
from crewai.project import CrewBase, task, agent, crew

from config import get_settings


@CrewBase
class PromptMakerCrew:
    """
    이미지 생성용 프롬프트를 만드는 CrewAI 에이전트
    사용자의 요청을 신분증/프로필 사진 스타일의 프롬프트로 변환
    """
    
    @agent
    def prompt_maker_agent(self) -> Agent:
        return Agent(
            role="최고의 신분증 및 프로필 사진 프롬프트 엔지니어",
            goal="사용자가 요청한 인물을 신분증 사진처럼 정면을 응시하고 가만히 있는 정적인 자세로 설계한다.",
            backstory="""당신은 증명사진 및 전문 프로필 사진 촬영 감독입니다. 
            인물이 정면을 똑바로 바라보며(front-facing), 중립적인 표정이나 아주 미세한 미소만을 짓도록 설정합니다. 
            배경은 단순하게(clean background), 조명은 얼굴 윤곽이 뚜렷하게 드러나는 증명사진 스타일을 추구합니다.""",
            llm="gemini/gemini-2.5-flash",
            verbose=True,
        )

    @task
    def make_prompt_task(self) -> Task:
        return Task(
            agent=self.prompt_maker_agent(),
            description="""사용자의 메시지('{message}')를 분석하여 다음 요소를 '필수'로 포함한 영어 프롬프트를 만드세요:
            1. 자세: 신분증 사진처럼 정면을 응시하고 가만히 있는 자세 (ID photo pose, front view, looking at camera)
            2. 구도: 상반신 위주의 증명사진 구도 (shoulder-up portrait, passport photo style)
            3. 배경: 인물을 방해하지 않는 깔끔하고 단순한 배경 (plain solid background)
            4. 일관성: 얼굴의 특징이 명확하게 드러나는 고해상도 묘사""",
            expected_output="신분증 스타일의 정적인 인물 생성용 영어 프롬프트. (프롬프트 결과물만 출력하세요.)"
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.prompt_maker_agent()],
            tasks=[self.make_prompt_task()],
            verbose=True,
        )


class CreateImageService:
    """
    이미지 생성 서비스
    - Replicate의 Imagen-4 모델을 사용하여 이미지 생성
    - 생성된 이미지를 S3에 업로드하고 URL 반환
    """
    
    def __init__(self):
        self.settings = get_settings()
        # S3 클라이언트 초기화 (명시적 인증 정보 사용)
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
            region_name=self.settings.AWS_REGION
        )

    def create_image(self, message: str, user_id: str = "default") -> str:
        """
        텍스트 프롬프트로 이미지 생성
        
        Args:
            message: 사용자의 이미지 생성 요청 텍스트
            user_id: 사용자 ID (S3 경로 구분용)
            
        Returns:
            생성된 이미지의 S3 URL
        """
        # CrewAI로 프롬프트 향상
        prompt_crew = PromptMakerCrew().crew()
        enhanced_prompt = prompt_crew.kickoff(inputs={"message": message}).raw
        
        # Imagen-4 모델로 이미지 생성
        output = replicate.run(
            "google/imagen-4-fast",
            input={
                "prompt": enhanced_prompt,
                "aspect_ratio": "4:3"
            }
        )
        
        # S3에 업로드하고 URL 반환
        return self._upload_to_s3(str(output), "created", user_id)

    def _upload_to_s3(self, url: str, prefix: str, user_id: str) -> str:
        """
        URL에서 이미지를 다운로드하여 S3에 업로드
        
        Args:
            url: 생성된 이미지 URL
            prefix: 파일명 접두사 (created, edited 등)
            user_id: 사용자 ID
            
        Returns:
            업로드된 이미지의 S3 URL
        """
        response = requests.get(url)
        file_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        # 사용자별 폴더 구조: geminiImages/{user_id}/{filename}
        s3_key = f"geminiImages/{user_id}/{file_name}"
        
        self.s3_client.put_object(
            Bucket=self.settings.MEDIA_S3_BUCKET_NAME,
            Key=s3_key,
            Body=response.content,
            ContentType='image/png'
        )
        
        return f"https://{self.settings.MEDIA_S3_BUCKET_NAME}.s3.{self.settings.AWS_REGION}.amazonaws.com/{s3_key}"
