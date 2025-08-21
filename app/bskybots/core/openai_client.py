import os, json
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt

# Build a Tenacity "wait" policy that works across versions
try:
    from tenacity import wait_exponential
    WAIT_POLICY = wait_exponential(multiplier=1, min=1, max=10)
except Exception:
    try:
        from tenacity import wait_random_exponential
        WAIT_POLICY = wait_random_exponential(max=10)
    except Exception:
        from tenacity import wait_fixed
        WAIT_POLICY = wait_fixed(2)

class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.7, system_prompt: Optional[str] = None):
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = float(temperature)
        self.system_prompt = system_prompt or "You are a helpful assistant."

    @retry(stop=stop_after_attempt(3), wait=WAIT_POLICY)
    def classify_and_generate(
        self,
        *,
        text: str,
        author: str,
        nsfw_allowed: bool,
        persona: Dict[str, Any],
        thread_context: Optional[Dict[str, Any]] = None,
        target_lang: str = "en",
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps({
                "post_text": text,
                "author": author,
                "nsfw_allowed": nsfw_allowed,
                "target_lang": target_lang,
                "persona": persona,
                "thread_context": thread_context or {}
            })}
        ]
        r = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=self.temperature, max_tokens=180
        )
        out = r.choices[0].message.content
        try:
            data = json.loads(out)
        except Exception:
            data = {"should_reply": False, "reply": ""}
        return data
