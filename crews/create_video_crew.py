# 영상 생성 서비스 : 프롬프트 기반 비디오 생성
# ByteDance의 seedance-1-lite 모델 사용
# nano_banana 프로젝트에서 이관됨

import replicate
from crewai import Crew, Agent, Task
from crewai.project import CrewBase, task, agent, crew

from config import get_settings


@CrewBase
class VideoPromptMakerCrew:
    """
    비디오 생성용 프롬프트를 만드는 CrewAI 에이전트
    사용자의 요청을 영화적이고 제작 수준의 프롬프트로 변환
    """
    
    @agent
    def video_prompt_maker_agent(self) -> Agent:
        return Agent(
            role="Video Prompt Engineer",
            goal="""Transform every user brief into a cinematic, production-ready prompt tailored to ByteDance Seedance-1-Lite, maximizing narrative clarity, sensory richness, and frame-to-frame coherence.""",
            backstory="""Expert video prompt engineer specializing in AI video generation tools. Operate as a senior video prompt architect. Analysis blueprint: 1. Decode narrative core. 2. Map setting. 3. Define visual storytelling. 4. Shape sensory layers. 5. Calibrate pacing.""",
            llm="gemini/gemini-2.5-flash",
            verbose=True,
        )

    @task
    def make_video_prompt_task(self) -> Task:
        return Task(
            agent=self.video_prompt_maker_agent(),
            description="""Analyze the user message '{message}' and convert it into a Seedance-1-Lite prompt that can drive a polished video. Specify environment, lighting, and precise camera language for cinematic continuity.""",
            expected_output="""Return exactly one polished English prompt (80-150 words) optimized for ByteDance Seedance-1-Lite as a single paragraph."""
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.video_prompt_maker_agent()],
            tasks=[self.make_video_prompt_task()],
            verbose=True,
        )


class CreateVideoService:
    """
    비디오 생성 서비스
    - Replicate의 ByteDance Seedance-1-Lite 모델을 사용하여 비디오 생성
    
    Note: 현재 S3 업로드 미구현 (추후 필요시 추가)
    """
    
    def __init__(self):
        self.settings = get_settings()

    def create_video(self, message: str, user_id: str = "default") -> str:
        """
        텍스트 프롬프트로 비디오 생성
        
        Args:
            message: 사용자의 비디오 생성 요청 텍스트
            user_id: 사용자 ID (향후 S3 업로드시 사용)
            
        Returns:
            생성된 비디오 URL (Replicate 직접 반환 URL)
        """
        # CrewAI로 비디오 프롬프트 향상
        crew = VideoPromptMakerCrew().crew()
        enhanced_prompt = crew.kickoff(inputs={"message": message}).raw
        
        # Seedance-1-Lite 모델로 비디오 생성
        output = replicate.run(
            "bytedance/seedance-1-lite",
            input={
                "prompt": enhanced_prompt,
                "num_frames": 16
            }
        )
        
        # TODO: 향후 S3 업로드 구현시 geminiVideos/{user_id}/ 경로 사용
        return str(output)
