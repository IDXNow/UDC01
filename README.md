# Universal Data Converter (UDC01)
<!-- markdownlint-disable first-line-h1 -->
<!-- markdownlint-disable html -->
<div>
  <h2>Leveraging LLMs for Intelligent Data Transformation</h2>
</div>

## Table of Contents
- [Introduction](#introduction)
- [Key Features](#key-features)
- [Framework Architecture](#framework-architecture)
  - [Data Process Flow](#data-process-flow)
- [Technical Requirements](#technical-requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Command Line Options](#command-line-options)
  - [Example Commands](#example-commands)
- [Sample Conversions](#sample-conversions)
- [Validation Mechanism & Evolution](#validation-mechanism--evolution)
- [Cloud Provider Configuration](#cloud-provider-configuration)
  - [Setting Up API Keys](#setting-up-api-keys)
  - [Provider Configuration](#provider-configuration)
  - [Per-Agent Provider Selection](#per-agent-provider-selection)
  - [Performance Optimization for Cloud APIs](#performance-optimization-for-cloud-apis)
  - [Detailed Logging](#detailed-logging)
- [Configuration Files](#configuration-files)
- [License](#license)
- [Contact & Community](#contact--community)


## Introduction

The **Universal Data Converter (UDC01)** is an **AI-driven data transformation framework**, designed to produce standardized output data formats using **structured, semi-structured, and unstructured** input data.  It leverages **LLM-powered verification, validation and conversion** to **automate** data transformation, ensuring a consistent output format for enterprise integration.

UDC01 implements a robust validation system using a unique 2/3 majority voting mechanism, ensuring high accuracy and reliability in data transformations.  The framework is particularly effective for organizations dealing with diverse data sources and formats that require standardization for downstream processing.

---

## Key Features

- **Intelligent Data Processing**: Advanced LLM-based transformation pipeline for handling structured, semi-structured, and unstructured input data
- **Multi-Stage Validation**: Implements a 2/3 voting mechanism across multiple LLM agents to ensure transformation accuracy
- **Multi-Provider Support**: Works with local models, OpenAI (GPT), Anthropic (Claude), and Google (Gemini)
- **Parallel Execution**: Concurrent agent execution for faster processing with cloud APIs
- **Automated Workflow**: Complete pipeline from data intake to output generation with minimal human intervention
- **Early-Exit Consensus**: Optimized validation with early-exit when 2/3 consensus is reached
- **Retry Mechanism**: Configurable retry attempts for failed conversions with exponential backoff
- **Agent Identification System**: Unique identifiers and human-readable names for each LLM agent in the process
- **Detailed Logging**: Optional comprehensive logging with error tracking and performance metrics

---

## Framework Architecture

### Data Process Flow

The core transformation pipeline consists of several key stages:

1. **Input Processing**
   - File/queue content reading
   - Initial data structure analysis
   - Format identification

2. **LLM Verification (2/3 Consensus)**
   - Field completeness verification
   - Structure validation
   - Data integrity checks

3. **Intelligent Transformation**
   - Format-specific processing
   - Data standardization
   - Quality assurance checks
   - Configurable retry mechanism for failed conversions

4. **Multi-Stage Validation**
   - Three independent LLM validations
   - Automatic retry mechanism
   - Comprehensive validation reporting

<p align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/udc01.data_flow.jpg">
</p>

---

## Technical Requirements

### Dependencies
To run the Universal Data Converter with the samples provided, you'll need the following Python packages:

```
pandas
pyyaml
requests
openpyxl
```

### LLM Requirements
The framework supports multiple LLM providers:

**Local Models:**
- Local LLM server (default: http://localhost:1234/)
- Any OpenAI-compatible API endpoint

**Cloud Providers:**
- **OpenAI**: GPT-5, GPT-5-mini, GPT-5-nano, GPT-5.1
- **Anthropic**: Claude 4.5 Sonnet, Claude 4.5 Haiku, Claude 4.5 Opus
- **Google**: Gemini 2.5 Flash, Gemini 2.5 Flash-Lite, Gemini 2.5 Pro, Gemini 3 Pro

**Note**: Cloud providers require API keys set as environment variables. See [Cloud Provider Configuration](#cloud-provider-configuration) for details.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/IDXNow/UDC01.git
   cd UDC01
   ```

2. Install the required packages:
   ```bash
   pip install pandas pyyaml requests openpyxl
   ```
   or
   ```bash
   pip install -r requirements.txt
   ```

3. **For Local Models**: Ensure your local LLM API is accessible (default: http://localhost:1234/)

4. **For Cloud Providers**: Set up API keys as environment variables:
   ```powershell
   # Windows PowerShell
   $env:OPENAI_API_KEY="sk-proj-..."
   $env:ANTHROPIC_API_KEY="sk-ant-..."
   $env:GOOGLE_API_KEY="..."
   ```
   ```bash
   # Linux/Mac
   export OPENAI_API_KEY="sk-proj-..."
   export ANTHROPIC_API_KEY="sk-ant-..."
   export GOOGLE_API_KEY="..."
   ```

   See [Cloud Provider Configuration](#cloud-provider-configuration) for detailed setup instructions.

---

## Usage

The Universal Data Converter is designed to be used from the command line, with various parameters to configure the conversion process.

### Command Line Options

```bash
python udc01.py
  --config CONFIG_PATH           # Path to main configuration file (default: udc01/default_config.json)
  --conversion CONVERSION_PATH   # Path to conversion YAML (default: samples/conversions/sales_invoice_conv.yaml)
  --file FILE_PATH               # Specific file to load
  --folder FOLDER_PATH           # Folder to search for files
  --pattern FILE_PATTERN         # File search pattern (e.g., '*.csv')
  --output-folder OUTPUT_PATH    # Folder to save output files
  --parallel-agents              # Run validator agents in parallel (faster for cloud APIs)
```

**Note**: If no `--config` or `--conversion` arguments are provided, the defaults will be used.  You can also use the config file in `udc01/default_config.json` for your own custom setup.

**Performance Tip**: Enable `--parallel-agents` when working with cloud API providers (OpenAI, Anthropic, etc.)

### Example Commands

#### Converting a CSV file to pipe-delimited format (using defaults):

```bash
python udc01.py --file "samples/sources/sales_invoice.csv"
```

Or explicitly specify the conversion configuration:

```bash
python udc01.py --conversion "samples/conversions/sales_invoice_conv.yaml" \
                --file "samples/sources/sales_invoice.csv"
```

#### Converting an XML file to pipe-delimited format:

```bash
python udc01.py --conversion "samples/conversions/product_inventory_conv.yaml" \
                --file "samples/sources/product_inventory.xml"
```

#### Converting multiple files in a directory:

```bash
python udc01.py --conversion "samples/conversions/customer_order_conv.yaml" \
                --folder "samples/sources" \
                --pattern "*.xlsx"
```

#### Using parallel execution for faster processing (cloud APIs):

```bash
python udc01.py --file "samples/sources/sales_invoice.csv" \
                --parallel-agents
```

#### Using cloud providers with custom configuration:

```bash
# Set up your API keys first
set ANTHROPIC_API_KEY=sk-ant-...
set OPENAI_API_KEY=sk-proj-...

# Use the cloud example configuration
python udc01.py --config "samples/config/cloud_example_config.json" \
                --file "samples/sources/sales_invoice.csv" \
                --parallel-agents
```

This will use Claude for conversion and GPT/Gemini for validation, running validators in parallel for maximum speed.

---

## Sample Conversions

The repository includes several sample data files and corresponding conversion configurations:

### Sales Invoice (CSV to Pipe-delimited)
**Input**: A CSV file containing sales invoice data with multiple columns
**Configuration**: `samples/conversions/sales_invoice_conv.yaml`
**Output**: Pipe-delimited text file with standardized columns:
```
InvoiceID|CustomerID|CustomerName|InvoiceDate|DueDate|TotalAmount|PaymentStatus
INV-001|CUST-100|Acme Corporation|2023-01-15|2023-02-15|1250.75|Paid
```

### Product Inventory (XML to Pipe-delimited)
**Input**: XML structured product inventory data
**Configuration**: `samples/conversions/product_inventory_conv.yaml`
**Output**: Pipe-delimited text file with standardized columns:
```
SKU|ProductName|Brand|QuantityOnHand|Status|RetailPrice
PROD-100|Deluxe Widget|XYZ Manufacturing|150|In Stock|29.99
```

### Customer Orders (Excel to Pipe-delimited)
**Input**: Excel spreadsheet with customer order information
**Configuration**: `samples/conversions/customer_order_conv.yaml`
**Output**: Pipe-delimited text file with standardized columns:
```
OrderNumber|CustomerID|CustomerName|OrderDate|ProductSKU|ProductDescription|Quantity|OrderTotal|ShippingStatus
ORD-12345|CUST-100|Acme Corporation|2023-01-20|PROD-100|Deluxe Widget|10|299.90|Shipped
```

---

## Validation Mechanism & Evolution

### 2/3 Majority Consensus

UDC01 ensures high data quality through a unique 2/3 majority voting system:

1. **Pre-Conversion Verification**:
   - Three independent LLM agents verify the input data's structure and content
   - At least two agents must approve for processing to continue
   - Early-exit optimization: If the first two agents agree, the third agent is not called

2. **Post-Conversion Validation**:
   - Three independent LLM agents validate the conversion output
   - At least two agents must approve the conversion
   - Early-exit optimization: If the first two agents agree, the third agent is not called

3. **Retry Logic**:
   - If validation fails, conversion is retried up to a configurable number of times
   - Each retry uses the same input data but may generate different outputs

### Multi-Agent Validation: Statistical Reliability

The 2/3 majority validation mechanism achieves substantially higher accuracy than single-agent approaches:

| Agent Quality | Single Agent Accuracy | **UDC01 2/3 Majority Accuracy** | Error Reduction |
|---------------|----------------------|----------------------------|----------------|
| :robot:90% | 90.0% | **97.2%** | 72% |
| :robot:95% | 95.0% | **99.3%** | 86% |
| :robot:98% | 98.0% | **99.9%** | 95% |

The framework's validation design reconciles two competing realities: LLMs' inherent variability and enterprise systems' need for consistent, predictable outputs.

### From ETL Developer to Data Prompt Engineer
As data engineering has evolved beyond traditional ETL workflows, Data Prompt Engineering represents a natural progression in the field.  This emerging specialization involves:

- Crafting precise, robust prompts that guide LLMs in performing reliable data transformations
- Implementing validation gates and quality checks specifically designed for LLM-driven processes
- Creating reusable prompt templates that ensure consistent processing across diverse data formats
- Balancing deterministic validation with the flexibility of natural language processing

UDC01 provides a structured framework where Data Prompt Engineers focus on crafting effective transformation instructions rather than writing procedural code for each new data format.  The 2/3 verification and validation gates demonstrate how traditional ETL quality assurance principles can be reimagined for the era of LLM-driven transformations.

---

## Cloud Provider Configuration

UDC01 supports multiple cloud-based LLM providers, allowing you to mix models based on your needs.  Each agent can use a different provider to optimize cost and performance.

### Setting Up API Keys

Cloud providers require API keys, which should be stored as environment variables for security:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-proj-..."
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:GOOGLE_API_KEY="..."
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY="sk-proj-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
```

**Important**: You should not commit API keys to version control.  The configuration file uses environment variable placeholders like `${OPENAI_API_KEY}` which are automatically resolved at runtime.

### Provider Configuration

The `default_config.json` includes provider definitions for all supported services:

```json
{
  "default_provider": "local",
  "providers": {
    "local": {
      "base_url": "http://localhost:1235",
      "endpoint": "v1/chat/completions",
      "request_format": "openai"
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer"
    },
    "anthropic": {
      "base_url": "https://api.anthropic.com",
      "endpoint": "v1/messages",
      "auth_header": "x-api-key"
    },
    "google": {
      "base_url": "https://generativelanguage.googleapis.com",
      "endpoint": "v1beta/models/{model}:generateContent",
      "auth_header": "x-goog-api-key"
    }
  }
}
```

### Per-Agent Provider Selection

You can specify which provider each agent can use:

```json
{
  "agents": {
    "data_conversion": {
      "name": "Ted Sagan",
      "provider": "anthropic",
      "model": "claude-sonnet-4-5",
      "temperature": 1
    },
    "data_verifier": [
      {
        "name": "Jane Dirac",
        "provider": "openai",
        "model": "gpt-5-mini"
      },
      {
        "name": "Chris Einstein"
        // Uses default_provider (local)
      }
    ]
  }
}
```

### Performance Optimization for Cloud APIs

When using cloud providers, enable parallel execution for faster processing:

```bash
python udc01.py --file "samples/sources/sales_invoice.csv" --parallel-agents
```

Or set in configuration:
```json
{
  "parallel_agents": true,
  "max_parallel_workers": 2
}
```

### Detailed Logging

Enable comprehensive logging to track API calls, errors, and performance:

```json
{
  "log_details": true
}
```

When enabled, log files will include:
- All INFO, WARNING, and ERROR messages
- API authentication details (with masked keys)
- Detailed error responses from providers
- Performance metrics for each agent

For complete cloud provider documentation, see [CLOUD_PROVIDERS.md](CLOUD_PROVIDERS.md).

---

## Configuration Files

### Main Configuration (JSON)

The main configuration file (`default_config.json`) contains settings for:
- API endpoints and model parameters
- Cloud provider configurations
- Agent definitions and roles with per-agent provider selection
- File paths and patterns
- Retry limits and timeout settings
- Performance tuning (parallelism, timeouts, retries)
- Logging configuration

Example:
```json
{
  "default_provider": "local",
  "default_model": "granite-3.1-8b-instruct",
  "default_temperature": 1,
  "max_retries": 3,
  "api_timeout": 600,
  "api_retry_attempts": 3,
  "api_retry_backoff": 2,
  "parallel_agents": true,
  "max_parallel_workers": 2,
  "log_details": true,

  "providers": {
    "local": {
      "base_url": "http://localhost:1234",
      "endpoint": "v1/chat/completions",
      "request_format": "openai"
    },
    "openai": {
      "base_url": "https://api.openai.com",
      "endpoint": "v1/chat/completions",
      "auth_header": "Authorization",
      "auth_prefix": "Bearer"
    }
  },

  "api_keys": {
    "openai": "${OPENAI_API_KEY}",
    "anthropic": "${ANTHROPIC_API_KEY}",
    "google": "${GOOGLE_API_KEY}"
  },

  "file_save": {
    "folder": "output/",
    "file_extension": "txt"
  },

  "agents": {
    "data_verifier": [
      {
        "name": "Jane Dirac",
        "role": "verify",
        "instructions": "data_verification_system_msg"
      }
    ],
    "data_conversion": {
      "name": "Ted Sagan",
      "role": "convert",
      "provider": "anthropic",
      "model": "claude-3-5-sonnet-20241022",
      "temperature": 0.2
    }
  }
}
```

**Configuration Options:**

*Provider Settings:*
- `default_provider`: Default LLM provider for all agents (default: "local")
- `providers`: Provider-specific API configurations
- `api_keys`: API keys with environment variable placeholders

*Performance Settings:*
- `api_timeout`: Timeout in seconds for API calls (default: 600)
- `api_retry_attempts`: Number of retry attempts for failed API calls (default: 3)
- `api_retry_backoff`: Exponential backoff multiplier for retries (default: 2)
- `parallel_agents`: Enable parallel execution of validators (default: false)
- `max_parallel_workers`: Maximum concurrent agent threads (default: 2)

*Logging Settings:*
- `log_details`: Include detailed system logs in output files (default: false)

### Conversion Configuration (YAML)

Each conversion type has a YAML configuration file that defines:
- System instructions for LLM agents
- Input/output format specifications
- Field mapping rules
- Validation criteria

Example from `sales_invoice_conv.yaml`:
```yaml
data_conversion_system_msg: |
  You are a data conversion agent specializing in format transformation. 
  Your task is to convert Sales Invoice data from CSV format to pipe-delimited (|) format.

  Conversion requirements:
  1. Transform CSV data to pipe-delimited (|) format
  2. Ensure these specific column names in this exact order: 
     InvoiceID|CustomerID|CustomerName|InvoiceDate|DueDate|TotalAmount|PaymentStatus
  # Additional instructions...

data_verification_system_msg: |
  You are a data verification agent tasked with examining input Sales Invoice data before processing.
  # Verification instructions...

data_validation_system_msg: |
  You are a data validation agent responsible for ensuring the quality of converted Sales Invoice data.
  # Validation instructions...
```

---

## License
Copyright (c) 2025 Steve Wint / I D X

This project is licensed under the [MIT License](https://github.com/IDXNow/UDC01/blob/main/LICENSE) - see the LICENSE file for details.

---

<div align="center">
  <p>For more information or support, please contact the development team.</p>
</div>

## Contact & Community

💬 **Have Questions?**  
Open an issue on [GitHub](https://github.com/IDXNow/UDC01/issues) or contact us at [support@idxnow.co](mailto:support@idxnow.co).

---
