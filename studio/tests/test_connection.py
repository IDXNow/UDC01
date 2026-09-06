"""
Preflight checks for UDC-Studio: config, UDC01 integration, provider reachability.
Run before using Studio: python studio/tests/test_connection.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

STUDIO_CONFIG = REPO_ROOT / "studio" / "config" / "studio_config.json"


def test_config_loading():
    """Studio config loads and carries the keys the UI reads."""
    config = json.loads(STUDIO_CONFIG.read_text(encoding="utf-8"))

    generation = config["generation"]
    print(f"  version: {config['version']}")
    print(f"  cloud API: {config['cloud_managed_api']['api_base_url']}")
    print(f"  verification: {generation.get('verification_enabled')}")
    print(f"  include_prior_output_on_retry: {generation.get('include_prior_output_on_retry')}")

    for key in ("templates_path", "retry_limit", "consensus_requirement"):
        assert key in generation, f"missing generation.{key}"

    return config


def test_udc01_import():
    """UDC01 is importable and exposes what Studio calls into."""
    import udc01
    from udc01.validators import verify_input_data_2of3, validate_output_2of3  # noqa: F401
    from udc01.data_flow import perform_conversion  # noqa: F401
    from udc01.converter import validate_conversion_yaml  # noqa: F401

    udc_config = json.loads(
        (Path(udc01.__file__).parent / "default_config.json").read_text(encoding="utf-8")
    )
    print(f"  default_provider: {udc_config['default_provider']}")
    print(f"  providers: {', '.join(udc_config['providers'])}")

    return udc_config


def test_provider_profiles(udc_config):
    """Every provider profile resolves a model, so no provider falls back to a literal."""
    for name, profile in udc_config["providers"].items():
        model = profile.get("default_model")
        assert model, f"provider '{name}' has no default_model"
        print(f"  {name}: {model} (token_param={profile.get('token_param', 'max_tokens')})")


def test_templates(config):
    """Templates parse and carry the runtime settings UDC01 reads."""
    import yaml

    templates_path = REPO_ROOT / config["generation"]["templates_path"]
    templates = sorted(templates_path.glob("*.yaml"))
    assert templates, f"no templates found in {templates_path}"

    for template in templates:
        data = yaml.safe_load(template.read_text(encoding="utf-8"))
        assert isinstance(data["verification"]["enabled"], bool)
        assert isinstance(data["include_prior_output_on_retry"], bool)
        print(f"  {template.name}: ok")


def test_schema_validation():
    """Studio's schema gate rejects configs UDC01 would reject."""
    from studio.config_builder.core.builder import ConfigurationBuilder
    import logging

    builder = ConfigurationBuilder.__new__(ConfigurationBuilder)
    builder.logger = logging.getLogger(__name__)

    complete = "".join(
        f"{key}: text with placeholder\n"
        for key in (
            "data_conversion_system_msg", "data_conversion_request_msg",
            "data_verification_system_msg", "data_verification_request_msg",
            "data_validation_system_msg", "data_validation_request_msg",
        )
    )

    assert builder._validate_yaml_schema(complete) is None, "valid config was rejected"
    assert builder._validate_yaml_schema('key: "unterminated\n'), "broken YAML was accepted"
    assert builder._validate_yaml_schema(
        complete + 'include_prior_output_on_retry: "true"\n'
    ), "quoted boolean was accepted"
    print("  valid / unparseable / quoted-boolean cases all behave")


def test_runtime_settings(config):
    """Settings are prepended as real booleans and survive awkward generator output."""
    import yaml
    from studio.config_builder.core.yaml_generator import YAMLGenerator

    generator = YAMLGenerator(config)
    NL, TAB = "\n", "\t"

    shapes = {
        "plain": "data_conversion_system_msg: hi" + NL,
        "document marker": "---" + NL + "data_conversion_system_msg: hi" + NL,
        "leading comment": "# generated" + NL + "data_conversion_system_msg: hi" + NL,
        "tab indentation": "data_conversion_system_msg: |" + NL + TAB + "hi" + NL,
        "marker and tabs": "---" + NL + "a: |" + NL + TAB + "x" + NL,
        "generator emitted settings": (
            "verification: { enabled: false }" + NL
            + 'include_prior_output_on_retry: "true"' + NL
            + "data_conversion_system_msg: hi" + NL
        ),
    }

    for label, body in shapes.items():
        applied = generator.apply_runtime_settings(body)
        data = yaml.safe_load(applied)
        assert isinstance(data["verification"]["enabled"], bool), f"{label}: non-boolean verification"
        assert isinstance(data["include_prior_output_on_retry"], bool), f"{label}: quoted boolean survived"
        assert applied.count("include_prior_output_on_retry") == 1, f"{label}: duplicated setting"

    # A tab inside a value is content, not indentation, and must survive
    kept = yaml.safe_load(generator.apply_runtime_settings("a: 'left" + TAB + "right'" + NL))
    assert TAB in kept["a"], "tab inside a value was destroyed"

    print(f"  {len(shapes)} generator output shapes normalised")


