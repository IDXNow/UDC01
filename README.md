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
- [Configuration Files](#configuration-files)
- [License](#license)
- [Contact & Community](#contact--community)


## Introduction

The **Universal Data Converter (UDC01)** is an **AI-driven data transformation framework**, designed to produce standardized output data formats using **structured, semi-structured, and unstructured** input data. It leverages **LLM-powered verification, validation and conversion** to **automate** data transformation, ensuring a consistent output format for enterprise integration.

UDC01 implements a robust validation system using a unique 2/3 majority voting mechanism, ensuring high accuracy and reliability in data transformations. The framework is particularly effective for organizations dealing with diverse data sources and formats that require standardization for downstream processing.

---

## Key Features

- **Intelligent Data Processing**: Advanced LLM-based transformation pipeline for handling structured, semi-structured, and unstructured input data
- **Multi-Stage Validation**: Implements a 2/3 voting mechanism across multiple LLM agents to ensure transformation accuracy
- **Automated Workflow**: Complete pipeline from data intake to output generation with minimal human intervention
- **Early-Exit Consensus**: Optimized validation with early-exit when 2/3 consensus is reached
- **Retry Mechanism**: Configurable retry attempts for failed conversions
- **Agent Identification System**: Unique identifiers and human-readable names for each LLM agent in the process

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
```

### LLM Requirements
The framework requires access to a compatible LLM API. The default configuration uses a local LLM server, but it can be configured to use other providers.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/IDXNow/UDC01.git
   cd UDC01
   ```

2. Install the required packages:
   ```bash
   pip install pandas pyyaml requests
   ```
   or
   ```bash
   pip install -r requirements.txt
   ```
   

3. Ensure your LLM API is accessible (default is http://localhost:1234/).

---

## Usage

The Universal Data Converter is designed to be used from the command line, with various parameters to configure the conversion process.

### Command Line Options

```bash
python src/main.py 
  --config CONFIG_PATH           # Path to main configuration file
  --conversion CONVERSION_PATH   # Path to conversion YAML
  --file FILE_PATH               # Specific file to load
  --folder FOLDER_PATH           # Folder to search for files
  --pattern FILE_PATTERN         # File search pattern (e.g., '*.csv')
  --output-folder OUTPUT_PATH    # Folder to save output files
```

### Example Commands

#### Converting a CSV file to pipe-delimited format:

```bash
python src/main.py --config "samples/config/default_config.json" \
                  --conversion "samples/conversions/sales_invoice_conv.yaml" \
                  --file "samples/sources/sales_invoice.csv"
```

#### Converting an XML file to pipe-delimited format:

```bash
python src/main.py --config "samples/config/default_config.json" \
                  --conversion "samples/conversions/product_inventory_conv.yaml" \
                  --file "samples/sources/product_inventory.xml"
```

#### Converting multiple files in a directory:

```bash
python src/main.py --config "samples/config/default_config.json" \
                  --conversion "samples/conversions/customer_order_conv.yaml" \
                  --folder "samples/sources" \
                  --pattern "*.xlsx"
```

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
As data engineering has evolved beyond traditional ETL workflows, Data Prompt Engineering represents a natural progression in the field. This emerging specialization involves:

- Crafting precise, robust prompts that guide LLMs in performing reliable data transformations
- Implementing validation gates and quality checks specifically designed for LLM-driven processes
- Creating reusable prompt templates that ensure consistent processing across diverse data formats
- Balancing deterministic validation with the flexibility of natural language processing

UDC01 provides a structured framework where Data Prompt Engineers focus on crafting effective transformation instructions rather than writing procedural code for each new data format. The 2/3 verification and validation gates demonstrate how traditional ETL quality assurance principles can be reimagined for the era of LLM-driven transformations.

---

## Configuration Files

### Main Configuration (JSON)

The main configuration file (`default_config.json`) contains settings for:
- API endpoints and model parameters
- Agent definitions and roles
- File paths and patterns
- Retry limits

Example:
```json
{
  "api_base_url": "http://localhost:1234/",
  "default_model": "granite-3.1-8b-instruct",
  "default_temperature": 0.3,
  "max_retries": 3,
  "file_save": {
    "folder": "output/",
    "file_extension": "txt"
  },
  "agents": {
    "data_verifier": [
      {
        "name": "Julie Euler",
        "role": "verify",
        "instructions": "data_verification_system_msg"
      },
      // Additional agents...
    ]
  }
}
```

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
