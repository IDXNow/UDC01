# UDC01 Configuration Guide

This guide explains how the configuration system works, where settings can be placed, and how values override each other across the configuration hierarchy.

---

## Table of Contents

- [Configuration Files Overview](#configuration-files-overview)
- [Runtime Priority: Which Value Wins?](#runtime-priority-which-value-wins)
- [Provider Profiles](#provider-profiles)
- [Agent Configuration Hierarchy](#agent-configuration-hierarchy)
  - [Level 1 — Global Default](#level-1--global-default)
  - [Level 2 — Role-Group Default](#level-2--role-group-default)
  - [Level 3 — Individual Agent](#level-3--individual-agent)
- [Temperature: An Optional Setting](#temperature-an-optional-setting)
- [Thinking & Reasoning](#thinking--reasoning)
- [Complete Example](#complete-example)
- [Quick Reference](#quick-reference)

---

## Configuration Files Overview

UDC01 uses two configuration files:

| File | Format | Purpose |
|------|--------|---------|
| `udc01/default_config.json` (or `--config` path) | JSON | Provider connections, agent definitions, file paths, runtime settings |
| Your conversion YAML (e.g. `samples/conversions/sales_invoice_conv.yaml`) | YAML | LLM prompts and instructions for a specific conversion job |

Specify which files to use at startup:
```bash
python udc01.py --config "my_config.json" --conversion "my_conversion.yaml"
```

---

## Runtime Priority: Which Value Wins?

Settings are applied in layers, each one overriding the previous. **Higher priority wins.**

```
1. Code defaults       (lowest)  — built-in fallbacks, always present
2. Config file                   — your JSON config, merged over code defaults
3. CLI arguments       (highest) — --file, --folder, --pattern, --output-folder, --parallel-agents
```

**Example:**
The config file sets `"folder": "data/"`. You run with `--folder "inputs/"`. The `inputs/` folder is used.

---

## Provider Profiles

The `providers` section defines connection details for each LLM service. Each provider profile can also set its own `default_model` and `default_temperature`, which become the defaults for any agent that uses that provider.

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
    "default_model": "claude-sonnet-4-5",
    "default_temperature": 1
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
    "default_model": "my-local-model"
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
| `default_temperature` | No | Default temperature for agents using this provider. Omit for providers that don't support it (e.g. OpenAI o-series reasoning models) |

---

## Agent Configuration Hierarchy

Model, provider, and temperature can be set at **three levels**. The most specific level wins.

```
Level 1: Global default         (default_provider at config top level)
Level 2: Role-group default     (default_provider on an agent group)
Level 3: Individual agent       (provider / model / temperature on one agent)
```

### Level 1 — Global Default

Set at the top of your config. All agents use this provider unless overridden.

```json
{
  "default_provider": "google"
}
```

The selected provider's `default_model` and `default_temperature` (from the `providers` section) automatically apply to every agent.

---

### Level 2 — Role-Group Default

Wrap an agent group in an object with `default_provider` (and optionally `default_model` / `default_temperature`) to override the global default for that entire role.

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

The flat array format (without a wrapper object) also works and simply inherits global defaults:

```json
"data_verifier": [
  { "name": "Jane Dirac", "role": "verify", ... },
  ...
]
```

---

### Level 3 — Individual Agent

Set `provider`, `model`, and/or `temperature` directly on one agent to override everything above it.

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
        "model": "gpt-4o",
        "temperature": 0.5
        // fully overrides — uses OpenAI gpt-4o at temperature 0.5
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

Temperature is **not required** and intentionally omitted from the top-level config. Some models (such as OpenAI o-series reasoning models) reject the `temperature` parameter entirely — if it is not set at any level, UDC01 simply omits it from the API request.

**Resolution order for temperature:**

```
1. Agent-level "temperature"                          -> use it
2. Role-group "default_temperature"                   -> use it
3. Provider profile "default_temperature"             -> use it
4. None of the above                                  -> field omitted from request
```

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

Three providers support extended thinking or reasoning modes. Each uses a different mechanism, but all follow the same 3-level hierarchy (provider profile -> role-group -> individual agent).

### Provider support

| Provider | Parameter | Values | Effect on temperature |
|----------|-----------|--------|-----------------------|
| **Anthropic** | `thinking_budget` | integer ≥ 1024 (tokens) | **Replaced** — forced to 1 by the API when thinking is on |
| **Google Gemini** | `thinking_budget` | integer, `0` (off), `-1` (dynamic) | **Coexists** — temperature still applies |
| **OpenAI** (o-series) | `reasoning_effort` | `"low"`, `"medium"`, `"high"` | **Replaced** — o-series never supported temperature |

### Setting thinking_budget (Anthropic & Google)

**In the provider profile** — applies to all agents using that provider:
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

**In a role-group** — applies to all agents in that role:
```json
"data_conversion": {
  "default_provider": "anthropic",
  "default_thinking_budget": 15000,
  "agents": { "name": "Ted Sagan", "role": "convert" }
}
```

**On an individual agent** — overrides everything above:
```json
{ "name": "Ted Sagan", "role": "convert", "thinking_budget": 12000 }
```

> **Anthropic note:** When `thinking_budget` is set, the API forces `temperature: 1` regardless of any other temperature configuration. UDC01 handles this automatically.
>
> **Anthropic + thinking:** Anthropic requires `max_tokens` to be large enough to accommodate both thinking tokens and output tokens. Set `max_tokens` explicitly at the provider, role-group, or agent level when using `thinking_budget`. See [max_tokens](#max_tokens) below.

### Setting reasoning_effort (OpenAI o-series)

**In the provider profile:**
```json
"openai": {
  ...
  "default_model": "o3-mini",
  "default_reasoning_effort": "medium"
}
```

**On an individual agent:**
```json
{ "name": "Ted Sagan", "role": "convert", "provider": "openai", "model": "o3", "reasoning_effort": "high" }
```

When `reasoning_effort` is set, `temperature` is automatically omitted from the request — these two parameters are mutually exclusive on OpenAI o-series models.

### max_tokens

`max_tokens` controls the maximum number of output tokens per API call. It follows the same 3-level hierarchy and is supported by all three providers.

**In the provider profile** — applies to all agents using that provider:
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

If `max_tokens` is not set at any level, each provider falls back to its own built-in default (`10000` for Anthropic, no limit sent for Google and OpenAI).

---

## Complete Example

This example shows all three levels in action:

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
      "default_model": "claude-sonnet-4-5",
      "default_temperature": 1
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer",
      "request_format": "openai",
      "default_model": "gpt-4o-mini"
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
          // -> anthropic / claude-haiku-4-5-20251001 / temperature 1
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

> **Note:** JSON does not support `//` comments. The comments above are for illustration only — remove them before using this as an actual config file.

---

## Quick Reference

### What can be set at each level?

| Setting | Provider Profile | Role-Group | Individual Agent |
|---------|:---:|:---:|:---:|
| `default_model` | Yes | Yes | — |
| `default_temperature` | Yes | Yes | — |
| `default_thinking_budget` | Yes | Yes | — |
| `default_reasoning_effort` | Yes | Yes | — |
| `default_max_tokens` | Yes | Yes | — |
| `model` | — | — | Yes |
| `provider` | — | — | Yes |
| `temperature` | — | — | Yes |
| `thinking_budget` | — | — | Yes |
| `reasoning_effort` | — | — | Yes |
| `max_tokens` | — | — | Yes |

### Resolution order (first match wins)

| Setting | Priority order |
|---------|---------------|
| Provider | Agent `provider` -> Role-group `default_provider` -> Global `default_provider` |
| Model | Agent `model` -> Role-group `default_model` -> Provider profile `default_model` |
| Temperature | Agent `temperature` -> Role-group `default_temperature` -> Provider profile `default_temperature` -> *(omitted)* |
| Thinking budget | Agent `thinking_budget` -> Role-group `default_thinking_budget` -> Provider profile `default_thinking_budget` -> *(omitted)* |
| Reasoning effort | Agent `reasoning_effort` -> Role-group `default_reasoning_effort` -> Provider profile `default_reasoning_effort` -> *(omitted)* |
| Max tokens | Agent `max_tokens` -> Role-group `default_max_tokens` -> Provider profile `default_max_tokens` -> *(provider default)* |

### Thinking & temperature interaction

| Condition | Temperature in request |
|-----------|----------------------|
| Anthropic + `thinking_budget` set | Always `1` (API requirement, handled automatically) |
| OpenAI + `reasoning_effort` set | Omitted (mutually exclusive) |
| Google + `thinking_budget` set | Included if configured (they coexist) |
| No thinking/reasoning configured | Follows normal temperature resolution |
