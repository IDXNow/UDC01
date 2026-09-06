# UDC01 Configuration Guide

Configuration is where you shape UDC01 to your specific environment - which models run which roles, how aggressively to retry failed conversions, whether to run agents in parallel. This guide explains the full configuration system: what each file controls, how settings override each other, and how to take advantage of the three-level hierarchy that makes UDC01 both flexible and predictable.

---

## Table of Contents

- [Configuration Files Overview](#configuration-files-overview)
- [Runtime Priority: Which Value Wins?](#runtime-priority-which-value-wins)
- [Provider Profiles](#provider-profiles)
- [Custom Endpoints (the local profile)](#custom-endpoints-the-local-profile)
- [Agent Configuration Hierarchy](#agent-configuration-hierarchy)
  - [Level 1 - Global Default](#level-1--global-default)
  - [Level 2 - Role-Group Default](#level-2--role-group-default)
  - [Level 3 - Individual Agent](#level-3--individual-agent)
- [Temperature: An Optional Setting](#temperature-an-optional-setting)
- [Thinking & Reasoning](#thinking--reasoning)
- [Complete Example](#complete-example)
- [Quick Reference](#quick-reference)

---

## Configuration Files Overview

UDC01 uses two configuration files, each with a distinct responsibility.

| File | Format | Purpose |
|------|--------|---------|
| `udc01/default_config.json` (or `--config` path) | JSON | Provider connections, agent definitions, file paths, runtime settings |
| Your conversion YAML (e.g. `samples/conversions/sales_invoice_conv.yaml`) | YAML | LLM prompts and instructions for a specific conversion job |

The JSON config defines *who* does the work and *how the system behaves*. The YAML defines *what the agents are told to do* for a particular data format. Keeping these separate means you can run the same conversion instructions against different provider configurations - or the same provider configuration against different conversion types - without duplication.

Specify which files to use at startup:
```bash
python udc01.py --config "my_config.json" --conversion "my_conversion.yaml"
```

---

## Runtime Priority: Which Value Wins?

Settings are applied in layers, each one overriding the previous. **Higher priority wins.** This layered approach means you can establish sensible defaults in your config file and override specific settings at runtime without maintaining multiple copies of the same file.

```
1. Code defaults       (lowest)  - built-in fallbacks, always present
2. Config file                   - your JSON config, merged over code defaults
3. Conversion YAML               - top-level keys in the recipe, merged over the config file
4. CLI arguments       (highest) - --file, --folder, --pattern, --output-folder,
                                   --parallel-agents, --include-prior-output-on-retry
```

**Example:**
The config file sets `"folder": "data/"`. You run with `--folder "inputs/"`. The `inputs/` folder is used.

The conversion YAML layer means a recipe can carry runtime behavior alongside its prompts. Setting `include_prior_output_on_retry: true` as a top-level key in a recipe overrides the config file for that conversion - useful when a specific conversion type converges faster with the prior output in the retry prompt, without changing the setting globally.  The CLI flag still wins over both: `--include-prior-output-on-retry` forces it on, `--no-include-prior-output-on-retry` forces it off, and omitting the flag defers to the lower layers.

---

## Provider Profiles

The `providers` section is where you define connection details for each LLM service you want UDC01 to talk to. Each profile can also declare its own `default_model` and `default_temperature` - these become the baseline for any agent that uses that provider, which means you set model preferences once per provider rather than on every individual agent.

```json
"providers": {
  "openai": {
    "base_url": "https://api.openai.com",
    "endpoint": "v1/chat/completions",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer",
    "request_format": "openai",
    "default_model": "gpt-4o-mini"
  },
  "anthropic": {
    "base_url": "https://api.anthropic.com",
    "endpoint": "v1/messages",
    "auth_header": "x-api-key",
    "request_format": "anthropic",
    "default_model": "claude-sonnet-5",
    "supports_temperature": false,
    "default_max_tokens": 16000
  },
  "google": {
    "base_url": "https://generativelanguage.googleapis.com",
    "endpoint": "v1beta/models/{model}:generateContent",
    "auth_header": "x-goog-api-key",
    "request_format": "google",
    "default_model": "gemini-2.5-flash",
    "default_temperature": 1
  },
  "local": {
    "base_url": "http://localhost:1234",
    "endpoint": "v1/chat/completions",
    "request_format": "openai",
    "default_max_tokens": 16000,
    "default_model": "openai/gpt-oss-20b"
  },
  "ollama": {
    "base_url": "http://localhost:11434",
    "endpoint": "v1/chat/completions",
    "request_format": "openai",
    "default_max_tokens": 16000,
    "default_model": "qwen3:8b"
  }
}
```

**Provider profile fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `base_url` | Yes | Base URL for the provider API |
| `endpoint` | Yes | API endpoint path. Use `{model}` placeholder for Google-style URLs |
| `request_format` | Yes | Payload format: `openai`, `anthropic`, or `google` |
| `auth_header` | No | HTTP header name for authentication |
| `auth_prefix` | No | Prefix before the API key (e.g. `"Bearer"`) |
| `default_model` | No | Default model for agents using this provider |
| `default_temperature` | No | Default temperature for agents using this provider.  Omit for providers that don't support it |
| `token_param` | No | Field name for the output-token cap. Defaults to `max_tokens`.  Set to `max_completion_tokens` for OpenAI - GPT-5.x rejects `max_tokens` outright. |
| `supports_temperature` | No | Defaults to `true`.  Set to `false` for providers whose models reject or ignore sampling parameters, and UDC01 omits `temperature` for agents that did not set one |
| `strip_reasoning` | No | OpenAI-format profiles only.  Defaults to `true` - UDC01 removes inline `<think>` blocks and moves a separate `reasoning_content` / `reasoning` field off the message before anything parses it.  Set to `false` to keep raw model output |

`token_param` and `supports_temperature` are profile *defaults*, not fixed properties - a role-group or an individual agent can override either.  See [Resolution order](#resolution-order-first-match-wins).

---

## Custom Endpoints (the `local` profile)

`local` is a name, not a constraint. It's UDC01's bring-your-own-endpoint slot: anything that speaks the OpenAI chat-completions format works through it, whether it runs on your laptop, a GPU box down the hall, or a cloud region. LM Studio and Ollama are the common cases, but nothing in the code assumes localhost - `base_url`, `endpoint`, and `auth_header` are the entire contract.

Provider names are arbitrary keys, so copy the profile and rename it when you're pointing at more than one endpoint.

### Worked examples

| Host | `base_url` | `endpoint` | Auth |
|------|------------|------------|------|
| LM Studio | `http://localhost:1234` | `v1/chat/completions` | none |
| Ollama | `http://localhost:11434` | `v1/chat/completions` | none |
| vLLM / llama.cpp | `https://gpu.internal:8000` | `v1/chat/completions` | `Authorization` + `Bearer`, if started with a key |
| LiteLLM proxy | `https://litellm.corp.net` | `v1/chat/completions` | `Authorization` + `Bearer` |
| Azure OpenAI | `https://<resource>.openai.azure.com` | `openai/deployments/<deployment>/chat/completions?api-version=2024-10-21` | `api-key`, no prefix |
| Azure AI Foundry | `https://<name>.<region>.models.ai.azure.com` | `v1/chat/completions` | `Authorization` + `Bearer` |

Azure OpenAI is the one that looks unusual: the deployment name sits in the URL path, the API version rides along as a query parameter, and `model` in the payload should be the deployment name as well. UDC01 joins `base_url` and `endpoint` as written, so the query string survives intact.

**AWS Bedrock** is the exception worth calling out. Its native API requires SigV4 request signing and UDC01 sends static headers, so it won't work directly. Put LiteLLM or the Bedrock Access Gateway in front and point `local` at that - the proxy signs, UDC01 keeps talking OpenAI.

### Authenticating a remote endpoint

Once you leave localhost you generally need a key. That's two fields on the profile plus one entry in `api_keys`, which is keyed by provider name:

```json
"providers": {
  "local": {
    "base_url": "https://gpu.internal:8000",
    "endpoint": "v1/chat/completions",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer",
    "request_format": "openai",
    "default_max_tokens": 16000,
    "default_model": "meta-llama/Llama-3.3-70B-Instruct"
  }
},
"api_keys": {
  "local": "${LOCAL_API_KEY}"
}
```

`${VAR}` resolves from the environment when the config loads, so credentials stay out of the file. Set `auth_prefix` to `""` for headers that take a bare key, as Azure's `api-key` does. Leave `auth_header` as `null` and UDC01 sends no credentials at all - which is what you want for LM Studio and Ollama.

Remote endpoints also argue for a longer `api_timeout` than a local one, since you're adding network latency to generation time.

### Model IDs go over the wire verbatim

Model IDs on these hosts carry a namespace: `openai/gpt-oss-20b`, `qwen/qwen3.5-35b-a3b`, `zai-org/glm-4.6v-flash`. Ollama does the same with tags like `hf.co/user/repo:Q4_K_M`. UDC01 sends the string you configure exactly as written, so copy it from the source of truth:

```bash
lms ls          # LM Studio
ollama list     # Ollama
```

Remote hosts make this stricter rather than looser. vLLM wants the full repo id (`meta-llama/Llama-3.3-70B-Instruct`), a LiteLLM proxy wants its routing prefix (`bedrock/anthropic.claude-sonnet-4-20250514-v1:0`), and Azure OpenAI wants the deployment name. All of those are exact-match; only LM Studio is forgiving enough to resolve a trimmed name, and only when one model is loaded.

Google is the sole exception - its URL needs the bare model name in the path, so UDC01 strips the namespace there and only there.

### Reasoning models need headroom

Nearly every current open model reasons before it answers: gpt-oss, Qwen3.5, GLM-4.7, Granite 4.  That reasoning has to go somewhere, and UDC01 keeps it clear of your output at both ends of the call.

**On the way in**, `default_max_tokens` buys room to think *and* answer.  Both shipped profiles set `16000`.  Set it too low and the model spends the whole budget reasoning, gets cut off before writing anything, and returns empty content - which surfaces in the log as `Response was entirely reasoning, no answer returned`.

**On the way out**, UDC01 strips reasoning before any tag parsing happens.  LM Studio returns it in `reasoning_content` and Ollama in `reasoning`; both get moved off the message.  Models that inline it instead have their `<think>`, `<thinking>`, and `<reasoning>` blocks removed, including the prefilled-opener style where only a closing tag arrives.

That second part matters more than it looks, because UDC01 reads verdicts out of model text.  A validator reasoning *"so `<isvalid>False</isvalid>` - no wait, the totals do match"* would otherwise have its rehearsal counted as its vote, quietly corrupting 2/3 consensus.  Verdict parsing takes the **last** `<isvalid>` rather than the first as a second line of defence, so the final answer wins even when reasoning arrives in a wrapper UDC01 doesn't recognise.

Set `"strip_reasoning": false` on the profile when you want to see exactly what the model emitted.

### Parallel agents and one backend

`parallel_agents: true` fires two verification or validation agents at once.  Against a hosted endpoint that roughly halves wall time, because the service handles concurrency.  Against a single loaded local model it doesn't, since the server queues the second request behind the first - and both race the same `api_timeout`.  On one instance, either set `parallel_agents: false` or give `api_timeout` enough room to cover two generations back to back.

---

## Agent Configuration Hierarchy

This is the heart of UDC01's configuration flexibility. Model, provider, and temperature can be set at **three levels**, and the most specific level always wins. The hierarchy exists because different roles often have different needs - you might want a frontier model doing the conversion, a faster/cheaper model doing verification, and the freedom to override that for one specific agent without touching anything else.

```
Level 1: Global default         (default_provider at config top level)
Level 2: Role-group default     (default_provider on an agent group)
Level 3: Individual agent       (provider / model / temperature on one agent)
```

### Level 1 - Global Default

Set at the top of your config. Every agent uses this provider unless something more specific overrides it. This is your baseline - the provider you use most of the time.

```json
{
  "default_provider": "google"
}
```

The selected provider's `default_model` and `default_temperature` (from the `providers` section) automatically apply to every agent.

---

### Level 2 - Role-Group Default

When all agents in a role should share a provider and model, wrap the group in an object with `default_provider` (and optionally `default_model` / `default_temperature`). This overrides the global default for every agent in that role, without requiring you to set it individually on each one.

```json
"agents": {
  "data_verifier": {
    "default_provider": "anthropic",
    "default_model": "claude-haiku-4-5-20251001",
    "agents": [
      { "name": "Jane Dirac",    "role": "verify", ... },
      { "name": "Chris Einstein","role": "verify", ... },
      { "name": "Nathan Fourier","role": "verify", ... }
    ]
  }
}
```

All three verifiers now use Anthropic / `claude-haiku-4-5-20251001`, regardless of the global `default_provider`.

You can set any combination of role-level overrides:

| Key on role-group object | What it overrides |
|--------------------------|-------------------|
| `default_provider` | Global `default_provider` |
| `default_model` | Provider profile's `default_model` |
| `default_temperature` | Provider profile's `default_temperature` |
| `default_thinking_budget` | Provider profile's `default_thinking_budget` |
| `default_reasoning_effort` | Provider profile's `default_reasoning_effort` |
| `default_max_tokens` | Provider profile's `default_max_tokens` |
| `default_supports_temperature` | Provider profile's `supports_temperature` |
| `default_token_param` | Provider profile's `token_param` |

> **An agent that names its own profile stops inheriting these.**  Role-group values are scoped to the role's profile, so an agent setting `provider` takes its own profile's defaults instead.  Give that agent whatever it needs directly.

The flat array format (without a wrapper object) also works and simply inherits global defaults:

```json
"data_verifier": [
  { "name": "Jane Dirac", "role": "verify", ... },
  ...
]
```

---

### Level 3 - Individual Agent

When one specific agent needs different settings - a different model for a critical conversion step, a lower temperature for a validation agent, a completely different provider - set it directly on that agent. This overrides everything above it.

```json
"agents": {
  "data_verifier": {
    "default_provider": "anthropic",
    "agents": [
      {
        "name": "Jane Dirac",
        "role": "verify"
        // inherits anthropic + anthropic's default_model
      },
      {
        "name": "Chris Einstein",
        "role": "verify",
        "provider": "openai",
        "model": "gpt-5.4-mini",
        // fully overrides - uses OpenAI gpt-5.4-mini at temperature 0.5
      }
    ]
  }
}
```

**Agent-level fields:**

| Field | Description |
|-------|-------------|
| `provider` | Override the provider for this agent only |
| `model` | Override the model for this agent only |
| `temperature` | Override the temperature for this agent only |

---

## Temperature: An Optional Setting

Temperature is not required at the top level, and that's intentional. Some models - particularly OpenAI's o-series reasoning models - reject the `temperature` parameter entirely. If temperature is not set at any level in the hierarchy, UDC01 simply omits it from the API request, which is exactly what those models need.

**Resolution order for temperature:**

```
1. Agent-level "temperature"                          -> use it
2. Role-group "default_temperature"                   -> use it
3. Provider profile "default_temperature"             -> use it
4. Global "default_temperature"                       -> use it
5. None of the above                                  -> field omitted from request
```

**`supports_temperature` is a default, not a veto.**  Setting it `false` on a provider profile means "models on this profile generally reject temperature", and UDC01 omits the parameter for agents that did not ask for one.  An agent that sets its own `temperature` still gets it.

To enable temperature for a provider, add it to the provider profile:

```json
"anthropic": {
  ...
  "default_temperature": 1
}
```

To set a different temperature for one specific agent:

```json
{ "name": "Nathan Fourier", "role": "verify", "temperature": 0.3 }
```

---

## Thinking & Reasoning

The vendors appear to have converged on the same idea: reasoning depth is an effort level, not a token count.  Anthropic replaced its token budget with adaptive thinking plus an effort setting, Google replaced `thinkingBudget` with a `thinkingLevel` enum, and OpenAI expanded `reasoning_effort`.  UDC01 goes with that convergence - **`reasoning_effort` is available across each provider**, and the same three-level hierarchy (provider profile → role-group → individual agent) applies.

`thinking_budget` still works for older models.  The config key you set decides the wire format, so you don't have to manage this per model.

### Which key to use

| You set | Anthropic sends | Google sends | OpenAI / local / Ollama sends |
|---------|-----------------|--------------|--------------|
| `reasoning_effort` | `thinking: {type: adaptive}` + `output_config: {effort}` | `thinkingConfig: {thinkingLevel}` | `reasoning_effort` |
| `thinking_budget` *(legacy)* | `thinking: {type: enabled, budget_tokens}` | `thinkingConfig: {thinkingBudget}` | n/a |

Local servers share the OpenAI wire format, so `reasoning_effort` reaches them too - gpt-oss honours it through both LM Studio and Ollama.  Models that don't recognise the field generally ignore it.  Controlling *whether* a hybrid model thinks at all (Qwen3.5's `enable_thinking`, for one) isn't reachable from config yet.

Set both and `reasoning_effort` wins, with a warning in the log.  UDC01 never sends both on one request.

**Values.** Anthropic takes `low`, `medium`, `high`, `xhigh`, `max`.  Google takes `minimal`, `low`, `medium`, `high`, defaulting to `medium` on Gemini 3.5 Flash.  OpenAI takes `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, varying by model.


### Setting thinking_budget (legacy - Anthropic & Google)

**In the provider profile** - applies to all agents using that provider:
```json
"anthropic": {
  ...
  "default_thinking_budget": 10000
},
"google": {
  ...
  "default_thinking_budget": 8000
}
```

**In a role-group** - applies to all agents in that role:
```json
"data_conversion": {
  "default_provider": "anthropic",
  "default_thinking_budget": 15000,
  "agents": { "name": "Ted Sagan", "role": "convert" }
}
```

**On an individual agent** - overrides everything above:
```json
{ "name": "Ted Sagan", "role": "convert", "thinking_budget": 12000 }
```

> **Anthropic note:** On models that still accept `budget_tokens`, the API forces `temperature: 1` whenever thinking is on.  UDC01 handles this automatically.  Current models reject `budget_tokens` entirely - use `reasoning_effort` there.
>
> **Budget covers thinking and output together.** Anthropic counts thinking tokens against `max_tokens`, so the cap has to cover both.  See [max_tokens](#max_tokens) below.

### Setting reasoning_effort

**In the provider profile** - applies to all agents using that provider:
```json
"anthropic": {
  ...
  "default_reasoning_effort": "medium"
}
```

**In a role-group:**
```json
"data_conversion": {
  "default_provider": "anthropic",
  "default_reasoning_effort": "high",
  "agents": { "name": "Ted Sagan", "role": "convert" }
}
```

**On an individual agent** - overrides everything above:
```json
{ "name": "Ted Sagan", "role": "convert", "provider": "openai", "model": "gpt-5.4-mini", "reasoning_effort": "high" }
```

On OpenAI, setting `reasoning_effort` omits `temperature` automatically - the two are mutually exclusive once reasoning is on.

### max_tokens

`max_tokens` controls the maximum number of output tokens per API call. It follows the same 3-level hierarchy and is supported by all three providers.

**In the provider profile** - applies to all agents using that provider:
```json
"anthropic": {
  ...
  "default_max_tokens": 16000
}
```

**In a role-group:**
```json
"data_conversion": {
  "default_provider": "anthropic",
  "default_thinking_budget": 10000,
  "default_max_tokens": 16000,
  "agents": { "name": "Ted Sagan", "role": "convert" }
}
```

**On an individual agent:**
```json
{ "name": "Ted Sagan", "role": "convert", "max_tokens": 8000 }
```

---

## Complete Example

This example shows all three levels working together - a global default of Google Gemini, a verifier group that runs on Anthropic, and individual agent overrides for cases where a specific model or provider makes more sense. Read the inline comments to follow the resolution logic.

```json
{
  "default_provider": "google",

  "providers": {
    "google": {
      "base_url": "https://generativelanguage.googleapis.com",
      "endpoint": "v1beta/models/{model}:generateContent",
      "auth_header": "x-goog-api-key",
      "request_format": "google",
      "default_model": "gemini-2.5-flash",
      "default_temperature": 1
    },
    "anthropic": {
      "base_url": "https://api.anthropic.com",
      "endpoint": "v1/messages",
      "auth_header": "x-api-key",
      "request_format": "anthropic",
      "default_model": "claude-sonnet-5-4",
      "default_temperature": 1
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer",
      "request_format": "openai",
      "default_model": "gpt-4.5-mini"
    }
  },

  "agents": {

    "data_verifier": {
      "default_provider": "anthropic",
      "agents": [
        {
          "name": "Jane Dirac",
          "role": "verify",
          "instructions": "data_verification_system_msg",
          "request_instructions": "data_verification_request_msg"
          // -> anthropic / claude-sonnet-4-5 / temperature 1
        },
        {
          "name": "Chris Einstein",
          "role": "verify",
          "model": "claude-haiku-4-5-20251001",
          "instructions": "data_verification_system_msg",
          "request_instructions": "data_verification_request_msg"
          // -> anthropic / claude-haiku-4-5 / temperature 1
        },
        {
          "name": "Nathan Fourier",
          "role": "verify",
          "provider": "openai",
          "model": "gpt-4o",
          "temperature": 0.5,
          "instructions": "data_verification_system_msg",
          "request_instructions": "data_verification_request_msg"
          // -> openai / gpt-4o / temperature 0.5  (fully overridden)
        }
      ]
    },

    "data_conversion": {
      "name": "Ted Sagan",
      "role": "convert",
      "provider": "anthropic",
      "model": "claude-sonnet-4-5"
      // -> anthropic / claude-sonnet-4-5 / no temperature (anthropic profile has default_temperature: 1)
    },

    "data_validator": [
      {
        "name": "Charles Turing",
        "role": "validate",
        "instructions": "data_validation_system_msg",
        "request_instructions": "data_validation_request_msg"
        // -> google (global default) / gemini-2.5-flash / temperature 1
      },
      {
        "name": "Macy Hopper",
        "role": "validate",
        "provider": "openai",
        "instructions": "data_validation_system_msg",
        "request_instructions": "data_validation_request_msg"
        // -> openai / gpt-4o-mini / no temperature (omitted from request)
      },
      {
        "name": "Vanessa Lovelace",
        "role": "validate",
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "instructions": "data_validation_system_msg",
        "request_instructions": "data_validation_request_msg"
        // -> anthropic / claude-haiku-4-5-20251001 / temperature 1
      }
    ]

  }
}
```

> **Note:** JSON does not support `//` comments. The comments above are for illustration only - remove them before using this as an actual config file.

---

## Quick Reference

Use these tables as a quick lookup when building or debugging configurations.

### Top-level runtime settings

| Setting | Description |
|---------|-------------|
| `max_retries` | Max conversion retry attempts before giving up (default: 3) |
| `include_prior_output_on_retry` | When `true`, the previous failed output is included in the next retry prompt alongside validator error messages, giving the conversion agent full context on what it produced and why it was rejected.  When `false`, only the validator error messages are sent.  Can be set in the config file, overridden per-recipe as a top-level conversion YAML key, and forced either way at runtime with `--include-prior-output-on-retry` / `--no-include-prior-output-on-retry`. (default: false) |
| `parallel_agents` | Run verifier/validator agents in parallel (default: false) |
| `max_parallel_workers` | Max concurrent agent threads when `parallel_agents` is true (default: 2) |
| `log_details` | Include detailed operational logs (default: false) |
| `api_timeout` | API call timeout in seconds (default: 600) |
| `api_retry_attempts` | Retry attempts per individual API call (default: 3) |
| `api_retry_backoff` | Exponential backoff multiplier between API retries (default: 2) |

### What can be set at each level?

| Setting | Global | Provider Profile | Role-Group | Individual Agent |
|---------|:---:|:---:|:---:|:---:|
| `default_model` | Yes | Yes | Yes | - |
| `default_temperature` | Yes | Yes | Yes | - |
| `default_thinking_budget` | Yes | Yes | Yes | - |
| `default_reasoning_effort` | Yes | Yes | Yes | - |
| `default_max_tokens` | Yes | Yes | Yes | - |
| `supports_temperature` | Yes | Yes | Yes (`default_supports_temperature`) | - |
| `token_param` | Yes | Yes | Yes (`default_token_param`) | - |
| `model` | - | - | - | Yes |
| `provider` | - | - | - | Yes |
| `temperature` | - | - | - | Yes |
| `thinking_budget` | - | - | - | Yes |
| `reasoning_effort` | - | - | - | Yes |
| `max_tokens` | - | - | - | Yes |
| `supports_temperature` | - | - | - | Yes |
| `token_param` | - | - | - | Yes |

### Resolution order (first match wins)

| Setting | Priority order |
|---------|---------------|
| Provider | Agent `provider` -> Role-group `default_provider` -> Global `default_provider` |
| Model | Agent `model` -> Role-group `default_model` -> Provider profile `default_model` -> Global `default_model` |
| Temperature | Agent `temperature` -> Role-group `default_temperature` -> Provider profile `default_temperature` -> Global `default_temperature` -> *(omitted)* |
| Thinking budget | Agent `thinking_budget` -> Role-group `default_thinking_budget` -> Provider profile `default_thinking_budget` -> Global -> *(omitted)* |
| Reasoning effort | Agent `reasoning_effort` -> Role-group `default_reasoning_effort` -> Provider profile `default_reasoning_effort` -> Global -> *(omitted)* |
| Max tokens | Agent `max_tokens` -> Role-group `default_max_tokens` -> Provider profile `default_max_tokens` -> Global -> *(provider default)* |
| Supports temperature | Agent `supports_temperature` -> Role-group `default_supports_temperature` -> Provider profile `supports_temperature` -> Global -> `true` |
| Token param | Agent `token_param` -> Role-group `default_token_param` -> Provider profile `token_param` -> Global -> `max_tokens` |

> **Naming a profile detaches from role defaults.** The role-group tier applies only while an agent is on the role's profile. An agent that sets its own `provider` takes that profile's values for everything it does not set itself - role-group settings no longer reach it. That keeps a role's model choice from following an agent to a vendor where the model name doesn't exist.

### Thinking & temperature interaction

| Condition | Temperature in request |
|-----------|----------------------|
| Anthropic + `thinking_budget` set | Always `1` (API requirement, handled automatically) |
| OpenAI + `reasoning_effort` set | Omitted (mutually exclusive) |
| Google + `thinking_budget` set | Included if configured (they coexist) |
| No thinking/reasoning configured | Follows normal temperature resolution |
