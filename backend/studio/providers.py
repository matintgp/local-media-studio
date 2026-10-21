"""Opt-in text planning, never tools, media uploads or model downloads."""
import asyncio
import json
import os
from typing import Literal
from urllib.parse import urlsplit
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['disabled', 'ollama', 'openai'] = 'disabled'
    base_url: str = 'http://127.0.0.1:11434'
    model: str = Field(default='', max_length=120)
    api_key: str = Field(default='', max_length=512, repr=False)

    @field_validator('base_url')
    @classmethod
    def safe_endpoint(cls, value):
        u = urlsplit(value)
        local = u.hostname in ('127.0.0.1', 'localhost', '::1')
        remote = u.scheme == 'https' and u.hostname == 'api.openai.com' and u.port in (None, 443)
        if u.username or u.password or u.query or u.fragment or not (remote or (local and u.scheme in ('http', 'https'))):
            raise ValueError('Use loopback HTTP(S) or https://api.openai.com/v1')
        if u.path.rstrip('/') not in ('', '/v1'): raise ValueError('Base path must be empty or /v1')
        return value.rstrip('/')

    @model_validator(mode='after')
    def endpoint_matches_provider(self):
        u = urlsplit(self.base_url)
        if self.provider == 'openai' and (u.hostname != 'api.openai.com' or u.path != '/v1'):
            raise ValueError('OpenAI requires https://api.openai.com/v1')
        if self.provider == 'ollama' and (u.hostname not in ('127.0.0.1','localhost','::1') or u.path):
            raise ValueError('Ollama requires a loopback base URL without a path')
        return self

class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=6000)

class ChatIn(BaseModel):
    project_id: str
    language: Literal['fa', 'en'] = 'fa'
    messages: list[Message] = Field(min_length=1, max_length=12)
    allow_remote: bool = False

class PlanStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['image', 'video', 'speech', 'music', 'ambience']
    prompt: str = Field(min_length=1, max_length=4000)
    language: Literal['fa', 'en'] = 'fa'

class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reply: str = Field(min_length=1, max_length=6000)
    name: str = Field(default='Assistant plan', min_length=1, max_length=100)
    steps: list[PlanStep] = Field(default_factory=list, max_length=8)

SYSTEM = '''You are a media production assistant. Reply in the requested language.
Return only JSON with keys reply (text), name (short title), steps (array).
For discussion/questions leave steps empty. When asked to create media, propose
an ordered plan, never claim anything has been generated. Each step has only
kind (image/video/speech/music/ambience), prompt (English visual/music prompt or
literal narration text), language (fa/en). Video needs an earlier image; ambience
needs an earlier video. Maximum 8 steps. These are suggestions awaiting review.
No commands, downloads, paths, URLs, provider settings, or tool calls.
Installed presets: image 1024 square, video 5 seconds, music 24 seconds;
speech Persian/English. Never promise long-form video from a single generation.'''

class Assistant:
    def __init__(self, root):
        self.path = root / 'assistant.local.json'
        self.lock = asyncio.Lock()
        self.config = ProviderConfig()
        if self.path.exists(): self.config = ProviderConfig.model_validate_json(self.path.read_text('utf-8'))
        self.key = os.getenv('STUDIO_ASSISTANT_API_KEY', '')

    def public(self):
        return self.config.model_dump(exclude={'api_key'}) | {'has_key': bool(self.key), 'remote': urlsplit(self.config.base_url).hostname == 'api.openai.com', 'local_cpu_only': True}

    def configure(self, cfg):
        if cfg.provider == 'disabled': self.key = ''
        elif cfg.provider != self.config.provider: self.key = os.getenv('STUDIO_ASSISTANT_API_KEY', '')
        self.key = cfg.api_key or self.key
        self.config = cfg.model_copy(update={'api_key': ''})
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(self.config.model_dump_json(exclude={'api_key'}), 'utf-8')
        os.replace(tmp, self.path)
        return self.public()

    async def suggest(self, request):
        c = self.config
        if c.provider == 'disabled' or not c.model.strip(): raise ValueError('Configure and save an assistant provider and installed model first')
        remote = urlsplit(c.base_url).hostname == 'api.openai.com'
        if remote and (not request.allow_remote or not self.key): raise ValueError('Remote text sharing consent and a backend API key are required')
        if self.lock.locked(): raise ValueError('Assistant is busy; wait before sending again')
        messages = [{'role': 'system', 'content': SYSTEM + '\nLanguage: ' + request.language}] + [m.model_dump() for m in request.messages]
        async with self.lock:
            payload = {'model': c.model, 'messages': messages, 'stream': False}
            headers = {}
            if c.provider == 'ollama':
                if remote: raise ValueError('Ollama must use a loopback endpoint')
                # Enforced CPU use avoids taking the media queue GPU slot. No persistent model residency.
                payload.update(format='json', keep_alive=0, options={'num_gpu': 0, 'num_ctx': 8192, 'num_predict': 2200})
                endpoint = c.base_url + '/api/chat'
            else:
                if not remote: raise ValueError('OpenAI provider requires https://api.openai.com/v1')
                payload['response_format'] = {'type': 'json_object'}
                headers['Authorization'] = 'Bearer ' + self.key
                endpoint = c.base_url + '/chat/completions'
            try:
                async with httpx.AsyncClient(timeout=180, follow_redirects=False, trust_env=False) as client:
                    async with client.stream('POST', endpoint, json=payload, headers=headers) as r:
                        if r.status_code != 200: raise ValueError(f'Assistant provider returned HTTP {r.status_code}; check endpoint, model and credentials')
                        data = bytearray()
                        async for chunk in r.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 256000: raise ValueError('Assistant response exceeds size limit')
                doc = json.loads(data)
                text = doc['message']['content'] if c.provider == 'ollama' else doc['choices'][0]['message']['content']
                plan = Plan.model_validate_json(text)
                seen = set()
                for step in plan.steps:
                    if step.kind == 'video' and 'image' not in seen: raise ValueError('Plan video needs a preceding image')
                    if step.kind == 'ambience' and 'video' not in seen: raise ValueError('Plan ambience needs a preceding video')
                    seen.add(step.kind)
                return plan.model_dump()
            except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as e:
                raise ValueError('Provider unavailable or returned an invalid planning response; nothing was executed') from e
