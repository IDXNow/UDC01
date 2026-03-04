# UDC-Studio: AI-Assisted Configuration Generator

<div align="center">
  <img width="90%" src="https://github.com/IDXNow/UDC01/blob/main/img/UDC01-Img00011.jpg" alt="UDC01 - Universal data Converter">
</div>

<div align="center">
  <img width="90%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_001.png" alt="UDC-Studio Main Interface">
  <!--![UDC-Studio Main Interface](./img/Studio_001.png)-->
</div>

<div align="center">
  <p><i>UDC-Studio: a visual workspace for building and validating UDC01 conversion configurations</i></p>
</div>

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Complete Workflow](#complete-workflow)
  - [Step 1: Upload & Analyze Data](#step-1-upload--analyze-data)
  - [Step 2: Generate Configuration](#step-2-generate-configuration)
  - [Step 3: Validation & Download](#step-3-validation--download)
- [Profile Configuration](#profile-configuration)
- [Using Generated Configurations](#using-generated-configurations)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## Overview

Writing a YAML conversion configuration from scratch - specifying field mappings, verification rules, and validation criteria - requires understanding both the input data structure and the UDC01 prompt format.  UDC-Studio removes that barrier.  It's a Streamlit-based web application that analyzes your data file and generates a complete, validated YAML configuration using AI assistance.  The result is a ready-to-use file you can drop straight into a UDC01 pipeline.

### Key Benefits

- **Visual Data Analysis**: Load and preview your data files before conversion
- **AI-Assisted Generation**: Automatically creates YAML configurations based on data structure
- **Interactive Validation**: Real-time validation with multi-agent consensus
- **Custom Instructions**: Add specific transformation requirements in natural language
- **Ready-to-Use Output**: Download configurations with usage examples

### Who Should Use UDC-Studio?

- **New Users**: Explore UDC01 capabilities without writing configurations by hand
- **Data Engineers**: Quickly prototype conversions for new data formats
- **Business Analysts**: Create configurations without deep technical knowledge
- **Developers**: Test and validate transformation logic interactively before committing it to a pipeline

---

## Installation

### Requirements

UDC-Studio requires a few additional dependencies beyond the base UDC01 installation:

```bash
# Install UDC-Studio dependencies
pip install -r requirements_studio.txt
```

The `requirements_studio.txt` includes:
- `streamlit` - Web application framework
- All base UDC01 dependencies (pandas, pyyaml, requests, openpyxl)

### Cloud Provider Setup (Optional)

To use cloud-based AI models for configuration generation, set your API keys as environment variables before launching:

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:OPENAI_API_KEY="sk-proj-..."
$env:GOOGLE_API_KEY="..."
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."
export GOOGLE_API_KEY="..."
```

See [Cloud Provider Configuration](README.md#cloud-provider-configuration) in the main README for details.

---

## Quick Start

1. **Launch UDC-Studio**:
   ```bash
   python udc_studio.py
   ```

2. **Open your browser** to the URL shown (typically `http://localhost:8501`)

3. **Select a profile** (or use default settings)

4. **Upload a data file** and let AI generate your configuration

5. **Download the YAML** and use it with UDC01

---

## Complete Workflow

The workflow runs in three stages: understand the data, generate the configuration, validate and download.  Each stage builds on the previous one.

### Step 1: Upload & Analyze Data

This stage answers the question: *what are we actually working with?*  Before generating any configuration, UDC-Studio needs to understand the shape and content of your data.

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_002.png" alt="Upload and Preview">
  <!--![Upload and Preview](./img/Studio_002.png)-->
</div>

#### 1.1 Upload Your Data File

- Drag and drop a file or click **"Browse files"**
- Supported formats: CSV, XML, Excel (XLSX), JSON, TXT, PDF
- Maximum file size: 200MB

#### 1.2 Review Sample Preview

Once uploaded, UDC-Studio displays:
- Filename and file size
- Sample data preview (first few rows/records)
- File format detection

#### 1.3 Analyze Data Structure

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_003.png" alt="Analyzing Data">
  <!--![Analyzing Data](./img/Studio_003.png)-->
</div>

Click **"Analyze Data"** to run AI-powered analysis against your file.  This is where UDC-Studio is relevant - it identifies the structure, field types, and relationships that the generated configuration will need to handle correctly.

**Analysis includes:**
- Field count and data types
- Date format detection
- Numeric range analysis
- Null value identification

---

### Step 2: Generate Configuration

With the data analysis complete, UDC-Studio has what it needs to write the conversion configuration.  This stage translates the data profile into the three-part YAML that UDC01 expects: conversion instructions, verification rules, and validation criteria.

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_004.png" alt="Configuration Generation">
  <!--![Configuration Generation](./img/Studio_004.png)-->
</div>


#### 2.1 Review Data Structure Summary

The analysis results show:
- Detected fields and their types
- Sample values for each field
- Recommended transformations

#### 2.2 Select Target Format

Choose your desired output format:
- **Pipe-delimited** (|) - Default
- **CSV** (comma-delimited)
- **JSON** (array of objects)
- **SQL View** (CREATE VIEW statement)
- **Custom** (describe in instructions)

#### 2.3 Add Custom Instructions (Optional)

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_005.png" alt="Custom Instructions">
  <!--![Custom Instructions](./img/Studio_005.png)-->
</div>

Describe any specific transformation requirements in plain language.  UDC-Studio incorporates these into the generated prompts - no need to know the YAML structure to express what you want.

**Examples:**
```
Format dates as YYYY-MM-DD
Remove rows where Status=Void
Extract only InvoiceID, CustomerID, and InvoiceDate
Convert all currency values to 2 decimal places
Standardize customer names to uppercase
Filter records from last 30 days only
```

#### 2.4 Generate YAML

Click **"Generate YAML Configuration"** to kick off the generation process. UDC-Studio:
- Creates conversion instructions using AI
- Generates verification prompts
- Creates validation criteria
- Assembles the complete YAML configuration file

Generation typically takes 10-30 seconds depending on file complexity and the model selected.

---

### Step 3: Validation & Download

The configuration isn't done when it's generated - it's done when it passes validation.  This stage runs the same 2/3 majority consensus that UDC01 uses in production, so you know the configuration works before you ever run it against real data.

#### 3.1 Review Generated YAML

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_006.png" alt="YAML Content">
  <!--![YAML Content](./img/Studio_006.png)-->
</div>

The **YAML Content** tab displays:
- Complete configuration file
- System messages for all agents
- Conversion rules and field mappings
- Validation criteria

**Key YAML Sections:**
- `data_conversion_system_msg` - Instructions for transformation
- `data_verification_system_msg` - Pre-conversion checks
- `data_validation_system_msg` - Post-conversion validation

#### 3.2 Validation Report

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_007.png" alt="Validation Report">
  <!--![Validation Report](./img/Studio_007.png)-->
</div>


The **Validation Report** tab shows:
- Multi-agent validation results
- Approval status from each validator
- Consensus achievement (2/3 majority required)
- Validation feedback and suggestions

**Validation Outcomes:**
- ✅ **Approved** - Configuration meets validation standards
- ⚠️ **Needs Revision** - Suggestions for improvement
- ❌ **Rejected** - Significant issues detected

If validation doesn't pass on the first attempt, click **"Regenerate"** to create an improved version based on the feedback.

#### 3.3 Download Configuration

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_008.png" alt="Download Options">
  <!--![Download Options](./img/Studio_008.png)-->
</div>

Before downloading:
1. Enter a **filename** for your YAML (or use the suggested name)
2. Click **"Download YAML"** to save the configuration

**Available Actions:**
- **Download YAML** - Save configuration for use with UDC01
- **Regenerate** - Create new configuration with different approach
- **Start Over** - Upload a new file and begin again

#### 3.4 Usage Example

<div align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_009.png" alt="Usage Example">
  <!--![Usage Example](./img/Studio_009.png)-->
</div>

UDC-Studio generates ready-to-run command examples alongside the YAML - just copy and paste to start processing:

```bash
# Basic usage
python udc01.py --conversion "your_conversion_config.yaml" \
                --file "samples/sources/your_data.csv"

# Process entire folder
python udc01.py --conversion "conversions/your_config.yaml" \
                --folder "samples/sources" \
                --pattern "*.csv"
```

---

## Profile Configuration

### Using the Profile Selector

<div align="center">
  <img width="40%" src="https://github.com/IDXNow/UDC01/blob/main/img/Studio_001.png" alt="Profile Selection">
  <!--![Profile Selection](./img/Studio_001.png)-->
</div>

Profiles control which AI provider and model UDC-Studio uses to generate configurations. Switching profiles lets you compare output quality across providers or test configurations with the same models you plan to use in production.

### Available Profiles

**Default Profile:**
- Uses settings from `udc01/default_config.json`
- Typically configured for local LLM

**Cloud Profiles:**
- **OpenAI** - GPT-5, GPT-5-mini
- **Anthropic** - Claude 4.5 Sonnet, Claude 4.5 Opus
- **Google** - Gemini 2.5 Flash, Gemini 2.5 Pro

### Connectivity Test

Click **"Test Connection"** before generating configurations to verify that the selected profile can reach its API endpoint and authenticate successfully. This saves you from waiting through a generation process only to find out the API key isn't set.

---

## Using Generated Configurations

### Basic Usage

After downloading your YAML from UDC-Studio, drop it into your conversions folder and run it:

1. **Save to conversions folder (or anywhere you want)**:
   ```bash
   # Place your downloaded YAML here
   mv ~/Downloads/my_conversion.yaml samples/conversions/
   ```

2. **Run UDC01**:
   ```bash
   python udc01.py --conversion "samples/conversions/my_conversion.yaml" \
                   --file "path/to/your/data.csv"
   ```

### Batch Processing

Process multiple files with the same configuration:

```bash
python udc01.py --conversion "samples/conversions/my_conversion.yaml" \
                --folder "data/input" \
                --pattern "*.csv" \
                --output-folder "data/output"
```

### Integration with Workflows

Generated YAMLs slot directly into:
- **Automated pipelines** - Scheduled data processing jobs
- **API integrations** - Programmatic file conversions
- **Data validation** - Pre-processing quality checks

See the main [UDC01 README](README.md#usage) for complete CLI documentation.

---

## Advanced Usage

### Custom AI Instructions

UDC-Studio is particularly good at translating precise business requirements into the right prompts. The more specific you are, the better the result.

**Data Filtering:**
```
Only include records where OrderStatus is 'Completed' or 'Shipped'
Exclude any rows with missing CustomerID
Filter for dates between 2024-01-01 and 2024-12-31
```

**Field Transformations:**
```
Convert ProductCode to uppercase
Trim whitespace from all text fields
Split FullName into FirstName and LastName
```

**Format Requirements:**
```
Format all dates as MM/DD/YYYY
Round all currency values to 2 decimal places
Convert Yes/No values to true/false
Standardize phone numbers to (###) ###-#### format
```

### Regenerating Configurations

When the initial YAML doesn't quite match your requirements, the regeneration loop is quick:

1. Review the validation feedback
2. Adjust your custom instructions with more specificity
3. Click **"Regenerate"** for a new attempt
4. Compare versions in the YAML Content tab

### Testing Configurations

Before running a configuration against a full dataset, test it with a small sample. A few rows are enough to confirm the field mappings and transformations are correct.

1. **Small Sample Test**:
   ```bash
   # Test with 10 rows
   python udc01.py --conversion "my_config.yaml" --file "small_test_sample.csv"
   ```

2. **Review Output Quality**:
   - Check field mappings
   - Verify data transformations
   - Validate formatting

3. **Iterate if Needed**:
   - Return to UDC-Studio
   - Refine custom instructions
   - Regenerate and test again

---

## Troubleshooting

These are the issues that come up most often. Each one has a clear path to resolution.

**Problem**: "Connection failed" when testing connectivity

The most common causes: API keys aren't set in the current shell session, the local LLM server isn't running, or there's a mismatch between the API endpoint in the config and what the provider actually uses. Check each in that order - verify environment variables, confirm the local server is up, then check the endpoint configuration.

---

**Problem**: Generated YAML fails validation

Validation feedback is specific - read it before regenerating. The most common fix is adding more explicit custom instructions: instead of "format dates consistently", write "format all dates as YYYY-MM-DD". If a particular transformation is complex, breaking it into smaller, sequential requirements often helps.

---

**Problem**: Analysis takes too long or times out

Large files slow down the analysis step. If your data file is big, extract a representative sample (a few hundred rows is usually sufficient) and analyze that instead. You can also increase the API timeout in your configuration, or try a faster model from a different profile.

---

**Problem**: Downloaded YAML produces incorrect conversions

This usually means the data structure summary didn't capture something important about the input format. Return to UDC-Studio, review the analysis output carefully, and add custom instructions that explicitly describe the edge cases - unusual date formats, embedded delimiters, multi-value fields. You can also open the downloaded YAML and edit specific rules by hand for fine-grained control.

---

### Getting Help

- 📖 Review the [main UDC01 documentation](README.md)
- 🐛 Report issues on [GitHub](https://github.com/IDXNow/UDC01/issues)
- 📧 Contact support: [support@idxnow.co](mailto:support@idxnow.co)
- 💬 Check [Cloud Provider Configuration](README.md#cloud-provider-configuration) for API setup

---

## Best Practices

### For Best Results

The quality of the generated configuration depends on the quality of what you give it. A few habits make a real difference:

1. **Start with representative data** - Use sample files that include the full range of values your real data contains, including edge cases. A sample with only "clean" records will produce a configuration that doesn't handle messier inputs.

2. **Be specific in your instructions** - Vague requirements produce vague configurations. "Format dates as YYYY-MM-DD" is better than "normalize dates." "Exclude rows where Status is blank or 'Void'" is better than "filter out bad records."

3. **Validate early with small files** - Test the downloaded YAML against a 10-row sample before running it against thousands of records. Catching a field mapping error early costs seconds; catching it late costs reruns.

---

<div align="center">
  <p>
    <a href="README.md">Main Documentation</a>
  </p>
  <p><i>UDC-Studio - from raw data to validated conversion configuration in minutes</i></p>
</div>
