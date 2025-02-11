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
  - [Job Process Flow](#job-process-flow)
  - [Messaging Process Flow](#messaging-process-flow)
- [Technical Specifications](#technical-specifications)
- [Use Cases](#use-cases)
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
- **Enterprise-Grade Messaging**: Comprehensive notification system for process tracking and error handling
- **Containerized Execution**: Optimized resource management through containerization
- **Audit-Ready Logging**: Detailed process tracking and validation reporting with named agent accountability
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

### Job Process Flow

The job management system orchestrates the overall execution:

1. **Container Lifecycle**
   - Initialization of LLM service container
   - Resource allocation and management
   - Graceful shutdown procedures

2. **Process Management**
   - File detection and monitoring
   - Transformation pipeline execution
   - Output validation and delivery

3. **Resource Optimization**
   - Efficient container utilization
   - Automated cleanup procedures

<p align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/udc01.job_flow.jpg">
</p>

---

### Messaging Process Flow

The **messaging system** ensures that stakeholders receive **relevant updates** while maintaining clear accountability:

1. **Message Processing**
   - Log aggregation and analysis
   - Severity categorization
   - Message routing and delivery

2. **Notification Management**
   - User/Admin notifications
   - Error alerts and reporting
   - Success confirmations

<p align="center">
  <img width="80%" src="https://github.com/IDXNow/UDC01/blob/main/img/udc01.messaging_flow.jpg">
</p>

---

## Technical Specifications

### Current Capabilities and Future Scalability

The framework's current processing capacity is optimized for smaller datasets due to existing model context window limitations. While this ensures high accuracy and reliability for typical use cases, we maintain an active development roadmap aligned with advancing LLM capabilities.

**Present Implementation:**
  - Small to medium-sized text files
  - Optimized for common business document sizes

**Validation Requirements:**
  - Minimum 2/3 successful verifications
  - User-configurable number of conversion retry attempts
  - Strict output format validation

**Scalability Pathway:**
The framework is designed to scale seamlessly with advancing LLM technology. As model capabilities evolve, particularly in areas of context window size and processing capacity, the framework will naturally accommodate larger datasets and more complex transformations. The integration of specialized agent tools is expected to further enhance the framework's capabilities, enabling more sophisticated data processing and expanded conversion options.
  
### Supported Input Formats
  - CSV, JSON, XML, Excel
  - Unstructured text

### Agent Identification System
Each LLM agent in the framework is assigned both a unique identifier and a human-readable name (e.g., "Jane Dirac", "Chris Einstein"). This personification system serves multiple purposes:

- Enhanced Traceability: Clear identification of which agent performed specific actions
- User Familiarity: Intuitive understanding of different process stages through personified agents
- Accountability: Precise tracking in logs and notifications
- Audit Trail: Clear chain of responsibility throughout the transformation process


---

## Use Cases

### Enterprise Data Standardization
The framework excels in scenarios where organizations receive varied data formats that need to be standardized for data warehouse ingestion. A prime example is the standardization of payment transaction data from multiple sources, where field names, formats, and structures may vary significantly.

### Automated Data Transformation
UDC01 is particularly effective for regular data processing tasks where manual standardization would be time-consuming and error-prone. The framework's ability to understand and adapt to various input formats makes it ideal for automated data pipeline implementations.

## License

This project is licensed under the [MIT License](https://github.com/IDXNow/UDC01/LICENSE) - see the LICENSE file for details.

---

<div align="center">
  <p>For more information or support, please contact the development team.</p>
</div>

## Contact & Community

💬 **Have Questions?**  
Open an issue on [GitHub](https://github.com/IDXNow/UDC01/issues) or contact us at [support@idxnow.co](mailto:support@idxnow.co).

---
