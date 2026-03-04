# Cloud Provider Configuration Guide

UDC01 starts with a local LLM server by default, but its real power comes from mixing providers - using Claude for complex conversions, Gemini for fast validation, GPT for verification, or any combination your workflow calls for. This guide covers how to connect each cloud provider, keep your credentials secure, and troubleshoot the problems that actually come up.

## Overview

UDC01 speaks to four provider types out of the box:
- **local**: Your local LLM server (default, no API key required)
- **openai**: OpenAI API (GPT-5.2, GPT-4.1, etc.)
- **anthropic**: Anthropic API (Claude models)
- **google**: Google AI API (Gemini models)

## Configuration Structure

### 1. Provider Definitions

The `providers` section in your config file defines the connection details for each provider. UDC01 handles the payload format differences between providers automatically - you just tell it which format to use.

```json
{
  "providers": {
    "local": {
      "base_url": "http://localhost:1234",
      "endpoint": "v1/chat/completions",
      "auth_header": null,
      "request_format": "openai"
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer",
      "request_format": "openai"
    },
    "anthropic": {
      "base_url": "https://api.anthropic.com",
      "endpoint": "v1/messages",
      "auth_header": "x-api-key",
      "auth_prefix": "",
      "version_header": "anthropic-version",
      "version": "2023-06-01",
      "request_format": "anthropic"
    },
    "google": {
      "base_url": "https://generativelanguage.googleapis.com",
      "endpoint": "v1beta/models/{model}:generateContent",
      "auth_header": "x-goog-api-key",
      "auth_prefix": "",
      "request_format": "google"
    }
  }
}
```

### 2. API Keys Configuration

API keys can be configured in two ways. We recommend environment variables - they keep credentials out of your config files and out of version control.

#### Option A: Environment Variables (Recommended)

Store the actual key in your environment and reference it by name in the config:

```json
{
  "api_keys": {
    "openai": "${OPENAI_API_KEY}",
    "anthropic": "${ANTHROPIC_API_KEY}",
    "google": "${GOOGLE_API_KEY}"
  }
}
```

Then set the environment variables before running:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-..."
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:GOOGLE_API_KEY="..."
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=sk-...
set ANTHROPIC_API_KEY=sk-ant-...
set GOOGLE_API_KEY=...
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
```

#### Option B: Direct in Config (Fast Usage)

For quick local testing, you can put keys directly in the config. Just don't commit that file.

```json
{
  "api_keys": {
    "openai": "sk-proj-...",
    "anthropic": "sk-ant-...",
    "google": "AIza..."
  }
}
```

⚠️ **Warning**: Add config files containing API keys to `.gitignore` before you run your first commit. It's much easier to do this before than after.

### 3. Setting Default Provider

The global default provider applies to every agent that doesn't have a more specific override. Start here, then refine per-role or per-agent as needed.

```json
{
  "default_provider": "local",
  "default_model": "openai/gpt-oss-120b"
}
```

## Agent Configuration

### Using Default Provider

Any agent without an explicit `provider` field inherits from `default_provider`. This lets you configure the common case once and only specify exceptions.

```json
{
  "agents": {
    "data_verifier": [
      {
        "name": "Jane Dirac",
        "role": "verify"
        // Uses default_provider="local"
      }
    ]
  }
}
```

### Per-Agent Provider Override

When you need a specific agent to use a different provider - say, a frontier model for the conversion step and a faster model for verification - override it directly on the agent.

```json
{
  "agents": {
    "data_conversion": {
      "name": "Ted Sagan",
      "role": "convert",
      "provider": "openai",           // Override to use OpenAI
      "model": "gpt-5.1",
      "temperature": 1
    },
    "data_verifier": [
      {
        "name": "Jane Dirac",
        "role": "verify",
        "provider": "anthropic",       // Override to use Anthropic
        "model": "claude-3-5-sonnet",
        "temperature": 1
      },
      {
        "name": "Chris Einstein",
        "role": "verify"
        // Uses default_provider="local"
      }
    ]
  }
}
```

For the full picture on how provider, model, and temperature interact across global, role-group, and individual agent levels, see the [**Configuration Hierarchy Guide**](CONFIGURATION.md).

## Logging Configuration

When you're setting up a new provider or debugging an unexpected error, detailed logging gives you the full picture of what each agent is doing and what each API call returns.

```json
{
  "log_details": true
}
```

When enabled, the log file includes a `system_logs` section with:
- Timestamps for each log entry
- Log level (INFO, WARNING, ERROR)
- Module, function, and line number
- Full error messages from API calls

This is the first thing to enable when tracking down authentication issues or provider-side errors.

## Complete Example Configuration

```json
{
  "default_provider": "local",
  "default_model": "openai/gpt-oss-120b",
  "default_endpoint": "v1/chat/completions",
  "default_temperature": 1,
  "log_details": true,

  "providers": {
    "local": {
      "base_url": "http://localhost:1234",
      "endpoint": "v1/chat/completions",
      "auth_header": null,
      "request_format": "openai"
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer",
      "request_format": "openai"
    },
    "anthropic": {
      "base_url": "https://api.anthropic.com",
      "endpoint": "v1/messages",
      "auth_header": "x-api-key",
      "auth_prefix": "",
      "version_header": "anthropic-version",
      "version": "2023-06-01",
      "request_format": "anthropic"
    },
    "google": {
      "base_url": "https://generativelanguage.googleapis.com",
      "endpoint": "v1beta/models/{model}:generateContent",
      "auth_header": "x-goog-api-key",
      "auth_prefix": "",
      "request_format": "google"
    }
  },

  "api_keys": {
    "openai": "${OPENAI_API_KEY}",
    "anthropic": "${ANTHROPIC_API_KEY}",
    "google": "${GOOGLE_API_KEY}"
  },

  "agents": {
    "data_verifier": [
      {
        "name": "Jane Dirac",
        "role": "verify"
      },
      {
        "name": "Chris Einstein",
        "role": "verify",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.1
      },
      {
        "name": "Nathan Fourier",
        "role": "verify"
      }
    ],
    "data_conversion": {
      "name": "Ted Sagan",
      "role": "convert",
      "provider": "anthropic",
      "model": "claude-3-5-sonnet",
      "temperature": 0.2
    },
    "data_validator": [
      {
        "name": "Charles Turing",
        "role": "validate",
        "provider": "google",
        "model": "gemini-2.5-flash"
      },
      {
        "name": "Macy Hopper",
        "role": "validate"
      },
      {
        "name": "Vanessa Lovelace",
        "role": "validate"
      }
    ]
  }
}
```

## Supported Models

### OpenAI
- `gpt-5`
- `gpt-5-mini`
- `gpt-5-nano`
- `gpt-5.2-pro`

### Anthropic Claude
- `claude-sonnet-4-5`
- `claude-haiku-4-5`
- `claude-opus-4-5`

### Google Gemini
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash`
- `gemini-3-pro-preview`
- `gemini-3-flash-preview`


