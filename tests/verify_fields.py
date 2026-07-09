"""Temel alan kalıcılığını gerçek kullanıcı verisine dokunmadan doğrular."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix="oms_verify_") as temp_dir:
    os.environ["LOCALAPPDATA"] = temp_dir

    from models.customer import Customer
    from models.offer import Offer
    from models.offer_item import OfferItem
    from services.customer_service import CustomerService
    from services.offer_service import OfferService

    customer_service = CustomerService()
    offer_service = OfferService()

    customer_id = customer_service.add(Customer(
        company_name="Test Co",
        phone="555-TEST",
        email="test@example.com",
    ))
    offer_id = offer_service.save(Offer(
        customer_id=customer_id,
        company_name="Test Co",
        customer_phone="555-TEST",
        customer_email="test@example.com",
        date="2026-03-26",
        currency="USD",
        total_amount=100.0,
        items=[OfferItem(
            product_name="Test Ürün",
            quantity=1,
            unit_price=100.0,
            total_price=100.0,
        )],
    ))

    saved = offer_service.get_by_id(offer_id)
    assert saved.customer_phone == "555-TEST"
    assert saved.customer_email == "test@example.com"
    assert len(saved.items) == 1
    print("VERIFICATION_SUCCESSFUL")
