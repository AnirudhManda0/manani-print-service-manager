from typing import Dict, List, Optional

import requests


class APIClient:
    """Simple synchronous API client used by desktop widgets."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = 5

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        response = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict) -> dict:
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, payload: dict) -> dict:
        response = requests.put(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> dict:
        response = requests.delete(f"{self.base_url}{path}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health(self) -> dict:
        return self._get("/health")

    def get_version(self) -> dict:
        return self._get("/api/version")

    def get_system_config(self) -> dict:
        return self._get("/api/system-config")

    def update_system_config(
        self,
        server_ip: str,
        server_port: int,
        auto_discovery_enabled: bool,
        discovery_port: int,
        computer_name: str,
        operator_id: str,
        autostart_enabled: bool,
        poll_interval: float,
        bw_price_per_page: float,
        color_price_per_page: float,
    ) -> dict:
        return self._put(
            "/api/system-config",
            {
                "server_ip": server_ip,
                "server_port": server_port,
                "auto_discovery_enabled": auto_discovery_enabled,
                "discovery_port": discovery_port,
                "computer_name": computer_name,
                "operator_id": operator_id,
                "autostart_enabled": autostart_enabled,
                "poll_interval": poll_interval,
                "bw_price_per_page": bw_price_per_page,
                "color_price_per_page": color_price_per_page,
            },
        )

    def get_dashboard(self, day: Optional[str] = None) -> dict:
        return self._get("/api/dashboard", params={"date": day} if day else None)

    def get_print_jobs(self, day: Optional[str] = None, limit: int = 300) -> List[Dict]:
        params = {"limit": limit}
        if day:
            params["date"] = day
        return self._get("/api/print-jobs", params=params)["items"]

    def delete_print_job(self, job_id: int) -> dict:
        return self._delete(f"/api/print-jobs/{int(job_id)}")

    def update_print_job_type(self, job_id: int, print_type: str) -> dict:
        return self._put(f"/api/print-jobs/{int(job_id)}/type", {"print_type": print_type})

    def get_settings(self) -> dict:
        return self._get("/api/settings")

    def update_settings(
        self,
        bw_price_per_page: float,
        color_price_per_page: float,
        currency: str,
        retention_mode: str = "retain_all",
        retention_days: int = 30,
        backup_enabled: bool = True,
        backup_folder: str = "backup",
    ) -> dict:
        return self._put(
            "/api/settings",
            {
                "bw_price_per_page": bw_price_per_page,
                "color_price_per_page": color_price_per_page,
                "currency": currency,
                "retention_mode": retention_mode,
                "retention_days": retention_days,
                "backup_enabled": backup_enabled,
                "backup_folder": backup_folder,
            },
        )

    def list_services(self) -> List[Dict]:
        return self._get("/api/services/catalog")["items"]

    def list_service_records(self, day: Optional[str] = None, limit: int = 200) -> List[Dict]:
        params = {"limit": limit}
        if day:
            params["date"] = day
        return self._get("/api/services/records", params=params)["items"]

    def add_service(self, service_name: str, default_price: float) -> dict:
        return self._post("/api/services/catalog", {"service_name": service_name, "default_price": default_price})

    def record_service(self, service_id: int, price: Optional[float] = None) -> dict:
        payload = {"service_id": service_id}
        if price is not None:
            payload["price"] = price
        return self._post("/api/services/record", payload)

    def get_report(self, period: str, day: Optional[str] = None) -> dict:
        params = {"date": day} if day else None
        return self._get(f"/api/reports/{period}", params=params)

    def get_retention_status(self, days: int = 30) -> dict:
        return self._get("/api/data-retention/status", params={"days": days})

    def execute_retention(self, mode: str, days: int = 30) -> dict:
        return self._post("/api/data-retention/execute", {"mode": mode, "days": days})

    def run_daily_backup(self, force: bool = False) -> dict:
        return self._post(f"/api/backup/run?force={'true' if force else 'false'}", {})