## Testing Your Configuration

Work from the inside out - start with what you know is working and add providers one at a time.

1. **Test local provider first** (ensure your local server is running)
2. **Add one cloud provider** (set environment variable with API key)
3. **Run a simple conversion** to verify connectivity
4. **Check logs** for provider information and any errors

The system logs confirm which provider and model each agent used:
```
Agent Ted Sagan (anthropic/claude-4-5-sonnet) completed in 2.34s
```

## Things Worth Knowing Going In

These are the issues that come up most often when connecting cloud providers for the first time. Each one has a straightforward fix.

**"Provider 'X' not found in configuration"**

The provider name in the agent config doesn't match a key in the `providers` section. Check for typos - provider names are case-sensitive. Confirm the provider you're referencing is defined in the `providers` block.

**"No API key found for provider 'X'"**

Three things to check: the environment variable is set in the same shell session where you're running UDC01 (not a different terminal), the variable name in the config's `api_keys` section matches the actual environment variable name exactly, and there are no leading/trailing quotes in the environment variable value.

**Authentication errors (401, 403)**

The API key itself is wrong, expired, or has insufficient permissions. Verify the key is correct and active on the provider's dashboard, and check that you haven't hit quota limits or exhausted your balance.

**Request format errors**

UDC01 handles format differences automatically - but only if `request_format` in the provider config matches the provider type (`openai`, `anthropic`, or `google`). If you're seeing unexpected request errors, this is the first field to double-check.

## Migration from Legacy Configuration

Old configurations without a `providers` section automatically fall back to legacy mode with a default local provider. To enable multi-provider support, add four things to your config:

1. The `providers` section
2. The `api_keys` section
3. A `default_provider` field
4. Optionally, `provider` fields on individual agents

The system is fully backward compatible - your existing configs continue to work exactly as before.

## Security Practices

These aren't optional ceremony - they're the habits that prevent API key exposure in the real world.

1. ✅ **Use environment variables** for API keys
2. ✅ **Add config files with keys to `.gitignore`**
3. ✅ **Rotate API keys regularly**
4. ✅ **Use API key restrictions** (IP allowlists, rate limits)
5. ✅ **Monitor API usage** and set budget alerts
6. ❌ **Never commit API keys** to version control
7. ❌ **Never share config files** containing API keys
