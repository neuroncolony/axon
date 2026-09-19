"""Model roster. ids are OpenRouter ids. Pricing is USD per 1M tokens (input, output) used for billing the compute pool.
Keep this honest: if a model is not on OpenRouter, it cannot be selected."""
MODELS = [
  {"id":"openai/gpt-4o","name":"GPT-4o","provider":"OpenAI","ctx":128000,"in":2.5,"out":10.0,"tag":"flagship"},
  {"id":"openai/gpt-4o-mini","name":"GPT-4o mini","provider":"OpenAI","ctx":128000,"in":0.15,"out":0.6,"tag":"fast"},
  {"id":"anthropic/claude-sonnet-4","name":"Claude Sonnet 4","provider":"Anthropic","ctx":200000,"in":3.0,"out":15.0,"tag":"flagship"},
  {"id":"anthropic/claude-3.5-haiku","name":"Claude 3.5 Haiku","provider":"Anthropic","ctx":200000,"in":0.8,"out":4.0,"tag":"fast"},
  {"id":"google/gemini-2.5-flash","name":"Gemini 2.5 Flash","provider":"Google","ctx":1000000,"in":0.3,"out":2.5,"tag":"fast"},
  {"id":"google/gemma-3-27b-it","name":"Gemma 3 27B","provider":"Google","ctx":131072,"in":0.1,"out":0.2,"tag":"open"},
  {"id":"x-ai/grok-4","name":"Grok 4","provider":"xAI","ctx":256000,"in":3.0,"out":15.0,"tag":"flagship"},
  {"id":"deepseek/deepseek-chat-v3-0324","name":"DeepSeek V3","provider":"DeepSeek","ctx":163840,"in":0.3,"out":0.88,"tag":"open"},
  {"id":"meta-llama/llama-guard-4-12b","name":"Llama Guard 4 12B","provider":"Meta","ctx":163840,"in":0.18,"out":0.18,"tag":"safety"},
  {"id":"mistralai/mistral-large-2411","name":"Mistral Large","provider":"Mistral","ctx":131072,"in":2.0,"out":6.0,"tag":"flagship"},
  {"id":"qwen/qwen3-235b-a22b","name":"Qwen3 235B","provider":"Qwen","ctx":40960,"in":0.2,"out":0.6,"tag":"open"},
]
BY_ID = {m["id"]: m for m in MODELS}
def cost_usd(model_id, prompt_tokens, completion_tokens):
    m = BY_ID.get(model_id)
    if not m: return 0.0
    return prompt_tokens / 1e6 * m["in"] + completion_tokens / 1e6 * m["out"]
