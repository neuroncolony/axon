"""Model roster. ids are OpenRouter ids. Pricing is USD per 1M tokens (input, output) used for billing the compute pool.
Keep this honest: if a model is not on OpenRouter, it cannot be selected.
Every model carries description, context (tokens), inputPerM and outputPerM (USD per 1M tokens).
Prices are approximations of public OpenRouter list prices, so each row is marked approx: True."""
MODELS = [
  {"id":"openai/gpt-6-astra-pro","name":"GPT-6 Astra Pro","provider":"OpenAI","ctx":1050000,"in":10.0,"out":50.0,"tag":"flagship",
   "description":"OpenAI's flagship reasoning model, tuned for long agentic tasks.","context":1050000,"inputPerM":10.0,"outputPerM":50.0,"approx":True},
  {"id":"openai/gpt-6-astra","name":"GPT-6 Astra","provider":"OpenAI","ctx":1050000,"in":10.0,"out":50.0,"tag":"flagship",
   "description":"OpenAI's flagship general model for hard reasoning and writing.","context":1050000,"inputPerM":10.0,"outputPerM":50.0,"approx":True},
  {"id":"openai/gpt-5.6-terra","name":"GPT-5.6 Terra","provider":"OpenAI","ctx":1050000,"in":2.0,"out":12.0,"tag":"balanced",
   "description":"Balanced OpenAI model with a million token context at mid pricing.","context":1050000,"inputPerM":2.0,"outputPerM":12.0,"approx":True},
  {"id":"openai/gpt-5.6-luna","name":"GPT-5.6 Luna","provider":"OpenAI","ctx":1050000,"in":0.2,"out":1.2,"tag":"fast",
   "description":"Fast, cheap OpenAI model for chat and short summaries.","context":1050000,"inputPerM":0.2,"outputPerM":1.2,"approx":True},
  {"id":"anthropic/claude-opus-5","name":"Claude Opus 5","provider":"Anthropic","ctx":1000000,"in":5.0,"out":25.0,"tag":"flagship",
   "description":"Anthropic's flagship model for careful reasoning and code.","context":1000000,"inputPerM":5.0,"outputPerM":25.0,"approx":True},
  {"id":"anthropic/claude-fable-5.1","name":"Claude Fable 5.1","provider":"Anthropic","ctx":1000000,"in":10.0,"out":50.0,"tag":"flagship",
   "description":"Anthropic's top tier creative and long form writing model.","context":1000000,"inputPerM":10.0,"outputPerM":50.0,"approx":True},
  {"id":"anthropic/claude-sonnet-5","name":"Claude Sonnet 5","provider":"Anthropic","ctx":1000000,"in":2.0,"out":10.0,"tag":"balanced",
   "description":"Anthropic's balanced workhorse for everyday coding and analysis.","context":1000000,"inputPerM":2.0,"outputPerM":10.0,"approx":True},
  {"id":"google/gemini-3.8-flash","name":"Gemini 3.8 Flash","provider":"Google","ctx":1048576,"in":0.75,"out":3.75,"tag":"balanced",
   "description":"Google's fast multimodal model with a huge context window.","context":1048576,"inputPerM":0.75,"outputPerM":3.75,"approx":True},
  {"id":"google/gemini-3.5-flash-lite","name":"Gemini 3.5 Flash Lite","provider":"Google","ctx":1048576,"in":0.3,"out":2.5,"tag":"fast",
   "description":"Google's cheapest fast model for high volume chat.","context":1048576,"inputPerM":0.3,"outputPerM":2.5,"approx":True},
  {"id":"x-ai/grok-4.6","name":"Grok 4.6","provider":"xAI","ctx":500000,"in":2.0,"out":6.0,"tag":"flagship",
   "description":"xAI's flagship model with real time knowledge and sharp wit.","context":500000,"inputPerM":2.0,"outputPerM":6.0,"approx":True},
  {"id":"x-ai/grok-4.5","name":"Grok 4.5","provider":"xAI","ctx":500000,"in":2.0,"out":6.0,"tag":"balanced",
   "description":"xAI's balanced model for chat, search and reasoning.","context":500000,"inputPerM":2.0,"outputPerM":6.0,"approx":True},
  {"id":"deepseek/deepseek-v4-pro-0813","name":"DeepSeek V4 Pro","provider":"DeepSeek","ctx":1048576,"in":0.66,"out":1.98,"tag":"open",
   "description":"DeepSeek's open weights flagship for math and code.","context":1048576,"inputPerM":0.66,"outputPerM":1.98,"approx":True},
  {"id":"deepseek/deepseek-v4.1-flash","name":"DeepSeek V4.1 Flash","provider":"DeepSeek","ctx":1048576,"in":0.15,"out":0.6,"tag":"fast",
   "description":"DeepSeek's fastest open model, priced for high volume agents.","context":1048576,"inputPerM":0.15,"outputPerM":0.6,"approx":True},
  {"id":"qwen/qwen3.8-max-0902","name":"Qwen3.8 Max","provider":"Qwen","ctx":1000000,"in":2.0,"out":6.0,"tag":"flagship",
   "description":"Qwen's largest open weights model for hard multilingual tasks.","context":1000000,"inputPerM":2.0,"outputPerM":6.0,"approx":True},
  {"id":"qwen/qwen3.8-flash","name":"Qwen3.8 Flash","provider":"Qwen","ctx":1000000,"in":0.15,"out":0.47,"tag":"fast",
   "description":"Qwen's fast small model for cheap, snappy chat.","context":1000000,"inputPerM":0.15,"outputPerM":0.47,"approx":True},
  {"id":"qwen/qwen3.8-27b","name":"Qwen3.8 27B","provider":"Qwen","ctx":1000000,"in":0.42,"out":3.0,"tag":"open",
   "description":"Qwen's mid size open model, a good price to quality middle ground.","context":1000000,"inputPerM":0.42,"outputPerM":3.0,"approx":True},
  {"id":"moonshotai/kimi-k3","name":"Kimi K3","provider":"Moonshot","ctx":1048576,"in":1.7,"out":8.5,"tag":"open",
   "description":"Moonshot's open long context model for research and agents.","context":1048576,"inputPerM":1.7,"outputPerM":8.5,"approx":True},
  {"id":"z-ai/glm-5.3","name":"GLM 5.3","provider":"Z.ai","ctx":1310720,"in":0.896,"out":2.816,"tag":"open",
   "description":"Z.ai's open flagship for coding and tool use.","context":1310720,"inputPerM":0.896,"outputPerM":2.816,"approx":True},
  {"id":"z-ai/glm-5.3-flash","name":"GLM 5.3 Flash","provider":"Z.ai","ctx":1310720,"in":0.09,"out":0.3,"tag":"fast",
   "description":"Z.ai's cheapest open model for bulk background work.","context":1310720,"inputPerM":0.09,"outputPerM":0.3,"approx":True},
  {"id":"minimax/minimax-m2","name":"MiniMax M2","provider":"MiniMax","ctx":204800,"in":0.255,"out":1.02,"tag":"open",
   "description":"MiniMax's open model tuned for agentic tool calling.","context":204800,"inputPerM":0.255,"outputPerM":1.02,"approx":True},
  {"id":"nvidia/nemotron-3-ultra-550b-a55b","name":"Nemotron 3 Ultra","provider":"NVIDIA","ctx":262144,"in":0.6,"out":2.4,"tag":"open",
   "description":"NVIDIA's large open mixture of experts model for reasoning.","context":262144,"inputPerM":0.6,"outputPerM":2.4,"approx":True},
  {"id":"perplexity/sonar-pro","name":"Sonar Pro","provider":"Perplexity","ctx":200000,"in":3.0,"out":15.0,"tag":"search",
   "description":"Perplexity's search grounded model with live web citations.","context":200000,"inputPerM":3.0,"outputPerM":15.0,"approx":True},
  {"id":"meta-llama/llama-guard-4-12b","name":"Llama Guard 4 12B","provider":"Meta","ctx":163840,"in":0.18,"out":0.18,"tag":"safety",
   "description":"Meta's open safety classifier for prompt and response moderation.","context":163840,"inputPerM":0.18,"outputPerM":0.18,"approx":True},
  {"id":"nvidia/nemotron-3.5-content-safety","name":"Nemotron 3.5 Safety","provider":"NVIDIA","ctx":131072,"in":0.2,"out":0.2,"tag":"safety",
   "description":"NVIDIA's open content safety model for filtering outputs.","context":131072,"inputPerM":0.2,"outputPerM":0.2,"approx":True},
]
BY_ID = {m["id"]: m for m in MODELS}
def cost_usd(model_id, prompt_tokens, completion_tokens):
    m = BY_ID.get(model_id)
    if not m: return 0.0
    return prompt_tokens / 1e6 * m["in"] + completion_tokens / 1e6 * m["out"]
