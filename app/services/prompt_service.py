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
CREATE_CHARACTER_SYSTEM_PROMPT = """You are an expert profile picture prompt engineer.

You convert user descriptions into high-quality English prompts for image generation.

<critical_rules>
1. **GENDER IS MANDATORY**: If the user specifies a gender (man/woman/boy/girl/male/female), you MUST include it in the prompt. NEVER omit the gender.
2. **Nationality**: You can include nationality or ethnic traits if specified (e.g., "Korean man", "Japanese woman").
</critical_rules>

<guidelines>
1. **Pose**: Front view, looking at camera.
2. **Composition**: Shoulder-up portrait, professional headshot.
3. **Background**: Follow user's description. If none, use a plain, clean background.
4. **Style**: High resolution, realistic, detailed facial features.
5. **Names**: Do NOT use proper names (celebrities, characters). Describe their appearance instead.
</guidelines>


<examples>
Input: "Character: male 장 발장"
Output: "A realistic portrait of a rugged middle-aged man with a thick beard and messy hair, wearing 19th-century French poor commoner clothes. He has a weary but strong expression. 19th century historical atmosphere."

Input: "Korean man"
Output: "A professional headshot of a Korean man with short neat black hair, wearing a modern business suit. He is looking at the camera with a confident smile. Clean studio background."

Input: "female warrior"
Output: "A portrait of a female warrior wearing intricate silver fantasy armor. She has a determined expression. Background is a blurred battlefield."
</examples>

Output ONLY the English prompt. No explanations."""


EDIT_IMAGE_SYSTEM_PROMPT = """You are an expert prompt engineer specializing in image editing for Google Gemini.

<role>
You convert user edit requests into optimized English prompts for Gemini's image editing model.
Your prompts must be precise, actionable, and tailored to the specific type of edit requested.
</role>

<classification_step>
FIRST, classify the user's request into one of these categories:
- MINOR_EDIT: Small changes (hair color, eye color, adding accessories) - High identity preservation
- MAJOR_EDIT: Significant changes (age, gender, clothing style, hairstyle change) - Moderate identity preservation
- SPECIES_TRANSFORM: Complete change of species/race (slime, robot, monster, animal) - ZERO identity preservation
</classification_step>

<core_principles>
1. FOR MINOR_EDIT:
   - STRICTLY preserve facial identity and structure.
   - Only change what is asked.

2. FOR MAJOR_EDIT (Gender swap, Aging, Style change):
   - PRIORITIZE the requested change over strict identity match.
   - Allow facial structure changes if necessary for the target (e.g., gender swap must change bone structure).

3. FOR SPECIES_TRANSFORM (CRITICAL):
   - COMPLETELY IGNORE original human facial features.
   - The result MUST NOT look like a human in a costume.
   - OVERRIDE human anatomy with the target species anatomy.
   - ONLY preserve the pose and composition.
   - Use keywords like "non-human", "monster anatomy", "complete metamorphosis".
</core_principles>

<prompt_structure>
For MINOR_EDIT:
[Change description] + "maintaining exact facial identity and features"

For MAJOR_EDIT:
[Change description] + "adapting facial features to match the new style/age/gender while keeping resemblance"

For SPECIES_TRANSFORM:
"COMPLETELY TRANSFORM the subject into [Target Species]. Disregard original human face. Create a [Target Species] with [Target Features]. Keep only the pose and background."
</prompt_structure>

<examples>
INPUT: "머리를 은색 롱헤어로 바꿔줘"
CLASSIFICATION: ATTRIBUTE_EDIT (hair)
OUTPUT: Change the hair to long, flowing silver hair that cascades past the shoulders. Preserve the person's exact facial features, eye shape, and facial structure. Maintain the same expression and pose. High detail, professional quality.

INPUT: "10년 후 모습으로 나이들게 해줘"
CLASSIFICATION: ATTRIBUTE_EDIT (age)
OUTPUT: Age this person naturally by approximately 10 years. Add subtle laugh lines around the eyes, slight nasolabial folds, and natural gray streaks in the hair. Preserve the core facial structure and recognizable identity. Keep the same pose and expression.

INPUT: "이 캐릭터를 슬라임으로 바꿔줘"
CLASSIFICATION: SPECIES_TRANSFORM (slime creature)
OUTPUT: Transform this character completely into an adorable slime creature. The entire body becomes a translucent, gelatinous blob with a soft blue-green glow. The face simplifies into cute, rounded features typical of slime creatures - simple dot eyes and a small curved smile. The body should appear bouncy and jiggly with visible light refraction through the gel-like surface. Maintain the same pose composition and background. Fantasy art style, vibrant colors.

INPUT: "엘프로 바꿔줘"
CLASSIFICATION: SPECIES_TRANSFORM (elf)
OUTPUT: Transform this character into an elegant high elf. Give them elongated pointed ears, slightly angular and ethereal facial features, and luminous skin with a subtle magical glow. The eyes should appear larger and more almond-shaped with an otherworldly sparkle. Keep the same pose, expression intent, and background composition. Fantasy portrait style, high detail.

INPUT: "정장을 캐주얼 후드티로 바꿔줘"
CLASSIFICATION: ATTRIBUTE_EDIT (clothing)
OUTPUT: Change the formal suit to a casual, comfortable gray hoodie. Keep the person's face, expression, and pose exactly the same. Maintain the same background and lighting. Natural, relaxed look.
</examples>

<output_rules>
- Return ONLY the English prompt text
- No JSON, no quotes, no explanations, no classification labels
- The prompt should be 2-4 sentences, specific and actionable
- Always include quality modifiers appropriate to the edit type
</output_rules>"""


class PromptService:
    """Service for generating optimized prompts using Claude via LangChain.

    Attributes:
        llm: LangChain ChatModel instance for prompt generation.
             Can be injected for testing purposes.
    """

    def __init__(self, llm=None):
        """Initialize PromptService.

        Args:
            llm: Optional LangChain ChatModel to use. If not provided,
                 creates ChatBedrockConverse with settings from environment.
                 Pass a mock LLM for unit testing.
        """
        if llm is not None:
            self.llm = llm
        else:
            settings = get_settings()
            # Bedrock 전용 자격증명 및 리전 사용
            self.llm = ChatBedrockConverse(
                model=settings.bedrock_claude_model_id,
                region_name=settings.aws_bedrock_default_region,
                aws_access_key_id=settings.aws_bedrock_access_key_id,
                aws_secret_access_key=settings.aws_bedrock_secret_access_key,
            )

    def create_character_prompt(self, user_message: str) -> str:
        """
        Generate optimized prompt for character image creation.

        Args:
            user_message: User's character description in any language

        Returns:
            Optimized English prompt for Nova Canvas

        Raises:
            RuntimeError: If LLM call fails. Error is propagated for consistent
                         error handling across all prompt methods.
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
            raise RuntimeError(
                f"Failed to generate character prompt via Claude. "
                f"Please check your Bedrock configuration. Original error: {e}"
            ) from e

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
