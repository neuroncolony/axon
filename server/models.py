"""Model roster. ids are OpenRouter ids. Pricing is USD per 1M tokens (input, output) used for billing the compute pool.
Keep this honest: if a model is not on OpenRouter, it cannot be selected."""
MODELS = [
  {"id":"openai/gpt-6-astra-pro","name":"GPT-6 Astra Pro","provider":"OpenAI","ctx":1050000,"in":10.0,"out":50.0,"tag":"flagship"},
  {"id":"openai/gpt-6-astra","name":"GPT-6 Astra","provider":"OpenAI","ctx":1050000,"in":10.0,"out":50.0,"tag":"flagship"},
  {"id":"openai/gpt-5.6-terra","name":"GPT-5.6 Terra","provider":"OpenAI","ctx":1050000,"in":2.0,"out":12.0,"tag":"balanced"},
  {"id":"openai/gpt-5.6-luna","name":"GPT-5.6 Luna","provider":"OpenAI","ctx":1050000,"in":0.2,"out":1.2,"tag":"fast"},
  {"id":"anthropic/claude-opus-5","name":"Claude Opus 5","provider":"Anthropic","ctx":1000000,"in":5.0,"out":25.0,"tag":"flagship"},
  {"id":"anthropic/claude-fable-5.1","name":"Claude Fable 5.1","provider":"Anthropic","ctx":1000000,"in":10.0,"out":50.0,"tag":"flagship"},
  {"id":"anthropic/claude-sonnet-5","name":"Claude Sonnet 5","provider":"Anthropic","ctx":1000000,"in":2.0,"out":10.0,"tag":"balanced"},
  {"id":"google/gemini-3.8-flash","name":"Gemini 3.8 Flash","provider":"Google","ctx":1048576,"in":0.75,"out":3.75,"tag":"balanced"},
  {"id":"google/gemini-3.5-flash-lite","name":"Gemini 3.5 Flash Lite","provider":"Google","ctx":1048576,"in":0.3,"out":2.5,"tag":"fast"},
  {"id":"x-ai/grok-4.6","name":"Grok 4.6","provider":"xAI","ctx":500000,"in":2.0,"out":6.0,"tag":"flagship"},
  {"id":"x-ai/grok-4.5","name":"Grok 4.5","provider":"xAI","ctx":500000,"in":2.0,"out":6.0,"tag":"balanced"},
  {"id":"deepseek/deepseek-v4-pro-0813","name":"DeepSeek V4 Pro","provider":"DeepSeek","ctx":1048576,"in":0.66,"out":1.98,"tag":"open"},
  {"id":"deepseek/deepseek-v4.1-flash","name":"DeepSeek V4.1 Flash","provider":"DeepSeek","ctx":1048576,"in":0.15,"out":0.6,"tag":"fast"},
  {"id":"qwen/qwen3.8-max-0902","name":"Qwen3.8 Max","provider":"Qwen","ctx":1000000,"in":2.0,"out":6.0,"tag":"flagship"},
  {"id":"qwen/qwen3.8-flash","name":"Qwen3.8 Flash","provider":"Qwen","ctx":1000000,"in":0.15,"out":0.47,"tag":"fast"},
  {"id":"qwen/qwen3.8-27b","name":"Qwen3.8 27B","provider":"Qwen","ctx":1000000,"in":0.42,"out":3.0,"tag":"open"},
  {"id":"moonshotai/kimi-k3","name":"Kimi K3","provider":"Moonshot","ctx":1048576,"in":1.7,"out":8.5,"tag":"open"},
  {"id":"z-ai/glm-5.3","name":"GLM 5.3","provider":"Z.ai","ctx":1310720,"in":0.896,"out":2.816,"tag":"open"},
  {"id":"z-ai/glm-5.3-flash","name":"GLM 5.3 Flash","provider":"Z.ai","ctx":1310720,"in":0.09,"out":0.3,"tag":"fast"},
  {"id":"minimax/minimax-m2","name":"MiniMax M2","provider":"MiniMax","ctx":204800,"in":0.255,"out":1.02,"tag":"open"},
  {"id":"nvidia/nemotron-3-ultra-550b-a55b","name":"Nemotron 3 Ultra","provider":"NVIDIA","ctx":262144,"in":0.6,"out":2.4,"tag":"open"},
  {"id":"perplexity/sonar-pro","name":"Sonar Pro","provider":"Perplexity","ctx":200000,"in":3.0,"out":15.0,"tag":"search"},
  {"id":"meta-llama/llama-guard-4-12b","name":"Llama Guard 4 12B","provider":"Meta","ctx":163840,"in":0.18,"out":0.18,"tag":"safety"},
  {"id":"nvidia/nemotron-3.5-content-safety","name":"Nemotron 3.5 Safety","provider":"NVIDIA","ctx":131072,"in":0.2,"out":0.2,"tag":"safety"},
]
BY_ID = {m["id"]: m for m in MODELS}
def cost_usd(model_id, prompt_tokens, completion_tokens):
    m = BY_ID.get(model_id)
    if not m: return 0.0
    return prompt_tokens / 1e6 * m["in"] + completion_tokens / 1e6 * m["out"]
