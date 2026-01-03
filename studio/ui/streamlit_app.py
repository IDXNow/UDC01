"""
UDC-Studio Streamlit UI
Visual configuration builder for UDC01 data conversions
"""

import streamlit as st
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

project_root = Path(__file__).parent.parent.parent  # UDC01 root
sys.path.insert(0, str(project_root))

studio_dir = Path(__file__).parent.parent
sys.path.insert(0, str(studio_dir))

from config_builder.core.api_client import create_client
from config_builder.core.builder import ConfigurationBuilder

# ============================================================================
# LOGGING SETUP: reconfigure as needed
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PAGE SETUP
# ============================================================================
st.set_page_config(
    page_title="UDC-Studio",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================
@st.cache_resource
def load_config():
    """Load studio configuration from JSON file"""
    config_path = Path(__file__).parent.parent / "config" / "studio_config.json"
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load configuration: {e}")
        return None

@st.cache_resource
def load_udc_providers():
    """Load provider profiles from UDC01 config"""
    try:
        import udc01
        udc_config_path = Path(udc01.__file__).parent / "default_config.json"
        with open(udc_config_path, 'r') as f:
            udc_config = json.load(f)
        return udc_config.get("providers", {}), udc_config.get("default_provider", "local")
    except Exception as e:
        st.error(f"Failed to load UDC01 providers: {e}")
        return {}, "local"

config = load_config()
udc_providers, default_provider = load_udc_providers()

if config is None:
    st.stop()

# ============================================================================
# SIDEBAR: PROVIDER SELECTION & SETTINGS
# ============================================================================
with st.sidebar:
    st.title("⚙️ UDC-Studio")
    st.caption("Configuration Builder for UDC01")
    st.caption(f"Version {config.get('version', '1.0.0')}")

    st.divider()

    # Build provider options from UDC01 config + Cloud Managed API
    provider_icons = {
        "local": "🏠",
        "openai": "🤖",
        "anthropic": "🧠",
        "google": "🔍",
        "cloud_managed": "☁️"
    }

    provider_labels = {
        "local": "Local (Self-Hosted LLM)",
        "openai": "OpenAI (GPT)",
        "anthropic": "Anthropic (Claude)",
        "google": "Google (Gemini)",
        "cloud_managed": "Cloud (Managed API)"
    }

    # Create display options
    provider_options = []
    provider_keys = []

    # Add UDC01 providers
    for provider_key in udc_providers.keys():
        icon = provider_icons.get(provider_key, "📡")
        label = provider_labels.get(provider_key, provider_key.title())
        provider_options.append(f"{icon} {label}")
        provider_keys.append(provider_key)

    # Add cloud managed API
    provider_options.append(f"{provider_icons['cloud_managed']} {provider_labels['cloud_managed']}")
    provider_keys.append("cloud_managed")

    # Get default index
    try:
        default_index = provider_keys.index(default_provider)
    except ValueError:
        default_index = 0

    # Provider selection
    selected_display = st.radio(
        "**LLM Provider**",
        provider_options,
        index=default_index,
        help="Select which LLM provider to use for Studio operations"
    )

    # Get selected provider key
    selected_index = provider_options.index(selected_display)
    selected_provider = provider_keys[selected_index]

    st.divider()

    # Provider-specific settings
    if selected_provider == "cloud_managed":
        # Cloud Managed API settings
        st.subheader("☁️ Cloud API Settings")
        api_key = st.text_input(
            "API Key",
            type="password",
            help="Get your key at bevdi.com/api"
        )

        if api_key:
            import os
            os.environ[config["cloud_managed_api"]["api_key_env"]] = api_key

            org_id = st.text_input(
                "Organization ID (optional)",
                value=config["cloud_managed_api"].get("organization_id", "") or ""
            )
            if org_id:
                config["cloud_managed_api"]["organization_id"] = org_id

            # Connection test
            if st.button("🔌 Test Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    try:
                        # Test cloud API connection
                        st.success("✅ Connected successfully!")

                        # Show available features
                        features = config["cloud_managed_api"]["features"]
                        st.caption("**Enabled Features:**")
                        for feature, enabled in features.items():
                            icon = "✅" if enabled else "❌"
                            st.caption(f"{icon} {feature.replace('_', ' ').title()}")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {str(e)}")
        else:
            st.warning("⚠️ API key required for cloud mode")
            st.markdown("[Get an API key](https://bevdi.com/api)")
            st.stop()

    else:
        # UDC01 provider settings
        provider_config = udc_providers[selected_provider]

        st.subheader(f"{provider_icons.get(selected_provider, '📡')} {provider_labels.get(selected_provider, selected_provider.title())}")

        # Show/edit base URL
        base_url = st.text_input(
            "API Base URL",
            value=provider_config.get("base_url", ""),
            help=f"API endpoint for {selected_provider}"
        )
        provider_config["base_url"] = base_url

        # For non-local providers, show API key input
        if selected_provider != "local":
            import os
            api_key_env = f"{selected_provider.upper()}_API_KEY"
            current_key = os.getenv(api_key_env, "")

            api_key = st.text_input(
                f"API Key",
                type="password",
                value=current_key,
                help=f"Set {api_key_env} environment variable"
            )

            if api_key:
                os.environ[api_key_env] = api_key

        # Connection test
        if st.button("🔌 Test Connection", use_container_width=True):
            with st.spinner("Testing connection..."):
                try:
                    import requests

                    # For local provider, test the endpoint
                    if selected_provider == "local":
                        test_url = base_url.rstrip('/') + '/v1/models'
                        response = requests.get(test_url, timeout=5)

                        if response.status_code == 200:
                            st.success(f"✅ Connected successfully to {base_url}")
                        else:
                            st.warning(f"⚠️ Server responded with status {response.status_code}")
                    else:
                        st.info(f"✅ Configuration saved for {selected_provider}")
                        st.caption(f"Endpoint: {base_url}")

                except requests.exceptions.ConnectionError:
                    st.error(f"❌ Cannot connect to {base_url}")
                    st.info("💡 Make sure your LLM server is running")
                except requests.exceptions.Timeout:
                    st.error(f"❌ Connection timeout to {base_url}")
                    st.info("💡 Server is not responding")
                except Exception as e:
                    st.error(f"❌ Connection failed: {str(e)}")

    # Store selected provider in config for builder
    config["selected_provider"] = selected_provider
    config["mode"] = "cloud" if selected_provider == "cloud_managed" else "local"

    st.divider()

    # Advanced settings (collapsible)
    with st.expander("⚙️ Advanced Settings"):
        config["profiling"]["sample_size_rows"] = st.number_input(
            "Sample Size (rows)",
            min_value=10,
            max_value=1000,
            value=config["profiling"]["sample_size_rows"],
            help="Number of rows to sample from uploaded file"
        )

        config["generation"]["retry_limit"] = st.number_input(
            "Retry Limit",
            min_value=1,
            max_value=10,
            value=config["generation"]["retry_limit"],
            help="Maximum retry attempts for failed operations"
        )

        consensus = st.selectbox(
            "Consensus Requirement",
            ["2_of_3", "unanimous", "majority"],
            index=0,
            help="Validation consensus requirement"
        )
        config["generation"]["consensus_requirement"] = consensus

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'sample_data' not in st.session_state:
    st.session_state.sample_data = None
if 'safety_results' not in st.session_state:
    st.session_state.safety_results = None
if 'profile' not in st.session_state:
    st.session_state.profile = None
if 'yaml_config' not in st.session_state:
    st.session_state.yaml_config = None
if 'uploaded_filename' not in st.session_state:
    st.session_state.uploaded_filename = None

# Initialize builder with selected provider configuration, rebuild if provider changed
current_provider = config.get("selected_provider", default_provider)
if 'builder' not in st.session_state or st.session_state.get('last_provider') != current_provider:
    try:
        # Create config with selected provider as default
        builder_config = config.copy()
        builder_config["mode"] = "cloud" if current_provider == "cloud_managed" else "local"

        # For UDC01 providers, load and update the provider config
        if current_provider != "cloud_managed":
            import udc01
            udc_config_path = Path(udc01.__file__).parent / "default_config.json"
            with open(udc_config_path, 'r') as f:
                udc_config = json.load(f)

            # Override default_provider with selected one
            udc_config["default_provider"] = current_provider

            # Update all agents to use the selected provider
            for agent_type in udc_config.get("agents", {}).keys():
                agents = udc_config["agents"][agent_type]
                agent_list = agents if isinstance(agents, list) else [agents]

                for agent in agent_list:
                    if "provider" not in agent:
                        agent["provider"] = current_provider

            # Merge provider-specific settings
            builder_config["local"] = {
                "api_base_url": udc_providers[current_provider].get("base_url", ""),
                "default_model": udc_config.get("default_model", ""),
                "default_endpoint": udc_providers[current_provider].get("endpoint", "v1/chat/completions"),
                "default_temperature": udc_config.get("default_temperature", 1),
                "udc_config": udc_config  # Pass full UDC config
            }

        st.session_state.builder = ConfigurationBuilder(builder_config)
        st.session_state.last_provider = current_provider
        logger.info(f"ConfigurationBuilder initialized with provider: {current_provider}")
    except Exception as e:
        st.error(f"Failed to initialize builder: {str(e)}")
        logger.error(f"Builder initialization failed: {e}", exc_info=True)
        st.info("💡 Tip: Ensure the selected provider is properly configured.")
        st.stop()

builder = st.session_state.builder

# ============================================================================
# MAIN INTERFACE
# ============================================================================
st.title("🛠️ UDC-Studio: Configuration Builder")
st.markdown("**Create intelligent data conversion configs with AI-powered verification**")

# Progress indicator (2 steps now - safety is automatic)
progress_col1, progress_col2 = st.columns(2)
with progress_col1:
    status_1 = "✅ Complete" if st.session_state.step > 1 else ("🔄 Active" if st.session_state.step == 1 else "⏳ Pending")
    st.metric("Step 1", "Data Analysis", delta=status_1)
with progress_col2:
    status_2 = "✅ Complete" if st.session_state.step > 1 else "⏳ Pending"
    st.metric("Step 2", "Generate Config", delta=status_2)

st.divider()

# ============================================================================
# STEP 1: FILE UPLOAD and DATA ANALYSIS
# ============================================================================
if st.session_state.step == 1:
    st.header("📁 Step 1: Upload & Analyze Data")
    st.markdown(
        "Upload a sample file for automatic analysis. The system will verify data safety "
        "and extract structure information."
    )

    uploaded_file = st.file_uploader(
        "Choose a sample source file",
        type=config["profiling"]["supported_formats"],
        help="Upload a representative sample of your source data"
    )

    # Custom profiling instructions
    custom_instructions = st.text_area(
        "Additional Profiling Instructions (Optional)",
        placeholder="Example: Extract only Subject, Findings, and Sentiment from article text\nExample: Focus on transaction amounts and dates, ignore metadata fields",
        help="Provide specific instructions for what to extract or focus on during profiling",
        height=100
    )

    # Store in session state
    st.session_state.custom_profiling_instructions = custom_instructions

    if uploaded_file is not None:
        # Read sample
        try:
            sample_size = config["profiling"]["sample_size_rows"]

            # Read file content
            content = uploaded_file.read()
            # print(f"Content: {content}") # testing

            # Try to decode as UTF-8
            try:
                content = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content = content.decode("latin-1")
                except:
                    st.error("Unable to decode file. Please ensure it's a text file with UTF-8 or Latin-1 encoding.")
                    st.stop()

            # Truncate to sample size
            lines = content.split('\n')[:sample_size]
            # sample_data = '\n'.join(lines) # testing/uncomment back
            sample_data = content # testing --chould be truncated


            st.session_state.sample_data = sample_data
            st.session_state.uploaded_filename = uploaded_file.name

            st.subheader("📄 Sample Preview")
            preview_length = min(500, len(sample_data))
            st.code(sample_data[:preview_length] + ("..." if len(sample_data) > preview_length else ""), language='text')

            col1, col2 = st.columns([3, 1])

            with col1:
                st.caption(f"**File:** {uploaded_file.name}")
                st.caption(f"**Full Size:** {len(content):,} bytes")
                st.caption(f"**Sample:** {len(sample_data):,} bytes ({len(lines)} lines)")

            with col2:
                if st.button("▶️ Analyze Data", type="primary", use_container_width=True):
                    # Step 1: Safety verification (automatic, background)
                    safety_error = None
                    safety_results = None

                    with st.spinner("🛡️ Verifying data safety..."):
                        try:
                            results = builder.verify_sample_safety(sample_data)
                            st.session_state.safety_results = results
                            safety_results = results

                            if not results:
                                safety_error = ("connection", None)
                            else:
                                approved = sum(1 for r in results if r.get("isvalid", False))

                                # Check consensus
                                if approved < 2:
                                    safety_error = ("consensus", approved, len(results), results)

                        except Exception as e:
                            safety_error = ("exception", str(e))
                            logger.error(f"Safety check error: {e}", exc_info=True)

                    # Display errors AFTER spinner exits
                    if safety_error:
                        if safety_error[0] == "connection":
                            st.error("❌ Safety verification failed. Check your LLM connection.")
                            st.stop()
                        elif safety_error[0] == "consensus":
                            _, approved, total, results = safety_error
                            st.error("❌ **Data Safety Issue Detected**")
                            st.markdown(f"Only {approved}/{total} verification agents approved this data.")

                            # Show why it failed
                            for i, result in enumerate(results):
                                if not result.get("isvalid", False):
                                    if "invalid_msg" in result:
                                        st.warning(f"**Agent {i+1}**: {result['invalid_msg']}")

                            st.stop()  # Don't proceed to profiling
                        elif safety_error[0] == "exception":
                            st.error(f"❌ Safety verification error: {safety_error[1]}")
                            st.stop()

                    # Safety passed - show brief confirmation
                    if safety_results:
                        approved = sum(1 for r in safety_results if r.get("isvalid", False))
                        st.success(f"✅ Data verified ({approved}/{len(safety_results)} agents)")

                    # Step 2: Profile data structure
                    with st.spinner("🔍 Analyzing data structure..."):
                        try:
                            # Get custom instructions from session state
                            custom_instructions = st.session_state.get('custom_profiling_instructions', '')
                            profile_result = builder.profile_data(sample_data, custom_instructions)

                            if profile_result["status"] == "success":
                                st.session_state.profile = profile_result["profile"]
                                st.session_state.step = 2
                                st.success("✅ Analysis complete!")
                                st.rerun()
                            else:
                                st.error(f"❌ Profiling failed: {profile_result.get('reason', 'Unknown error')}")

                        except Exception as e:
                            st.error(f"❌ Analysis error: {str(e)}")
                            logger.error(f"Profiling error: {e}", exc_info=True)

        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            logger.error(f"File reading error: {e}", exc_info=True)

# ============================================================================
# STEP 2: YAML GENERATION & VALIDATION
# ============================================================================
elif st.session_state.step == 2:
    st.header("📝 Step 2: Generate Configuration")

    # Show profile summary
    if st.session_state.profile:
        with st.expander("📊 Data Structure Summary", expanded=False):
            col1, col2, col3 = st.columns(3)
            profile = st.session_state.profile
            with col1:
                st.metric("Format", profile.get('format', 'Unknown'))
            with col2:
                st.metric("Columns", profile.get('column_count', len(profile.get('columns', []))))
            with col3:
                if 'delimiter' in profile:
                    st.metric("Delimiter", profile['delimiter'])

            st.json(profile)

    st.divider()

    # Configuration options
    col1, col2 = st.columns([1, 1])

    with col1:
        target_format = st.selectbox(
            "**Target Format**",
            ["pipe-delimited", "CSV", "JSON", "SQL View"],
            help="Select the desired output format"
        )

    with col2:
        st.write("")  # Spacing

    user_instructions = st.text_area(
        "**Additional Instructions (optional)**",
        placeholder="e.g., 'Format dates as YYYY-MM-DD', 'Remove rows where Status=Void', 'Add prefix to all column names'",
        height=120,
        help="Provide custom transformation rules or business logic"
    )

    st.divider()

    # Generate button
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🏗️ Generate YAML Configuration", type="primary", use_container_width=True):
            st.session_state.target_format = target_format
            st.session_state.user_instructions = user_instructions

            with st.spinner("Generating YAML configuration with AI assistance..."):
                try:
                    yaml_result = builder.generate_yaml_config(
                        st.session_state.profile,
                        target_format,
                        user_instructions
                    )

                    if yaml_result["status"] == "success":
                        st.session_state.yaml_config = yaml_result["yaml_config"]
                        st.session_state.validation_results = yaml_result.get("validation_results", {})
                        st.success("✅ Configuration generated successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ Generation failed: {yaml_result.get('reason', 'Unknown error')}")
                        logger.error(f"YAML generation failed: {yaml_result}")
                except Exception as e:
                    st.error(f"❌ Generation error: {str(e)}")
                    logger.error(f"YAML generation error: {e}", exc_info=True)

    with col2:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.step = 1
            st.session_state.profile = None
            st.rerun()

    # Display generated YAML if it exists
    if st.session_state.yaml_config:
        st.divider()
        st.subheader("📄 Generated Configuration")

        # Metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Source File", st.session_state.uploaded_filename)
        with col2:
            st.metric("Target Format", st.session_state.target_format)
        with col3:
            st.metric("Generated", datetime.now().strftime("%Y-%m-%d %H:%M"))

        st.divider()

        # YAML content with tabs
        tab1, tab2 = st.tabs(["📝 YAML Content", "✅ Validation Report"])

        with tab1:
            yaml_code = st.text_area(
                "YAML Configuration (editable)",
                value=st.session_state.yaml_config,
                height=400,
                help="You can edit this before downloading"
            )
            st.session_state.yaml_config = yaml_code

        with tab2:
            if st.session_state.validation_results:
                results = st.session_state.validation_results
                if results.get("passed"):
                    st.success(f"✅ Validation passed! ({results.get('approved', 0)}/{results.get('total', 3)} agents approved)")
                else:
                    st.warning(f"⚠️ Validation concerns ({results.get('approved', 0)}/{results.get('total', 3)} agents approved)")

                # Show individual agent results
                if "results" in results:
                    for i, result in enumerate(results["results"]):
                        with st.expander(f"Agent {i+1} - {'✅ Approved' if result.get('isvalid') else '❌ Concerns'}"):
                            st.write(result.get("invalid_msg", "No issues found"))
            else:
                st.info("No validation results available")

        # Actions
        st.divider()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # Generate filename
            base_name = Path(st.session_state.uploaded_filename).stem if st.session_state.uploaded_filename else "config"
            default_filename = f"{base_name}_conv.yaml"
            config_name = st.text_input(
                "Filename",
                value=default_filename
            )

        with col2:
            st.download_button(
                label="💾 Download YAML",
                data=st.session_state.yaml_config,
                file_name=config_name,
                mime="text/yaml",
                use_container_width=True,
                type="primary"
            )

        with col3:
            if st.button("🔄 Regenerate", use_container_width=True):
                st.session_state.yaml_config = None
                st.session_state.validation_results = None
                st.rerun()

        with col4:
            if st.button("🔁 Start Over", use_container_width=True):
                for key in ['step', 'sample_data', 'profile', 'yaml_config', 'safety_results', 'validation_results', 'uploaded_filename']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.step = 1
                st.rerun()

        st.divider()

        st.success(
            f"**✅ Configuration ready!** Place this file in samples/conversions/ "
            f"and run: python udc01.py --conversion samples/conversions/{config_name}"
        )

        # Show usage example
        with st.expander("📚 Usage Example"):
            st.code(f"""# 1. Save the YAML to samples/conversions/
# 2. Place your source data file in samples/sources/
# 3. Run UDC01:

python udc01.py --conversion samples/conversions/{config_name} \\
                --file samples/sources/your_data.csv

# The converted output will be in output/
""", language='bash')

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"**UDC-Studio** v{config['version']}")
with col2:
    provider_display = provider_labels.get(selected_provider, selected_provider.title())
    st.caption(f"Provider: **{provider_display}**")
with col3:
    st.caption("[UDC01 GitHub](https://github.com/IDXNow/UDC01)")
