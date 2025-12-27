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


EDIT_IMAGE_SYSTEM_PROMPT = """You are an expert at crafting prompts for Stability AI's Search & Replace image editing model.

Your task: Convert the user's edit request into optimized English prompts that PRESERVE the original person's identity while making minimal, targeted changes.

**CRITICAL RULES FOR IDENTITY PRESERVATION:**
1. search_prompt: Target the SMALLEST, MOST SPECIFIC area possible
2. replace_prompt: Describe ONLY what replaces that specific area
3. NEVER target the whole face or person - always target a specific feature
4. The model replaces EVERYTHING that matches search_prompt, so be very precise

**CONTENT FILTER RULES (VERY IMPORTANT):**
- ABSOLUTELY FORBIDDEN: scar, wound, injury, blood, cut, knife, weapon, violence, damage
- For facial marks: use "beauty mark", "freckle", "mole", "natural skin texture" 
- For lines on face: use "expression line", "laugh line", "natural crease"

**EDIT TYPE STRATEGIES:**

1. HAIR CHANGES (length, style, color):
   - search_prompt: describe current hair precisely (e.g., "short straight black hair")
   - replace_prompt: describe new hair only (e.g., "long wavy black hair past shoulders")

2. FACIAL MARKS/FEATURES:
   - search_prompt: target very small area (e.g., "smooth cheek skin near left eye")
   - replace_prompt: describe subtle addition (e.g., "cheek with small beauty mark near left eye")
   - Keep it natural and subtle!

3. AGING (10+ years older) - CRITICAL: Target ONLY hair, not skin!
   - search_prompt: "dark [color] hair" (target ONLY hair color, NOT the face!)
   - replace_prompt: "salt and pepper gray hair with natural aging"
   - NEVER target skin/face for aging - it destroys identity!

4. CLOTHING/ACCESSORIES:
   - search_prompt: describe current item (e.g., "black suit jacket")
   - replace_prompt: describe new item (e.g., "casual blue denim jacket")

**EXAMPLES:**

Hair change:
{"search_prompt": "short black hair", "replace_prompt": "long flowing black hair reaching shoulders"}

Adding mark (safe for content filter):
{"search_prompt": "clear smooth skin on left cheekbone", "replace_prompt": "skin with small natural mole on left cheekbone"}

Aging (ONLY target hair!):
{"search_prompt": "black hair on head", "replace_prompt": "gray and white hair with natural aging, salt and pepper style"}

**OUTPUT FORMAT:**
Return ONLY valid JSON:
{"search_prompt": "specific small area", "replace_prompt": "replacement for that area only"}"""


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
    
    def create_edit_prompts(self, edit_request: str) -> Tuple[str, str]:
        """
        Generate search and replace prompts for image editing.
        
        Args:
            edit_request: User's edit request in any language
            
        Returns:
            Tuple of (search_prompt, replace_prompt)
        """
        try:
            messages = [
                SystemMessage(content=EDIT_IMAGE_SYSTEM_PROMPT),
                HumanMessage(content=f"Convert this edit request to optimized search/replace prompts:\n\n{edit_request}"),
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
            response_text = response_text.strip()
            
            # Debug: log the raw response
            logger.info(f"[Claude Raw Response]: {response_text[:500]}")
            
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON from response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                logger.info(f"[Claude JSON String]: {json_str}")
                result = json.loads(json_str)
                search_prompt = result.get("search_prompt", "")
                replace_prompt = result.get("replace_prompt", "")
                
                # Validate that we got meaningful prompts
                if not search_prompt or not replace_prompt:
                    raise ValueError(f"Empty prompts returned from Claude. Parsed result: {result}")
                    
            else:
                raise ValueError(f"No valid JSON found in response: {response_text[:200]}")
            
            logger.info(f"Generated edit prompts - search: {search_prompt}, replace: {replace_prompt}")
            return search_prompt, replace_prompt
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}, response: {response_text[:300]}")
            raise RuntimeError(
                f"Failed to parse Claude response as JSON. Response: {response_text[:200]}"
            ) from e
        except Exception as e:
            logger.error(f"Failed to generate edit prompts: {e}")
            raise RuntimeError(
                f"Failed to generate edit prompts via Claude. "
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
