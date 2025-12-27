# Prompt Engineering Service
# Uses Claude 3.5 Haiku via LangChain ChatBedrockConverse for prompt optimization

import json
import logging
from typing import Optional, Tuple

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


# System prompts for different tasks
CREATE_CHARACTER_SYSTEM_PROMPT = """당신은 최고의 신분증 및 프로필 사진 프롬프트 엔지니어입니다.

사용자가 요청한 인물을 증명사진 스타일로 생성하기 위한 영어 프롬프트를 작성합니다.

규칙:
1. 자세: 신분증 사진처럼 정면을 응시하고 가만히 있는 자세 (ID photo pose, front view, looking at camera)
2. 구도: 상반신 위주의 증명사진 구도 (shoulder-up portrait, passport photo style)
3. 배경: 인물을 방해하지 않는 깔끔하고 단순한 배경 (plain solid background)
4. 일관성: 얼굴의 특징이 명확하게 드러나는 고해상도 묘사
5. 결과물은 영어 프롬프트만 출력하세요. 다른 설명은 필요 없습니다."""


EDIT_IMAGE_SYSTEM_PROMPT = """You are an expert at crafting prompts for Google Gemini's image editing model.

Your task: Convert the user's edit request into an optimized English prompt that describes the desired changes while PRESERVING the original person's identity.

**CRITICAL RULES FOR IDENTITY PRESERVATION:**
1. Always emphasize preserving the person's facial features and identity
2. Describe the specific change you want, not a complete redescription of the person
3. Be precise about which aspect to change (hair, clothing, expression, etc.)
4. The model should only modify what you specifically mention

**CONTENT GUIDELINES:**
- Keep prompts positive and constructive
- Describe the desired result, not what to remove
- Use natural, descriptive language

**EDIT TYPE STRATEGIES:**

1. HAIR CHANGES (length, style, color):
   - "Change the hair to long flowing silver hair while keeping the same face"
   - "Make the hair shorter with a modern pixie cut, preserve facial features"

2. FACIAL FEATURES:
   - "Add subtle expression lines to make the person look more mature"
   - "Add a small beauty mark on the left cheek"

3. AGING:
   - "Age this person by 10-15 years: add gray/silver hair and subtle aging while preserving their core facial features and identity"
   - Focus on natural aging signs like hair graying

4. CLOTHING/ACCESSORIES:
   - "Change the outfit to a casual blue denim jacket"
   - "Add glasses with thin black frames"

**EXAMPLES:**

Hair change:
"Transform the short black hair into long flowing silver hair reaching past the shoulders. Keep the person's face and features exactly the same."

Aging:
"Age this person naturally by about 15 years. Add salt-and-pepper gray hair. Preserve their facial identity and features."

Clothing:
"Change the formal suit to a casual sweater. Keep everything else the same."

**OUTPUT FORMAT:**
Return ONLY the English prompt text. No JSON, no quotes, just the prompt.

Example output:
Change the short black hair to long wavy auburn hair while preserving the person's facial features and identity."""


class PromptService:
    """Service for generating optimized prompts using Claude via LangChain."""
    
    def __init__(self):
        settings = get_settings()
        self.llm = ChatBedrockConverse(
            model=settings.bedrock_claude_model_id,
            region_name=settings.aws_region,
            credentials_profile_name=None,  # Use default credentials
            # Pass AWS credentials explicitly if not using default profile
        )
        # Set credentials for boto3 session
        import boto3
        self._session = boto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        # Recreate LLM with explicit credentials
        self.llm = ChatBedrockConverse(
            model=settings.bedrock_claude_model_id,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    
    def create_character_prompt(self, user_message: str) -> str:
        """
        Generate optimized prompt for character image creation.
        
        Args:
            user_message: User's character description in any language
            
        Returns:
            Optimized English prompt for Nova Canvas
        """
        try:
            messages = [
                SystemMessage(content=CREATE_CHARACTER_SYSTEM_PROMPT),
                HumanMessage(content=f"다음 인물 설명을 기반으로 증명사진 스타일의 영어 프롬프트를 작성하세요:\n\n{user_message}"),
            ]
            
            response = self.llm.invoke(messages)
            enhanced_prompt = response.content.strip()
            
            logger.info(f"Generated character prompt: {enhanced_prompt[:100]}...")
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Failed to generate character prompt: {e}")
            # Fallback to basic prompt
            return f"Professional ID photo portrait, {user_message}, front view, plain background, high quality"
    
    def create_edit_prompt(self, edit_request: str) -> str:
        """
        Generate an edit prompt for Gemini image editing.
        
        Args:
            edit_request: User's edit request in any language
            
        Returns:
            Optimized English edit prompt for Gemini
        """
        try:
            messages = [
                SystemMessage(content=EDIT_IMAGE_SYSTEM_PROMPT),
                HumanMessage(content=f"Convert this edit request to an optimized English prompt for Gemini:\n\n{edit_request}"),
            ]
            
            response = self.llm.invoke(messages)
            
            # Handle response content - could be string or list
            content = response.content
            if isinstance(content, list):
                # Extract text from content blocks
                response_text = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            else:
                response_text = str(content)
            
            # Clean up the response
            edit_prompt = response_text.strip()
            
            # Remove any quotes that might wrap the prompt
            if edit_prompt.startswith('"') and edit_prompt.endswith('"'):
                edit_prompt = edit_prompt[1:-1]
            if edit_prompt.startswith("'") and edit_prompt.endswith("'"):
                edit_prompt = edit_prompt[1:-1]
            
            # Validate that we got a meaningful prompt
            if not edit_prompt or len(edit_prompt) < 10:
                raise ValueError(f"Edit prompt too short or empty: {edit_prompt}")
            
            logger.info(f"Generated edit prompt: {edit_prompt[:100]}...")
            return edit_prompt
            
        except Exception as e:
            logger.error(f"Failed to generate edit prompt: {e}")
            raise RuntimeError(
                f"Failed to generate edit prompt via Claude. "
                f"Please check your Bedrock configuration. Original error: {e}"
            ) from e


# Singleton instance
_prompt_service: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    """Get or create PromptService singleton."""
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service