def test_local_profiling():
    """Delimited data profiles exactly, with no LLM call."""
    from studio.config_builder.core.profiler import DataProfiler

    profiler = DataProfiler({"profiling": {}})
    sample = (REPO_ROOT / "samples" / "sources" / "sales_invoice.csv").read_text(encoding="utf-8")
    profile = profiler.profile_locally(sample)

    assert profile is not None, "local profiler did not recognise the CSV"
    assert profile["format"] == "csv"
    assert profile["delimiter"] == ","
    assert profile["has_header"] is True
    assert len(profile["columns"]) == 25, f"expected 25 columns, got {len(profile['columns'])}"
    assert profiler.validate_profile(profile)

    by_name = {c["name"]: c for c in profile["columns"]}
    assert by_name["SubTotal"]["data_type"] == "float"
    assert by_name["InvoiceDate"]["data_type"] == "date"
    assert by_name["PaymentDate"]["nullable"] is True

    # The doubled-quote address is the value that breaks LLM transcription
    addresses = by_name["BillingAddress"]["samples"]
    assert any("5500 Technology Pkwy" in a for a in addresses), "quoted address was mangled"

    enriched = profiler.enrich_profile(profile, sample)
    assert enriched["format_category"] == "delimited"
    print(f"  25 columns, types inferred, quoted addresses intact")


def test_profile_parsing():
    """Every malformed-response shape yields a profile or a specific error."""
    from studio.config_builder.core.profiler import DataProfiler

    profiler = DataProfiler({"profiling": {}})
    good = '{"format": "csv", "columns": [{"name": "a", "data_type": "string"}]}'

    should_parse = {
        "clean tags": "<o>" + good + "</o>",
        "code fence": "<o>\n```json\n" + good + "\n```\n</o>",
        "uppercase tags": "<O>" + good + "</O>",
        "prose before": "Here is the profile:\n<o>" + good + "</o>",
        "trailing comma": "<o>" + good.replace("}]}", "},]}") + "</o>",
        "no tags": good,
    }
    for label, content in should_parse.items():
        profile, error = profiler.parse_profile_result_verbose({"result": {"content": content}})
        assert profile is not None, f"{label} failed to parse: {error}"

    should_fail = {
        "none content": {"result": {"content": None}},
        "empty content": {"result": {"content": ""}},
        "api error": {"status": "failed", "error": "Context size has been exceeded"},
        "no json": {"result": {"content": "I cannot do that."}},
        "not an object": {"result": {"content": "<o>[1,2,3]</o>"}},
    }
    for label, payload in should_fail.items():
        profile, error = profiler.parse_profile_result_verbose(payload)
        assert profile is None, f"{label} should not have parsed"
        assert error, f"{label} returned no error message"

    print(f"  {len(should_parse)} tolerated shapes, {len(should_fail)} specific errors")


def test_provider_reachable(udc_config):
    """The default provider answers, when it is a keyless local runtime."""
    import requests

    name = udc_config["default_provider"]
    profile = udc_config["providers"][name]

    if profile.get("auth_header"):
        print(f"  skipped: '{name}' is a hosted provider")
        return

    url = profile["base_url"].rstrip("/") + "/v1/models"
    try:
        response = requests.get(url, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"  unreachable at {url}: {e}")
        print("  start your local LLM server, or point the profile elsewhere")
        return

    models = [m.get("id") for m in response.json().get("data", [])]
    print(f"  {url} -> {response.status_code}, loaded: {models or '(none)'}")
    if not models:
        print("  no model loaded; load one before running a conversion")


def main():
    config = None
    udc_config = None
    failures = []

    checks = [
        ("Configuration loading", lambda: test_config_loading()),
        ("UDC01 import", lambda: test_udc01_import()),
        ("Provider profiles", lambda: test_provider_profiles(udc_config)),
        ("Templates", lambda: test_templates(config)),
        ("Schema validation", lambda: test_schema_validation()),
        ("Runtime settings", lambda: test_runtime_settings(config)),
        ("Local profiling", lambda: test_local_profiling()),
        ("Profile parsing", lambda: test_profile_parsing()),
        ("Provider reachability", lambda: test_provider_reachable(udc_config)),
    ]

    for name, check in checks:
        print(f"\n{name}")
        print("-" * 60)
        try:
            result = check()
            if name == "Configuration loading":
                config = result
            elif name == "UDC01 import":
                udc_config = result
            print("PASS")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")
            failures.append(name)

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
