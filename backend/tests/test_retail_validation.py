from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.retail import Adjustment, OrderCreate, ProductCreate
from app.services.retail import ensure_manager, money, reporting_period


def test_monetary_values_remain_decimal():
    assert money(Decimal("123.45") + Decimal("0.10")) == Decimal("123.55")
    assert isinstance(money(Decimal("123.45")), Decimal)


def test_reporting_period_is_inclusive_utc_and_leap_safe():
    start, end, days = reporting_period(date(2024, 2, 28), date(2024, 3, 1))
    assert days == 3
    assert start == datetime(2024, 2, 28, tzinfo=UTC)
    assert end == datetime(2024, 3, 2, tzinfo=UTC)


@pytest.mark.parametrize(
    "start,end", [(date(2026, 2, 2), date(2026, 2, 1)), (date(2020, 1, 1), date(2026, 1, 1))]
)
def test_rejects_unbounded_or_reversed_report_periods(start, end):
    with pytest.raises(HTTPException) as error:
        reporting_period(start, end)
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "delta,reason", [(0, "Stock count"), (1.2, "Stock count"), (1, "    "), (True, "Stock count")]
)
def test_adjustment_requires_integer_nonzero_and_reason(delta, reason):
    with pytest.raises(ValidationError):
        Adjustment(delta=delta, reason=reason)


def test_order_rejects_duplicate_product_and_fabricated_price():
    product_id = uuid4()
    body = {
        "store_id": uuid4(),
        "supplier_id": uuid4(),
        "items": [{"product_id": product_id, "quantity": 5}] * 2,
    }
    with pytest.raises(ValidationError, match="only once"):
        OrderCreate.model_validate(body)
    body["items"] = [{"product_id": product_id, "quantity": 5, "unit_cost": "0.01"}]
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(body)


def test_product_requires_nonblank_name_and_decimal_precision():
    data = {
        "sku": "NEW-001",
        "name": "     ",
        "category_id": uuid4(),
        "unit_cost": "0.10",
        "unit_price": "1.10",
    }
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(data)
    data.update(name="New product", unit_cost="1.001")
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(data)


def test_service_layer_also_enforces_write_role():
    with pytest.raises(HTTPException) as error:
        ensure_manager(SimpleNamespace(role="analyst"))
    assert error.value.status_code == 403
    ensure_manager(SimpleNamespace(role="manager"))


@pytest.mark.parametrize(
    "start,end", [(date(1, 1, 1), date(1, 1, 2)), (date(9999, 12, 30), date(9999, 12, 31))]
)
def test_extreme_dates_are_validation_errors_instead_of_overflows(start, end):
    with pytest.raises(HTTPException) as error:
        reporting_period(start, end)
    assert error.value.status_code == 422
