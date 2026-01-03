"""
UDC-Studio API Client Abstraction
Provides unified interface for local and cloud UDC01 operations
"""

from abc import ABC, abstractmethod
import requests
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging


class UDCClient(ABC):
    """Abstract base for local or cloud UDC operations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def run_job(self, job_contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a job following UDC01 protocol

        Args:
            job_contract: Dictionary following job_contract.schema.json

        Returns:
            Dictionary with job results and status
        """
        pass

    def verify_data(self, data: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convenience method for verification jobs

        Args:
            data: Input data to verify
            config: Verification configuration

        Returns:
            List of verification results from agents
        """
        job = {
            "job_type": "verification",
            "inputs": {"data": data, "config": config},
            "constraints": {"consensus": "2_of_3"}
        }
        result = self.run_job(job)
        return result.get("results", [])

    def convert_data(self, data: str, config: Dict[str, Any],
                     previous_notes: str = "") -> Dict[str, Any]:
        """
        Convenience method for conversion jobs

        Args:
            data: Input data to convert
            config: Conversion configuration
            previous_notes: Optional notes from previous attempts (for retries)

        Returns:
            Conversion result dictionary
        """
        # If previous_notes provided, replace the placeholder in the request message
        if previous_notes and "data_conversion_request_msg" in config:
            config = config.copy()
            config["data_conversion_request_msg"] = config["data_conversion_request_msg"].replace(
                "{{<!--PreviousConversionNotes-->}}",
                previous_notes
            )

        job = {
            "job_type": "conversion",
            "inputs": {"data": data, "config": config},
            "constraints": {"consensus": "2_of_3", "retry_limit": 1}  # We handle retries at builder level
        }
        return self.run_job(job)

    def validate_output(self, original: str, converted: str,
                       config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convenience method for validation jobs

        Args:
            original: Original input data
            converted: Converted output data
            config: Validation configuration

        Returns:
            List of validation results from agents
        """
        job = {
            "job_type": "validation",
            "inputs": {
                "data": original,
                "output": converted,
                "config": config
            },
            "constraints": {"consensus": "2_of_3"}
        }
        result = self.run_job(job)
        return result.get("results", [])


class LocalUDCClient(UDCClient):
    """Uses local UDC01 package"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Import UDC01 functions from the udc01 package
        try:
            import udc01
            from udc01.validators import verify_input_data_2of3, validate_output_2of3
            from udc01.data_flow import perform_conversion

            self.verify_func = verify_input_data_2of3
            self.validate_func = validate_output_2of3
            self.convert_func = perform_conversion

            # DEBUG: Show where udc01 is being imported from
            # self.logger.info(f"Successfully loaded UDC01 package from: {udc01.__file__}")
            # self.logger.info(f"Python path: {udc01.__path__}")
        except ImportError as e:
            raise ImportError(
                f"Failed to import udc01 package: {e}. "
                "Ensure udc01 is installed and in Python path."
            )

    def run_job(self, job_contract: Dict[str, Any]) -> Dict[str, Any]:
        """Route job to appropriate UDC01 function"""
        job_type = job_contract["job_type"]
        inputs = job_contract["inputs"]

        # main local run_job

        try:
            if job_type == "verification":
                results = self.verify_func(inputs["data"], inputs["config"])
                return {"status": "completed", "results": results}

            elif job_type == "conversion":
                result = self.convert_func(
                    inputs["data"],
                    inputs["config"],
                    run_index=0
                )
                return {"status": "completed", "result": result}

            elif job_type == "validation":
                results = self.validate_func(
                    inputs["data"],
                    inputs["output"],
                    inputs["config"]
                )
                return {"status": "completed", "results": results}

            else:
                raise ValueError(f"Unknown job type: {job_type}")

        except Exception as e:
            self.logger.error(f"Job execution failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "job_type": job_type
            }


class CloudUDCClient(UDCClient):
    """Uses BevDI managed API"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.base_url = config["cloud"]["api_base_url"].rstrip('/')
        self.api_key = os.getenv(config["cloud"]["api_key_env"])
        self.org_id = config["cloud"].get("organization_id")

        if not self.api_key:
            raise ValueError(
                f"API key required.  Set {config['cloud']['api_key_env']} "
                "environment variable."
            )

        self.logger.info(f"Initialized CloudUDCClient for {self.base_url}")

    def _headers(self) -> Dict[str, str]:
        """Generate request headers with authentication"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Client-Version": f"studio-{self.config['version']}"
        }
        if self.org_id:
            headers["X-Organization-ID"] = self.org_id
        return headers

    def run_job(self, job_contract: Dict[str, Any]) -> Dict[str, Any]:
        """Submit job to cloud API"""
        try:
            # Add metadata
            import datetime
            job_contract["metadata"] = {
                "submitted_at": datetime.datetime.utcnow().isoformat(),
                "client_version": f"studio-{self.config['version']}"
            }
            if self.org_id:
                job_contract["metadata"]["organization_id"] = self.org_id

            # Submit job
            response = requests.post(
                f"{self.base_url}/jobs",
                json=job_contract,
                headers=self._headers(),
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            job_id = result["job_id"]

            self.logger.info(f"Job submitted: {job_id}")

            # Poll for completion
            return self._poll_job(job_id)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return {
                "status": "failed",
                "error": f"API request failed: {str(e)}"
            }

    def _poll_job(self, job_id: str, max_wait: int = 300) -> Dict[str, Any]:
        """
        Poll job status until complete

        Args:
            job_id: Job identifier
            max_wait: Maximum wait time in seconds

        Returns:
            Job result dictionary
        """
        import time
        start = time.time()

        while time.time() - start < max_wait:
            try:
                response = requests.get(
                    f"{self.base_url}/jobs/{job_id}",
                    headers=self._headers(),
                    timeout=10
                )
                response.raise_for_status()

                result = response.json()
                status = result.get("status")

                if status == "completed":
                    self.logger.info(f"Job {job_id} completed successfully")
                    return result
                elif status == "failed":
                    self.logger.error(f"Job {job_id} failed: {result.get('error')}")
                    return result

                # Still processing, wait and retry
                time.sleep(2)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Polling error: {e}")
                time.sleep(2)

        # Timeout
        self.logger.error(f"Job {job_id} timed out after {max_wait}s")
        return {
            "status": "failed",
            "error": f"Job did not complete in {max_wait}s",
            "job_id": job_id
        }

    def get_base_config(self) -> Dict[str, Any]:
        """
        Retrieve base configuration from cloud API

        Returns:
            Base configuration dictionary
        """
        try:
            response = requests.get(
                f"{self.base_url}/config/base",
                headers=self._headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to retrieve base config: {e}")
            # Return minimal fallback config
            return {
                "api_base_url": self.base_url,
                "default_temperature": 0.3
            }


def create_client(config: Dict[str, Any]) -> UDCClient:
    """
    Factory to create appropriate client based on configuration

    Args:
        config: Studio configuration dictionary

    Returns:
        Appropriate UDCClient subclass instance

    Raises:
        ValueError: If mode is invalid
    """
    mode = config.get("mode", "local")

    if mode == "local":
        return LocalUDCClient(config)
    elif mode == "cloud":
        return CloudUDCClient(config)
    else:
        raise ValueError(
            f"Unknown mode: {mode}. Use 'local' or 'cloud'."
        )
