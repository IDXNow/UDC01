# Cloud Provider Configuration Guide

This guide explains how to configure and use cloud-based LLM providers (OpenAI, Anthropic Claude, Google Gemini) in addition to local models.

## Overview

The system now supports multiple LLM providers:
- **local**: Local LLM server (default)
- **openai**: OpenAI API (GPT-4, GPT-3.5, etc.)
- **anthropic**: Anthropic API (Claude models)
- **google**: Google AI API (Gemini models)

## Configuration Structure

### 1. Provider Definitions

The `providers` section in your config file defines the connection details for each provider:

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

API keys can be configured in two ways:

#### Option A: Environment Variables (Recommended)

Set environment variables and reference them in the config:

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

For quick testing, you can put keys directly in the config:

```json
{
  "api_keys": {
    "openai": "sk-proj-...",
    "anthropic": "sk-ant-...",
    "google": "AIza..."
  }
}
```

⚠️ **Warning**: It's not recommended to commit API keys to version control! Add config files with keys to `.gitignore`.

### 3. Setting Default Provider

Set a global default provider that all agents inherit:

```json
{
  "default_provider": "local",
  "default_model": "openai/gpt-oss-120b"
}
```

## Agent Configuration

### Using Default Provider

Agents without an explicit `provider` field use the `default_provider`:

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

Override the provider for specific agents:

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

## Logging Configuration

To include detailed system logs (INFO, WARNING, ERROR messages) in the output log files, add:

```json
{
  "log_details": true
}
```

When enabled, the log file will include a `system_logs` section with all logging output:
- Timestamps for each log entry
- Log level (INFO, WARNING, ERROR)
- Module, function, and line number
- Full error messages from API calls

This can be useful for debugging provider authentication issues and API errors.

## Complete Example Configuration

```json
{
  "api_base_url": "http://localhost:1235/",
  "default_provider": "local",
  "default_model": "openai/gpt-oss-120b",
  "default_endpoint": "v1/chat/completions",
  "default_temperature": 1,
  "log_details": true,

  "providers": {
    "local": {
      "base_url": "http://localhost:1235",
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
      "model": "claude-3-5-sonnet-20241022",
      "temperature": 0.2
    },
    "data_validator": [
      {
        "name": "Charles Turing",
        "role": "validate",
        "provider": "google",
        "model": "gemini-2.0-flash-exp"
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
- `gemini-2.5-pro`
- `gemini-3-pro-preview`


## Testing Your Configuration

1. **Test local provider first** (ensure your local server is running)
2. **Add one cloud provider** (set environment variable with API key)
3. **Run a simple conversion** to verify connectivity
4. **Check logs** for provider information and any errors

The system logs will show which provider and model each agent uses:
```
Agent Ted Sagan (anthropic/claude-3-5-sonnet) completed in 2.34s
```

## Troubleshooting

### "Provider 'X' not found in configuration"
- Ensure the provider is defined in the `providers` section
- Check for typos in provider names

### "No API key found for provider 'X'"
- Verify environment variable is set correctly
- Check that the variable name in config matches the environment variable name
- Ensure no extra quotes or spaces in environment variable value

### Authentication errors
- Verify API key is correct and active
- Check that you have credits/quota remaining with the provider
- Ensure the auth_header and auth_prefix match the provider's requirements

### Request format errors
- The system automatically handles format differences
- Check that `request_format` in provider config matches the provider type

## Migration from Legacy Configuration

Old configurations without `providers` section will automatically fall back to legacy mode using the `api_base_url` setting.  To enable multi-provider support:

1. Add the `providers` section to your config
2. Add the `api_keys` section
3. Add `default_provider` field
4. Optionally add `provider` field to individual agents

The system is backward compatible and will work with old configurations.

## Security Best Practices

1. ✅ **Use environment variables** for API keys
2. ✅ **Add config files with keys to `.gitignore`**
3. ✅ **Rotate API keys regularly**
4. ✅ **Use API key restrictions** (IP allowlists, rate limits)
5. ✅ **Monitor API usage** and set budget alerts
6. ❌ **Never commit API keys** to version control
7. ❌ **Never share config files** containing API keys
