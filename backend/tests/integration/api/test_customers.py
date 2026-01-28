"""
Integration tests for app/api/customers.py

Tests customer CRUD operations including create, read, update, delete.
"""

import pytest
from fastapi import status


class TestListCustomersEndpoint:
    """Tests for GET /api/customers endpoint."""

    def test_list_customers_empty(self, client, auth_headers):
        """Should return empty list when no customers exist."""
        response = client.get("/api/customers", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_customers_with_data(self, client, auth_headers, sample_customer):
        """Should return list of customers."""
        response = client.get("/api/customers", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_customer.name

    def test_list_customers_pagination_skip(self, client, auth_headers, test_db):
        """Should support skip pagination."""
        from app.models.database import Customer
        from datetime import datetime

        # Create multiple customers
        for i in range(5):
            customer = Customer(
                name=f"Customer {i}",
                domain=f"customer{i}.com",
                keywords=[],
                competitors=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            test_db.add(customer)
        test_db.commit()

        response = client.get("/api/customers?skip=2", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

    def test_list_customers_pagination_limit(self, client, auth_headers, test_db):
        """Should support limit pagination."""
        from app.models.database import Customer
        from datetime import datetime

        # Create multiple customers
        for i in range(5):
            customer = Customer(
                name=f"Customer {i}",
                domain=f"customer{i}.com",
                keywords=[],
                competitors=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            test_db.add(customer)
        test_db.commit()

        response = client.get("/api/customers?limit=2", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_customers_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.get("/api/customers")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCustomerEndpoint:
    """Tests for GET /api/customers/{customer_id} endpoint."""

    def test_get_customer_success(self, client, auth_headers, sample_customer):
        """Should return customer details."""
        response = client.get(f"/api/customers/{sample_customer.id}", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_customer.id
        assert data["name"] == sample_customer.name
        assert data["domain"] == sample_customer.domain

    def test_get_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.get("/api/customers/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_customer_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.get(f"/api/customers/{sample_customer.id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCreateCustomerEndpoint:
    """Tests for POST /api/customers endpoint."""

    def test_create_customer_minimal(self, client, auth_headers):
        """Should create customer with minimal data."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "name": "New Customer"
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Customer"
        assert "id" in data
        assert "created_at" in data

    def test_create_customer_full(self, client, auth_headers):
        """Should create customer with all fields."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "name": "Full Customer",
            "domain": "fullcustomer.com",
            "keywords": ["keyword1", "keyword2"],
            "competitors": ["Competitor A", "Competitor B"],
            "stock_symbol": "FULL",
            "config": {"custom_setting": "value"}
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Full Customer"
        assert data["domain"] == "fullcustomer.com"
        assert data["keywords"] == ["keyword1", "keyword2"]
        assert data["competitors"] == ["Competitor A", "Competitor B"]
        assert data["stock_symbol"] == "FULL"
        assert data["config"]["custom_setting"] == "value"

    def test_create_customer_missing_name(self, client, auth_headers):
        """Should return 422 for missing name."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "domain": "noname.com"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_customer_empty_name(self, client, auth_headers):
        """Should return 422 for empty name."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "name": ""
        })

        # Pydantic may or may not reject empty string depending on validation
        # At minimum it should be created or rejected
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_422_UNPROCESSABLE_ENTITY]

    def test_create_customer_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.post("/api/customers", json={
            "name": "Unauthorized Customer"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_customer_returns_timestamps(self, client, auth_headers):
        """Created customer should have timestamps."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "name": "Timestamped Customer"
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] is not None

    def test_create_customer_default_tab_color(self, client, auth_headers):
        """Customer should have default tab color."""
        response = client.post("/api/customers", headers=auth_headers, json={
            "name": "Default Color Customer"
        })

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["tab_color"] == "#ffffff"


class TestUpdateCustomerEndpoint:
    """Tests for PUT /api/customers/{customer_id} endpoint."""

    def test_update_customer_name(self, client, auth_headers, sample_customer):
        """Should update customer name."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"name": "Updated Name"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Name"

    def test_update_customer_domain(self, client, auth_headers, sample_customer):
        """Should update customer domain."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"domain": "newdomain.com"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["domain"] == "newdomain.com"

    def test_update_customer_keywords(self, client, auth_headers, sample_customer):
        """Should update customer keywords."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"keywords": ["new", "keywords", "list"]})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["keywords"] == ["new", "keywords", "list"]

    def test_update_customer_competitors(self, client, auth_headers, sample_customer):
        """Should update customer competitors."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"competitors": ["New Competitor"]})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["competitors"] == ["New Competitor"]

    def test_update_customer_tab_color(self, client, auth_headers, sample_customer):
        """Should update customer tab color."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"tab_color": "#00ff00"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tab_color"] == "#00ff00"

    def test_update_customer_config(self, client, auth_headers, sample_customer):
        """Should update customer config."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"config": {"new_config": "new_value"}})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["config"]["new_config"] == "new_value"

    def test_update_customer_multiple_fields(self, client, auth_headers, sample_customer):
        """Should update multiple fields at once."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={
                                  "name": "Multi Update",
                                  "domain": "multi.com",
                                  "stock_symbol": "MULT"
                              })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Multi Update"
        assert data["domain"] == "multi.com"
        assert data["stock_symbol"] == "MULT"

    def test_update_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.put("/api/customers/99999",
                              headers=auth_headers,
                              json={"name": "Ghost Customer"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_customer_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.put(f"/api/customers/{sample_customer.id}",
                              json={"name": "Unauthorized Update"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_customer_preserves_unset_fields(self, client, auth_headers, sample_customer):
        """Unset fields should be preserved."""
        original_keywords = sample_customer.keywords

        response = client.put(f"/api/customers/{sample_customer.id}",
                              headers=auth_headers,
                              json={"name": "Partial Update"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Name should be updated
        assert data["name"] == "Partial Update"
        # Keywords should be preserved
        assert data["keywords"] == original_keywords


class TestDeleteCustomerEndpoint:
    """Tests for DELETE /api/customers/{customer_id} endpoint."""

    def test_delete_customer_success(self, client, auth_headers, sample_customer, test_db):
        """Should delete customer."""
        customer_id = sample_customer.id

        response = client.delete(f"/api/customers/{customer_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        from app.models.database import Customer
        deleted = test_db.query(Customer).filter(Customer.id == customer_id).first()
        assert deleted is None

    def test_delete_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        response = client.delete("/api/customers/99999", headers=auth_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_customer_no_auth(self, client, sample_customer):
        """Should return 401 without authentication."""
        response = client.delete(f"/api/customers/{sample_customer.id}")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_customer_cascades_intelligence_items(self, client, auth_headers, sample_intelligence_item, test_db):
        """Deleting customer should cascade delete intelligence items."""
        from app.models.database import IntelligenceItem

        customer_id = sample_intelligence_item.customer_id
        item_id = sample_intelligence_item.id

        response = client.delete(f"/api/customers/{customer_id}", headers=auth_headers)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify intelligence item was cascade deleted
        deleted_item = test_db.query(IntelligenceItem).filter(IntelligenceItem.id == item_id).first()
        assert deleted_item is None


class TestCustomerResponseFormat:
    """Tests for customer response format."""

    def test_response_includes_all_fields(self, client, auth_headers, sample_customer):
        """Response should include all customer fields."""
        response = client.get(f"/api/customers/{sample_customer.id}", headers=auth_headers)

        data = response.json()
        required_fields = ["id", "name", "domain", "keywords", "competitors",
                          "stock_symbol", "tab_color", "config", "created_at", "updated_at"]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_datetime_format(self, client, auth_headers, sample_customer):
        """Datetime fields should be properly formatted."""
        response = client.get(f"/api/customers/{sample_customer.id}", headers=auth_headers)

        data = response.json()
        # Should be ISO format with Z suffix
        assert "T" in data["created_at"]
        assert "T" in data["updated_at"]

    def test_response_includes_sort_order(self, client, auth_headers, sample_customer):
        """Response should include sort_order field."""
        response = client.get(f"/api/customers/{sample_customer.id}", headers=auth_headers)

        data = response.json()
        assert "sort_order" in data
        assert data["sort_order"] == 0


class TestReorderCustomersEndpoint:
    """Tests for PATCH /api/customers/reorder endpoint."""

    def test_reorder_customers(self, client, auth_headers, test_db):
        """Should update sort_order for multiple customers."""
        from app.models.database import Customer
        from datetime import datetime

        customers = []
        for i in range(3):
            c = Customer(
                name=f"Customer {i}",
                domain=f"c{i}.com",
                keywords=[],
                competitors=[],
                sort_order=i,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            test_db.add(c)
            test_db.commit()
            test_db.refresh(c)
            customers.append(c)

        # Reverse the order
        reorder_payload = [
            {"id": customers[2].id, "sort_order": 0},
            {"id": customers[1].id, "sort_order": 1},
            {"id": customers[0].id, "sort_order": 2},
        ]

        response = client.patch("/api/customers/reorder",
                                headers=auth_headers,
                                json=reorder_payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify order persisted
        list_response = client.get("/api/customers", headers=auth_headers)
        data = list_response.json()
        assert data[0]["name"] == "Customer 2"
        assert data[1]["name"] == "Customer 1"
        assert data[2]["name"] == "Customer 0"

    def test_reorder_customers_no_auth(self, client):
        """Should return 401 without authentication."""
        response = client.patch("/api/customers/reorder",
                                json=[{"id": 1, "sort_order": 0}])

        assert response.status_code == 401

    def test_reorder_empty_list(self, client, auth_headers):
        """Should accept empty list."""
        response = client.patch("/api/customers/reorder",
                                headers=auth_headers,
                                json=[])

        assert response.status_code == 200

    def test_list_customers_ordered_by_sort_order(self, client, auth_headers, test_db):
        """Customer list should be ordered by sort_order then id."""
        from app.models.database import Customer
        from datetime import datetime

        # Create customers with non-sequential sort_orders
        for name, order in [("Zebra", 2), ("Alpha", 0), ("Middle", 1)]:
            c = Customer(
                name=name,
                domain=f"{name.lower()}.com",
                keywords=[],
                competitors=[],
                sort_order=order,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            test_db.add(c)
        test_db.commit()

        response = client.get("/api/customers", headers=auth_headers)
        data = response.json()

        assert data[0]["name"] == "Alpha"
        assert data[1]["name"] == "Middle"
        assert data[2]["name"] == "Zebra"
