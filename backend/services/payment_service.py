"""Fetch.ai Payment Protocol integration and simulation adapter."""
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class PaymentRecord:
    payment_id: str
    task_id: str
    service_name: str
    amount_fet: float
    payment_rail: str
    simulated: bool
    status: PaymentStatus
    tx_hash: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, PaymentStatus) else self.status
        return d


class PaymentService:
    SERVICES = {
        "hardware_dossier": {
            "name": "Verified Cross-Retailer Hardware Sourcing Report",
            "fee_fet": 5.0,
            "description": "Multi-provider benchmark compilation and warranty verification."
        },
        "autonomous_action": {
            "name": "Autonomous Tool Execution Action",
            "fee_fet": 2.0,
            "description": "Dynamic tool argument compilation and verified cart mutation."
        }
    }

    def __init__(self):
        self._records: Dict[str, PaymentRecord] = {}

    def request_payment(
        self,
        task_id: str,
        service_key: str
    ) -> PaymentRecord:
        svc = self.SERVICES.get(service_key)
        if not svc:
            raise ValueError(f"Unknown paid service: {service_key}")

        pay_id = f"pay_{uuid.uuid4().hex[:10]}"
        record = PaymentRecord(
            payment_id=pay_id,
            task_id=task_id,
            service_name=svc["name"],
            amount_fet=svc["fee_fet"],
            payment_rail="Skyfire/FetchNet Testnet (Simulated)",
            simulated=True,
            status=PaymentStatus.PENDING,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self._records[pay_id] = record
        return record

    def resolve_payment(
        self,
        payment_id: str,
        authorized: bool = True
    ) -> PaymentRecord:
        record = self._records.get(payment_id)
        if not record:
            raise ValueError(f"Payment record '{payment_id}' not found.")

        if authorized:
            record.status = PaymentStatus.COMPLETED
            record.tx_hash = f"0xsimulated_tx_{uuid.uuid4().hex}"
        else:
            record.status = PaymentStatus.REJECTED

        return record


payment_service = PaymentService()
